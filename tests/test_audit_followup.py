"""Independent, synthetic acceptance checks for the audit remediation review.

Assertions express required behavior, including positive controls. No model
inference, production data, or external I/O.
"""
from contextlib import ExitStack, closing
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import threading

import pytest

from aletheia import Memory
from aletheia.core import federation
from aletheia.core.errors import ValidationError
from aletheia.models import ServiceConfig
from aletheia.retrieval.policy import DEFAULT_WEIGHTS
from aletheia.semantic import MockEmbeddingProvider
from aletheia.service.http import AletheiaDaemon, AletheiaService

NS = "review/tenant-a"
OTHER = "review/tenant-b"
MARKER = "REVIEW_ONLY_PRIVATE_CONTENT_6c3fb"


@pytest.fixture
def memory(tmp_path):
    with closing(Memory.open(str(tmp_path / "memory.db"), namespace=NS)) as item:
        yield item


def client(memory, *, namespace=NS, capabilities=("memory:read",), privacy="personal"):
    service = AletheiaService(memory, ServiceConfig(db_path=memory.store.path, rate_limit_enabled=False))
    principal = service.auth.create_client(name="independent synthetic review", client_type="test")
    token_row, token = service.auth.create_token(client_id=principal.id, namespace_grants=[namespace],
        capabilities=list(capabilities), privacy_ceiling=privacy)

    def call(method, path, payload=None, *, key=None):
        headers = {"Authorization": "Bearer " + token}
        if key:
            headers["Idempotency-Key"] = key
        return service.handle_http(method=method, path=path, headers=headers,
            body=json.dumps(payload).encode() if payload is not None else b"")
    call.service, call.token_id = service, token_row.id
    return call


def claim(memory, *, namespace=NS, value=MARKER, privacy="public", subject="reviewneedle", project_id=None):
    return memory.remember(namespace=namespace, memory_type="project", subject=subject,
        predicate="records", object=value, privacy_level=privacy, project_id=project_id)


@pytest.fixture
def pair(tmp_path):
    with ExitStack() as stack:
        left, right = [stack.enter_context(closing(Memory.open(str(tmp_path / (name + ".db")), namespace=NS)))
                       for name in ("sender", "receiver")]
        for memory in (left, right):
            memory.create_federation_identity(display_name="synthetic review", protected=False)
        recipient = left.add_peer(peer_identity=right.export_federation_identity(), reason="synthetic pairing")
        sender = right.add_peer(peer_identity=left.export_federation_identity(), reason="synthetic pairing")
        right.trust_peer(sender.id, trust_status="trusted_device", reason="synthetic approval")
        yield left, right, recipient


def export(pair, path, *, permissions, privacy="private"):
    left, right, recipient = pair
    share = left.create_share_grant(name="review share", namespace=NS, recipient_peer_ids=[recipient.id],
        permissions=permissions, privacy_ceiling=privacy, reason="synthetic review")
    left.export_share_bundle(share_id=share.id, output_path=str(path), encrypt=True)
    return share


@pytest.mark.parametrize("include_evidence", [False, True])
@pytest.mark.parametrize("policy", ["candidate_only", "trusted_device"])
def test_claims_only_federation_does_not_lower_private_claim_privacy(pair, tmp_path, policy, include_evidence):
    left, right, _ = pair
    original = claim(left, privacy="private")
    assert client(left)("GET", "/v1/claims/" + original.id)[0] == 403
    bundle = tmp_path / "claims-only.aletsync"
    export(pair, bundle, permissions=["read_claims"] + (["read_evidence"] if include_evidence else []))
    _, payload = federation._read_bundle(right, str(bundle))
    assert payload["payloads"]["claims"] and bool(payload["payloads"]["evidence"]) == include_evidence
    right.import_share_bundle(input_path=str(bundle), trust_policy=policy)
    if policy == "candidate_only":
        imported, = right.list_candidates(NS)
        route = "/v1/candidates/" + imported.id
        read = client(right, capabilities=["memory:read", "memory:review"])
    else:
        imported, = right.list_claims(namespace=NS)
        route = "/v1/claims/" + imported.id
        read = client(right)
    status, body = read("GET", route)
    assert status == 403, {"status": status, "source_privacy": [right.read_event(x).privacy_level for x in imported.evidence_ids], "leaked": MARKER in json.dumps(body)}


@pytest.mark.parametrize("read_claims", [False, True])
def test_evidence_only_share_propagates_its_source_redaction(pair, tmp_path, read_claims):
    left, right, _ = pair
    original = claim(left)
    bundle = tmp_path / "evidence-only.aletsync"
    share = export(pair, bundle, permissions=["read_evidence", "receive_redactions"] + (["read_claims"] if read_claims else []), privacy="public")
    right.import_share_bundle(input_path=str(bundle))
    imported, = right.list_events(namespace=NS)
    assert MARKER in imported.content
    left.redact(target_type="evidence", target_id=original.evidence_ids[0], reason="synthetic removal", dry_run=False)
    left.export_share_bundle(share_id=share.id, output_path=str(bundle), encrypt=True)
    right.import_share_bundle(input_path=str(bundle))
    assert MARKER not in right.read_event(imported.id).content


@pytest.mark.parametrize("change", ["privacy", "redaction", "unchanged"])
def test_llm_idempotency_replay_rechecks_source_access(memory, change):
    event = memory.write_event(namespace=NS, source_type="manual", content=MARKER, privacy_level="personal")
    call = client(memory, capabilities=["memory:review"])
    path = "/v1/llm/summarize-evidence"
    payload = {"namespace": NS, "evidence_ids": [event.id], "provider": "mock_llm"}
    status, body = call("POST", path, payload, key="review-summarize")
    assert status == 200 and MARKER in json.dumps(body)
    if change == "privacy":
        with memory.store.transaction():
            memory.store.connection.execute("UPDATE evidence_events SET privacy_level = 'secret' WHERE id = ?", (event.id,))
    elif change == "redaction":
        memory.redact(target_type="evidence", target_id=event.id, reason="synthetic removal", dry_run=False)
    if change == "unchanged":
        assert call("POST", path, payload, key="review-summarize") == (status, body)
        assert len(memory.list_llm_runs(namespace=NS)) == 1
        return
    assert call("POST", path, payload)[0] == 403  # The uncached route correctly denies access.
    status, body = call("POST", path, payload, key="review-summarize")
    assert status == 403 and MARKER not in json.dumps(body), {"status": status, "leaked": MARKER in json.dumps(body)}
    assert len(memory.list_llm_runs(namespace=NS)) == 1
    if change == "redaction":
        cached = memory.store.connection.execute("SELECT response_json, status, expires_at FROM idempotency_records").fetchone()
        assert cached["response_json"] is None and cached["status"] == "redacted" and cached["expires_at"] is None


def test_scoped_service_report_contains_only_authorized_tenant(memory):
    victim = claim(memory, namespace=OTHER, value="foreign operation")
    foreign = client(memory, namespace=OTHER)
    assert foreign("GET", "/v1/claims/" + victim.id + "?namespace=" + OTHER)[0] == 200
    own = client(memory)
    status, body = own("POST", "/v1/reports/export", {"namespace": NS, "report_type": "service_activity", "format": "json"})
    assert status == 200, body
    report = json.loads(Path(body["data"]["file_path"]).read_text())
    assert all(row["namespace"] == NS for row in report["service_requests"]), report


def test_scoped_metrics_do_not_return_another_tenants_request_paths(memory):
    victim = claim(memory, namespace=OTHER, value="foreign operation")
    foreign = client(memory, namespace=OTHER)
    assert foreign("GET", "/v1/claims/" + victim.id + "?namespace=" + OTHER)[0] == 200
    status, body = client(memory)("GET", "/v1/metrics/latest?namespace=" + NS)
    assert status == 200
    assert victim.id not in json.dumps(body), body


@pytest.mark.parametrize("route", ["ordinary", "console"])
@pytest.mark.parametrize("field", ["rejected_claim_ids", "superseded_claim_ids"])
def test_conflict_resolution_cannot_mutate_foreign_claims(memory, route, field):
    own = [memory.remember(namespace=NS, memory_type="preference", subject="user", predicate="prefers_editor", object=value)
           for value in ("vim", "emacs")]
    memory.detect_conflicts(namespace=NS)
    family = next(item for item in memory.list_conflict_families(namespace=NS) if set(item.claim_ids) == {x.id for x in own})
    victim = claim(memory, namespace=OTHER, value="foreign immutable claim")
    path = ("/v1/conflicts/" if route == "ordinary" else "/v1/console/actions/conflicts/") + family.id + "/resolve"
    call = client(memory, capabilities=["memory:review"])
    status, body = call("POST", path, {"strategy": "manual", "active_claim_id": own[0].id, field: [victim.id],
        "confirmation": "resolve conflict", "reason": "synthetic review"})
    assert status in {400, 403} and memory.read_claim(victim.id).status == "active", {"status": status, "victim_status": memory.read_claim(victim.id).status}
    assert memory.read_conflict_family(family.id).status == "unresolved"
    assert not memory.store.connection.execute("SELECT 1 FROM conflict_resolutions").fetchone()
    assert not memory.store.connection.execute("SELECT 1 FROM console_action_confirmations").fetchone()


def conflict_fixture(pair, tmp_path):
    left, right, _ = pair
    original = claim(left)
    local = claim(right, value="local harmless alternative")
    bundle = tmp_path / "conflict.aletsync"
    export(pair, bundle, permissions=["read_claims", "read_evidence", "receive_redactions"], privacy="public")
    right.import_share_bundle(input_path=str(bundle))
    conflict, = right.list_sync_conflicts(namespace=NS)
    source, = [x for x in right.list_remote_sources() if x.remote_object_type == "claim"]
    return right, conflict, source


@pytest.mark.parametrize("target", ["evidence", "claim"])
def test_redaction_removes_federation_conflict_content_snapshot(pair, tmp_path, target):
    right, conflict, source = conflict_fixture(pair, tmp_path)
    if target == "evidence":
        marker = MARKER
        event_id = right.read_candidate(source.local_object_id).evidence_ids[0]
        right.redact(target_type="evidence", target_id=event_id, reason="synthetic removal", dry_run=False)
        assert right.read_candidate(source.local_object_id).object == "[REDACTED]"
    else:
        marker = right.read_claim(conflict.local_object_id).object
        right.forget(selector={"target_type": "claim", "target_id": conflict.local_object_id},
            mode="hard_delete", reason="synthetic removal", dry_run=False, confirmation="forget memory")
        assert right.store.connection.execute("SELECT 1 FROM claims WHERE id = ?", (conflict.local_object_id,)).fetchone() is None
    call = client(right, capabilities=["memory:sync"])
    status, body = call("GET", "/v1/sync/conflicts?namespace=" + NS)
    assert status == 200
    assert marker not in json.dumps(body), body
    assert marker not in right.store.connection.execute("SELECT metadata_json FROM sync_conflicts WHERE id=?", (conflict.id,)).fetchone()[0]


def test_background_worker_provider_wait_does_not_block_health(tmp_path, monkeypatch):
    started, release = threading.Event(), threading.Event()
    original = MockEmbeddingProvider.embed_texts

    def delayed(self, *args, **kwargs):
        started.set()
        assert release.wait(10), "synthetic provider was not released"
        return original(self, *args, **kwargs)

    monkeypatch.setattr(MockEmbeddingProvider, "embed_texts", delayed)
    daemon = AletheiaDaemon(ServiceConfig(db_path=str(tmp_path / "daemon.db"), auto_migrate=True, rate_limit_enabled=False))
    try:
        claim(daemon.service.memory)
        job = daemon.service.memory.enqueue_job(namespace=NS, job_type="index_semantic", payload={})
        daemon._start_worker_loop()  # The production daemon worker, with no listening socket.
        assert started.wait(5)
        with ThreadPoolExecutor(max_workers=1) as pool:
            health_entered = threading.Event()
            def call_health():
                health_entered.set()
                return daemon.service.handle_http(method="GET", path="/v1/health", headers={})
            health = pool.submit(call_health)
            assert health_entered.wait(5)
            try:
                try:
                    response = health.result(timeout=0.5)
                    responsive = True
                except TimeoutError:
                    responsive = False
            finally:
                release.set()
            response = health.result(timeout=5)
            assert response[0] == 200
            daemon._worker_stop.set()
            daemon._worker_thread.join(timeout=5)
            assert not daemon._worker_thread.is_alive()
            assert daemon.service.memory.get_job(job.id).status == "completed"
            assert daemon.service.memory.get_job(job.id).attempts == 1
            assert responsive, "Health completed only after the background provider was released"
    finally:
        release.set()
        daemon.shutdown()


@pytest.mark.parametrize("mode", ["lexical", "hybrid", "semantic"])
def test_project_policy_considers_the_actual_project_before_bounded_reranking(memory, mode):
    values = [claim(memory, value="policyneedle", subject="source" + str(i)) for i in range(105)]
    # All IDs are normal public-API-generated IDs. Choose the last one so it
    # cannot accidentally enter the first 100 merely through the ID tie-break.
    target = max(values, key=lambda item: item.id)
    project = memory.create_project(NS, "review-project", title="policy review")
    memory.link_claim_to_project(namespace=NS, project_id=project.id, claim_id=target.id)
    if mode == "semantic":
        memory.index_semantic(NS, provider="mock")
    weights = {**dict.fromkeys(DEFAULT_WEIGHTS, 0.0), "project_relevance": 1.0}
    proposed = memory.propose_policy_update(NS, policy_type="ranking", target_policy_id="rpol_default",
        proposed_config={"weights": weights}, reason="synthetic review")
    memory.review_policy_proposal(proposed.id, decision="approve", reason="synthetic approval")
    memory.apply_policy_proposal(proposed.id, reason="synthetic activation", require_evaluation_pass=False)
    all_results = memory.retrieve(NS, "policyneedle", mode=mode, project_id=project.id, predicate="records", limit=105)
    assert all_results[0].claim_id == target.id and all_results[0].score == 1.0
    first = memory.retrieve(NS, "policyneedle", mode=mode, project_id=project.id, predicate="records", limit=1)
    assert first[0].claim_id == target.id, {"expected": target.id, "actual": first[0].claim_id, "actual_score": first[0].score}


def test_context_trace_inherits_active_budget_when_request_omits_override(memory):
    item = claim(memory, value="tracepolicyneedle is longer than one token")
    proposed = memory.propose_policy_update(NS, policy_type="context_pack", target_policy_id="cpol_default",
        proposed_config={"token_budget": 1}, reason="synthetic review")
    memory.review_policy_proposal(proposed.id, decision="approve", reason="synthetic approval")
    memory.apply_policy_proposal(proposed.id, reason="synthetic activation", require_evaluation_pass=False)
    call = client(memory, capabilities=["memory:read", "memory:context"])
    payload = {"namespace": NS, "query": "tracepolicyneedle", "retrieval_mode": "lexical"}
    status, ordinary = call("POST", "/v1/context-pack", payload)
    assert status == 200 and not ordinary["data"]["items"]
    status, trace = call("POST", "/v1/traces/context-pack", payload)
    assert status == 200
    assert trace["data"]["policy_version_id"] == ordinary["data"]["policy"]["context_policy_version_id"]
    included = [row for row in memory.list_trace_items(trace["data"]["id"]) if row.included]
    assert not included, {"configured_budget": 1, "trace_budget": trace["data"]["metadata"]["token_budget"], "included_ids": [row.target_id for row in included]}


@pytest.mark.parametrize("change", ["capability", "namespace", "ceiling"])
def test_cached_reply_uses_current_credential_grants(memory, change):
    event = memory.write_event(namespace=NS, source_type="manual", content=MARKER, privacy_level="personal")
    call = client(memory, capabilities=["memory:review"])
    payload = {"namespace": NS, "evidence_ids": [event.id], "provider": "mock_llm"}
    assert call("POST", "/v1/llm/summarize-evidence", payload, key="current-grants")[0] == 200
    db = memory.store.connection
    with memory.store.transaction():
        if change == "capability":
            db.execute("DELETE FROM capability_grants WHERE token_id=?", (call.token_id,))
        elif change == "namespace":
            db.execute("UPDATE namespace_access_grants SET namespace=? WHERE token_id=?", (OTHER, call.token_id))
        else:
            db.execute("UPDATE api_tokens SET privacy_ceiling='public' WHERE id=?", (call.token_id,))
    status, body = call("POST", "/v1/llm/summarize-evidence", payload, key="current-grants")
    assert status == 403 and MARKER not in json.dumps(body)
    assert len(memory.list_llm_runs(namespace=NS)) == 1


def test_unclassified_legacy_receipt_is_not_disclosed_or_reexecuted(memory):
    event = memory.write_event(namespace=NS, source_type="manual", content=MARKER)
    call = client(memory, capabilities=["memory:review"])
    payload = {"namespace": NS, "evidence_ids": [event.id]}
    assert call("POST", "/v1/llm/summarize-evidence", payload, key="legacy")[0] == 200
    row = memory.store.connection.execute("SELECT id,response_json FROM idempotency_records").fetchone()
    legacy = json.loads(row["response_json"])
    legacy.pop("_authorization", None)
    memory.store.connection.execute("UPDATE idempotency_records SET response_json=? WHERE id=?", (json.dumps(legacy), row["id"]))
    status, body = call("POST", "/v1/llm/summarize-evidence", payload, key="legacy")
    assert status == 403 and MARKER not in json.dumps(body)
    assert len(memory.list_llm_runs(namespace=NS)) == 1


@pytest.mark.parametrize("field", ["rejected_claim_ids", "superseded_claim_ids"])
@pytest.mark.parametrize("namespace", [NS, OTHER])
def test_embedded_conflict_resolution_rejects_nonmembers_atomically(memory, field, namespace):
    own = [memory.remember(namespace=NS, memory_type="preference", subject="user", predicate="prefers_editor", object=value)
           for value in ("vim", "emacs")]
    memory.detect_conflicts(namespace=NS)
    family = next(item for item in memory.list_conflict_families(namespace=NS) if set(item.claim_ids) == {x.id for x in own})
    victim = claim(memory, namespace=namespace)
    before = list(memory.store.connection.iterdump())
    with pytest.raises(ValidationError, match="belong"):
        memory.resolve_conflict(family.id, active_claim_id=own[0].id, **{field: [victim.id]})
    assert list(memory.store.connection.iterdump()) == before


def test_scoped_operational_aggregates_and_old_snapshots(memory):
    db = memory.store.connection
    for namespace, count, latency in [(NS, 2, 10), (OTHER, 110, 10000)]:
        db.executemany("""INSERT INTO service_request_log
            (id,request_id,namespace,method,path,status_code,duration_ms,log_mode,created_at)
            VALUES (?,?,?,'POST','/v1/retrieve',200,?,'off',?)""",
            [(namespace + str(i), namespace + str(i), namespace, latency,
              "2025-01-01" if namespace == NS else "2026-01-01") for i in range(count)])
        item = claim(memory, namespace=namespace)
        evaluation = memory.create_eval_set(namespace, name="scope test")
        memory.add_eval_case(evaluation.id, query="reviewneedle", expected_claim_ids=[item.id])
        run = memory.run_evaluation(namespace, eval_set_id=evaluation.id, retrieval_mode="lexical", context_pack=False)
        db.execute("UPDATE evaluation_metrics SET passed=? WHERE evaluation_run_id=?", (int(namespace == NS), run.id))
    old = memory.metrics_snapshot(namespace=NS)
    db.execute("UPDATE metric_snapshots SET metadata_json='{}',metrics_json=? WHERE id=?",
               (json.dumps({"service_requests_by_endpoint": {MARKER: 110}}), old.id))
    call = client(memory)
    assert call("GET", "/v1/metrics/snapshots?namespace=" + NS)[1]["data"] == []
    status, response = call("GET", "/v1/metrics/latest?namespace=" + NS)
    assert status == 200 and MARKER not in json.dumps(response)
    metrics = response["data"]["metrics"]
    assert metrics["service_requests_by_endpoint"]["/v1/retrieve"] == 2
    assert metrics["average_retrieval_latency"] == 10
    assert metrics["evaluation_pass_rate"] == 1
    own = memory._report_payload(namespace=NS, report_type="service_activity", filters={})
    assert own["service_requests"] and all(row["namespace"] == NS for row in own["service_requests"])
    assert any(row["path"] == "/v1/retrieve" for row in own["service_requests"])
    global_metrics = memory.metrics_snapshot().metrics
    assert global_metrics["service_requests_by_endpoint"]["/v1/retrieve"] == 112
    assert global_metrics["evaluation_pass_rate"] < 1


@pytest.mark.parametrize("label,include_evidence,accepted", [(None, False, False), (None, True, True),
    ("unclassified", True, False), ([], True, False), (4, True, False), ("public", True, True), ("secret", True, True)])
def test_federation_labels_are_validated_and_never_lower_source_privacy(pair, tmp_path, label, include_evidence, accepted):
    left, right, _ = pair
    claim(left, privacy="private")
    path = tmp_path / "labels.aletsync"
    share = export(pair, path, permissions=["read_claims"] + (["read_evidence"] if include_evidence else []))
    manifest, payload = federation._read_bundle(right, str(path))
    item = payload["payloads"]["claims"][0]
    if label is None:
        item.pop("privacy_level", None)
    else:
        item["privacy_level"] = label
    federation._write_bundle(str(path), manifest=manifest, payload=payload, encrypt=True,
        signer=left.active_federation_identity(), recipients=left.list_share_recipients(share.id))
    before = list(right.store.connection.iterdump())
    if not accepted:
        with pytest.raises(ValidationError, match="privacy label"):
            right.import_share_bundle(input_path=str(path))
        assert list(right.store.connection.iterdump()) == before
        return
    right.import_share_bundle(input_path=str(path))
    candidate, = right.list_candidates(NS)
    assert candidate.privacy_level == ("secret" if label == "secret" else "private")
    call = client(right, capabilities=["memory:read", "memory:review"])
    assert call("GET", "/v1/candidates/" + candidate.id)[0] == 403
    authorized = client(right, capabilities=["memory:read", "memory:review"], privacy="secret")
    assert authorized("GET", "/v1/candidates/" + candidate.id)[0] == 200


def test_claims_only_secret_federation_preserves_protected_evidence_and_spans(pair, tmp_path, monkeypatch):
    monkeypatch.setenv("ALETHEIA_PROTECTED_KEY", "synthetic-followup-secret-key")
    left, right, recipient = pair
    right.enable_protected_mode()
    claim(left, privacy="secret")
    share = left.create_share_grant(name="secret claim", namespace=NS, recipient_peer_ids=[recipient.id],
        permissions=["read_claims"], privacy_ceiling="secret", allow_secret=True, reason="synthetic test")
    path = tmp_path / "secret.aletsync"
    left.export_share_bundle(share_id=share.id, output_path=str(path), encrypt=True)
    right.import_share_bundle(input_path=str(path))
    candidate, = right.list_candidates(NS)
    assert candidate.privacy_level == "secret"
    assert MARKER in right.read_event(candidate.evidence_ids[0]).content
    db = right.store.connection
    assert MARKER not in db.execute("SELECT content FROM evidence_events").fetchone()[0]
    assert all(MARKER not in row[0] for row in db.execute("SELECT span_text FROM evidence_spans"))


def test_redaction_notices_exclude_never_disclosed_objects(pair, tmp_path):
    left, right, _ = pair
    shared = claim(left)
    hidden = claim(left, privacy="private", subject="not shared")
    path = tmp_path / "notices.aletsync"
    share = export(pair, path, permissions=["read_evidence", "receive_redactions"], privacy="public")
    right.import_share_bundle(input_path=str(path))
    for item in [shared, hidden]:
        left.redact(target_type="evidence", target_id=item.evidence_ids[0], reason="remove " + item.id, dry_run=False)
    left.export_share_bundle(share_id=share.id, output_path=str(path), encrypt=True)
    _, payload = federation._read_bundle(right, str(path))
    tombstones = payload["payloads"]["tombstones"]
    assert tombstones and {item["object_id"] for item in tombstones} == {shared.evidence_ids[0]}
    assert hidden.id not in json.dumps(payload) and hidden.evidence_ids[0] not in json.dumps(payload)
    right.import_share_bundle(input_path=str(path))
    assert all(MARKER not in event.content for event in right.list_events(namespace=NS))


@pytest.mark.parametrize("change", ["privacy", "changed_content"])
def test_sync_conflict_reads_revalidate_live_sources(pair, tmp_path, change):
    right, conflict, source = conflict_fixture(pair, tmp_path)
    call = client(right, capabilities=["memory:sync", "memory:review"])
    assert MARKER in json.dumps(call("GET", "/v1/sync/conflicts?namespace=" + NS)[1])
    candidate = right.read_candidate(source.local_object_id)
    if change == "privacy":
        right.store.connection.execute("UPDATE evidence_events SET privacy_level='secret' WHERE id=?", (candidate.evidence_ids[0],))
    else:
        right.store.connection.execute("UPDATE candidate_claims SET object='updated' WHERE id=?", (candidate.id,))
    status, response = call("GET", "/v1/sync/conflicts?namespace=" + NS)
    assert status == 200 and MARKER not in json.dumps(response)
    assert response["data"][0]["id"] == conflict.id


@pytest.mark.parametrize("mode", ["lexical", "hybrid", "semantic"])
def test_duplicate_penalty_participates_before_candidate_bound(memory, mode):
    values = [claim(memory, value="penaltyneedle", subject="source" + str(i)) for i in range(105)]
    target = max(values, key=lambda item: item.id)
    peer = claim(memory, value="unrelated", subject="penalty target")
    with memory.store.transaction():
        for item in values:
            if item.id != target.id:
                memory._create_relationship(source_claim_id=item.id, target_claim_id=peer.id,
                                            relationship_type="duplicate_of", reason="synthetic relation")
    if mode == "semantic":
        memory.index_semantic(NS, provider="mock")
    policy = memory.propose_policy_update(NS, policy_type="ranking", target_policy_id="rpol_default",
        proposed_config={"weights": {**dict.fromkeys(DEFAULT_WEIGHTS, 0.0), "duplicate_penalty": 1.0}}, reason="test")
    memory.review_policy_proposal(policy.id, decision="approve", reason="test")
    memory.apply_policy_proposal(policy.id, reason="test", require_evaluation_pass=False)
    results = memory.retrieve(NS, "penaltyneedle", mode=mode, limit=1)
    assert results[0].claim_id == target.id and results[0].score == 0.0


def test_trace_core_and_cli_default_and_explicit_budget(memory):
    from aletheia.cli.main import build_parser
    item = claim(memory, value="tracepolicyneedle consumes more than one token")
    policy = memory.propose_policy_update(NS, policy_type="context_pack", target_policy_id="cpol_default",
        proposed_config={"token_budget": 1}, reason="test")
    memory.review_policy_proposal(policy.id, decision="approve", reason="test")
    memory.apply_policy_proposal(policy.id, reason="test", require_evaluation_pass=False)
    trace = memory.trace_context_pack(NS, query="tracepolicyneedle", retrieval_mode="lexical")
    assert trace.metadata["token_budget"] == 1
    assert not any(row.included for row in memory.list_trace_items(trace.id))
    explicit = memory.trace_context_pack(NS, query="tracepolicyneedle", retrieval_mode="lexical", token_budget=100)
    assert explicit.metadata["token_budget"] == 100
    assert item.id in {row.target_id for row in memory.list_trace_items(explicit.id) if row.included}
    assert build_parser().parse_args(["traces", "context", "--namespace", NS, "--query", "needle"]).budget is None


@pytest.mark.parametrize("change", ["unchanged", "content", "close", "failure"])
def test_background_job_ownership_and_completion(memory, monkeypatch, change):
    from aletheia.core.provider_work import ProviderInputsChanged
    item = claim(memory)
    job = memory.enqueue_job(namespace=NS, job_type="index_semantic", payload={})
    server = AletheiaService(memory, ServiceConfig(db_path=memory.store.path, rate_limit_enabled=False))
    started, release = threading.Event(), threading.Event()
    calls = []
    original = MockEmbeddingProvider.embed_texts
    def controlled(self, *args, **kwargs):
        assert not memory.store.connection.in_transaction
        calls.append(True)
        started.set()
        assert release.wait(5)
        if change == "failure":
            raise RuntimeError("synthetic worker failure")
        return original(self, *args, **kwargs)
    monkeypatch.setattr(MockEmbeddingProvider, "embed_texts", controlled)
    with closing(Memory.open(memory.store.path, namespace=NS, auto_migrate=False)) as other:
        competitor = AletheiaService(other, server.config)
        with ThreadPoolExecutor(max_workers=1) as pool:
            pending = pool.submit(server.run_background_jobs, max_jobs=1)
            try:
                assert started.wait(3)
                assert other.get_job(job.id).status == "running"
                assert competitor.run_background_jobs(max_jobs=1) == []
                if change == "content":
                    other.store.connection.execute("UPDATE claims SET object='changed input' WHERE id=?", (item.id,))
                elif change == "close":
                    server.close()
                    assert other.get_job(job.id).status == "pending"
            finally:
                release.set()
            if change in {"content", "failure"}:
                with pytest.raises(ProviderInputsChanged if change == "content" else RuntimeError):
                    pending.result(timeout=5)
            else:
                pending.result(timeout=5)
        assert len(calls) == 1
        final = other.get_job(job.id)
        assert final.attempts == 1
        assert final.status == ("completed" if change == "unchanged" else "pending")
        assert other.store.connection.execute("SELECT count(*) FROM embeddings").fetchone()[0] == int(change == "unchanged")
        if change == "failure":
            monkeypatch.setattr(MockEmbeddingProvider, "embed_texts", original)
            competitor.run_background_jobs(max_jobs=1)
            assert other.get_job(job.id).status == "completed"
            assert other.get_job(job.id).attempts == 2


def test_project_only_authority_cannot_read_namespace_metrics(memory):
    project = memory.create_project(NS, "own-project", title="authorized project")
    call = client(memory, namespace=NS + "/projects/" + project.id, capabilities=["memory:admin"])
    status, _ = call("POST", "/v1/metrics/snapshot", {"namespace": NS, "project_id": project.id})
    assert status == 403
    assert not memory.list_metric_snapshots(namespace=NS)


@pytest.mark.parametrize("provider", [["mock_llm"], {"entrypoint": "unexpected"}])
def test_malformed_provider_is_rejected_without_running_or_caching(memory, provider):
    event = memory.write_event(namespace=NS, source_type="manual", content=MARKER)
    call = client(memory, capabilities=["memory:review"])
    status, response = call("POST", "/v1/llm/summarize-evidence", {"namespace": NS,
        "evidence_ids": [event.id], "provider": provider}, key="bad-provider")
    assert status == 400 and MARKER not in json.dumps(response)
    assert not memory.list_llm_runs(namespace=NS)
    assert not memory.store.connection.execute("SELECT 1 FROM idempotency_records").fetchone()
