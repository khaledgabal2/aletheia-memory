"""Actual review protocol, independent SQLite writers, migration and recovery."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import threading
from urllib.parse import urlencode

import pytest
from jsonschema import Draft202012Validator
from openapi_spec_validator import validate

from aletheia import Memory
from aletheia.cli.main import main
from aletheia.client import AletheiaClient, AletheiaStaleRevisionError, AletheiaUnsupportedFeatureError
from aletheia.core.errors import ValidationError
from aletheia.models import ServiceConfig
from aletheia.service.http import AletheiaService, openapi_schema
from aletheia.service.review_contracts import review_document, REVIEW_PATHS
from aletheia.storage import SQLiteStore, SCHEMA_VERSION
from aletheia.storage.review import inventory, integrity, trigger_definitions
from scripts.v1_4_phase0 import local_service, request, NAMESPACE
from tests.test_v1_4_reads import candidate, credential, domain_state

PROFILE = {"X-Aletheia-Contract": "memory-review-v1"}


def inspect(url, token, target):
    result = request(url, "GET", "/v1/candidates/" + target, token=token, headers=PROFILE)
    assert result["status"] == 200, result
    return result["body"]["data"]


def decide(url, token, target, revision, *, action="promote", key="test-operation", reason="Explicit fixture decision", headers=None):
    return request(url, "POST", f"/v1/candidates/{target}/{action}", token=token,
        headers={**PROFILE, "Idempotency-Key": key, **(headers or {})}, payload={"reason": reason, "expected_revision": revision})


def conform(document, path, result):
    method = REVIEW_PATHS[path][0]
    shape = document["paths"][path][method]["responses"][str(result["status"])]["content"]["application/json"]["schema"]
    Draft202012Validator({**shape, "components": document["components"]}).validate(result["body"])
    assert result["headers"]["Cache-Control"] == "no-store"
    assert result["headers"]["X-Request-ID"] == result["body"]["request_id"]


@pytest.mark.parametrize("action", ["promote", "reject"])
def test_actual_review_schemas_replay_and_audit(action, tmp_path):
    with local_service(tmp_path) as (service, url, tokens):
        item = candidate(service.memory, "review schema")
        document = review_document(request(url, "GET", "/v1/openapi.json")["body"]["data"])
        validate(document)
        listing = request(url, "GET", "/v1/candidates?" + urlencode({"namespace": NAMESPACE, "limit": 1}), token=tokens["reviewer"], headers=PROFILE)
        conform(document, "/v1/candidates", listing)
        detail = request(url, "GET", "/v1/candidates/" + item.id, token=tokens["reviewer"], headers=PROFILE)
        conform(document, "/v1/candidates/{candidate_id}", detail)
        revision = detail["body"]["data"]["revision"]
        first = decide(url, tokens["reviewer"], item.id, revision, action=action, headers={"X-Request-ID": "first-transport"})
        assert first["status"] == 200, first
        conform(document, "/v1/candidates/{candidate_id}/" + action, first)
        before = domain_state(service.memory)
        replay = decide(url, tokens["reviewer"], item.id, revision, action=action, headers={"X-Request-ID": "retry-transport"})
        assert replay["status"] == 200
        assert first["body"]["data"] == replay["body"]["data"]
        assert first["body"]["request_id"] != replay["body"]["request_id"]
        assert before == domain_state(service.memory)
        receipt = first["body"]["data"]
        row = service.memory.store.connection.execute("SELECT details FROM audit_log WHERE id=?", (receipt["audit_id"],)).fetchone()
        assert json.loads(row[0])["operation_id"] == receipt["operation_id"]
        assert item.object not in json.dumps(receipt) and "reason" not in receipt
        assert service.memory.store.connection.execute("SELECT count(*) FROM extraction_decisions WHERE candidate_id=? AND decision=?", (item.id, action)).fetchone()[0] == 1
        stale = decide(url, tokens["reviewer"], item.id, revision, action=action, key="new-key")
        assert stale["status"] == 412
        conform(document, "/v1/candidates/{candidate_id}/" + action, stale)
        fresh = inspect(url, tokens["reviewer"], item.id)["revision"]
        assert decide(url, tokens["reviewer"], item.id, fresh, action=action, key="fresh-terminal-key")["status"] == 409
        assert decide(url, tokens["reviewer"], item.id, revision, action=action, reason="Different payload")["status"] == 409
        opposite = "reject" if action == "promote" else "promote"
        assert decide(url, tokens["reviewer"], item.id, revision, action=opposite)["status"] == 409


@pytest.mark.parametrize("payload,key,status", [({"reason": "review"}, "key", 428),
    ({"reason": "review", "expected_revision": "old"}, None, 400),
    ({"reason": "review", "expected_revision": 1}, "key", 400),
    ({"reason": " ", "expected_revision": "old"}, "key", 400),
    ({"reason": "review", "expected_revision": "old", "force": True}, "key", 400),
    ({"reason": "review", "expected_revision": "قديم"}, "key", 412),
    ({"reason": "review", "expected_revision": "old"}, "key", 412)])
def test_review_preconditions_and_validation_never_commit(tmp_path, payload, key, status):
    with local_service(tmp_path) as (service, url, tokens):
        item = candidate(service.memory, "validation")
        before = domain_state(service.memory)
        headers = {**PROFILE, **({"Idempotency-Key": key} if key else {})}
        result = request(url, "POST", f"/v1/candidates/{item.id}/promote", token=tokens["reviewer"], headers=headers, payload=payload)
        assert result["status"] == status
        conform(review_document(openapi_schema()), "/v1/candidates/{candidate_id}/promote", result)
        assert before == domain_state(service.memory)
        if "expected_revision" in payload and status == 412:
            legacy_header = request(url, "POST", f"/v1/candidates/{item.id}/promote", token=tokens["reviewer"], headers={"Idempotency-Key": "legacy-condition"}, payload=payload)
            assert legacy_header["status"] == 412  # Explicit preconditions are never ignored.


def test_scope_privacy_capabilities_and_changed_access_apply_before_replay(tmp_path):
    with local_service(tmp_path) as (service, url, tokens):
        item = candidate(service.memory, "authorization")
        secret = candidate(service.memory, "secret-marker", privacy_level="secret")
        _, wrong_namespace = credential(service, ["memory:review"], grants=["user/elsewhere"])
        token, owner = credential(service, ["memory:review"])
        revision = inspect(url, owner, item.id)["revision"]
        for raw, target in [(tokens["reader"], item.id), (wrong_namespace, item.id), (owner, secret.id)]:
            assert decide(url, raw, target, revision)["status"] == 403
            legacy = request(url, "POST", f"/v1/candidates/{target}/promote", token=raw, payload={"reason": "legacy inspection"})
            assert legacy["status"] == 403
        first = decide(url, owner, item.id, revision)
        assert first["status"] == 200
        service.auth.revoke_token(token.id, reason="Test current authorization")
        assert decide(url, owner, item.id, revision)["status"] == 401
        assert service.memory.store.connection.execute("SELECT count(*) FROM review_replays").fetchone()[0] == 1


def test_replay_keys_are_separate_for_credentials_of_the_same_client(tmp_path):
    with local_service(tmp_path) as (service, url, _):
        client = service.auth.create_client(name="Two credentials", client_type="test")
        values = [service.auth.create_token(client_id=client.id, capabilities=["memory:review"], namespace_grants=[NAMESPACE])[1] for _ in range(2)]
        one, two = candidate(service.memory, "one"), candidate(service.memory, "two")
        for raw, item in zip(values, [one, two]):
            result = decide(url, raw, item.id, inspect(url, raw, item.id)["revision"], action="reject", key="same-key")
            assert result["status"] == 200
        assert service.memory.store.connection.execute("SELECT count(*) FROM review_replays").fetchone()[0] == 2


def test_keyset_pagination_ties_hidden_rows_tampering_and_invalidations(tmp_path):
    with local_service(tmp_path) as (service, url, tokens):
        items = [candidate(service.memory, str(i)) for i in range(5)]
        candidate(service.memory, "invisible", privacy_level="secret")
        with service.memory.store.transaction():
            service.memory.store.connection.execute("UPDATE candidate_claims SET created_at='2026-08-30T00:00:00+00:00'")
        query = {"namespace": NAMESPACE, "status": "pending_review", "limit": 2}
        base = "/v1/candidates?" + urlencode(query)
        seen, cursor = [], None
        while True:
            result = request(url, "GET", base + ("&" + urlencode({"cursor": cursor}) if cursor else ""), token=tokens["reviewer"], headers=PROFILE)
            assert result["status"] == 200
            conform(review_document(openapi_schema()), "/v1/candidates", result)
            seen.extend(item["id"] for item in result["body"]["data"])
            cursor = result["body"]["pagination"]["next_cursor"]
            if cursor is None:
                break
        assert seen == sorted(item.id for item in items)
        first = request(url, "GET", base, token=tokens["reviewer"], headers=PROFILE)
        cursor = first["body"]["pagination"]["next_cursor"]
        assert all(item.id not in cursor for item in items)
        tampered = request(url, "GET", base + "&cursor=bad-token", token=tokens["reviewer"], headers=PROFILE)
        assert tampered["status"] == 400
        altered = request(url, "GET", base.replace("pending_review", "rejected") + "&" + urlencode({"cursor": cursor}), token=tokens["reviewer"], headers=PROFILE)
        assert altered["status"] == 409
        service.memory.review_candidate(items[0].id, decision="edit", reason="Changed between pages", edits={"object": "new text"})
        stale = request(url, "GET", base + "&" + urlencode({"cursor": cursor}), token=tokens["reviewer"], headers=PROFILE)
        assert stale["status"] == 409


def test_two_independent_connections_cannot_commit_competing_decisions(tmp_path):
    with local_service(tmp_path) as (service, url, tokens):
        item = candidate(service.memory, "concurrency")
        second_memory = Memory.open(service.memory.store.path, auto_migrate=False)
        other = AletheiaService(second_memory, ServiceConfig(db_path=service.memory.store.path, rate_limit_enabled=False))
        headers = {**PROFILE, "Authorization": "Bearer " + tokens["reviewer"]}
        try:
            revision_one = inspect(url, tokens["reviewer"], item.id)["revision"]
            _, detail = other.handle_http(method="GET", path="/v1/candidates/" + item.id, headers=headers)
            revision_two = detail["data"]["revision"]
            barrier = threading.Barrier(2)
            def submit(server, revision, key):
                barrier.wait(timeout=5)
                return server.handle_http(method="POST", path=f"/v1/candidates/{item.id}/promote", headers={**headers, "Idempotency-Key": key}, body=json.dumps({"reason": "Competing explicit review", "expected_revision": revision}).encode())
            with ThreadPoolExecutor(2) as pool:
                futures = [pool.submit(submit, service, revision_one, "one"), pool.submit(submit, other, revision_two, "two")]
                results = [future.result(timeout=15) for future in futures]
            assert sorted(status for status, _ in results) == [200, 412]
            assert service.memory.store.connection.execute("SELECT count(*) FROM claims").fetchone()[0] == 1
            assert service.memory.store.connection.execute("SELECT count(*) FROM extraction_decisions WHERE decision='promote'").fetchone()[0] == 1
        finally:
            other.close()


@pytest.mark.parametrize("writer", ["embedded", "cli", "legacy_http"])
def test_supported_writers_invalidate_review_tokens(tmp_path, writer):
    with local_service(tmp_path) as (service, url, tokens):
        item = candidate(service.memory, "cross-writer")
        revision = inspect(url, tokens["reviewer"], item.id)["revision"]
        if writer == "embedded":
            separate = Memory.open(service.memory.store.path, auto_migrate=False)
            try:
                separate.review_candidate(item.id, decision="edit", reason="Embedded change", edits={"object": "changed"})
            finally:
                separate.close()
        elif writer == "cli":
            result = subprocess.run([sys.executable, "-m", "aletheia.cli.main", "candidates", "edit", item.id, "--db", service.memory.store.path, "--object", "CLI change", "--reason", "Explicit CLI edit"], capture_output=True, text=True, timeout=15)
            assert result.returncode == 0, result.stderr
        else:
            result = request(url, "POST", f"/v1/candidates/{item.id}/reject", token=tokens["reviewer"], payload={"reason": "Legacy decision"})
            assert result["status"] == 200
        assert decide(url, tokens["reviewer"], item.id, revision)["status"] == 412


@pytest.mark.parametrize("point", ["decision", "scope", "receipt"])
def test_failed_review_rolls_back_claim_links_scope_audit_epoch_and_replay(tmp_path, monkeypatch, point):
    with local_service(tmp_path) as (service, url, tokens):
        item = candidate(service.memory, "rollback")
        if point == "scope":
            service.memory.review_candidate(item.id, decision="edit", reason="Scope fixture", edits={"suggested_scope": {"type": "project", "applies_when": "fixture"}})
        revision = inspect(url, tokens["reviewer"], item.id)["revision"]
        before = domain_state(service.memory)
        def fail(*args, **kwargs):
            raise RuntimeError("Injected rollback point")
        if point == "decision":
            monkeypatch.setattr(service.memory, "_write_extraction_decision_in_transaction", fail)
        elif point == "scope":
            monkeypatch.setattr(service.memory, "scope_claim", fail)
        else:
            # A storage failure after the complete governance mutation must roll back too.
            service.memory.store.connection.execute("CREATE TRIGGER fail_review_receipt BEFORE INSERT ON review_replays BEGIN SELECT RAISE(ABORT, 'fixture'); END")
        result = decide(url, tokens["reviewer"], item.id, revision)
        assert result["status"] == 500
        assert before == domain_state(service.memory)


def test_trigger_inventory_and_read_only_operational_activity(tmp_path):
    with local_service(tmp_path) as (service, url, tokens):
        db = service.memory.store.connection
        assert integrity(db)
        assert len(list(trigger_definitions())) == 3 * len(inventory()["invalidates"])
        item = candidate(service.memory, "operational")
        revision = inspect(url, tokens["reviewer"], item.id)["revision"]
        for _ in range(3):
            request(url, "GET", "/v1/auth/me", token=tokens["reviewer"])
            request(url, "GET", "/v1/candidates/" + item.id, token=tokens["reviewer"], headers=PROFILE)
        from aletheia.diagnostics import diagnose
        diagnose(db_path=service.memory.store.path, namespace=NAMESPACE)
        assert inspect(url, tokens["reviewer"], item.id)["revision"] == revision
        db.execute("DROP TRIGGER review_epoch_evidence_events_update")
        assert not integrity(db)
        assert service.memory.integrity_check().status == "failed"


def old_database(path):
    fixture = Path(__file__).parent / "fixtures" / "v1_3_1"
    data = (fixture / "storage_schema.sql").read_bytes()
    assert hashlib.sha256(data).hexdigest() == json.loads((fixture / "storage_schema_source.json").read_text())["sha256"]
    with sqlite3.connect(path) as connection:
        connection.executescript(data.decode())
        connection.execute("INSERT INTO schema_version (id, version, applied_at) VALUES (1, '1.3.0', '2026-08-30')")
    return Memory.open(str(path), auto_migrate=False)


def test_migration_is_atomic_preserves_data_and_has_complete_trigger_integrity(tmp_path, monkeypatch):
    path = tmp_path / "legacy.db"
    memory = old_database(path)
    event = memory.write_event(namespace=NAMESPACE, source_type="manual", content="Preserve original source")
    memory.close()
    original = SQLiteStore._backfill_m12_records
    def fail(*args):
        raise RuntimeError("Injected migration failure")
    monkeypatch.setattr(SQLiteStore, "_backfill_m12_records", fail)
    with pytest.raises(RuntimeError, match="Injected"):
        Memory.open(str(path))
    with sqlite3.connect(path) as connection:
        assert connection.execute("SELECT version FROM schema_version").fetchone()[0] == "1.3.0"
        assert connection.execute("SELECT 1 FROM sqlite_master WHERE name='review_state'").fetchone() is None
        assert connection.execute("SELECT content FROM evidence_events WHERE id=?", (event.id,)).fetchone()[0] == "Preserve original source"
    monkeypatch.setattr(SQLiteStore, "_backfill_m12_records", original)
    upgraded = Memory.open(str(path))
    try:
        assert upgraded.health()["schema_version"] == SCHEMA_VERSION
        assert upgraded.read_event(event.id).content == "Preserve original source"
        assert integrity(upgraded.store.connection)
    finally:
        upgraded.close()


@pytest.mark.parametrize("spelling", ["absolute", "tilde"])
@pytest.mark.parametrize("command", ["backup", "plan", "apply"])
def test_cli_backup_precedes_upgrade_and_reports_actual_stored_schema(tmp_path, capsys, spelling, command):
    path = tmp_path / "legacy.db"
    memory = old_database(path)
    event = memory.write_event(namespace=NAMESPACE, source_type="manual", content="Keep original recovery evidence")
    support = memory.compatibility_report()["migration_support"]
    assert support["from"] == "1.3.0" and support["to"] == SCHEMA_VERSION
    assert support["safe"] and support["requires_pre_upgrade_backup"]
    memory.close()
    # Exercise real expansion without changing HOME or writing in the home directory.
    db_arg = str(path) if spelling == "absolute" else "~/" + os.path.relpath(path, Path.home())
    assert Path(db_arg).expanduser().resolve() == path.resolve()
    archive = tmp_path / "before.alet"
    if command == "backup":
        args = ["backup", "create", "--db", db_arg, "--output", str(archive), "--encrypt", "--passphrase", "synthetic-test-password"]
    elif command == "plan":
        args = ["migrate", "plan", "--db", db_arg]
    else:
        args = ["migrate", "apply", "--db", db_arg, "--backup-before", "--backup-output", str(archive), "--passphrase", "synthetic-test-password"]
    assert main(args) == 0
    capsys.readouterr()
    with sqlite3.connect(path) as connection:
        assert connection.execute("SELECT version FROM schema_version").fetchone()[0] == (SCHEMA_VERSION if command == "apply" else "1.3.0")
        assert connection.execute("SELECT content FROM evidence_events WHERE id=?", (event.id,)).fetchone()[0] == "Keep original recovery evidence"
    if command == "plan":
        assert not archive.exists()
        return
    from aletheia.core.hardening import verify_backup_file
    status, _, manifest, payload = verify_backup_file(backup_path=str(archive), passphrase="synthetic-test-password", deep=True)
    assert status == "passed"
    assert manifest["schema_version"] == "1.3.0"
    old = tmp_path / "snapshot.db"
    old.write_bytes(payload["database.sqlite"])
    with sqlite3.connect(old) as connection:
        assert connection.execute("SELECT version FROM schema_version").fetchone()[0] == "1.3.0"
        assert connection.execute("SELECT content FROM evidence_events WHERE id=?", (event.id,)).fetchone()[0] == "Keep original recovery evidence"
        assert connection.execute("SELECT 1 FROM sqlite_master WHERE name='review_state'").fetchone() is None


def test_restore_changes_live_identity_and_invalidates_pre_restore_revisions_and_replays(tmp_path):
    with local_service(tmp_path) as (service, url, tokens):
        item = candidate(service.memory, "restore")
        archive = tmp_path / "before-review.alet"
        service.memory.create_backup(output_path=str(archive), passphrase="synthetic-restore-password")
        revision = inspect(url, tokens["reviewer"], item.id)["revision"]
        identity = request(url, "GET", "/v1/version")["body"]["data"]["service_identity"]
        first = decide(url, tokens["reviewer"], item.id, revision)
        assert first["status"] == 200
        restored = service.memory.restore_backup(backup_path=str(archive), target_db_path=service.memory.store.path,
            mode="in_place", passphrase="synthetic-restore-password", dry_run=False)
        assert restored.status == "completed"
        assert service.memory.store.connection.execute("SELECT count(*) FROM review_replays").fetchone()[0] == 0
        assert request(url, "GET", "/v1/version")["body"]["data"]["service_identity"] != identity
        assert decide(url, tokens["reviewer"], item.id, revision)["status"] == 412
        assert service.memory.read_candidate(item.id).candidate_status == "pending_review"
        latest = inspect(url, tokens["reviewer"], item.id)["revision"]
        assert decide(url, tokens["reviewer"], item.id, latest, key="new-post-restore-decision")["status"] == 200


def test_restart_preserves_safe_replay_but_requires_new_inspection_for_new_writes(tmp_path):
    with local_service(tmp_path) as (service, url, tokens):
        one, two = candidate(service.memory, "replay"), candidate(service.memory, "restart")
        first_revision = inspect(url, tokens["reviewer"], one.id)["revision"]
        first = decide(url, tokens["reviewer"], one.id, first_revision)
        assert first["status"] == 200
        second_revision = inspect(url, tokens["reviewer"], two.id)["revision"]
        reopened = AletheiaService.open(ServiceConfig(db_path=service.memory.store.path, auto_migrate=False))
        headers = {**PROFILE, "Authorization": "Bearer " + tokens["reviewer"], "Idempotency-Key": "test-operation"}
        try:
            code, replay = reopened.handle_http(method="POST", path=f"/v1/candidates/{one.id}/promote", headers=headers,
                body=json.dumps({"expected_revision": first_revision, "reason": "Explicit fixture decision"}).encode())
            assert code == 200 and replay["data"] == first["body"]["data"]
            code, _ = reopened.handle_http(method="POST", path=f"/v1/candidates/{two.id}/promote", headers={**headers, "Idempotency-Key": "restart-key"},
                body=json.dumps({"expected_revision": second_revision, "reason": "New decision"}).encode())
            assert code == 412
        finally:
            reopened.close()


def test_aba_scope_changes_and_background_jobs_invalidate_old_inspection(tmp_path):
    with local_service(tmp_path) as (service, url, tokens):
        item = candidate(service.memory, "ABA")
        old = inspect(url, tokens["reviewer"], item.id)["revision"]
        for value in ["changed", item.object]:
            service.memory.review_candidate(item.id, decision="edit", reason="Explicit fixture edit", edits={"object": value})
        assert service.memory.read_candidate(item.id).object == item.object
        assert decide(url, tokens["reviewer"], item.id, old)["status"] == 412
        service.memory.remember(namespace=NAMESPACE, memory_type="preference", subject="background", predicate="prefers", object="architecture", source_type="manual")
        job = service.memory.enqueue_job(namespace=NAMESPACE, job_type="index_semantic", payload={})
        before = inspect(url, tokens["reviewer"], item.id)["revision"]
        worker = Memory.open(service.memory.store.path, namespace=NAMESPACE, auto_migrate=False)
        try:
            worker.run_jobs(namespace=NAMESPACE)
            assert worker.get_job(job.id).status == "completed"
        finally:
            worker.close()
        assert decide(url, tokens["reviewer"], item.id, before, key="after-worker")["status"] == 412


def test_federation_import_is_candidate_first_and_invalidates_review(tmp_path, monkeypatch):
    from tests.test_m10_federated_memory import _identity_pair, NAMESPACE as federation_namespace
    monkeypatch.setenv("ALETHEIA_FEDERATION_KEY", "synthetic-review-federation-key")
    left, right, metadata, _ = _identity_pair(tmp_path)
    try:
        batch = right.ingest(federation_namespace, source_type="manual", content="User prefers careful architecture notes.")
        run = right.extract_candidates(federation_namespace, batch_id=batch.id)
        item = right.list_candidates(federation_namespace, extraction_run_id=run.id)[0]
        service = AletheiaService(right, ServiceConfig(db_path=right.store.path))
        _, raw = credential(service, ["memory:review"], grants=[federation_namespace])
        headers = {**PROFILE, "Authorization": "Bearer " + raw}
        code, detail = service.handle_http(method="GET", path="/v1/candidates/" + item.id, headers=headers)
        assert code == 200
        left.remember(namespace=federation_namespace, memory_type="project", subject="sync", predicate="mode", object="candidate first", source_type="unit")
        share = left.create_share_grant(name="review-sync", namespace=federation_namespace, recipient_peer_ids=[metadata["peer"].id],
            permissions=["read", "sync_pull", "receive_redactions"], privacy_ceiling="personal", memory_types=["project"], statuses=["active"], reason="Synthetic review test")
        bundle = tmp_path / "review.aletsync"
        left.export_share_bundle(share_id=share.id, output_path=str(bundle), encrypt=True)
        assert right.import_share_bundle(input_path=str(bundle), trust_policy="candidate_only").status == "completed"
        code, result = service.handle_http(method="POST", path=f"/v1/candidates/{item.id}/promote", headers={**headers, "Idempotency-Key": "after-sync"},
            body=json.dumps({"reason": "Old decision", "expected_revision": detail["data"]["revision"]}).encode())
        assert code == 412, result
        assert len(right.list_candidates(federation_namespace)) == 2
    finally:
        left.close()
        right.close()


def test_new_sdk_requires_profile_then_uses_explicit_review_keys(tmp_path, monkeypatch):
    import aletheia.version as versions
    with local_service(tmp_path) as (service, url, tokens):
        item = candidate(service.memory, "SDK")
        client = AletheiaClient(url, tokens["reviewer"])
        monkeypatch.setattr(versions, "SUPPORTED_PROFILES", ("memory-read-v1",))
        with pytest.raises(AletheiaUnsupportedFeatureError):
            client.get_candidate_for_review(item.id)
        # Advertise only in this fixture until the complete G3 gate passes.
        monkeypatch.setattr(versions, "SUPPORTED_PROFILES", ("memory-read-v1", "memory-review-v1"))
        detail = client.get_candidate_for_review(item.id)
        rows = client.list_candidates_for_review(namespace=NAMESPACE, limit=1)
        assert rows[0]["id"] == item.id and client.last_pagination["count"] == 1
        outcome = client.review_candidate(item.id, action="reject", reason="SDK explicit refusal", expected_revision=detail["revision"], idempotency_key="sdk-key")
        assert client.review_candidate(item.id, action="reject", reason="SDK explicit refusal", expected_revision=detail["revision"], idempotency_key="sdk-key") == outcome
        with pytest.raises(AletheiaStaleRevisionError):
            client.review_candidate(item.id, action="reject", reason="Another decision", expected_revision=detail["revision"], idempotency_key="another-key")


@pytest.mark.parametrize("change", ["privacy", "namespace", "capability"])
def test_replay_rechecks_current_scope_and_console_sibling(change, tmp_path):
    with local_service(tmp_path) as (service, url, _):
        item = candidate(service.memory, "Scoped receipt")
        token, raw = credential(service, ["memory:review"])
        revision = inspect(url, raw, item.id)["revision"]
        assert decide(url, raw, item.id, revision)["status"] == 200
        with service.memory.store.transaction():
            if change == "privacy":
                service.memory.store.connection.execute("UPDATE api_tokens SET privacy_ceiling='public' WHERE id=?", (token.id,))
            elif change == "namespace":
                service.memory.store.connection.execute("DELETE FROM namespace_access_grants WHERE token_id=?", (token.id,))
            else:
                service.memory.store.connection.execute("DELETE FROM capability_grants WHERE token_id=?", (token.id,))
        before = domain_state(service.memory)
        assert decide(url, raw, item.id, revision)["status"] == 403
        sibling = request(url, "POST", f"/v1/console/actions/candidates/{item.id}/reject", token=raw,
            payload={"reason": "Changed access", "confirmation": "reject candidate"})
        assert sibling["status"] == 403
        assert before == domain_state(service.memory)


def test_busy_transaction_and_expired_key_cannot_duplicate_review(tmp_path):
    with local_service(tmp_path) as (service, url, tokens):
        item = candidate(service.memory, "Busy database")
        revision = inspect(url, tokens["reviewer"], item.id)["revision"]
        writer = sqlite3.connect(service.memory.store.path)
        service.memory.store.connection.execute("PRAGMA busy_timeout=20")
        writer.execute("BEGIN IMMEDIATE")
        try:
            busy = decide(url, tokens["reviewer"], item.id, revision)
            assert busy["status"] == 503 and busy["body"]["error"]["code"] == "database_busy"
        finally:
            writer.rollback()
            writer.close()
        assert decide(url, tokens["reviewer"], item.id, revision)["status"] == 200
        with service.memory.store.transaction():
            service.memory.store.connection.execute("UPDATE review_replays SET expires_at='2000-01-01T00:00:00+00:00'")
        assert decide(url, tokens["reviewer"], item.id, revision)["status"] == 412
        assert service.memory.store.connection.execute("SELECT count(*) FROM extraction_decisions WHERE candidate_id=? AND decision='promote'", (item.id,)).fetchone()[0] == 1


def test_lost_http_response_replays_exactly_one_committed_decision(tmp_path, monkeypatch):
    from http.client import RemoteDisconnected
    from aletheia.service.http import AletheiaRequestHandler
    original = AletheiaRequestHandler._send_payload
    dropped = []
    def lose_first_receipt(handler, status, payload):
        if handler.command == "POST" and status == 200 and handler.path.endswith("/promote") and not dropped:
            dropped.append(payload["data"])
            handler.close_connection = True
            return
        return original(handler, status, payload)
    monkeypatch.setattr(AletheiaRequestHandler, "_send_payload", lose_first_receipt)
    with local_service(tmp_path) as (service, url, tokens):
        item = candidate(service.memory, "Uncertain transport")
        revision = inspect(url, tokens["reviewer"], item.id)["revision"]
        with pytest.raises(RemoteDisconnected):
            decide(url, tokens["reviewer"], item.id, revision)
        replay = decide(url, tokens["reviewer"], item.id, revision)
        assert replay["status"] == 200 and replay["body"]["data"] == dropped[0]
        assert service.memory.store.connection.execute("SELECT count(*) FROM extraction_decisions WHERE candidate_id=? AND decision='promote'", (item.id,)).fetchone()[0] == 1


def test_async_sdk_review_uses_same_guarded_workflow(tmp_path, monkeypatch):
    import asyncio
    import aletheia.version as versions
    from aletheia.client import AsyncAletheiaClient
    monkeypatch.setattr(versions, "SUPPORTED_PROFILES", ("memory-read-v1", "memory-review-v1"))
    with local_service(tmp_path) as (service, url, tokens):
        item = candidate(service.memory, "Async SDK")
        async def workflow():
            client = AsyncAletheiaClient(url, tokens["reviewer"])
            detail = await client.get_candidate_for_review(item.id)
            assert (await client.list_candidates_for_review(namespace=NAMESPACE))[0]["id"] == item.id
            return await client.review_candidate(item.id, action="reject", reason="Explicit asynchronous refusal",
                expected_revision=detail["revision"], idempotency_key="async-refusal")
        assert asyncio.run(workflow())["action"] == "reject"
