#!/usr/bin/env python3
"""Run live M8 production-hardening scorecard checks."""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import os
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from aletheia import Memory
from aletheia.cli.main import main as cli_main
from aletheia.models import ServiceConfig
from aletheia.service.auth import AuthService
from aletheia.service.http import AletheiaService, openapi_schema


NAMESPACE = "live/m8"
PASSPHRASE = "live-m8-passphrase"
os.environ.setdefault("ALETHEIA_PROTECTED_KEY", PASSPHRASE)


def run_cli(argv: list[str]) -> str:
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        status = cli_main(argv)
    assert status == 0
    return buffer.getvalue()


@dataclass
class ScoreCase:
    category: str
    name: str
    contract_measure: str
    fn: Callable[[], str]


class M8LiveScorecard:
    def __init__(self, base_dir: Path):
        self.base_dir = base_dir
        self.db_path = base_dir / "m8_live.db"
        self.backup_path = base_dir / "m8_live.alet"
        self.restore_path = base_dir / "m8_restore.db"
        self.export_path = base_dir / "m8_export.alet"
        self.support_path = base_dir / "m8_support.zip"
        self.release_path = base_dir / "m8_release.json"
        self.memory = Memory.open(str(self.db_path), namespace=NAMESPACE)
        self.claim_id: str | None = None
        self.secret_event_id: str | None = None

    def close(self) -> None:
        self.memory.close()

    def cases(self) -> list[ScoreCase]:
        return [
            ScoreCase("30.1 Backup", "Encrypted backup manifest and verification", "Backups are encrypted, checksummed, restorable, and corruption/missing-key aware.", self.case_backup),
            ScoreCase("30.2 Restore", "Dry-run and applied restore", "Restore can preview safely and create a verified target database.", self.case_restore),
            ScoreCase("30.3 Encryption", "Protected mode content encryption and key rotation", "Sensitive content is encrypted at rest, decrypted on read, and excluded from unsafe indexes.", self.case_encryption),
            ScoreCase("30.4 Redaction/Forget", "Redaction, forget, and tombstones", "Redaction/forget preserve auditability while invalidating affected retrieval surfaces.", self.case_redaction_forget),
            ScoreCase("30.5 Retention", "Retention policy preview and apply", "Retention policies select and apply governed actions.", self.case_retention),
            ScoreCase("30.6 Integrity", "Integrity findings and repair planning", "Integrity checks persist findings and identify index drift.", self.case_integrity),
            ScoreCase("30.7 Migration/Compaction", "Migration planner and compaction preview", "Migration plans/runs and compaction runs are recorded safely.", self.case_migration_compaction),
            ScoreCase("30.8 Import/Export", "Encrypted export and namespace import", "Archives can be exported, verified, dry-run imported, and applied.", self.case_import_export),
            ScoreCase("30.9 Support/Readiness", "Support bundle and readiness check", "Diagnostics are redacted by default and readiness records warnings/recommendations.", self.case_support_readiness),
            ScoreCase("30.10 Performance/Release", "Benchmark and release manifest", "Benchmark results persist and release metadata is reproducible.", self.case_benchmark_release),
            ScoreCase("30.11 Console/API/CLI", "CLI and HTTP production hardening endpoints", "M8 operations are reachable through CLI, API, OpenAPI, and console-safe auth gates.", self.case_cli_http),
        ]

    def run(self) -> int:
        print("Aletheia M8 Production Hardening Live Scorecard")
        print(f"workspace: {self.base_dir}")
        passed = 0
        results: list[dict] = []
        for index, case in enumerate(self.cases(), start=1):
            try:
                detail = case.fn()
                status = "PASS"
                passed += 1
            except Exception as exc:  # noqa: BLE001 - scorecard must record failures.
                detail = f"{type(exc).__name__}: {exc}"
                status = "FAIL"
            results.append({"status": status, "category": case.category, "name": case.name, "detail": detail})
            print(f"[{status}] {index:02d}. {case.category} - {case.name}")
            print(f"      measure: {case.contract_measure}")
            print(f"      outcome: {detail}")
        print()
        print(f"score: {passed}/{len(results)}")
        print(json.dumps(results, indent=2))
        return 0 if passed == len(results) else 1

    def seed(self) -> None:
        if self.claim_id:
            return
        claim = self.memory.remember(
            namespace=NAMESPACE,
            memory_type="project",
            subject="aletheia",
            predicate="has_m8_live_goal",
            object="production hardening live coverage",
            confidence=0.91,
            importance=0.8,
        )
        self.claim_id = claim.id

    def case_backup(self) -> str:
        self.seed()
        backup = self.memory.create_backup(
            output_path=str(self.backup_path),
            backup_type="hybrid",
            namespace=NAMESPACE,
            encrypt=True,
            passphrase=PASSPHRASE,
        )
        assert backup.encrypted is True
        assert backup.item_counts["claims"] >= 1
        assert b"production hardening live coverage" not in self.backup_path.read_bytes()
        assert self.memory.verify_backup(backup_path=str(self.backup_path), passphrase=PASSPHRASE).status == "passed"
        assert self.memory.verify_backup(backup_path=str(self.backup_path)).status == "failed"
        return f"backup_id={backup.id}, claims={backup.item_counts['claims']}, encrypted={backup.encrypted}"

    def case_restore(self) -> str:
        self.case_backup()
        dry_run = self.memory.restore_backup(
            backup_path=str(self.backup_path),
            target_db_path=str(self.restore_path),
            passphrase=PASSPHRASE,
            dry_run=True,
        )
        assert dry_run.dry_run is True
        if self.restore_path.exists():
            self.restore_path.unlink()
        applied = self.memory.restore_backup(
            backup_path=str(self.backup_path),
            target_db_path=str(self.restore_path),
            passphrase=PASSPHRASE,
            dry_run=False,
        )
        restored = Memory.open(str(self.restore_path), namespace=NAMESPACE)
        try:
            assert restored.integrity_check(namespace=NAMESPACE).status == "passed"
            assert restored.read_claim(self.claim_id).object == "production hardening live coverage"
        finally:
            restored.close()
        return f"restore_id={applied.id}, target={self.restore_path.name}"

    def case_encryption(self) -> str:
        self.memory.enable_protected_mode(actor="live")
        event = self.memory.write_event(
            namespace=NAMESPACE,
            source_type="live_secret",
            content="M8 live secret phrase",
            privacy_level="secret",
        )
        self.secret_event_id = event.id
        raw = self.memory.store.connection.execute("SELECT content FROM evidence_events WHERE id = ?", (event.id,)).fetchone()["content"]
        assert raw.startswith("enc:v2:")
        assert "M8 live secret" not in raw
        assert self.memory.read_event(event.id).content == "M8 live secret phrase"
        claim = self.memory.write_claim(
            namespace=NAMESPACE,
            subject="m8-secret",
            predicate="has_phrase",
            object="live",
            memory_type="preference",
            evidence_ids=[event.id],
        )
        fts_count = self.memory.store.connection.execute(
            "SELECT count(*) AS count FROM claims_fts WHERE claim_id = ?",
            (claim.id,),
        ).fetchone()["count"]
        assert fts_count == 0
        key = self.memory.list_keys()[0]
        rotation = self.memory.rotate_key(old_key_id=key.id, new_key_label="live-next", dry_run=True)
        return f"secret_event={event.id}, key={key.id}, rotation={rotation.status}"

    def case_redaction_forget(self) -> str:
        event_id = self.secret_event_id or self.memory.write_event(
            namespace=NAMESPACE,
            source_type="live_redact",
            content="redact me",
            privacy_level="personal",
        ).id
        preview = self.memory.redact(target_id=event_id, target_type="evidence", reason="live preview", dry_run=True)
        applied = self.memory.redact(target_id=event_id, target_type="evidence", reason="live apply", dry_run=False)
        assert preview.dry_run is True
        assert self.memory.read_event(event_id).content == "[REDACTED]"
        forget_claim = self.memory.remember(
            namespace=NAMESPACE,
            memory_type="task",
            subject="forget-live",
            predicate="target",
            object="one",
        )
        forget_run = self.memory.forget(
            selector={"target_type": "claim", "target_id": forget_claim.id},
            reason="live forget",
            dry_run=False,
        )
        tombstones = self.memory.list_tombstones(namespace=NAMESPACE)
        assert tombstones
        return f"redaction={applied.id}, forget={forget_run.id}, tombstones={len(tombstones)}"

    def case_retention(self) -> str:
        self.memory.remember(
            namespace=NAMESPACE,
            memory_type="task",
            subject="retention-live",
            predicate="expires",
            object="now",
        )
        policy = self.memory.create_retention_policy(
            namespace=NAMESPACE,
            memory_type="task",
            action="archive",
            after_days=0,
            reason="live retention",
        )
        preview = self.memory.run_retention(namespace=NAMESPACE, dry_run=True)
        applied = self.memory.run_retention(namespace=NAMESPACE, dry_run=False)
        assert preview.metadata["matched_count"] >= 1
        assert applied.metadata["applied_count"] >= 1
        return f"policy={policy.id}, matched={preview.metadata['matched_count']}, applied={applied.metadata['applied_count']}"

    def case_integrity(self) -> str:
        self.memory.store.connection.execute(
            """
            INSERT INTO claims_fts (claim_id, namespace, subject, predicate, object, memory_type, content)
            VALUES ('live-bogus', ?, 'bogus', 'bogus', 'bogus', 'task', 'bogus')
            """,
            (NAMESPACE,),
        )
        check = self.memory.integrity_check(namespace=NAMESPACE, deep=True)
        findings = self.memory.list_integrity_findings(run_id=check.id)
        assert any(finding.finding_type == "fts_drift" for finding in findings)
        return f"integrity={check.status}, findings={check.finding_count}"

    def case_migration_compaction(self) -> str:
        plan = self.memory.migration_plan()
        migration = self.memory.migration_apply(dry_run=True, verify_after=False)
        compact = self.memory.compact_database(dry_run=True)
        assert plan.to_version == "1.3.0"
        assert compact.metadata["dry_run"] is True
        return f"plan_steps={len(plan.steps)}, migration={migration.status}, compact={compact.status}"

    def case_import_export(self) -> str:
        export = self.memory.export_archive(
            output_path=str(self.export_path),
            namespace=NAMESPACE,
            encrypt=True,
            passphrase=PASSPHRASE,
        )
        target = Memory.open(str(self.base_dir / "m8_import.db"), namespace=NAMESPACE)
        try:
            dry = target.import_archive(input_path=str(self.export_path), namespace=NAMESPACE, passphrase=PASSPHRASE, dry_run=True)
            applied = target.import_archive(input_path=str(self.export_path), namespace=NAMESPACE, passphrase=PASSPHRASE, dry_run=False)
            assert dry.imported_counts["evidence"] >= 1
            assert applied.status == "completed"
        finally:
            target.close()
        return f"export={export.id}, dry_import={dry.imported_counts}, applied={applied.id}"

    def case_support_readiness(self) -> str:
        support = self.memory.support_bundle(output_path=str(self.support_path), include_raw_content=False)
        readiness = self.memory.readiness_check(namespace=NAMESPACE)
        assert support.includes_raw_content is False
        assert self.support_path.exists()
        assert readiness.status in {"ready", "ready_with_warnings"}
        return f"support={support.id}, readiness={readiness.status}, warnings={len(readiness.warnings)}"

    def case_benchmark_release(self) -> str:
        benchmark = self.memory.benchmark_run(profile="tiny")
        results = self.memory.list_benchmark_results(benchmark.id)
        release = self.memory.release_manifest(output_path=str(self.release_path))
        assert results
        assert release.version == "1.3.0"
        assert self.release_path.exists()
        return f"benchmark={benchmark.id}, results={len(results)}, release={release.id}"

    def case_cli_http(self) -> str:
        cli_db = self.base_dir / "cli.db"
        cli_backup = self.base_dir / "cli.alet"
        run_cli(["init", "--db", str(cli_db), "--protected"])
        run_cli([
            "remember",
            "--db",
            str(cli_db),
            "--namespace",
            NAMESPACE,
            "--type",
            "project",
            "--subject",
            "m8-cli",
            "--predicate",
            "has",
            "--object",
            "coverage",
        ])
        run_cli([
            "backup",
            "create",
            "--db",
            str(cli_db),
            "--namespace",
            NAMESPACE,
            "--output",
            str(cli_backup),
            "--encrypt",
            "--passphrase",
            PASSPHRASE,
        ])
        run_cli(["backup", "verify", str(cli_backup), "--db", str(cli_db), "--passphrase", PASSPHRASE])

        service = AletheiaService(
            self.memory,
            ServiceConfig(db_path=str(self.db_path), auto_migrate=True, auth_required=True, console_enabled=True),
        )
        auth = AuthService(self.memory)
        client = auth.create_client(name="live-m8-admin", client_type="agent")
        _token, raw = auth.create_token(
            client_id=client.id,
            namespace_grants=[NAMESPACE],
            capabilities=["memory:admin"],
            privacy_ceiling="secret",
        )
        headers = {"Authorization": f"Bearer {raw}", "X-Request-ID": "req_live_m8"}
        status, envelope = service.handle_http(method="GET", path="/v1/encryption/status", headers=headers)
        assert status == 200
        status, envelope = service.handle_http(
            method="POST",
            path="/v1/readiness/check",
            headers=headers,
            body=json.dumps({"namespace": NAMESPACE}).encode("utf-8"),
        )
        assert status == 200
        schema = openapi_schema()
        assert schema["info"]["version"] == "1.3.0"
        assert "/v1/backups/create" in schema["paths"]
        assert "Production Hardening" in service._console_static("/console")[1]["_raw_body"]
        return f"cli_backup={cli_backup.name}, http_readiness={envelope['data']['status']}, openapi=1.3.0"


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Aletheia M8 live scorecard.")
    parser.add_argument("--workdir", help="Directory for live test artifacts.")
    args = parser.parse_args()
    base_dir = Path(args.workdir) if args.workdir else Path(tempfile.mkdtemp(prefix="aletheia-m8-live-"))
    base_dir.mkdir(parents=True, exist_ok=True)
    scorecard = M8LiveScorecard(base_dir)
    try:
        return scorecard.run()
    finally:
        scorecard.close()


if __name__ == "__main__":
    raise SystemExit(main())
