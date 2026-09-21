"""Behavioral regressions for retrieval eligibility, limits and provider waits."""
from contextlib import closing
from concurrent.futures import ThreadPoolExecutor
import json
import threading

import pytest

from aletheia import Memory
from aletheia.core.errors import ValidationError
from aletheia.llm import MockLLMProvider
from aletheia.models import ServiceConfig
from aletheia.service.http import AletheiaService

NS = "audit/retrieval"
WORD = "uniqueretrievalsignal"


@pytest.fixture
def memory(tmp_path):
    with closing(Memory.open(str(tmp_path / "memory.db"), namespace=NS)) as value:
        yield value


def claim(memory, *, subject="source", text=WORD, status="active", privacy="personal", **kwargs):
    event = memory.write_event(namespace=NS, source_type="fixture", content=subject + " " + text, privacy_level=privacy)
    return memory.write_claim(namespace=NS, subject=subject, predicate="records", object=text,
        memory_type="fact", status=status, evidence_ids=[event.id], **kwargs)


def service(memory):
    server = AletheiaService(memory, ServiceConfig(db_path=memory.store.path, rate_limit_enabled=False))
    client = server.auth.create_client(name="synthetic", client_type="test")
    token, raw = server.auth.create_token(client_id=client.id, namespace_grants=[NS],
        capabilities=["memory:read", "memory:context", "memory:review", "memory:write_candidate"], privacy_ceiling="personal")
    def call(path, payload=None, **headers):
        return server.handle_http(method="POST" if payload is not None else "GET", path=path,
            headers={"Authorization": "Bearer " + raw, **headers}, body=json.dumps(payload).encode() if payload is not None else b"")
    return server, token, call


@pytest.mark.parametrize("mode", ["lexical", "semantic", "hybrid"])
def test_unreviewed_claims_require_an_explicit_opt_in(memory, mode):
    pending = claim(memory, subject="pending", status="candidate")
    active = claim(memory, subject="approved")
    batch = memory.ingest(NS, source_type="manual", content="Remember that " + WORD)
    memory.extract_candidates(NS, batch_id=batch.id, extractor="mock")
    governed_candidate = memory.list_candidates(NS)[0]
    memory.index_semantic(NS, provider="mock")
    default = memory.retrieve(NS, WORD, mode=mode)
    assert active.id in {item.claim_id for item in default}
    assert pending.id not in {item.claim_id for item in default}
    assert governed_candidate.id not in {item.claim_id for item in default}
    assert pending.id not in {item.claim_id for item in memory.context_pack(NS, WORD, retrieval_mode=mode).items()}
    assert pending.id in {item.claim_id for item in memory.retrieve(NS, WORD, mode=mode, include_candidates=True)}
    assert {item.claim_id for item in memory.retrieve(NS, WORD, mode=mode, statuses=["candidate"])} == {pending.id}


@pytest.mark.parametrize("mode", ["lexical", "semantic", "hybrid"])
def test_old_exact_match_competes_with_more_than_a_thousand_recent_claims(memory, monkeypatch, mode):
    old = claim(memory, subject="old", text=WORD + " exactneedle", confidence=1, importance=1)
    memory.store.connection.execute("UPDATE claims SET created_at = '2001-01-01T00:00:00+00:00' WHERE id = ?", (old.id,))
    with memory.store.transaction():
        for index in range(1005):
            claim(memory, subject="new " + str(index), text=WORD + " distractor", confidence=.3, importance=.1)
    if mode != "lexical":
        memory.index_semantic(NS, provider="mock")
    reranked = []
    owner = memory.retriever if mode == "lexical" else memory
    name = "_evidence_ids_by_claim" if mode == "lexical" else "_evidence_ids_for_claims"
    lookup = getattr(owner, name)
    def capture(ids):
        reranked.append(len(ids))
        return lookup(ids)
    monkeypatch.setattr(owner, name, capture)
    results = memory.retrieve(NS, WORD + " exactneedle", mode=mode, limit=1)
    assert results and results[0].claim_id == old.id
    assert reranked and max(reranked) <= 200


@pytest.mark.parametrize("mode", ["lexical", "semantic", "hybrid"])
@pytest.mark.parametrize("scope_type,applies_when", [("contextual", "unrelated_query"), ("project", "project/other"), ("session", "session/other")])
def test_ineligible_scope_cannot_consume_the_limit(memory, mode, scope_type, applies_when):
    high = claim(memory, subject="high", confidence=1, importance=1)
    low = claim(memory, subject="low", confidence=.5, importance=.1)
    memory.scope_claim(high.id, scope_type=scope_type, applies_when=applies_when, reason="fixture")
    results = memory.retrieve(NS, WORD, mode=mode, limit=1)
    assert [item.claim_id for item in results] == [low.id]


@pytest.mark.parametrize("mode", ["lexical", "semantic", "hybrid"])
def test_claim_validity_is_enforced_before_limits_and_context(memory, mode):
    expired = claim(memory, subject="expired", valid_to="2000-01-01T00:00:00Z", confidence=1)
    future = claim(memory, subject="future", valid_from="2099-01-01T00:00:00Z", confidence=1)
    current = claim(memory, subject="current", valid_from="2000-01-01T00:00:00-05:00", valid_to="2099-01-01T00:00:00+03:00")
    assert [item.claim_id for item in memory.retrieve(NS, WORD, mode=mode, limit=1)] == [current.id]
    ids = {item.claim_id for item in memory.context_pack(NS, WORD, retrieval_mode=mode).items()}
    assert current.id in ids and expired.id not in ids and future.id not in ids


@pytest.mark.parametrize("endpoint", ["/v1/retrieve", "/v1/search", "/v1/traces/retrieval"])
@pytest.mark.parametrize("mode", ["lexical", "hybrid", "semantic"])
def test_http_privacy_filtering_happens_before_result_limits(memory, endpoint, mode):
    for index in range(105):
        claim(memory, subject="hidden " + str(index), privacy="private", confidence=1, importance=1)
    visible = claim(memory, subject="visible", confidence=.4, importance=.1)
    _, _, call = service(memory)
    status, response = call(endpoint, {"namespace": NS, "query": WORD, "mode": mode, "limit": 1})
    assert status == 200, response
    if "traces" in endpoint:
        rows = memory.list_trace_items(response["data"]["id"])
        ids = [row.target_id for row in rows if row.included]
    else:
        ids = [row["claim_id"] for row in response["data"]]
    assert ids == [visible.id]


@pytest.mark.parametrize("endpoint", ["/v1/context-pack", "/v1/context", "/v1/traces/context-pack"])
def test_hidden_content_does_not_consume_context_budget(memory, endpoint):
    claim(memory, subject="hidden", text=WORD + " " + "long private source " * 60, privacy="private", confidence=1, importance=1)
    visible = claim(memory, subject="visible", confidence=.4, importance=.1)
    _, _, call = service(memory)
    status, response = call(endpoint, {"namespace": NS, "query": WORD, "retrieval_mode": "lexical", "token_budget": 315})
    assert status == 200, response
    if "traces" in endpoint:
        ids = [row.target_id for row in memory.list_trace_items(response["data"]["id"]) if row.included]
    else:
        ids = [row["claim_id"] for row in response["data"]["items"]]
    assert visible.id in ids


@pytest.mark.parametrize("backing", ["file", "memory"])
def test_provider_wait_does_not_block_health_or_an_unrelated_write(tmp_path, monkeypatch, backing):
    entered, release = threading.Event(), threading.Event()
    def slow(self, **kwargs):
        entered.set()
        assert release.wait(5), "fixture provider was not released"
        return {"original_query": WORD, "expanded_terms": [WORD]}
    monkeypatch.setattr(MockLLMProvider, "complete_json", slow)
    with closing(Memory.open(":memory:" if backing == "memory" else str(tmp_path / "server.db"), namespace=NS)) as memory:
        server, _, call = service(memory)
        with ThreadPoolExecutor(max_workers=3) as pool:
            pending = pool.submit(call, "/v1/llm/expand-query", {"namespace": NS, "query": WORD})
            assert entered.wait(3)
            try:
                health = pool.submit(call, "/v1/health")
                write = pool.submit(call, "/v1/remember", {"namespace": NS, "subject": "concurrent",
                    "predicate": "records", "object": "independent", "memory_type": "fact"})
                assert health.result(timeout=.75)[0] == 200
                assert write.result(timeout=.75)[0] == 200
            finally:
                release.set()
            assert pending.result(timeout=3)[0] == 200
        assert len(memory.list_candidates(NS)) == 1
        assert len(memory.list_llm_runs(namespace=NS)) == 1
        assert memory.store.connection.in_transaction is False


@pytest.mark.parametrize("mode", ["lexical", "semantic", "hybrid"])
def test_historical_queries_use_normalized_half_open_claim_and_scope_windows(memory, mode):
    bounded = claim(memory, valid_from="2020-01-01T02:00:00+02:00", valid_to="2020-01-02T00:00:00Z")
    memory.scope_claim(bounded.id, scope_type="contextual", applies_when=WORD,
        valid_from="2020-01-01T01:00:00Z", valid_to="2020-01-01T02:00:00Z", reason="fixture")
    for at, included in [("2020-01-01T00:59:59Z", False), ("2020-01-01T01:00:00Z", True),
                         ("2020-01-01T03:00:00+02:00", True), ("2020-01-01T02:00:00Z", False),
                         ("2020-01-02T00:00:00Z", False)]:
        results = memory.retrieve(NS, WORD, mode=mode, filters={"as_of": at})
        assert (bounded.id in {item.claim_id for item in results}) is included
    with pytest.raises(ValidationError, match="as_of"):
        memory.retrieve(NS, WORD, mode=mode, filters={"as_of": "not a timestamp"})


@pytest.mark.parametrize("status", ["rejected", "unknown_legacy_status"])
def test_unknown_or_rejected_status_never_enters_retrieval(memory, status):
    item = claim(memory)
    memory.store.connection.execute("UPDATE claims SET status = ? WHERE id = ?", (status, item.id))
    for mode in ("lexical", "hybrid", "semantic"):
        assert not memory.retrieve(NS, WORD, mode=mode, include_candidates=True, include_archived=True, include_disputed=True)
        assert not memory.retrieve(NS, WORD, mode=mode, statuses=[status])


@pytest.mark.parametrize("mode", ["lexical", "semantic", "hybrid"])
def test_malformed_legacy_validity_is_ineligible_without_hiding_valid_memory(memory, mode):
    claim(memory, subject="invalid claim dates", valid_from="not-a-date")
    scoped = claim(memory, subject="invalid scope dates")
    scope = memory.scope_claim(scoped.id, scope_type="contextual", applies_when=WORD, reason="legacy fixture")
    memory.store.connection.execute("UPDATE claim_scopes SET valid_to = 'not-a-date' WHERE id = ?", (scope.id,))
    valid = claim(memory, subject="valid")
    assert [row.claim_id for row in memory.retrieve(NS, WORD, mode=mode)] == [valid.id]


@pytest.mark.parametrize("change,expected", [("privacy", 403), ("content", 409), ("revoke", 401), ("redact", 403)])
def test_provider_completion_revalidates_sources_and_credentials(memory, monkeypatch, change, expected):
    item = claim(memory)
    server, token, call = service(memory)
    entered, release = threading.Event(), threading.Event()
    calls = []
    original = MockLLMProvider.complete_json
    def slow(self, **kwargs):
        calls.append(kwargs)
        entered.set()
        assert release.wait(5)
        return original(self, **kwargs)
    monkeypatch.setattr(MockLLMProvider, "complete_json", slow)
    with ThreadPoolExecutor(max_workers=1) as pool:
        pending = pool.submit(call, "/v1/llm/summarize-evidence", {"namespace": NS, "evidence_ids": item.evidence_ids})
        assert entered.wait(3)
        try:
            assert not memory.store.connection.in_transaction
            with closing(Memory.open(memory.store.path, auto_migrate=False)) as other:
                if change == "privacy":
                    other.store.connection.execute("UPDATE evidence_events SET privacy_level = 'private' WHERE id = ?", (item.evidence_ids[0],))
                elif change == "content":
                    other.store.connection.execute("UPDATE evidence_events SET content = 'updated source' WHERE id = ?", (item.evidence_ids[0],))
                elif change == "redact":
                    other.redact(target_type="evidence", target_id=item.evidence_ids[0], reason="fixture", dry_run=False)
                else:
                    from aletheia.service.auth import AuthService
                    AuthService(other).revoke_token(token.id, reason="fixture")
        finally:
            release.set()
        status, response = pending.result(timeout=3)
    assert status == expected, response
    assert WORD not in json.dumps(response)
    assert len(calls) == 1
    assert not memory.list_llm_runs(namespace=NS)
    assert not memory.store.connection.execute("SELECT 1 FROM llm_outputs").fetchone()
    assert not memory.store.connection.in_transaction


def test_provider_failure_cannot_rollback_another_request_and_idempotency_can_retry(memory, monkeypatch):
    server, _, call = service(memory)
    entered, release = threading.Event(), threading.Event()
    original = MockLLMProvider.complete_json
    def fail(self, **kwargs):
        entered.set()
        assert release.wait(5)
        raise RuntimeError("synthetic provider failure")
    monkeypatch.setattr(MockLLMProvider, "complete_json", fail)
    payload = {"namespace": NS, "query": WORD}
    with ThreadPoolExecutor(max_workers=2) as pool:
        pending = pool.submit(call, "/v1/llm/expand-query", payload, **{"Idempotency-Key": "provider-retry"})
        assert entered.wait(3)
        try:
            saved = pool.submit(call, "/v1/remember", {"namespace": NS, "subject": "concurrent",
                "predicate": "records", "object": "durable", "memory_type": "fact"}).result(timeout=.75)
            assert saved[0] == 200
        finally:
            release.set()
        assert pending.result(timeout=3)[0] == 500
    assert len(memory.list_candidates(NS)) == 1
    assert not memory.list_llm_runs(namespace=NS)
    monkeypatch.setattr(MockLLMProvider, "complete_json", original)
    assert call("/v1/llm/expand-query", payload, **{"Idempotency-Key": "provider-retry"})[0] == 200
    assert len(memory.list_llm_runs(namespace=NS)) == 1
    assert len(memory.list_candidates(NS)) == 1


def test_simultaneous_idempotent_provider_request_invokes_once(memory, monkeypatch):
    _, _, call = service(memory)
    entered, release = threading.Event(), threading.Event()
    calls = []
    original = MockLLMProvider.complete_json
    def slow(self, **kwargs):
        calls.append(True)
        entered.set()
        assert release.wait(5)
        return original(self, **kwargs)
    monkeypatch.setattr(MockLLMProvider, "complete_json", slow)
    payload = {"namespace": NS, "query": WORD}
    headers = {"Idempotency-Key": "same-provider-operation"}
    with ThreadPoolExecutor(max_workers=2) as pool:
        pending = pool.submit(call, "/v1/llm/expand-query", payload, **headers)
        assert entered.wait(3)
        try:
            second = pool.submit(call, "/v1/llm/expand-query", payload, **headers).result(timeout=.75)
            assert second[0] == 409
        finally:
            release.set()
        completed = pending.result(timeout=3)
    assert completed[0] == 200
    assert call("/v1/llm/expand-query", payload, **headers)[1]["data"] == completed[1]["data"]
    assert len(calls) == 1 and len(memory.list_llm_runs(namespace=NS)) == 1


@pytest.mark.parametrize("stage", ["constructor", "semantic_query"])
def test_other_provider_work_also_runs_outside_service_transactions(memory, monkeypatch, stage):
    from aletheia.semantic import MockEmbeddingProvider
    item = claim(memory)
    memory.index_semantic(NS, provider="mock")
    _, _, call = service(memory)
    entered, release = threading.Event(), threading.Event()
    def wait():
        assert not memory.store.connection.in_transaction
        entered.set()
        assert release.wait(5)
    if stage == "constructor":
        original = MockLLMProvider.__init__
        def initialize(self, *args, **kwargs):
            wait()
            original(self, *args, **kwargs)
        monkeypatch.setattr(MockLLMProvider, "__init__", initialize)
        endpoint, payload = "/v1/llm/expand-query", {"namespace": NS, "query": WORD}
    else:
        original = MockEmbeddingProvider.embed_texts
        def embed(self, *args, **kwargs):
            if kwargs.get("purpose") == "semantic_query":
                wait()
            return original(self, *args, **kwargs)
        monkeypatch.setattr(MockEmbeddingProvider, "embed_texts", embed)
        endpoint, payload = "/v1/retrieve", {"namespace": NS, "query": WORD, "mode": "semantic"}
    with ThreadPoolExecutor(max_workers=2) as pool:
        pending = pool.submit(call, endpoint, payload)
        try:
            assert entered.wait(3)
            assert pool.submit(call, "/v1/health").result(timeout=.75)[0] == 200
        finally:
            release.set()
        assert pending.result(timeout=3)[0] == 200


def test_provider_results_are_isolated_between_simultaneous_requests(memory, monkeypatch):
    _, _, call = service(memory)
    barrier = threading.Barrier(2)
    queries = []
    def complete(self, **kwargs):
        query = kwargs["metadata"]["query"]
        queries.append(query)
        barrier.wait(timeout=3)
        return {"original_query": query, "expanded_terms": [query]}
    monkeypatch.setattr(MockLLMProvider, "complete_json", complete)
    with ThreadPoolExecutor(max_workers=2) as pool:
        requests = [pool.submit(call, "/v1/llm/expand-query", {"namespace": NS, "query": query})
                    for query in ("first synthetic request", "second synthetic request")]
        results = [request.result(timeout=5) for request in requests]
    assert [item[0] for item in results] == [200, 200]
    assert [item[1]["data"]["original_query"] for item in results] == ["first synthetic request", "second synthetic request"]
    assert sorted(queries) == ["first synthetic request", "second synthetic request"]
    assert len({item[1]["data"]["llm_run_id"] for item in results}) == 2
    assert len(memory.list_llm_runs(namespace=NS)) == 2


@pytest.mark.parametrize("change", ["grants", "revoke", "credential"])
def test_console_credential_proof_does_not_cache_authorization(memory, monkeypatch, change):
    from aletheia.core.ids import content_hash
    from aletheia.service.auth import AuthService
    server = AletheiaService(memory, ServiceConfig(db_path=memory.store.path,
        console_enabled=True, rate_limit_enabled=False))
    raw = "synthetic-console-credential"
    metadata = {"session_token_lookup": content_hash(raw), "session_token_hash": AuthService.hash_secret(raw)}
    memory.store.connection.execute("""INSERT INTO console_sessions
        (id, namespace_grants_json, capabilities_json, privacy_ceiling, created_at, expires_at, metadata_json)
        VALUES ('csess_fixture', ?, '["memory:read"]', 'personal', '2020-01-01T00:00:00Z',
                '2099-01-01T00:00:00Z', ?)""", (json.dumps([NS]), json.dumps(metadata)))
    original = server._idempotency_replay
    def between_auth_and_route(**kwargs):
        if change == "grants":
            memory.store.connection.execute("UPDATE console_sessions SET namespace_grants_json = ? WHERE id = 'csess_fixture'",
                (json.dumps([NS + "/changed"]),))
        elif change == "revoke":
            memory.store.connection.execute("UPDATE console_sessions SET revoked_at = '2026-01-01T00:00:00Z' WHERE id = 'csess_fixture'")
        else:
            replacement = {**metadata, "session_token_hash": AuthService.hash_secret("different synthetic credential")}
            memory.store.connection.execute("UPDATE console_sessions SET metadata_json = ? WHERE id = 'csess_fixture'",
                (json.dumps(replacement),))
        return original(**kwargs)
    monkeypatch.setattr(server, "_idempotency_replay", between_auth_and_route)
    status, response = server.handle_http(method="GET", path="/v1/console/session", headers={"X-Console-Session": raw})
    if change == "grants":
        assert status == 200 and response["data"]["namespace_grants"] == [NS + "/changed"]
    else:
        assert status == 401, response


def test_semantic_index_job_completes_many_provider_calls_once_each(memory, monkeypatch):
    from aletheia.semantic import MockEmbeddingProvider
    with memory.store.transaction():
        for index in range(257):
            claim(memory, subject=f"source {index}")
    job = memory.enqueue_job(namespace=NS, job_type="index_semantic", payload={})
    calls = []
    original = MockEmbeddingProvider.embed_texts
    def observe(self, *args, **kwargs):
        assert not memory.store.connection.in_transaction
        calls.append(kwargs["metadata"]["target_id"])
        return original(self, *args, **kwargs)
    monkeypatch.setattr(MockEmbeddingProvider, "embed_texts", observe)
    server = AletheiaService(memory, ServiceConfig(db_path=memory.store.path,
        auth_required=False, tokenless_capabilities=["memory:jobs"], rate_limit_enabled=False))
    status, response = server.handle_http(method="POST", path="/v1/jobs/run", headers={},
        body=json.dumps({"namespace": NS, "job_type": "index_semantic"}).encode())
    assert status == 200, response
    assert memory.get_job(job.id).status == "completed", response
    assert memory.get_job(job.id).attempts == 1
    assert len(calls) == len(set(calls)) == 257
    assert memory.store.connection.execute("SELECT COUNT(*) FROM embeddings").fetchone()[0] == 257
    assert memory.store.connection.execute("SELECT COUNT(*) FROM audit_log WHERE action = 'semantic.index'").fetchone()[0] == 1


def test_provider_job_keeps_ownership_against_a_second_worker(memory, monkeypatch):
    from aletheia.semantic import MockEmbeddingProvider
    claim(memory)
    job = memory.enqueue_job(namespace=NS, job_type="index_semantic", payload={})
    entered, release = threading.Event(), threading.Event()
    original = MockEmbeddingProvider.embed_texts
    calls = []
    def slow(self, *args, **kwargs):
        calls.append(True)
        entered.set()
        assert release.wait(5)
        return original(self, *args, **kwargs)
    monkeypatch.setattr(MockEmbeddingProvider, "embed_texts", slow)
    config = ServiceConfig(db_path=memory.store.path, auth_required=False,
        tokenless_capabilities=["memory:jobs"], rate_limit_enabled=False)
    first = AletheiaService(memory, config)
    def run(server):
        return server.handle_http(method="POST", path="/v1/jobs/run", headers={}, body=json.dumps({"namespace": NS}).encode())
    with ThreadPoolExecutor(max_workers=1) as pool:
        pending = pool.submit(run, first)
        try:
            assert entered.wait(3)
            with closing(Memory.open(memory.store.path, namespace=NS, auto_migrate=False)) as other:
                assert other.get_job(job.id).status == "running"
                assert other.get_job(job.id).attempts == 1
                second = AletheiaService(other, config)
                assert second.handle_http(method="GET", path="/v1/health", headers={})[0] == 200
                status, response = run(second)
                assert status == 200 and response["data"] == []
        finally:
            release.set()
        assert pending.result(timeout=3)[0] == 200
    assert len(calls) == 1
    assert memory.get_job(job.id).status == "completed"
    assert memory.store.connection.execute("SELECT COUNT(*) FROM embeddings").fetchone()[0] == 1


def test_failed_provider_job_releases_its_claim_for_retry(memory, monkeypatch):
    from aletheia.semantic import MockEmbeddingProvider
    claim(memory)
    job = memory.enqueue_job(namespace=NS, job_type="index_semantic", payload={})
    original = MockEmbeddingProvider.embed_texts
    def fail(self, *args, **kwargs):
        raise RuntimeError("synthetic provider failure")
    monkeypatch.setattr(MockEmbeddingProvider, "embed_texts", fail)
    server = AletheiaService(memory, ServiceConfig(db_path=memory.store.path, auth_required=False,
        tokenless_capabilities=["memory:jobs"], rate_limit_enabled=False))
    def run():
        return server.handle_http(method="POST", path="/v1/jobs/run", headers={}, body=json.dumps({"namespace": NS}).encode())
    assert run()[0] == 500
    failed = memory.get_job(job.id)
    assert failed.status == "pending" and failed.attempts == 1
    assert memory.store.connection.execute("SELECT COUNT(*) FROM embeddings").fetchone()[0] == 0
    monkeypatch.setattr(MockEmbeddingProvider, "embed_texts", original)
    assert run()[0] == 200
    completed = memory.get_job(job.id)
    assert completed.status == "completed" and completed.attempts == 2
    assert memory.store.connection.execute("SELECT COUNT(*) FROM embeddings").fetchone()[0] == 1
