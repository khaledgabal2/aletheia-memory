from __future__ import annotations

import json
from datetime import timedelta
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import pytest

from aletheia import AletheiaClient, AsyncAletheiaClient, Memory
from aletheia.cli.main import main
from aletheia.core.errors import ValidationError
from aletheia.core.time import utc_now
from aletheia.models import ServiceConfig
from aletheia.service.auth import AuthService
from aletheia.service.http import AletheiaService, openapi_schema


NAMESPACE = "user/m10"


@pytest.fixture(autouse=True)
def _configured_federation_key(monkeypatch):
    monkeypatch.setenv("ALETHEIA_FEDERATION_KEY", "m10-test-federation-key")


def _json(payload: dict) -> bytes:
    return json.dumps(payload).encode("utf-8")


def _identity_pair(tmp_path: Path) -> tuple[Memory, Memory, dict, dict]:
    left = Memory.open(str(tmp_path / "left.db"), namespace=NAMESPACE)
    right = Memory.open(str(tmp_path / "right.db"), namespace=NAMESPACE)
    left_identity = left.create_federation_identity(display_name="Left Device")
    right_identity = right.create_federation_identity(display_name="Right Device")
    right_payload = right.export_federation_identity(output_path=str(tmp_path / "right.identity.json"))
    left_peer = left.add_peer(peer_identity=right_payload, reason="unit peer add")
    left.trust_peer(left_peer.id, trust_status="trusted_device", reason="unit trust device")
    left_payload = left.export_federation_identity(output_path=str(tmp_path / "left.identity.json"))
    right_peer = right.add_peer(peer_identity=left_payload, reason="unit peer add")
    return left, right, {"identity": left_identity, "peer": left_peer}, {"identity": right_identity, "peer": right_peer}


def _copy_bundle(source: Path, destination: Path, overrides: dict[str, bytes]) -> None:
    with ZipFile(source) as src, ZipFile(destination, "w", compression=ZIP_DEFLATED) as dst:
        for name in src.namelist():
            dst.writestr(name, overrides.get(name, src.read(name)))


def test_m10_migration_backfills_federation_contracts_without_implicit_identity(tmp_path):
    memory = Memory.open(str(tmp_path / "m10.db"), namespace=NAMESPACE)
    try:
        assert memory.health()["schema_version"] == "1.3.0"
        tables = {
            row["name"]
            for row in memory.store.connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
        }
        assert {
            "federation_identities",
            "peer_devices",
            "trust_domains",
            "share_grants",
            "share_recipients",
            "sync_collections",
            "sync_changesets",
            "sync_change_items",
            "sync_runs",
            "replication_cursors",
            "remote_memory_sources",
            "import_trust_policies",
            "sync_conflicts",
            "sync_conflict_resolutions",
            "federation_audit_events",
            "consent_records",
            "revocation_records",
            "sync_tombstones",
            "workspaces",
            "workspace_members",
            "agent_groups",
            "agent_group_members",
        } <= tables
        assert memory.list_federation_identities() == []
        contracts = {contract.name for contract in memory.list_public_contracts()}
        assert {"Federation protocol v1", "Aletheia sync bundle format", "Python SDK federation methods"} <= contracts
        assert {policy.id for policy in memory.list_import_trust_policies()} >= {"itp_candidate_only", "itp_trusted_device"}
        assert memory.federation_conformance()["status"] == "passed"
    finally:
        memory.close()


def test_nested_transaction_rolls_back_federation_identity(tmp_path):
    memory = Memory.open(str(tmp_path / "m10.db"), namespace=NAMESPACE)
    try:
        with pytest.raises(RuntimeError):
            with memory.store.transaction():
                memory.create_federation_identity(display_name="Rollback Device")
                raise RuntimeError("rollback outer transaction")

        assert memory.list_federation_identities() == []
    finally:
        memory.close()


def test_federation_identity_private_key_ref_is_encrypted_and_requires_key(monkeypatch, tmp_path):
    monkeypatch.delenv("ALETHEIA_FEDERATION_KEY", raising=False)
    monkeypatch.delenv("ALETHEIA_PROTECTED_KEY", raising=False)
    missing_key = Memory.open(str(tmp_path / "missing-key.db"), namespace=NAMESPACE)
    try:
        with pytest.raises(ValidationError, match="Protected federation key"):
            missing_key.create_federation_identity(display_name="Missing Key")
        unprotected = missing_key.create_federation_identity(display_name="Explicit Unprotected", protected=False)
        assert unprotected.metadata["private_key_ref"].startswith("local_v2_")
    finally:
        missing_key.close()

    monkeypatch.setenv("ALETHEIA_FEDERATION_KEY", "m10-test-federation-key")
    protected = Memory.open(str(tmp_path / "protected-key.db"), namespace=NAMESPACE)
    try:
        identity = protected.create_federation_identity(display_name="Protected Device")
        private_ref = identity.metadata["private_key_ref"]
        assert private_ref.startswith("local_enc_v2_")
        assert "private_key" not in private_ref
        protected.rotate_federation_key(reason="prove encrypted key material can be used", actor="pytest")
        rotated = protected.active_federation_identity()
        assert rotated.metadata["private_key_ref"].startswith("local_enc_v2_")
    finally:
        protected.close()


def test_identity_peer_share_and_encrypted_bundle_export(tmp_path):
    left, right, left_meta, _right_meta = _identity_pair(tmp_path)
    try:
        exported_identity = left.export_federation_identity()
        assert exported_identity["metadata"]["private_key_exported"] is False
        assert "private_key_ref" not in json.dumps(exported_identity)
        assert exported_identity["public_key"].startswith("fedpub_v2_")

        rotated = left.rotate_federation_key(reason="unit key rotation")
        assert rotated.key_fingerprint != exported_identity["key_fingerprint"]
        assert any(record.revocation_type == "key_revocation" for record in left.list_revocations())

        with pytest.raises(ValidationError):
            left.create_share_grant(
                name="secret-blocked",
                namespace=NAMESPACE,
                recipient_peer_ids=[left_meta["peer"].id],
                permissions=["read"],
                privacy_ceiling="secret",
                reason="secret must be explicit",
            )

        claim = left.remember(
            namespace=NAMESPACE,
            memory_type="project",
            subject="m10",
            predicate="exports",
            object="encrypted federation bundles",
            source_type="unit",
            status="active",
        )
        share = left.create_share_grant(
            name="project-share",
            namespace=NAMESPACE,
            recipient_peer_ids=[left_meta["peer"].id],
            permissions=["read", "sync_pull", "receive_redactions"],
            privacy_ceiling="personal",
            memory_types=["project"],
            statuses=["active"],
            reason="unit share",
        )
        assert left.list_share_recipients(share.id)[0].peer_id == left_meta["peer"].id

        bundle_path = tmp_path / "project.aletsync"
        run = left.export_share_bundle(share_id=share.id, output_path=str(bundle_path), encrypt=True)
        assert run.status == "completed"
        assert left.list_replication_cursors()
        with ZipFile(bundle_path) as archive:
            assert {"manifest.json", "encrypted_payload.bin", "encryption_metadata.json", "checksums.sha256", "signature.json"} <= set(archive.namelist())
            signature = json.loads(archive.read("signature.json").decode("utf-8"))
            metadata = json.loads(archive.read("encryption_metadata.json").decode("utf-8"))
            assert signature["algorithm"] == "ed25519"
            assert metadata["algorithm"] == "AES-256-GCM-X25519"
            raw_bundle = b"".join(archive.read(name) for name in archive.namelist())
        assert b"encrypted federation bundles" not in raw_bundle
        assert left.read_claim(claim.id).status == "active"
    finally:
        left.close()
        right.close()


def test_peer_identity_key_substitution_is_rejected(tmp_path):
    left, right, left_meta, _right_meta = _identity_pair(tmp_path)
    attacker = Memory.open(str(tmp_path / "attacker.db"), namespace=NAMESPACE)
    try:
        identity = right.export_federation_identity()
        attacker.create_federation_identity(display_name="Attacker Device")
        attacker_identity = attacker.export_federation_identity()
        tampered = {
            **identity,
            "public_key": attacker_identity["public_key"],
            "key_fingerprint": attacker_identity["key_fingerprint"],
        }
        with pytest.raises(ValidationError):
            left.add_peer(peer_identity=tampered, trust_status="trusted_device", reason="attempt key substitution")
        peer = left.get_peer(left_meta["peer"].id)
        assert peer.key_fingerprint == identity["key_fingerprint"]
        assert peer.trust_status == "trusted_device"
    finally:
        left.close()
        right.close()
        attacker.close()


def test_trusted_device_import_requires_pretrusted_peer(tmp_path):
    left = Memory.open(str(tmp_path / "trust-left.db"), namespace=NAMESPACE)
    right = Memory.open(str(tmp_path / "trust-right.db"), namespace=NAMESPACE)
    try:
        left.create_federation_identity(display_name="Trust Left")
        right.create_federation_identity(display_name="Trust Right")
        right_payload = right.export_federation_identity()
        right_peer = left.add_peer(peer_identity=right_payload, reason="unit peer add")
        left.trust_peer(right_peer.id, trust_status="trusted_device", reason="unit trust device")
        left.remember(
            namespace=NAMESPACE,
            memory_type="project",
            subject="trusted import",
            predicate="requires",
            object="pretrusted peer",
            source_type="unit",
            status="active",
        )
        share = left.create_share_grant(
            name="pretrusted-share",
            namespace=NAMESPACE,
            recipient_peer_ids=[right_peer.id],
            permissions=["read", "sync_pull"],
            privacy_ceiling="personal",
            memory_types=["project"],
            statuses=["active"],
            reason="pretrusted import share",
        )
        bundle = tmp_path / "pretrusted.aletsync"
        left.export_share_bundle(share_id=share.id, output_path=str(bundle), encrypt=True)

        with pytest.raises(ValidationError, match="previously added and trusted peer"):
            right.import_share_bundle(input_path=str(bundle), trust_policy="trusted_device")

        left_payload = left.export_federation_identity()
        left_peer = right.add_peer(peer_identity=left_payload, reason="add but do not trust")
        with pytest.raises(ValidationError, match="previously trusted peer"):
            right.import_share_bundle(input_path=str(bundle), trust_policy="trusted_device")

        right.trust_peer(left_peer.id, trust_status="trusted_device", reason="operator-confirmed fingerprint")
        run = right.import_share_bundle(input_path=str(bundle), trust_policy="trusted_device")
        assert run.status == "completed"
    finally:
        left.close()
        right.close()


def test_tampered_sync_bundle_payload_or_signature_is_rejected(tmp_path):
    left, right, left_meta, _right_meta = _identity_pair(tmp_path)
    try:
        left.remember(
            namespace=NAMESPACE,
            memory_type="project",
            subject="signed bundle",
            predicate="rejects",
            object="tampering",
            source_type="unit",
            status="active",
        )
        share = left.create_share_grant(
            name="signed-bundle-share",
            namespace=NAMESPACE,
            recipient_peer_ids=[left_meta["peer"].id],
            permissions=["read", "sync_pull"],
            privacy_ceiling="personal",
            memory_types=["project"],
            statuses=["active"],
            reason="signed bundle test",
        )
        bundle = tmp_path / "signed.aletsync"
        left.export_share_bundle(share_id=share.id, output_path=str(bundle), encrypt=True)

        tampered_payload = tmp_path / "tampered-payload.aletsync"
        _copy_bundle(bundle, tampered_payload, {"encrypted_payload.bin": b"tampered"})
        with pytest.raises(ValidationError):
            right.import_share_bundle(input_path=str(tampered_payload), trust_policy="candidate_only")

        tampered_signature = tmp_path / "tampered-signature.aletsync"
        _copy_bundle(
            bundle,
            tampered_signature,
            {
                "signature.json": json.dumps(
                    {
                        "algorithm": "ed25519",
                        "key_fingerprint": left.export_federation_identity()["key_fingerprint"],
                        "origin_instance_id": left.export_federation_identity()["instance_id"],
                        "signature": "AA",
                    },
                    sort_keys=True,
                ).encode("utf-8"),
            },
        )
        with pytest.raises(ValidationError):
            right.import_share_bundle(input_path=str(tampered_signature), trust_policy="candidate_only")
    finally:
        left.close()
        right.close()


def test_import_share_bundle_dry_run_does_not_mutate_peer_or_sync_state(tmp_path):
    left = Memory.open(str(tmp_path / "dry-left.db"), namespace=NAMESPACE)
    right = Memory.open(str(tmp_path / "dry-right.db"), namespace=NAMESPACE)
    try:
        left.create_federation_identity(display_name="Dry Left")
        right.create_federation_identity(display_name="Dry Right")
        right_payload = right.export_federation_identity()
        right_peer = left.add_peer(peer_identity=right_payload, reason="unit peer add")
        left.trust_peer(right_peer.id, trust_status="trusted_device", reason="unit trust device")
        left.remember(
            namespace=NAMESPACE,
            memory_type="project",
            subject="dry-run",
            predicate="stays",
            object="read only",
            source_type="unit",
            status="active",
        )
        share = left.create_share_grant(
            name="dry-run-share",
            namespace=NAMESPACE,
            recipient_peer_ids=[right_peer.id],
            permissions=["read", "sync_pull"],
            privacy_ceiling="personal",
            memory_types=["project"],
            statuses=["active"],
            reason="dry run share",
        )
        bundle = tmp_path / "dry-run.aletsync"
        left.export_share_bundle(share_id=share.id, output_path=str(bundle), encrypt=True)

        assert right.list_peers() == []
        assert right.list_sync_runs() == []
        run = right.import_share_bundle(input_path=str(bundle), trust_policy="trusted_device", dry_run=True)
        assert run.status == "planned"
        assert run.warnings == ["dry_run_no_mutation"]
        assert right.list_peers() == []
        assert right.list_sync_runs() == []
        assert right.list_candidates(NAMESPACE) == []
    finally:
        left.close()
        right.close()


def test_expired_share_grants_cannot_export_or_sync(tmp_path):
    left, right, left_meta, _right_meta = _identity_pair(tmp_path)
    try:
        left.remember(
            namespace=NAMESPACE,
            memory_type="project",
            subject="expired",
            predicate="share",
            object="blocked",
            source_type="unit",
            status="active",
        )
        share = left.create_share_grant(
            name="expired-share",
            namespace=NAMESPACE,
            recipient_peer_ids=[left_meta["peer"].id],
            permissions=["read", "sync_pull"],
            privacy_ceiling="personal",
            memory_types=["project"],
            statuses=["active"],
            expires_at=(utc_now() - timedelta(minutes=1)).isoformat(),
            reason="expired share",
        )
        with pytest.raises(ValidationError):
            left.export_share_bundle(share_id=share.id, output_path=str(tmp_path / "expired.aletsync"), encrypt=True)
        assert left.get_share_grant(share.id).status == "expired"
        collection = left.get_sync_collection(share.id)
        with pytest.raises(ValidationError):
            left.sync(collection_id=collection.id, output_path=str(tmp_path / "expired-sync.aletsync"))
    finally:
        left.close()
        right.close()


def test_import_is_candidate_first_conflicts_and_tombstones_are_governed(tmp_path):
    left, right, left_meta, _right_meta = _identity_pair(tmp_path)
    try:
        original = left.remember(
            namespace=NAMESPACE,
            memory_type="project",
            subject="sync",
            predicate="mode",
            object="candidate first",
            source_type="unit",
            status="active",
        )
        share = left.create_share_grant(
            name="sync-share",
            namespace=NAMESPACE,
            recipient_peer_ids=[left_meta["peer"].id],
            permissions=["read", "sync_pull", "receive_redactions"],
            privacy_ceiling="personal",
            memory_types=["project"],
            statuses=["active"],
            reason="unit sync",
        )
        first_bundle = tmp_path / "first.aletsync"
        left.export_share_bundle(share_id=share.id, output_path=str(first_bundle), encrypt=True)
        first_import = right.import_share_bundle(input_path=str(first_bundle), trust_policy="candidate_only")
        assert first_import.status == "completed"
        assert len(right.list_candidates(NAMESPACE)) == 1
        assert len(right.list_remote_sources()) >= 2

        right.remember(
            namespace=NAMESPACE,
            memory_type="project",
            subject="sync",
            predicate="mode",
            object="local active value",
            source_type="unit",
            status="active",
        )
        second_import = right.import_share_bundle(input_path=str(first_bundle), trust_policy="candidate_only")
        assert second_import.status == "completed_with_conflicts"
        conflicts = right.list_sync_conflicts(status="unresolved")
        assert conflicts and conflicts[0].conflict_type == "claim_value_conflict"
        resolution = right.resolve_sync_conflict(conflicts[0].id, strategy="keep_local", reason="unit conflict resolution")
        assert resolution.strategy == "keep_local"

        left.forget(
            selector={"target_type": "claim", "target_id": original.id},
            mode="tombstone",
            reason="unit remote redaction",
            dry_run=False,
        )
        tombstone_bundle = tmp_path / "tombstone.aletsync"
        left.export_share_bundle(share_id=share.id, output_path=str(tombstone_bundle), encrypt=True)
        redaction_import = right.import_share_bundle(input_path=str(tombstone_bundle), trust_policy="candidate_only")
        assert redaction_import.redaction_count >= 1
        assert right.list_sync_tombstones()
        assert any(event.content == "[REDACTED]" for event in right.list_events(namespace=NAMESPACE))
    finally:
        left.close()
        right.close()


def test_trusted_device_active_import_downgrades_remote_core_and_workspaces(tmp_path):
    left, right, left_meta, right_meta = _identity_pair(tmp_path)
    try:
        left.remember(
            namespace=NAMESPACE,
            memory_type="project",
            subject="trusted",
            predicate="imports",
            object="active project state",
            source_type="unit",
            status="core",
        )
        share = left.create_share_grant(
            name="trusted-share",
            namespace=NAMESPACE,
            recipient_peer_ids=[left_meta["peer"].id],
            permissions=["read", "sync_pull"],
            privacy_ceiling="personal",
            memory_types=["project"],
            statuses=["core"],
            reason="trusted sync",
        )
        bundle = tmp_path / "trusted.aletsync"
        left.export_share_bundle(share_id=share.id, output_path=str(bundle), encrypt=True)
        right.trust_peer(right_meta["peer"].id, trust_status="trusted_device", reason="unit trust device")
        run = right.import_share_bundle(input_path=str(bundle), trust_policy="trusted_device")
        assert run.status == "completed"
        imported = right.list_claims(namespace=NAMESPACE)
        assert imported and imported[0].status == "active"

        workspace = left.create_workspace(namespace=NAMESPACE, name="M10 Workspace")
        member = left.add_workspace_member(workspace.id, member_type="agent", member_id="agent-1", role="agent")
        assert member.role == "agent"
        assert left.workspace_role_allows("owner", "share")
        group = left.create_agent_group(namespace=NAMESPACE, name="M10 Agents", default_capabilities=["memory:read", "memory:sync"])
        left.add_agent_group_member(group.id, agent_id="agent-1", role="agent")
        assert left.agent_group_allows(group.id, "memory:sync")
    finally:
        left.close()
        right.close()


def test_m10_http_cli_openapi_and_sdk_surfaces(tmp_path, capsys):
    db_path = str(tmp_path / "service.db")
    memory = Memory.open(db_path, namespace=NAMESPACE)
    service = AletheiaService(memory, ServiceConfig(db_path=db_path, auto_migrate=True, auth_required=True, console_enabled=True))
    auth = AuthService(memory)
    client = auth.create_client(name="m10-admin", client_type="admin")
    _token, raw = auth.create_token(client_id=client.id, namespace_grants=["*"], capabilities=["memory:admin"], privacy_ceiling="secret")
    headers = {"Authorization": f"Bearer {raw}"}
    try:
        status, envelope = service.handle_http(method="GET", path="/v1/federation/status", headers=headers)
        assert status == 200
        assert envelope["data"]["schema_version"] == "1.3.0"

        status, envelope = service.handle_http(method="POST", path="/v1/federation/identity", headers=headers, body=_json({"display_name": "HTTP M10"}))
        assert status == 200
        assert envelope["data"]["display_name"] == "HTTP M10"

        status, envelope = service.handle_http(method="GET", path="/v1/peers/trust-domains", headers=headers)
        assert status == 200
        assert len(envelope["data"]) == 3

        schema = openapi_schema()
        assert schema["info"]["version"] == "1.3.0"
        for path in [
            "/v1/federation/status",
            "/v1/peers/{peer_id}/trust",
            "/v1/shares/{share_id}/export",
            "/v1/shares/import",
            "/v1/sync/run",
            "/v1/sync/conflicts/{conflict_id}/resolve",
            "/v1/workspaces/{workspace_id}/members",
            "/v1/revocations",
        ]:
            assert path in schema["paths"]
        assert "Federation" in service._console_static("/console")[1]["_raw_body"]
    finally:
        service.close()

    assert hasattr(AletheiaClient, "federation_status")
    assert hasattr(AletheiaClient, "sync_run")
    assert hasattr(AsyncAletheiaClient, "create_workspace")

    cli_db = tmp_path / "cli.db"
    assert main(["init", "--db", str(cli_db)]) == 0
    assert main(["federation", "init", "--db", str(cli_db), "--display-name", "CLI M10"]) == 0
    assert "CLI M10" in capsys.readouterr().out
    assert main(["federation-conformance", "run", "--db", str(cli_db)]) == 0
    assert '"status": "passed"' in capsys.readouterr().out
