from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict
from pathlib import Path
from zipfile import ZipFile

import pytest

from aletheia import Memory
from aletheia.cli.main import main
from aletheia.core.errors import NotFoundError, ValidationError
from aletheia.models import ServiceConfig
from aletheia.service.auth import AuthService
from aletheia.service.http import AletheiaService, openapi_schema


NAMESPACE = "user/default"
PASSPHRASE = "m8-test-passphrase"


def _json(payload: dict) -> bytes:
    return json.dumps(payload).encode("utf-8")


def _service(tmp_path, *, capabilities: list[str] | None = None) -> tuple[AletheiaService, str]:
    db_path = str(tmp_path / "service.db")
    memory = Memory.open(db_path, namespace=NAMESPACE)
    service = AletheiaService(
        memory,
        ServiceConfig(db_path=db_path, auto_migrate=True, auth_required=True, console_enabled=True),
    )
    auth = AuthService(memory)
    client = auth.create_client(name="m8-admin", client_type="agent")
    _token, raw = auth.create_token(
        client_id=client.id,
        namespace_grants=[NAMESPACE],
        capabilities=capabilities or ["memory:admin"],
        privacy_ceiling="secret",
    )
    return service, raw


def _post(service: AletheiaService, path: str, token: str, payload: dict):
    return service.handle_http(
        method="POST",
        path=path,
        headers={"Authorization": f"Bearer {token}", "X-Request-ID": "req_m8_unit"},
        body=_json(payload),
    )


def _get(service: AletheiaService, path: str, token: str):
    return service.handle_http(
        method="GET",
        path=path,
        headers={"Authorization": f"Bearer {token}", "X-Request-ID": "req_m8_unit"},
    )


def test_m8_migration_adds_hardening_tables_without_enabling_protection(tmp_path):
    memory = Memory.open(str(tmp_path / "migrate.db"), namespace=NAMESPACE)
    try:
        assert memory.health()["schema_version"] == "1.3.0"
        tables = {
            row["name"]
            for row in memory.store.connection.execute(
                "SELECT name FROM sqlite_master WHERE type IN ('table', 'virtual table')"
            ).fetchall()
        }
        assert {
            "backup_manifests",
            "backup_items",
            "backup_verification_runs",
            "restore_runs",
            "encryption_key_records",
            "key_rotation_events",
            "protected_mode_config",
            "redaction_events",
            "deletion_tombstones",
            "retention_policies",
            "retention_runs",
            "integrity_check_runs",
            "integrity_findings",
            "migration_plans",
            "migration_runs",
            "compaction_runs",
            "export_manifests",
            "import_runs",
            "support_bundles",
            "benchmark_runs",
            "benchmark_results",
            "release_manifests",
            "production_readiness_checks",
        }.issubset(tables)
        protected = memory.protected_mode_status()
        assert protected.enabled is False
        assert protected.content_encryption_enabled is False
        assert memory.list_keys() == []
        assert memory.list_backups() == []
    finally:
        memory.close()


def test_migration_skips_current_schema_and_rejects_forward_schema(tmp_path):
    db_path = tmp_path / "current.db"
    memory = Memory.open(str(db_path), namespace=NAMESPACE)
    try:
        first_applied_at = memory.store.connection.execute(
            "SELECT applied_at FROM schema_version WHERE id = 1"
        ).fetchone()["applied_at"]
    finally:
        memory.close()

    reopened = Memory.open(str(db_path), namespace=NAMESPACE)
    try:
        second_applied_at = reopened.store.connection.execute(
            "SELECT applied_at FROM schema_version WHERE id = 1"
        ).fetchone()["applied_at"]
        assert second_applied_at == first_applied_at
    finally:
        reopened.close()

    future_path = tmp_path / "future.db"
    connection = sqlite3.connect(str(future_path))
    try:
        connection.execute(
            "CREATE TABLE schema_version (id INTEGER PRIMARY KEY CHECK (id = 1), version TEXT NOT NULL, applied_at TEXT NOT NULL)"
        )
        connection.execute(
            "INSERT INTO schema_version (id, version, applied_at) VALUES (1, '9.9.9', '2026-01-01T00:00:00+00:00')"
        )
        connection.commit()
    finally:
        connection.close()
    with pytest.raises(RuntimeError, match="newer than supported"):
        Memory.open(str(future_path), namespace=NAMESPACE)


def test_storage_expands_home_path_and_enforces_nullable_embedding_key(monkeypatch, tmp_path):
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    memory = Memory.open("~/aletheia/expanded.db", namespace=NAMESPACE)
    try:
        assert Path(memory.store.path) == home / "aletheia" / "expanded.db"
        assert (home / "aletheia" / "expanded.db").exists()
        now = "2026-01-01T00:00:00+00:00"
        memory.store.connection.execute(
            """
            INSERT INTO embeddings (
                id, namespace, target_id, target_type, provider, model,
                dimension, vector_blob, content_hash, created_at
            )
            VALUES ('emb_one', ?, 'claim_1', 'claims', 'local', 'hash', 2, X'0000', 'hash-1', ?)
            """,
            (NAMESPACE, now),
        )
        with pytest.raises(sqlite3.IntegrityError):
            memory.store.connection.execute(
                """
                INSERT INTO embeddings (
                    id, namespace, target_id, target_type, provider, model,
                    dimension, vector_blob, content_hash, created_at
                )
                VALUES ('emb_two', ?, 'claim_1', 'claims', 'local', 'hash', 2, X'0001', 'hash-2', ?)
                """,
                (NAMESPACE, now),
            )
    finally:
        memory.close()


def test_encrypted_backup_verify_restore_and_corruption_detection(tmp_path):
    db_path = tmp_path / "source.db"
    backup_path = tmp_path / "source.alet"
    restored_path = tmp_path / "restored.db"
    memory = Memory.open(str(db_path), namespace=NAMESPACE)
    try:
        claim = memory.remember(
            namespace=NAMESPACE,
            memory_type="project",
            subject="aletheia",
            predicate="has_m8_goal",
            object="production hardening",
            confidence=0.9,
        )
        backup = memory.create_backup(
            output_path=str(backup_path),
            backup_type="hybrid",
            namespace=NAMESPACE,
            encrypt=True,
            passphrase=PASSPHRASE,
        )
        assert backup.encrypted is True
        assert backup.item_counts["claims"] >= 1
        assert backup_path.exists()
        assert b"production hardening" not in backup_path.read_bytes()
        with ZipFile(backup_path) as archive:
            metadata = json.loads(archive.read("encryption_metadata.json").decode("utf-8"))
        assert metadata["algorithm"] == "AES-256-GCM-PBKDF2-SHA256"

        verification = memory.verify_backup(backup_path=str(backup_path), passphrase=PASSPHRASE)
        assert verification.status == "passed"
        assert memory.verify_backup(backup_path=str(backup_path)).status == "failed"

        dry_run = memory.restore_backup(
            backup_path=str(backup_path),
            target_db_path=str(restored_path),
            passphrase=PASSPHRASE,
            dry_run=True,
        )
        assert dry_run.dry_run is True
        assert not restored_path.exists()

        restored = memory.restore_backup(
            backup_path=str(backup_path),
            target_db_path=str(restored_path),
            passphrase=PASSPHRASE,
            dry_run=False,
        )
        assert restored.status == "completed"
    finally:
        memory.close()

    restored_memory = Memory.open(str(restored_path), namespace=NAMESPACE)
    try:
        assert restored_memory.read_claim(claim.id).object == "production hardening"
        assert restored_memory.integrity_check(namespace=NAMESPACE).status == "passed"
    finally:
        restored_memory.close()

    bad_path = tmp_path / "bad.alet"
    bad_path.write_bytes(b"not a valid backup")
    memory = Memory.open(str(db_path), namespace=NAMESPACE)
    try:
        assert memory.verify_backup(backup_path=str(bad_path), passphrase=PASSPHRASE).status == "failed"
    finally:
        memory.close()


def test_redacted_logical_backup_excludes_raw_db_tokens_and_content(tmp_path):
    db_path = tmp_path / "redacted-source.db"
    backup_path = tmp_path / "redacted.alet"
    memory = Memory.open(str(db_path), namespace=NAMESPACE)
    try:
        auth = AuthService(memory)
        client = auth.create_client(name="backup-test", client_type="test")
        _token, raw_token = auth.create_token(
            client_id=client.id,
            namespace_grants=[NAMESPACE],
            capabilities=["memory:read"],
        )
        memory.remember(
            namespace=NAMESPACE,
            memory_type="project",
            subject="redacted backup",
            predicate="hides",
            object="raw launch phrase",
            source_type="unit",
        )
        backup = memory.create_backup(
            output_path=str(backup_path),
            backup_type="logical",
            namespace=NAMESPACE,
            encrypt=False,
            privacy_mode="redacted",
        )
        assert backup.includes_raw_content is False
        assert backup.includes_auth_metadata is False

        with ZipFile(backup_path) as archive:
            names = set(archive.namelist())
            manifest = json.loads(archive.read("manifest.json").decode("utf-8"))
            raw_archive = b"\n".join(archive.read(name) for name in archive.namelist())
        assert "database.sqlite" not in names
        assert "api_tokens" not in raw_archive.decode("utf-8", errors="ignore")
        assert raw_token.encode("utf-8") not in raw_archive
        assert b"raw launch phrase" not in raw_archive
        assert manifest["includes_raw_content"] is False
        assert manifest["includes_auth_metadata"] is False

        with pytest.raises(ValidationError):
            memory.create_backup(
                output_path=str(tmp_path / "bad-redacted-physical.alet"),
                backup_type="physical",
                encrypt=False,
                privacy_mode="redacted",
            )
    finally:
        memory.close()


def test_protected_mode_encrypts_secret_content_and_skips_secret_indexing(monkeypatch, tmp_path):
    monkeypatch.setenv("ALETHEIA_PROTECTED_KEY", PASSPHRASE)
    memory = Memory.open(str(tmp_path / "protected.db"), namespace=NAMESPACE)
    try:
        protected = memory.enable_protected_mode(actor="pytest")
        assert protected.enabled is True
        keys = memory.list_keys()
        assert len(keys) == 1
        assert "raw" not in json.dumps(asdict(keys[0])).lower()

        event = memory.write_event(
            namespace=NAMESPACE,
            source_type="unit",
            content="secret launch code is blue",
            privacy_level="secret",
        )
        stored = memory.store.connection.execute(
            "SELECT content FROM evidence_events WHERE id = ?",
            (event.id,),
        ).fetchone()["content"]
        assert stored.startswith("enc:v2:")
        assert "secret launch code" not in stored
        assert memory.read_event(event.id).content == "secret launch code is blue"
        duplicate = memory.write_event(
            namespace=NAMESPACE,
            source_type="unit",
            content="secret launch code is blue",
            privacy_level="secret",
        )
        assert duplicate.content == "secret launch code is blue"
        assert memory.audit(event.id)["evidence"]["content"] == "secret launch code is blue"

        claim = memory.write_claim(
            namespace=NAMESPACE,
            subject="launch",
            predicate="has_code",
            object="blue",
            memory_type="preference",
            evidence_ids=[event.id],
        )
        indexed = memory.store.connection.execute(
            "SELECT count(*) AS count FROM claims_fts WHERE claim_id = ?",
            (claim.id,),
        ).fetchone()["count"]
        assert indexed == 0
        assert memory.retrieve(NAMESPACE, "blue", mode="lexical") == []
        with pytest.raises(ValidationError):
            memory.create_backup(output_path=str(tmp_path / "plain.alet"), encrypt=False)

        rotation = memory.rotate_key(old_key_id=keys[0].id, new_key_label="next", dry_run=True)
        assert rotation.status == "planned"
    finally:
        memory.close()


def test_protected_secret_content_requires_configured_key(monkeypatch, tmp_path):
    monkeypatch.delenv("ALETHEIA_PROTECTED_KEY", raising=False)
    memory = Memory.open(str(tmp_path / "protected-missing-key.db"), namespace=NAMESPACE)
    try:
        protected = memory.enable_protected_mode(actor="pytest")
        assert protected.content_encryption_enabled is True
        key = memory.list_keys()[0]
        monkeypatch.delenv(f"ALETHEIA_KEY_{key.id}", raising=False)
        with pytest.raises(ValidationError):
            memory.write_event(
                namespace=NAMESPACE,
                source_type="unit",
                content="secret without configured key",
                privacy_level="secret",
            )
        readiness = memory.readiness_check(namespace=NAMESPACE)
        assert "Protected content key is not configured." in readiness.warnings
    finally:
        memory.close()


def test_redaction_forget_retention_integrity_and_migration_runs(tmp_path):
    memory = Memory.open(str(tmp_path / "governance.db"), namespace=NAMESPACE)
    try:
        claim = memory.remember(
            namespace=NAMESPACE,
            memory_type="task",
            subject="temp",
            predicate="contains",
            object="sensitive note",
        )
        event_id = claim.evidence_ids[0]
        preview = memory.redact(
            target_id=event_id,
            target_type="evidence",
            reason="unit preview",
            dry_run=True,
        )
        assert preview.dry_run is True
        applied = memory.redact(
            target_id=event_id,
            target_type="evidence",
            reason="unit apply",
            dry_run=False,
        )
        assert applied.affected_counts["claims"] == [claim.id]
        assert memory.read_event(event_id).content == "[REDACTED]"
        assert memory.read_claim(claim.id).status == "archived"
        assert memory.list_tombstones(namespace=NAMESPACE)

        forget_claim = memory.remember(
            namespace=NAMESPACE,
            memory_type="task",
            subject="forget",
            predicate="target",
            object="one",
        )
        preview_forget = memory.forget(
            selector={"target_type": "claim", "target_id": forget_claim.id},
            reason="unit forget",
            dry_run=True,
        )
        assert preview_forget.metadata["matched_count"] == 1
        applied_forget = memory.forget(
            selector={"target_type": "claim", "target_id": forget_claim.id},
            reason="unit forget",
            dry_run=False,
        )
        assert applied_forget.status == "completed"

        retention_claim = memory.remember(
            namespace=NAMESPACE,
            memory_type="task",
            subject="retention",
            predicate="matches",
            object="archive",
        )
        policy = memory.create_retention_policy(
            namespace=NAMESPACE,
            memory_type="task",
            action="archive",
            after_days=0,
            reason="unit retention",
        )
        assert policy.enabled is True
        run = memory.run_retention(namespace=NAMESPACE, dry_run=False)
        assert run.metadata["applied_count"] >= 1
        assert memory.read_claim(retention_claim.id).status == "archived"

        memory.store.connection.execute(
            """
            INSERT INTO claims_fts (claim_id, namespace, subject, predicate, object, memory_type, content)
            VALUES ('bogus', ?, 'bogus', 'bogus', 'bogus', 'task', 'bogus')
            """,
            (NAMESPACE,),
        )
        integrity = memory.integrity_check(namespace=NAMESPACE, deep=True)
        assert integrity.status == "passed_with_warnings"
        findings = memory.list_integrity_findings(run_id=integrity.id)
        assert any(finding.finding_type == "fts_drift" for finding in findings)

        plan = memory.migration_plan()
        assert plan.backup_required is True
        migration = memory.migration_apply(dry_run=True)
        assert migration.status == "completed"
    finally:
        memory.close()


@pytest.mark.parametrize(
    "action",
    ["archive", "queue_review", "lower_salience", "redact_content", "tombstone", "hard_delete"],
)
def test_retention_filters_and_all_actions_have_dry_run_apply_parity(tmp_path, action):
    memory = Memory.open(str(tmp_path / f"retention-{action}.db"), namespace=NAMESPACE)
    try:
        def create_claim(subject: str, *, privacy_level: str, source_type: str):
            event = memory.write_event(
                namespace=NAMESPACE,
                source_type=source_type,
                content=f"{subject} retention source",
                privacy_level=privacy_level,
            )
            return memory.write_claim(
                namespace=NAMESPACE,
                memory_type="task",
                subject=subject,
                predicate="matches_retention",
                object=f"{subject} retention object",
                evidence_ids=[event.id],
                confidence=0.8,
                importance=0.9,
            )

        target = create_claim("target", privacy_level="secret", source_type="manual")
        privacy_decoy = create_claim("privacy-decoy", privacy_level="personal", source_type="manual")
        source_decoy = create_claim("source-decoy", privacy_level="secret", source_type="import")
        policy = memory.create_retention_policy(
            namespace=NAMESPACE,
            memory_type="task",
            privacy_level="secret",
            source_type="manual",
            action=action,
            after_days=0,
            reason=f"unit retention {action}",
        )

        dry_run = memory.run_retention(namespace=NAMESPACE, dry_run=True)
        assert dry_run.metadata["matched_count"] == 1
        assert dry_run.metadata["applied_count"] == 0
        assert dry_run.metadata["matches"] == [
            {
                "policy_id": policy.id,
                "claim_id": target.id,
                "action": action,
                "filters": {
                    "memory_type": "task",
                    "privacy_level": "secret",
                    "source_type": "manual",
                    "after_days": 0,
                },
            }
        ]

        applied = memory.run_retention(namespace=NAMESPACE, dry_run=False)
        assert applied.metadata["matched_count"] == 1
        assert applied.metadata["applied_count"] == 1
        assert applied.metadata["matches"] == dry_run.metadata["matches"]
        assert memory.read_claim(privacy_decoy.id).status == "active"
        assert memory.read_claim(source_decoy.id).status == "active"

        if action == "archive":
            assert memory.read_claim(target.id).status == "archived"
        elif action == "queue_review":
            tasks = memory.list_review_tasks(namespace=NAMESPACE, task_type="stale_core_memory")
            assert [task.target_id for task in tasks] == [target.id]
            assert memory.read_claim(target.id).status == "active"
        elif action == "lower_salience":
            claim = memory.read_claim(target.id)
            assert claim.status == "active"
            assert claim.importance == pytest.approx(0.2)
        elif action == "redact_content":
            claim = memory.read_claim(target.id)
            assert claim.object == "[REDACTED]"
            assert claim.status == "archived"
            assert any(tombstone.target_id == target.id for tombstone in memory.list_tombstones(namespace=NAMESPACE))
        elif action == "tombstone":
            assert memory.read_claim(target.id).status == "archived"
            assert any(
                tombstone.target_id == target.id and tombstone.deletion_mode == "tombstone"
                for tombstone in memory.list_tombstones(namespace=NAMESPACE)
            )
        elif action == "hard_delete":
            with pytest.raises(NotFoundError):
                memory.read_claim(target.id)
            assert any(
                tombstone.target_id == target.id and tombstone.deletion_mode == "hard_delete"
                for tombstone in memory.list_tombstones(namespace=NAMESPACE)
            )
    finally:
        memory.close()


def test_retention_filters_use_effective_claim_privacy_and_source_set(tmp_path):
    memory = Memory.open(str(tmp_path / "retention-mixed-evidence.db"), namespace=NAMESPACE)
    try:
        public_event = memory.write_event(
            namespace=NAMESPACE,
            source_type="manual",
            content="public retention source",
            privacy_level="public",
        )
        secret_event = memory.write_event(
            namespace=NAMESPACE,
            source_type="import",
            content="secret retention source",
            privacy_level="secret",
        )
        mixed_privacy_claim = memory.write_claim(
            namespace=NAMESPACE,
            memory_type="task",
            subject="mixed privacy",
            predicate="requires",
            object="effective privacy filtering",
            evidence_ids=[public_event.id, secret_event.id],
            confidence=0.8,
            importance=0.9,
        )
        manual_event = memory.write_event(
            namespace=NAMESPACE,
            source_type="manual",
            content="manual retention source",
            privacy_level="secret",
        )
        imported_event = memory.write_event(
            namespace=NAMESPACE,
            source_type="import",
            content="import retention source",
            privacy_level="secret",
        )
        mixed_source_claim = memory.write_claim(
            namespace=NAMESPACE,
            memory_type="task",
            subject="mixed source",
            predicate="requires",
            object="source-set filtering",
            evidence_ids=[manual_event.id, imported_event.id],
            confidence=0.8,
            importance=0.9,
        )
        target_event = memory.write_event(
            namespace=NAMESPACE,
            source_type="manual",
            content="eligible retention source",
            privacy_level="secret",
        )
        target_claim = memory.write_claim(
            namespace=NAMESPACE,
            memory_type="task",
            subject="eligible",
            predicate="matches",
            object="effective filters",
            evidence_ids=[target_event.id],
            confidence=0.8,
            importance=0.9,
        )
        public_policy = memory.create_retention_policy(
            namespace=NAMESPACE,
            memory_type="task",
            privacy_level="public",
            action="queue_review",
            after_days=0,
            reason="unit public effective privacy",
        )
        manual_policy = memory.create_retention_policy(
            namespace=NAMESPACE,
            memory_type="task",
            privacy_level="secret",
            source_type="manual",
            action="queue_review",
            after_days=0,
            reason="unit source set",
        )

        run = memory.run_retention(namespace=NAMESPACE, dry_run=True)

        assert run.metadata["matched_count"] == 1
        assert run.metadata["matches"] == [
            {
                "policy_id": manual_policy.id,
                "claim_id": target_claim.id,
                "action": "queue_review",
                "filters": {
                    "memory_type": "task",
                    "privacy_level": "secret",
                    "source_type": "manual",
                    "after_days": 0,
                },
            }
        ]
        assert mixed_privacy_claim.id not in {match["claim_id"] for match in run.metadata["matches"]}
        assert mixed_source_claim.id not in {match["claim_id"] for match in run.metadata["matches"]}
        assert public_policy.id not in {match["policy_id"] for match in run.metadata["matches"]}
    finally:
        memory.close()


def test_fts_repair_is_scoped_to_finding_namespace(tmp_path):
    memory = Memory.open(str(tmp_path / "aletheia.db"), namespace=NAMESPACE)
    try:
        target = memory.remember(
            namespace=NAMESPACE,
            memory_type="preference",
            subject="user",
            predicate="prefers_integrity_repairs",
            object="scoped rebuilds",
        )
        other = memory.remember(
            namespace="user/other",
            memory_type="preference",
            subject="user",
            predicate="prefers_integrity_repairs",
            object="preserved rebuilds",
        )
        memory.store.connection.execute(
            """
            INSERT INTO claims_fts (claim_id, namespace, subject, predicate, object, memory_type, content)
            VALUES ('bogus_target_namespace', ?, 'bogus', 'bogus', 'bogus', 'task', 'bogus')
            """,
            (NAMESPACE,),
        )

        integrity = memory.integrity_check(namespace=NAMESPACE, deep=True)
        finding = next(
            finding
            for finding in memory.list_integrity_findings(run_id=integrity.id)
            if finding.finding_type == "fts_drift"
        )
        repaired = memory.repair_integrity(finding_id=finding.id, dry_run=False)

        assert repaired.status == "completed"
        assert memory.store.connection.execute(
            "SELECT count(*) AS count FROM claims_fts WHERE claim_id = ?",
            (target.id,),
        ).fetchone()["count"] == 1
        assert memory.store.connection.execute(
            "SELECT count(*) AS count FROM claims_fts WHERE claim_id = 'bogus_target_namespace'"
        ).fetchone()["count"] == 0
        assert memory.store.connection.execute(
            "SELECT count(*) AS count FROM claims_fts WHERE claim_id = ?",
            (other.id,),
        ).fetchone()["count"] == 1
    finally:
        memory.close()


def test_fts_repair_rolls_back_and_refuses_unscoped_delete(monkeypatch, tmp_path):
    memory = Memory.open(str(tmp_path / "aletheia.db"), namespace=NAMESPACE)
    try:
        target = memory.remember(
            namespace=NAMESPACE,
            memory_type="preference",
            subject="user",
            predicate="prefers_atomic_integrity_repairs",
            object="transactional rebuilds",
        )
        memory.store.connection.execute(
            """
            INSERT INTO claims_fts (claim_id, namespace, subject, predicate, object, memory_type, content)
            VALUES ('bogus_atomic_namespace', ?, 'bogus', 'bogus', 'bogus', 'task', 'bogus')
            """,
            (NAMESPACE,),
        )
        integrity = memory.integrity_check(namespace=NAMESPACE, deep=True)
        finding = next(
            finding
            for finding in memory.list_integrity_findings(run_id=integrity.id)
            if finding.finding_type == "fts_drift"
        )

        def fail_index(*args, **kwargs):
            raise RuntimeError("simulated index failure")

        monkeypatch.setattr(memory, "_index_claim", fail_index)
        with pytest.raises(RuntimeError, match="simulated index failure"):
            memory.repair_integrity(finding_id=finding.id, dry_run=False)

        assert memory.store.connection.execute(
            "SELECT count(*) AS count FROM claims_fts WHERE claim_id = ?",
            (target.id,),
        ).fetchone()["count"] == 1
        assert memory.store.connection.execute(
            "SELECT count(*) AS count FROM claims_fts WHERE claim_id = 'bogus_atomic_namespace'"
        ).fetchone()["count"] == 1

        memory.store.connection.execute(
            """
            INSERT INTO integrity_findings (
                id, run_id, severity, finding_type, target_id, target_type,
                message, repairable, recommended_action, created_at, metadata_json
            )
            VALUES (
                'ifind_unscoped_fts', 'irun_manual', 'high', 'fts_drift',
                'claim_without_namespace', 'claim', 'Manual unscoped FTS finding.',
                1, 'repair', '2026-01-01T00:00:00+00:00', '{}'
            )
            """
        )
        with pytest.raises(ValidationError, match="requires a resolvable namespace"):
            memory.repair_integrity(finding_id="ifind_unscoped_fts", dry_run=False)
    finally:
        memory.close()


def test_nested_transaction_rolls_back_hardening_write(tmp_path):
    memory = Memory.open(str(tmp_path / "aletheia.db"), namespace=NAMESPACE)
    try:
        with pytest.raises(RuntimeError):
            with memory.store.transaction():
                memory.create_retention_policy(
                    namespace=NAMESPACE,
                    memory_type="task",
                    action="archive",
                    after_days=1,
                    reason="Nested rollback regression.",
                )
                raise RuntimeError("rollback outer transaction")

        assert memory.list_retention_policies(namespace=NAMESPACE) == []
    finally:
        memory.close()


def test_export_import_support_benchmark_release_readiness_and_compaction(tmp_path):
    source = Memory.open(str(tmp_path / "source.db"), namespace=NAMESPACE)
    export_path = tmp_path / "export.alet"
    support_path = tmp_path / "support.zip"
    manifest_path = tmp_path / "release.json"
    try:
        source.remember(
            namespace=NAMESPACE,
            memory_type="project",
            subject="m8",
            predicate="exports",
            object="namespace archives",
        )
        export = source.export_archive(
            output_path=str(export_path),
            namespace=NAMESPACE,
            encrypt=True,
            passphrase=PASSPHRASE,
        )
        assert export.file_path == str(export_path)

        support = source.support_bundle(output_path=str(support_path))
        assert support.includes_raw_content is False
        assert support_path.exists()

        benchmark = source.benchmark_run(profile="tiny")
        assert benchmark.status == "completed"
        assert {result.operation for result in source.list_benchmark_results(benchmark.id)} >= {
            "write_event",
            "backup_create",
            "backup_verify",
        }

        release = source.release_manifest(output_path=str(manifest_path))
        assert release.version == "1.3.0"
        assert manifest_path.exists()

        readiness = source.readiness_check(namespace=NAMESPACE)
        assert readiness.status in {"ready", "ready_with_warnings"}

        compact_preview = source.compact_database(dry_run=True)
        assert compact_preview.metadata["dry_run"] is True
    finally:
        source.close()

    target = Memory.open(str(tmp_path / "target.db"), namespace=NAMESPACE)
    try:
        dry_import = target.import_archive(
            input_path=str(export_path),
            namespace=NAMESPACE,
            passphrase=PASSPHRASE,
            dry_run=True,
        )
        assert dry_import.imported_counts["evidence"] >= 1
        applied_import = target.import_archive(
            input_path=str(export_path),
            namespace=NAMESPACE,
            passphrase=PASSPHRASE,
            dry_run=False,
        )
        assert applied_import.status == "completed"
        assert target.list_claims(namespace=NAMESPACE)
    finally:
        target.close()


def test_m8_cli_and_http_surfaces(tmp_path, capsys):
    db_path = tmp_path / "cli.db"
    backup_path = tmp_path / "cli.alet"
    assert main(["init", "--db", str(db_path), "--protected"]) == 0
    init_status = json.loads(capsys.readouterr().out)
    assert init_status["schema_version"] == "1.3.0"
    assert main(["encrypt", "status", "--db", str(db_path)]) == 0
    status = json.loads(capsys.readouterr().out)
    assert status["enabled"] is True

    assert main([
        "remember",
        "--db",
        str(db_path),
        "--namespace",
        NAMESPACE,
        "--type",
        "project",
        "--subject",
        "cli",
        "--predicate",
        "tests",
        "--object",
        "m8",
    ]) == 0
    capsys.readouterr()
    assert main([
        "backup",
        "create",
        "--db",
        str(db_path),
        "--namespace",
        NAMESPACE,
        "--output",
        str(backup_path),
        "--encrypt",
        "--passphrase",
        PASSPHRASE,
    ]) == 0
    backup_payload = json.loads(capsys.readouterr().out)
    assert backup_payload["encrypted"] is True
    assert backup_path.exists()
    assert main(["backup", "verify", str(backup_path), "--db", str(db_path), "--passphrase", PASSPHRASE]) == 0

    service, token = _service(tmp_path)
    try:
        status_code, envelope = _get(service, "/v1/encryption/status", token)
        assert status_code == 200
        assert "enabled" in envelope["data"]

        status_code, envelope = _post(
            service,
            "/v1/readiness/check",
            token,
            {"namespace": NAMESPACE},
        )
        assert status_code == 200
        assert envelope["data"]["profile"] == "local_production"

        status_code, envelope = _post(
            service,
            "/v1/backups/create",
            token,
            {
                "namespace": NAMESPACE,
                "output_path": str(tmp_path / "api.alet"),
                "encrypt": True,
                "passphrase": PASSPHRASE,
            },
        )
        assert status_code == 200
        assert envelope["data"]["encrypted"] is True

        status_code, envelope = _post(
            service,
            "/v1/backups/create",
            token,
            {
                "namespace": NAMESPACE,
                "output_path": str(tmp_path.parent / "outside-admin-root.alet"),
                "encrypt": True,
                "passphrase": PASSPHRASE,
            },
        )
        assert status_code == 400
        assert envelope["error"]["code"] == "validation_error"
        assert "admin safe root" in envelope["error"]["message"]

        read_only_service, read_token = _service(tmp_path / "readonly", capabilities=["memory:read"])
        try:
            denied_status, _ = _get(read_only_service, "/v1/encryption/status", read_token)
            assert denied_status == 403
        finally:
            read_only_service.close()

        schema = openapi_schema()
        assert schema["info"]["version"] == "1.3.0"
        assert "/v1/backups/create" in schema["paths"]
        assert "/v1/readiness/check" in schema["paths"]
    finally:
        service.close()
