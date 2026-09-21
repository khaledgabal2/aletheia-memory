"""Conflict decisions must change governed objects, or fail without a receipt."""
from contextlib import ExitStack, closing
import json

import pytest

from aletheia import Memory
from aletheia.core import federation
from aletheia.core.errors import ValidationError
from aletheia.models import ServiceConfig
from aletheia.service.http import AletheiaService

NS = "audit/resolution"


@pytest.fixture
def pair(tmp_path):
    with ExitStack() as stack:
        left, right = [stack.enter_context(closing(Memory.open(str(tmp_path / (name + ".db")), namespace=NS)))
                       for name in ("left", "right")]
        for memory in (left, right):
            memory.create_federation_identity(display_name="Synthetic peer", protected=False)
        peer = left.add_peer(peer_identity=right.export_federation_identity(), reason="fixture")
        right_peer = right.add_peer(peer_identity=left.export_federation_identity(), reason="fixture")
        right.trust_peer(right_peer.id, trust_status="trusted_device", reason="fixture")
        left.remember(namespace=NS, memory_type="project", subject="syncneedle", predicate="has", object="remote choice")
        grant = left.create_share_grant(name="synthetic share", namespace=NS, recipient_peer_ids=[peer.id],
            permissions=["read", "read_evidence", "sync_pull", "receive_redactions"], privacy_ceiling="personal", reason="fixture")
        bundle = tmp_path / "fixture.aletsync"
        left.export_share_bundle(share_id=grant.id, output_path=str(bundle), encrypt=True)
        yield left, right, bundle


def conflicting(pair, *, imported_first=False, active=False):
    _, memory, bundle = pair
    if imported_first:
        memory.import_share_bundle(input_path=str(bundle), trust_policy="trusted_device" if active else "candidate_only")
    local = memory.remember(namespace=NS, memory_type="project", subject="syncneedle", predicate="has", object="local choice")
    memory.import_share_bundle(input_path=str(bundle), trust_policy="candidate_only")
    conflict, = memory.list_sync_conflicts(status="unresolved")
    source, = [item for item in memory.list_remote_sources() if item.remote_object_type == "claim"]
    return memory, local, conflict, source


def snapshot(memory):
    tables = ("claims", "candidate_claims", "claim_relationships", "candidate_claim_links", "extraction_decisions",
              "remote_memory_sources", "sync_conflicts", "sync_conflict_resolutions", "federation_audit_events", "audit_log")
    return {table: [tuple(row) for row in memory.store.connection.execute("SELECT * FROM " + table)] for table in tables}


@pytest.mark.parametrize("imported_first", [False, True])
@pytest.mark.parametrize("strategy", ["keep_local", "reject_remote", "accept_remote_as_candidate", "accept_remote_active"])
def test_resolution_changes_objects_and_reimport_preserves_the_decision(pair, imported_first, strategy):
    memory, local, conflict, source = conflicting(pair, imported_first=imported_first)
    receipt = memory.resolve_sync_conflict(conflict.id, strategy=strategy, reason="synthetic review")
    candidate = memory.read_candidate(source.local_object_id)
    if strategy == "accept_remote_active":
        assert candidate.candidate_status == "promoted"
        assert memory.read_claim(local.id).status == "superseded"
        remote_id = receipt.metadata["remote_local_id"]
        assert memory.read_claim(remote_id).object == "remote choice"
        assert memory.read_claim(remote_id).evidence_ids == candidate.evidence_ids
        assert memory.store.connection.execute("SELECT 1 FROM claim_relationships WHERE source_claim_id = ? AND target_claim_id = ? AND relationship_type = 'supersedes'", (remote_id, local.id)).fetchone()
        assert [row.object for row in memory.retrieve(NS, "syncneedle")] == ["remote choice"]
    else:
        assert candidate.candidate_status == ("pending_review" if strategy == "accept_remote_as_candidate" else "rejected")
        assert memory.read_claim(local.id).status == "active"
        assert [row.object for row in memory.retrieve(NS, "syncneedle")] == ["local choice"]
    assert receipt.metadata["postconditions_verified"] is True
    assert memory.get_sync_conflict(conflict.id).status == "resolved"
    assert memory.get_sync_conflict(conflict.id).resolved_at
    before = snapshot(memory)
    with pytest.raises(ValidationError, match="already resolved"):
        memory.resolve_sync_conflict(conflict.id, strategy="accept_remote_active", reason="second review")
    assert snapshot(memory) == before
    memory.import_share_bundle(input_path=str(pair[2]), trust_policy="candidate_only")
    assert len(memory.list_candidates(NS)) == 1
    assert len(memory.list_sync_conflict_resolutions(conflict.id)) == 1
    assert memory.read_candidate(candidate.id).candidate_status == candidate.candidate_status


@pytest.mark.parametrize("strategy", ["keep_local", "reject_remote", "accept_remote_as_candidate", "accept_remote_active"])
def test_resolution_of_previously_active_remote_import(pair, strategy):
    memory, local, conflict, source = conflicting(pair, imported_first=True, active=True)
    receipt = memory.resolve_sync_conflict(conflict.id, strategy=strategy, reason="synthetic review")
    remote = memory.read_claim(source.local_object_id)
    if strategy == "accept_remote_active":
        assert remote.status == "active" and memory.read_claim(local.id).status == "superseded"
    elif strategy == "accept_remote_as_candidate":
        assert remote.status == "archived"
        candidate = memory.read_candidate(receipt.metadata["remote_local_id"])
        assert candidate.candidate_status == "pending_review" and candidate.evidence_ids == remote.evidence_ids
    else:
        assert remote.status == "rejected" and memory.read_claim(local.id).status == "active"
    assert receipt.metadata["postconditions_verified"]


def test_deferral_remains_unresolved_and_can_later_be_resolved(pair):
    memory, _, conflict, source = conflicting(pair)
    memory.resolve_sync_conflict(conflict.id, strategy="defer", reason="needs review")
    current = memory.get_sync_conflict(conflict.id)
    assert current.status == "deferred" and current.resolved_at is None
    assert memory.read_candidate(source.local_object_id).candidate_status == "pending_review"
    repeated = memory.import_share_bundle(input_path=str(pair[2]), trust_policy="candidate_only")
    assert repeated.status == "completed_with_conflicts"
    memory.resolve_sync_conflict(conflict.id, strategy="reject_remote", reason="review complete")
    assert memory.read_candidate(source.local_object_id).candidate_status == "rejected"


@pytest.mark.parametrize("strategy", ["merge_as_conflict_family", "scope_both", "time_scope", "manual_merge"])
def test_unsupported_resolution_has_no_effect_or_success_receipt(pair, strategy):
    memory, _, conflict, _ = conflicting(pair)
    before = snapshot(memory)
    with pytest.raises(ValidationError, match="not supported"):
        memory.resolve_sync_conflict(conflict.id, strategy=strategy, reason="fixture")
    assert snapshot(memory) == before


@pytest.mark.parametrize("fault", ["promotion", "audit"])
def test_resolution_is_atomic_when_any_effect_or_receipt_fails(pair, monkeypatch, fault):
    memory, _, conflict, _ = conflicting(pair)
    before = snapshot(memory)
    def fail(*args, **kwargs):
        raise RuntimeError("synthetic fault")
    if fault == "promotion":
        monkeypatch.setattr(memory, "supersede_claim", fail)
    else:
        monkeypatch.setattr(federation, "_write_federation_audit", fail)
    with pytest.raises(RuntimeError, match="synthetic fault"):
        memory.resolve_sync_conflict(conflict.id, strategy="accept_remote_active", reason="fixture")
    assert snapshot(memory) == before


@pytest.mark.parametrize("change", ["local", "remote", "mapping", "evidence_namespace", "redacted_evidence"])
def test_changed_or_deleted_sources_cannot_be_resolved_from_a_stale_snapshot(pair, change):
    memory, local, conflict, source = conflicting(pair)
    if change == "local":
        memory.store.connection.execute("UPDATE claims SET object = 'changed' WHERE id = ?", (local.id,))
    elif change == "remote":
        memory.review_candidate(source.local_object_id, decision="edit", reason="fixture", edits={"object": "changed"})
    elif change == "mapping":
        memory.store.connection.execute("DELETE FROM remote_memory_sources WHERE id = ?", (source.id,))
    else:
        event = memory.read_candidate(source.local_object_id).evidence_ids[0]
        if change == "evidence_namespace":
            memory.store.connection.execute("UPDATE evidence_events SET namespace = 'other' WHERE id = ?", (event,))
        else:
            memory.forget(selector={"target_type": "evidence", "target_id": event}, mode="tombstone", reason="fixture", dry_run=False)
    memory.store.connection.commit()
    before = snapshot(memory)
    with pytest.raises(ValidationError):
        memory.resolve_sync_conflict(conflict.id, strategy="accept_remote_active", reason="fixture")
    assert snapshot(memory) == before


@pytest.mark.parametrize("denial", ["review_capability", "active_capability", "source_privacy", "namespace", "allowed"])
def test_http_resolution_checks_effect_permissions_and_current_sources(pair, denial):
    memory, local, conflict, source = conflicting(pair)
    capabilities = ["memory:sync", "memory:review", "memory:write_active", "memory:remote_active_write"]
    if denial == "review_capability":
        capabilities.remove("memory:review")
    if denial == "active_capability":
        capabilities.remove("memory:write_active")
    if denial == "source_privacy":
        event = memory.read_candidate(source.local_object_id).evidence_ids[0]
        memory.store.connection.execute("UPDATE evidence_events SET privacy_level = 'secret' WHERE id = ?", (event,))
        memory.store.connection.commit()
    service = AletheiaService(memory, ServiceConfig(db_path=memory.store.path, rate_limit_enabled=False))
    client = service.auth.create_client(name="fixture", client_type="test")
    _, token = service.auth.create_token(client_id=client.id, capabilities=capabilities,
        namespace_grants=["other" if denial == "namespace" else NS], privacy_ceiling="personal")
    before = snapshot(memory)
    status, response = service.handle_http(method="POST", path=f"/v1/sync/conflicts/{conflict.id}/resolve",
        headers={"Authorization": f"Bearer {token}"}, body=json.dumps({"strategy": "accept_remote_active", "reason": "fixture"}).encode())
    assert status == (200 if denial == "allowed" else 403), response
    if denial != "allowed":
        assert snapshot(memory) == before
    else:
        assert memory.read_claim(local.id).status == "superseded"


def test_resolution_cannot_silently_decide_an_additional_conflict_participant(pair):
    memory, _, conflict, _ = conflicting(pair)
    memory.remember(namespace=NS, memory_type="project", subject="syncneedle", predicate="has", object="third choice")
    before = snapshot(memory)
    with pytest.raises(ValidationError, match="additional claims"):
        memory.resolve_sync_conflict(conflict.id, strategy="accept_remote_active", reason="fixture")
    assert snapshot(memory) == before
