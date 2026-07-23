#!/usr/bin/env python3
"""Run live M10 federated-memory scorecard checks."""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from aletheia import AletheiaClient, AsyncAletheiaClient, Memory
from aletheia.cli.main import main as cli_main
from aletheia.models import ServiceConfig
from aletheia.service.auth import AuthService
from aletheia.service.http import AletheiaService, openapi_schema


NAMESPACE = "live/m10"


def run_cli(argv: list[str]) -> str:
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        status = cli_main(argv)
    assert status == 0
    return buffer.getvalue()


def json_body(payload: dict) -> bytes:
    return json.dumps(payload).encode("utf-8")


@dataclass
class ScoreCase:
    category: str
    name: str
    contract_measure: str
    fn: Callable[[], str]


class M10LiveScorecard:
    def __init__(self, base_dir: Path, db_path: Path):
        self.base_dir = base_dir
        self.db_path = db_path
        self.memory = Memory.open(str(self.db_path), namespace=NAMESPACE)
        self._service: AletheiaService | None = None
        self._token: str | None = None

    def close(self) -> None:
        if self._service:
            self._service.close()
        else:
            self.memory.close()

    def cases(self) -> list[ScoreCase]:
        return [
            ScoreCase("29.1 Identity", "Local identity is explicit and private-key safe", "No implicit identity, export excludes private keys, rotation records revocation.", self.case_identity),
            ScoreCase("29.2 Peers", "Peer add, trust, revoke, and audit", "Peers are unknown by default, trust requires reason, revocation blocks future sharing and warns about remote erasure limits.", self.case_peers),
            ScoreCase("29.3 Shares", "Scoped grants, consent, secret discipline", "Share grants are scoped by namespace/type/status/privacy and secret sharing is blocked unless explicit.", self.case_shares),
            ScoreCase("29.4 Sync", "Encrypted file-bundle sync and provenance", "Encrypted .aletsync bundles contain no plaintext, import preserves remote provenance and cursors.", self.case_sync_bundle),
            ScoreCase("29.5 Trust", "Candidate-first and trusted-device import policy", "Unknown imports become candidates; trusted-device active imports never promote remote core to local core.", self.case_trust_imports),
            ScoreCase("29.6 Conflicts", "Conflict detection and resolution", "Conflicting remote claims create sync conflicts and review tasks and require explicit resolution.", self.case_conflicts),
            ScoreCase("29.7 Redaction", "Tombstones and revocation propagation", "Remote tombstones propagate redaction/rejection locally and revocation propagation is recorded.", self.case_redaction_revocation),
            ScoreCase("29.8 Workspaces", "Workspace and agent-group governance", "Workspace roles and agent group capabilities gate shared memory access.", self.case_workspaces),
            ScoreCase("29.9 Interfaces", "Console/API/CLI/SDK access", "M10 functionality is reachable through HTTP, OpenAPI, CLI, console, sync SDK, and async SDK surfaces.", self.case_interfaces),
            ScoreCase("29.10 Completeness", "Migration and M0-M9 regression smoke", "M10 tables, contracts, conformance, and basic local recall continue to work on schema 1.3.0.", self.case_definition_complete),
        ]

    def run(self) -> int:
        print("Aletheia M10 Federated Memory Live Scorecard")
        print(f"workspace: {self.base_dir}")
        print(f"database: {self.db_path}")
        passed = 0
        results: list[dict] = []
        for index, case in enumerate(self.cases(), start=1):
            try:
                detail = case.fn()
                status = "PASS"
                passed += 1
            except Exception as exc:  # noqa: BLE001 - live scorecard records failures.
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

    def pair(self, label: str) -> tuple[Memory, Memory, str]:
        left = Memory.open(str(self.base_dir / f"{label}_left.db"), namespace=NAMESPACE)
        right = Memory.open(str(self.base_dir / f"{label}_right.db"), namespace=NAMESPACE)
        left.create_federation_identity(display_name=f"{label} left")
        right.create_federation_identity(display_name=f"{label} right")
        right_identity = right.export_federation_identity(output_path=str(self.base_dir / f"{label}_right.identity.json"))
        left_peer = left.add_peer(peer_identity=right_identity, reason=f"{label} add right")
        left.trust_peer(left_peer.id, trust_status="trusted_device", reason=f"{label} trust right")
        left_identity = left.export_federation_identity(output_path=str(self.base_dir / f"{label}_left.identity.json"))
        right.add_peer(peer_identity=left_identity, reason=f"{label} add left")
        return left, right, left_peer.id

    def service(self) -> tuple[AletheiaService, str]:
        if self._service and self._token:
            return self._service, self._token
        if not self.memory.list_federation_identities():
            self.memory.create_federation_identity(display_name="live M10 service")
        self._service = AletheiaService(
            self.memory,
            ServiceConfig(db_path=str(self.db_path), auto_migrate=True, auth_required=True, console_enabled=True),
        )
        auth = AuthService(self.memory)
        client = auth.create_client(name="live-m10-admin", client_type="admin")
        _token, raw = auth.create_token(
            client_id=client.id,
            namespace_grants=["*"],
            capabilities=["memory:admin"],
            privacy_ceiling="secret",
        )
        self._token = raw
        return self._service, raw

    def request(self, method: str, path: str, payload: dict | None = None) -> dict:
        service, token = self.service()
        status, envelope = service.handle_http(
            method=method,
            path=path,
            headers={"Authorization": f"Bearer {token}", "X-Request-ID": "req_live_m10"},
            body=json_body(payload or {}) if payload is not None else b"",
        )
        assert status == 200, envelope
        return envelope["data"]

    def case_identity(self) -> str:
        memory = Memory.open(str(self.base_dir / "identity.db"), namespace=NAMESPACE)
        try:
            assert memory.federation_conformance()["no_auto_identity"] is True
            identity = memory.create_federation_identity(display_name="identity live")
            exported = memory.export_federation_identity()
            assert exported["key_fingerprint"] == identity.key_fingerprint
            assert "private_key_ref" not in json.dumps(exported)
            rotated = memory.rotate_federation_key(reason="live key rotation")
            assert rotated.key_fingerprint != identity.key_fingerprint
            assert any(record.revocation_type == "key_revocation" for record in memory.list_revocations())
            return f"identity={identity.id}, rotated={rotated.key_fingerprint[:8]}"
        finally:
            memory.close()

    def case_peers(self) -> str:
        left, right, peer_id = self.pair("peers")
        try:
            peer = left.get_peer(peer_id)
            assert peer.trust_status == "trusted_device"
            record = left.revoke_peer(peer_id, reason="live peer revoke")
            assert record.revocation_type == "peer_revocation"
            assert "remote_erasure_limit" in record.metadata
            assert left.get_peer(peer_id).trust_status == "revoked"
            assert any(event.event_type == "peer.revoked" for event in left.list_federation_audit_events())
            return f"peer={peer_id}, revocation={record.id}"
        finally:
            left.close()
            right.close()

    def case_shares(self) -> str:
        left, right, peer_id = self.pair("shares")
        try:
            try:
                left.create_share_grant(
                    name="secret blocked",
                    namespace=NAMESPACE,
                    recipient_peer_ids=[peer_id],
                    permissions=["read"],
                    privacy_ceiling="secret",
                    reason="live secret block",
                )
                raise AssertionError("secret share should be blocked")
            except Exception as exc:
                assert "Secret sharing is blocked" in str(exc)
            share = left.create_share_grant(
                name="live scoped share",
                namespace=NAMESPACE,
                recipient_peer_ids=[peer_id],
                grant_type="read_only",
                permissions=["read", "sync_pull", "receive_redactions"],
                privacy_ceiling="personal",
                memory_types=["project"],
                statuses=["active"],
                reason="live scoped share",
            )
            assert share.candidate_write_allowed is False
            assert left.list_consent_records()
            return f"share={share.id}, recipients={len(left.list_share_recipients(share.id))}, consent={len(left.list_consent_records())}"
        finally:
            left.close()
            right.close()

    def case_sync_bundle(self) -> str:
        left, right, peer_id = self.pair("sync")
        try:
            left.remember(namespace=NAMESPACE, memory_type="project", subject="m10", predicate="syncs", object="encrypted bundles", source_type="live")
            share = left.create_share_grant(
                name="live sync",
                namespace=NAMESPACE,
                recipient_peer_ids=[peer_id],
                permissions=["read", "sync_pull"],
                privacy_ceiling="personal",
                memory_types=["project"],
                statuses=["active"],
                reason="live sync",
            )
            bundle = self.base_dir / "live_sync.aletsync"
            export_run = left.export_share_bundle(share_id=share.id, output_path=str(bundle), encrypt=True)
            with ZipFile(bundle) as archive:
                raw = b"".join(archive.read(name) for name in archive.namelist())
                assert {"manifest.json", "encrypted_payload.bin", "encryption_metadata.json", "checksums.sha256", "signature.json"} <= set(archive.namelist())
            assert b"encrypted bundles" not in raw
            import_run = right.import_share_bundle(input_path=str(bundle), trust_policy="candidate_only")
            assert import_run.status == "completed"
            assert right.list_remote_sources()
            assert left.list_replication_cursors()
            return f"export={export_run.id}, import={import_run.id}, remote_sources={len(right.list_remote_sources())}"
        finally:
            left.close()
            right.close()

    def case_trust_imports(self) -> str:
        left, right, peer_id = self.pair("trust")
        try:
            left.remember(namespace=NAMESPACE, memory_type="project", subject="trusted", predicate="imports", object="remote core downgrade", source_type="live", status="core")
            share = left.create_share_grant(
                name="live trusted",
                namespace=NAMESPACE,
                recipient_peer_ids=[peer_id],
                permissions=["read", "sync_pull"],
                privacy_ceiling="personal",
                memory_types=["project"],
                statuses=["core"],
                reason="live trusted import",
            )
            bundle = self.base_dir / "live_trusted.aletsync"
            left.export_share_bundle(share_id=share.id, output_path=str(bundle), encrypt=True)
            candidate_run = right.import_share_bundle(input_path=str(bundle), trust_policy="candidate_only")
            assert candidate_run.status == "completed"
            assert right.list_candidates(NAMESPACE)
            trusted = Memory.open(str(self.base_dir / "trust_active_right.db"), namespace=NAMESPACE)
            try:
                trusted.create_federation_identity(display_name="trusted import target")
                left_identity = left.export_federation_identity()
                trusted.add_peer(peer_identity=left_identity, reason="trusted import source")
                active_run = trusted.import_share_bundle(input_path=str(bundle), trust_policy="trusted_device")
                assert active_run.status == "completed"
                claims = trusted.list_claims(namespace=NAMESPACE)
                assert claims and claims[0].status == "active"
            finally:
                trusted.close()
            return f"candidate_run={candidate_run.id}, active_import_downgraded=true"
        finally:
            left.close()
            right.close()

    def case_conflicts(self) -> str:
        left, right, peer_id = self.pair("conflict")
        try:
            left.remember(namespace=NAMESPACE, memory_type="project", subject="sync", predicate="truth", object="remote value", source_type="live")
            share = left.create_share_grant(
                name="live conflict",
                namespace=NAMESPACE,
                recipient_peer_ids=[peer_id],
                permissions=["read", "sync_pull"],
                privacy_ceiling="personal",
                memory_types=["project"],
                statuses=["active"],
                reason="live conflict",
            )
            bundle = self.base_dir / "live_conflict.aletsync"
            left.export_share_bundle(share_id=share.id, output_path=str(bundle), encrypt=True)
            right.remember(namespace=NAMESPACE, memory_type="project", subject="sync", predicate="truth", object="local value", source_type="live")
            run = right.import_share_bundle(input_path=str(bundle), trust_policy="candidate_only")
            assert run.status == "completed_with_conflicts"
            conflict = right.list_sync_conflicts(status="unresolved")[0]
            assert right.list_review_tasks(namespace=NAMESPACE, task_type="conflict_resolution")
            resolution = right.resolve_sync_conflict(conflict.id, strategy="keep_local", reason="live keep local")
            assert resolution.strategy == "keep_local"
            return f"run={run.id}, conflict={conflict.id}, resolution={resolution.id}"
        finally:
            left.close()
            right.close()

    def case_redaction_revocation(self) -> str:
        left, right, peer_id = self.pair("redaction")
        try:
            claim = left.remember(namespace=NAMESPACE, memory_type="project", subject="remote", predicate="redacts", object="old value", source_type="live")
            share = left.create_share_grant(
                name="live redaction",
                namespace=NAMESPACE,
                recipient_peer_ids=[peer_id],
                permissions=["read", "sync_pull", "receive_redactions"],
                privacy_ceiling="personal",
                memory_types=["project"],
                statuses=["active"],
                reason="live redaction",
            )
            bundle = self.base_dir / "live_redaction.aletsync"
            left.export_share_bundle(share_id=share.id, output_path=str(bundle), encrypt=True)
            right.import_share_bundle(input_path=str(bundle), trust_policy="candidate_only")
            left.forget(selector={"target_type": "claim", "target_id": claim.id}, mode="tombstone", reason="live redaction", dry_run=False)
            tombstone_bundle = self.base_dir / "live_redaction_tombstone.aletsync"
            left.export_share_bundle(share_id=share.id, output_path=str(tombstone_bundle), encrypt=True)
            run = right.import_share_bundle(input_path=str(tombstone_bundle), trust_policy="candidate_only")
            assert run.redaction_count >= 1
            assert right.list_sync_tombstones()
            assert any(event.content == "[REDACTED]" for event in right.list_events(namespace=NAMESPACE))
            revocation = left.revoke_share_grant(share.id, reason="live revoke share")
            propagated = left.propagate_revocations(peer_id=peer_id)
            assert propagated["status"] == "completed"
            assert revocation.metadata["remote_erasure_limit"]
            return f"tombstones={len(right.list_sync_tombstones())}, revocation={revocation.id}"
        finally:
            left.close()
            right.close()

    def case_workspaces(self) -> str:
        memory = Memory.open(str(self.base_dir / "workspace.db"), namespace=NAMESPACE)
        try:
            memory.create_federation_identity(display_name="workspace live")
            workspace = memory.create_workspace(namespace=NAMESPACE, name="Live Workspace")
            memory.add_workspace_member(workspace.id, member_type="agent", member_id="agent-live", role="agent")
            group = memory.create_agent_group(namespace=NAMESPACE, name="Live Agent Group", default_capabilities=["memory:read", "memory:sync"])
            member = memory.add_agent_group_member(group.id, agent_id="agent-live", role="agent")
            assert memory.workspace_role_allows("owner", "share")
            assert not memory.workspace_role_allows("reader", "share")
            assert memory.agent_group_allows(group.id, "memory:sync")
            return f"workspace={workspace.id}, group={group.id}, member={member.id}"
        finally:
            memory.close()

    def case_interfaces(self) -> str:
        status = self.request("GET", "/v1/federation/status")
        assert status["schema_version"] == "1.3.0"
        peers = self.request("GET", "/v1/peers/trust-domains")
        assert len(peers) == 3
        schema = openapi_schema()
        required_paths = {
            "/v1/federation/status",
            "/v1/peers/{peer_id}/trust",
            "/v1/shares/{share_id}/export",
            "/v1/shares/import",
            "/v1/sync/run",
            "/v1/sync/conflicts/{conflict_id}/resolve",
            "/v1/workspaces/{workspace_id}/members",
            "/v1/revocations",
        }
        assert required_paths <= set(schema["paths"])
        assert "Federation" in self.service()[0]._console_static("/console")[1]["_raw_body"]
        cli_db = self.base_dir / "live_cli.db"
        run_cli(["init", "--db", str(cli_db)])
        identity_output = run_cli(["federation", "init", "--db", str(cli_db), "--display-name", "live CLI"])
        conformance_output = run_cli(["federation-conformance", "run", "--db", str(cli_db)])
        assert "live CLI" in identity_output
        assert '"status": "passed"' in conformance_output
        assert hasattr(AletheiaClient, "federation_status")
        assert hasattr(AletheiaClient, "sync_run")
        assert hasattr(AsyncAletheiaClient, "create_workspace")
        return f"openapi_paths={len(schema['paths'])}, cli_ok=true, sdk_ok=true"

    def case_definition_complete(self) -> str:
        health = self.memory.health()
        assert health["schema_version"] == "1.3.0"
        conformance = self.memory.federation_conformance()
        assert conformance["status"] == "passed"
        for suite in ["federation-identity", "peer-trust", "share-bundle", "sync-protocol", "federation-conflict", "federation-redaction"]:
            run = self.memory.run_conformance(suite=suite)
            assert run.status == "passed"
        claim = self.memory.remember(namespace=NAMESPACE, memory_type="project", subject="m10", predicate="preserves", object="local recall", source_type="live")
        results = self.memory.retrieve(namespace=NAMESPACE, query="local recall", mode="hybrid")
        assert any(result.claim_id == claim.id for result in results)
        pack = self.memory.context_pack(NAMESPACE, "local recall", token_budget=800)
        assert any(item.claim_id == claim.id for item in pack.items())
        contracts = {contract.name for contract in self.memory.list_public_contracts()}
        assert {"Federation protocol v1", "Aletheia sync bundle format"} <= contracts
        return f"schema={health['schema_version']}, conformance={conformance['status']}, recall_claim={claim.id}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Aletheia M10 live scorecard.")
    parser.add_argument("--workdir", help="Directory for live test artifacts.")
    parser.add_argument("--db", help="Database path. Defaults to a temp database inside workdir.")
    parser.add_argument("--allow-existing", action="store_true", help="Allow using an existing database.")
    args = parser.parse_args()
    base_dir = Path(args.workdir) if args.workdir else Path(tempfile.mkdtemp(prefix="aletheia-m10-live-"))
    base_dir.mkdir(parents=True, exist_ok=True)
    db_path = Path(args.db) if args.db else base_dir / "m10_live.db"
    if db_path.exists() and not args.allow_existing:
        parser.error(f"Database already exists: {db_path}. Pass --allow-existing to reuse it.")
    scorecard = M10LiveScorecard(base_dir, db_path)
    try:
        return scorecard.run()
    finally:
        scorecard.close()


if __name__ == "__main__":
    raise SystemExit(main())
