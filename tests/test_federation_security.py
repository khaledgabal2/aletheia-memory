"""Behavioral regressions for the September 2026 federation audit.

All identities, signed packages, tokens, and databases are synthetic. No model
or network service is needed. Rejection tests inspect persisted state as well
as the exception, so failing after a partial import is not considered safe.
"""

from __future__ import annotations

import json
from contextlib import closing
from datetime import timedelta
from zipfile import ZipFile

import pytest

from aletheia import Memory
from aletheia.core import federation
from aletheia.core.errors import ValidationError
from aletheia.core.time import utc_now
from aletheia.models import ServiceConfig
from aletheia.service.auth import AuthService
from aletheia.service.http import AletheiaService


NAMESPACE = "audit/federation"
CLAIM_MARKER = "synthetic-shared-claim"
SOURCE_MARKER = "synthetic-source-only-content"


@pytest.fixture
def pair(tmp_path):
    left = Memory.open(str(tmp_path / "left.db"), namespace=NAMESPACE)
    right = Memory.open(str(tmp_path / "right.db"), namespace=NAMESPACE)
    try:
        left.create_federation_identity(display_name="Sender", protected=False)
        right.create_federation_identity(display_name="Receiver", protected=False)
        recipient = left.add_peer(peer_identity=right.export_federation_identity(), reason="test pairing")
        sender = right.add_peer(peer_identity=left.export_federation_identity(), reason="test pairing")
        event = left.write_event(namespace=NAMESPACE, source_type="test", content=SOURCE_MARKER, privacy_level="public")
        left.write_claim(namespace=NAMESPACE, memory_type="project", subject="project", predicate="state",
                         object=CLAIM_MARKER, evidence_ids=[event.id])
        yield left, right, recipient, sender
    finally:
        left.close()
        right.close()


def export(left, recipient, tmp_path, *, encrypt=False, **overrides):
    options = dict(name="audit-share", namespace=NAMESPACE, recipient_peer_ids=[recipient.id],
                   permissions=["read_claims", "read_evidence"], privacy_ceiling="public", reason="test sharing")
    options.update(overrides)
    share = left.create_share_grant(**options)
    path = tmp_path / f"{share.id}.aletsync"
    left.export_share_bundle(share_id=share.id, output_path=str(path), encrypt=encrypt)
    return share, path


def snapshot(memory):
    return list(memory.store.connection.iterdump())


def rewrite_signed_bundle(left, right, path, mutate):
    """A malicious sender can sign arbitrary payloads with its own key."""
    manifest, payload = federation._read_bundle(right, str(path))
    mutate(manifest, payload)
    federation._write_bundle(str(path), manifest=manifest, payload=payload, encrypt=False,
                             signer=left.active_federation_identity(), recipients=[])


@pytest.mark.parametrize("protected", [False, True])
@pytest.mark.parametrize("encrypted", [False, True])
def test_bundle_contains_only_public_identity_material(pair, tmp_path, monkeypatch, protected, encrypted):
    left, right, recipient, _ = pair
    monkeypatch.setenv("ALETHEIA_FEDERATION_KEY", "synthetic-test-protection-key")
    identity = left.active_federation_identity()
    metadata = {**identity.metadata, "operator_note": "private-operator-metadata", "protected_private_key": protected}
    metadata["private_key_ref"] = federation._private_key_ref(federation._private_key_doc(identity), protected=protected)
    left.store.connection.execute("UPDATE federation_identities SET metadata_json = ? WHERE id = ?",
                                  (json.dumps(metadata), identity.id))
    identity = left.active_federation_identity()
    _, path = export(left, recipient, tmp_path, encrypt=encrypted)
    _, payload = federation._read_bundle(right, str(path))
    with ZipFile(path) as archive:
        serialized = b"\n".join(archive.read(name) for name in archive.namelist()) + json.dumps(payload).encode()
    assert identity.metadata["private_key_ref"].encode() not in serialized
    assert b"private_key_ref" not in serialized
    assert b"private-operator-metadata" not in serialized
    assert payload["peer_identity"] == payload["origin_identity"] == left.export_federation_identity()
    # Export still signs a valid package and legitimate recipients can import it.
    right.import_share_bundle(input_path=str(path))
    assert right.list_candidates(NAMESPACE)[0].object == CLAIM_MARKER


@pytest.mark.parametrize("trust_policy", ["candidate_only", "trusted_device"])
@pytest.mark.parametrize("dry_run", [False, True])
def test_import_rejects_impersonation_of_pinned_peer(pair, tmp_path, trust_policy, dry_run):
    left, right, recipient, _ = pair
    with closing(Memory.open(":memory:", namespace=NAMESPACE)) as trusted:
        trusted.create_federation_identity(display_name="Pinned device", protected=False)
        pinned = right.add_peer(peer_identity=trusted.export_federation_identity(), reason="test pinned identity")
    right.trust_peer(pinned.id, trust_status="trusted_device", reason="test trust")
    left.store.connection.execute("UPDATE federation_identities SET instance_id = ?", (pinned.peer_instance_id,))
    _, path = export(left, recipient, tmp_path)
    before = snapshot(right)
    with pytest.raises(ValidationError, match="key|identity"):
        right.import_share_bundle(input_path=str(path), trust_policy=trust_policy, dry_run=dry_run)
    assert snapshot(right) == before
    assert right.get_peer(pinned.id).public_key == pinned.public_key


@pytest.mark.parametrize("field", ["public_key", "instance_id", "key_fingerprint"])
def test_payload_identity_must_match_verified_signer(pair, tmp_path, field):
    left, right, recipient, _ = pair
    _, path = export(left, recipient, tmp_path)
    other = right.export_federation_identity()
    rewrite_signed_bundle(left, right, path, lambda _m, p: p["peer_identity"].update({field: other[field]}))
    before = snapshot(right)
    with pytest.raises(ValidationError, match="identity|key|fingerprint"):
        right.import_share_bundle(input_path=str(path))
    assert snapshot(right) == before


@pytest.mark.parametrize("peer_status", ["trusted_device", "trusted_team"])
@pytest.mark.parametrize("policy", ["candidate_only", "manual_review", "remote_claim_only"])
def test_explicit_review_policy_is_an_upper_bound(pair, tmp_path, peer_status, policy):
    left, right, recipient, sender = pair
    right.trust_peer(sender.id, trust_status=peer_status, reason="test legitimate trusted sender")
    _, path = export(left, recipient, tmp_path)
    run = right.import_share_bundle(input_path=str(path), trust_policy=policy)
    assert run.status == "completed"
    assert right.list_claims(namespace=NAMESPACE) == []
    candidates = right.list_candidates(NAMESPACE)
    assert len(candidates) == 1
    assert candidates[0].object == CLAIM_MARKER
    assert candidates[0].candidate_status == "pending_review"


@pytest.mark.parametrize("policy", ["invalid_policy", "reject_by_default"])
def test_rejected_import_policy_makes_no_changes(pair, tmp_path, policy):
    left, right, recipient, _ = pair
    _, path = export(left, recipient, tmp_path)
    before = snapshot(right)
    with pytest.raises(ValidationError, match="policy"):
        right.import_share_bundle(input_path=str(path), trust_policy=policy)
    assert snapshot(right) == before


def test_project_import_policy_limits_active_types_and_never_imports_core(pair, tmp_path):
    left, right, recipient, sender = pair
    right.trust_peer(sender.id, trust_status="trusted_team", reason="test legitimate trusted team")
    for memory_type in ("project", "fact"):
        left.remember(namespace=NAMESPACE, memory_type=memory_type, subject=f"core-{memory_type}",
                      predicate="state", object=f"core-{memory_type}-value", status="core", privacy_level="public")
    _, path = export(left, recipient, tmp_path)
    right.import_share_bundle(input_path=str(path), trust_policy="active_for_project_state")
    claims = right.list_claims(namespace=NAMESPACE)
    assert {claim.object for claim in claims} == {CLAIM_MARKER, "core-project-value"}
    assert all(claim.status == "active" for claim in claims)
    assert [candidate.object for candidate in right.list_candidates(NAMESPACE)] == ["core-fact-value"]


def test_peer_explicitly_trusted_at_registration_can_import_active(pair, tmp_path):
    left, _, recipient, _ = pair
    _, path = export(left, recipient, tmp_path)
    with closing(Memory.open(":memory:", namespace=NAMESPACE)) as receiver:
        receiver.add_peer(peer_identity=left.export_federation_identity(), trust_status="trusted_device",
                          reason="operator-confirmed identity at registration")
        receiver.import_share_bundle(input_path=str(path), trust_policy="trusted_device")
        assert [claim.object for claim in receiver.list_claims(namespace=NAMESPACE)] == [CLAIM_MARKER]
        assert receiver.list_candidates(NAMESPACE) == []


def test_failed_import_rolls_back_evidence_and_federation_state(pair, tmp_path):
    left, right, recipient, _ = pair
    _, path = export(left, recipient, tmp_path)
    rewrite_signed_bundle(left, right, path, lambda _m, p: p["payloads"]["claims"][0].pop("object"))
    before = snapshot(right)
    with pytest.raises((ValidationError, KeyError)):
        right.import_share_bundle(input_path=str(path))
    assert snapshot(right) == before


@pytest.mark.parametrize("peer_status", ["revoked", "blocked"])
@pytest.mark.parametrize("trust_policy", ["candidate_only", "trusted_device"])
@pytest.mark.parametrize("dry_run", [False, True])
def test_inactive_peers_cannot_import_even_as_candidates(pair, tmp_path, peer_status, trust_policy, dry_run):
    left, right, recipient, sender = pair
    right.trust_peer(sender.id, trust_status="trusted_device", reason="test trust")
    _, path = export(left, recipient, tmp_path)
    if peer_status == "revoked":
        right.revoke_peer(sender.id, reason="test revocation", revoke_shares=False)
    else:
        right.trust_peer(sender.id, trust_status="blocked", reason="test block")
    before = snapshot(right)
    with pytest.raises(ValidationError, match="revoked|blocked"):
        right.import_share_bundle(input_path=str(path), trust_policy=trust_policy, dry_run=dry_run)
    assert snapshot(right) == before


@pytest.mark.parametrize("local_state", ["revoked", "expired", "collection_paused", "recipient_revoked"])
def test_old_bundle_cannot_bypass_local_grant_revocation(pair, tmp_path, local_state):
    left, right, recipient, _ = pair
    share, path = export(left, recipient, tmp_path)
    right.import_share_bundle(input_path=str(path))
    if local_state == "revoked":
        right.revoke_share_grant(share.id, reason="test revocation")
    elif local_state == "expired":
        right.store.connection.execute("UPDATE share_grants SET expires_at = ? WHERE id = ?",
                                       ((utc_now() - timedelta(seconds=1)).isoformat(), share.id))
    elif local_state == "collection_paused":
        right.store.connection.execute("UPDATE sync_collections SET status = 'paused' WHERE share_grant_id = ?", (share.id,))
    else:
        right.store.connection.execute("UPDATE share_recipients SET status = 'revoked' WHERE share_grant_id = ?", (share.id,))
    before = snapshot(right)
    with pytest.raises(ValidationError, match="revoked|expired|inactive"):
        right.import_share_bundle(input_path=str(path))
    assert snapshot(right) == before


@pytest.mark.parametrize("state", ["revoked", "expired", "collection_paused"])
def test_invalid_signed_grant_is_rejected_before_import(pair, tmp_path, state):
    left, right, recipient, _ = pair
    _, path = export(left, recipient, tmp_path)

    def mutate(_manifest, payload):
        if state == "expired":
            payload["share_grant"]["expires_at"] = (utc_now() - timedelta(seconds=1)).isoformat()
        elif state == "collection_paused":
            payload["collection"]["status"] = "paused"
        else:
            payload["share_grant"]["status"] = state

    rewrite_signed_bundle(left, right, path, mutate)
    before = snapshot(right)
    with pytest.raises(ValidationError, match="revoked|expired|inactive"):
        right.import_share_bundle(input_path=str(path))
    assert snapshot(right) == before


@pytest.mark.parametrize("peer_status", ["revoked", "blocked"])
def test_export_excludes_inactive_recipients_but_keeps_valid_recipient(pair, tmp_path, peer_status):
    left, right, recipient, _ = pair
    with closing(Memory.open(":memory:", namespace=NAMESPACE)) as other:
        other.create_federation_identity(display_name="Other recipient", protected=False)
        other_peer = left.add_peer(peer_identity=other.export_federation_identity(), reason="test other recipient")
        share, path = export(left, recipient, tmp_path, encrypt=True,
                             recipient_peer_ids=[recipient.id, other_peer.id])
        if peer_status == "revoked":
            left.revoke_peer(recipient.id, reason="test revocation", revoke_shares=False)
        else:
            left.trust_peer(recipient.id, trust_status="blocked", reason="test block")
        left.export_share_bundle(share_id=share.id, output_path=str(path), encrypt=True)
        with ZipFile(path) as archive:
            metadata = json.loads(archive.read("encryption_metadata.json"))
        assert [item["peer_id"] for item in metadata["recipients"]] == [other_peer.id]
        with pytest.raises(ValidationError):
            right.import_share_bundle(input_path=str(path))
        other.import_share_bundle(input_path=str(path))
        assert other.list_candidates(NAMESPACE)[0].object == CLAIM_MARKER


@pytest.mark.parametrize("grant_type,permissions,include_evidence,claim_count,evidence_count", [
    ("feedback_only", ["write_feedback"], True, 0, 0),
    ("feedback_only", ["read_claims", "read_evidence", "write_feedback"], True, 0, 0),
    ("read_write_candidate", ["write_candidate"], True, 0, 0),
    ("read_only", ["read_claims"], True, 1, 0),
    ("read_only", ["read"], True, 1, 0),
    ("read_only", ["read_evidence"], True, 0, 1),
    ("read_only", ["read_claims", "read_evidence"], False, 1, 0),
    ("read_only", ["read_claims", "read_evidence"], True, 1, 1),
])
def test_grant_permissions_bound_actual_bundle_contents(pair, tmp_path, grant_type, permissions,
                                                       include_evidence, claim_count, evidence_count):
    left, right, recipient, _ = pair
    _, path = export(left, recipient, tmp_path, grant_type=grant_type, permissions=permissions,
                     include_evidence=include_evidence)
    _, payload = federation._read_bundle(right, str(path))
    assert len(payload["payloads"]["claims"]) == claim_count
    assert len(payload["payloads"]["evidence"]) == evidence_count
    assert payload["item_counts"]["claims"] == claim_count
    assert payload["item_counts"]["evidence"] == evidence_count
    serialized = json.dumps(payload)
    assert (CLAIM_MARKER in serialized) == bool(claim_count)
    assert (SOURCE_MARKER in serialized) == bool(evidence_count)
    if not evidence_count:
        assert all(not claim["evidence_ids"] for claim in payload["payloads"]["claims"])
    right.import_share_bundle(input_path=str(path))
    assert len(right.list_candidates(NAMESPACE)) == claim_count


@pytest.mark.parametrize("permissions,expected_count", [
    (["write_feedback"], 0),
    (["read_claims"], 0),
    (["read_claims", "receive_redactions"], 1),
])
def test_redaction_notices_require_read_and_redaction_permissions(pair, tmp_path, permissions, expected_count):
    left, right, recipient, _ = pair
    claim = left.remember(namespace=NAMESPACE, memory_type="project", subject="retired", predicate="state",
                          object="retired value", privacy_level="public")
    left.forget(selector={"target_type": "claim", "target_id": claim.id}, mode="tombstone",
                reason="synthetic-redaction-reason", dry_run=False)
    _, path = export(left, recipient, tmp_path, permissions=permissions)
    _, payload = federation._read_bundle(right, str(path))
    assert len(payload["payloads"]["tombstones"]) == expected_count
    assert ("synthetic-redaction-reason" in json.dumps(payload)) == bool(expected_count)


@pytest.mark.parametrize("policy,allow_active,expected_status", [
    (None, False, 200),
    ("candidate_only", False, 200),
    ("trusted_device", False, 403),
    ("active_if_trusted", False, 403),
    ("active_for_project_state", False, 403),
    ("trusted_device", True, 200),
])
def test_http_import_cannot_escalate_candidate_permissions(pair, tmp_path, policy, allow_active, expected_status):
    left, right, recipient, sender = pair
    right.trust_peer(sender.id, trust_status="trusted_device", reason="test legitimate pinned sender")
    _, path = export(left, recipient, tmp_path)
    service = AletheiaService(right, ServiceConfig(db_path=str(tmp_path / "right.db"), auth_required=True))
    auth = AuthService(right)
    client = auth.create_client(name="federation regression", client_type="test")
    capabilities = ["memory:share", "memory:sync"] + (["memory:remote_active_write"] if allow_active else [])
    _, raw = auth.create_token(client_id=client.id, namespace_grants=[NAMESPACE], capabilities=capabilities)
    request = {"input_path": str(path)}
    if policy is not None:
        request["trust_policy"] = policy
    status, body = service.handle_http(method="POST", path="/v1/shares/import",
                                      headers={"Authorization": f"Bearer {raw}"},
                                      body=json.dumps(request).encode())
    assert status == expected_status, body
    claims = right.list_claims(namespace=NAMESPACE)
    assert len(claims) == int(allow_active)
    assert len(right.list_candidates(NAMESPACE)) == int(policy in {None, "candidate_only"})
