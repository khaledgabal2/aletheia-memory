"""Read conformance and security regression cases using disposable synthetic data."""

from dataclasses import replace
import hashlib
import json
from concurrent.futures import ThreadPoolExecutor

from jsonschema import Draft202012Validator
from openapi_spec_validator import validate
import pytest

from aletheia import Memory
from aletheia.service.http import openapi_schema
from aletheia.service.read_contracts import READ_PATHS, read_document
from scripts.v1_4_phase0 import NAMESPACE, local_service, request


PROFILE = {"X-Aletheia-Contract": "memory-read-v1"}


def seed(memory, name, *, namespace=NAMESPACE, privacy="personal", project=None, subject=None):
    batch = memory.ingest(namespace, source_type="manual", content=f"User prefers {name} architecture notes.",
                          privacy_level=privacy, project_id=project, trust_level="user_asserted")
    return memory.write_claim(namespace=namespace, subject=subject or name, predicate="prefers", object=f"{name} architecture notes",
                              memory_type="preference", evidence_ids=batch.evidence_ids, confidence=.95, project_id=project)


def candidate(memory, name, **kwargs):
    batch = memory.ingest(NAMESPACE, source_type="manual", content=f"User prefers {name} architecture notes.", **kwargs)
    run = memory.extract_candidates(NAMESPACE, batch_id=batch.id)
    return memory.list_candidates(NAMESPACE, extraction_run_id=run.id)[0]


def credential(service, capabilities, *, grants=None, privacy="personal"):
    client = service.auth.create_client(name="Read conformance", client_type="test")
    token, raw = service.auth.create_token(client_id=client.id, capabilities=capabilities,
                                          namespace_grants=grants or [NAMESPACE], privacy_ceiling=privacy)
    return token, raw


def conform(document, path, result):
    method = READ_PATHS[path][0]
    shape = document["paths"][path][method]["responses"][str(result["status"])]["content"]["application/json"]["schema"]
    Draft202012Validator({**shape, "components": document["components"]}).validate(result["body"])
    assert result["headers"]["Cache-Control"] == "no-store"
    assert result["headers"]["X-Request-ID"] == result["body"]["request_id"]
    assert result["body"].get("pagination") is None


def domain_state(memory):
    tables = [row[0] for row in memory.store.connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
              if row[0] not in {"service_request_log", "rate_limit_records"}]
    result = {}
    for table in tables:
        rows = sorted(repr(tuple(row)) for row in memory.store.connection.execute('SELECT * FROM "' + table.replace('"', '""') + '"'))
        result[table] = hashlib.sha256(repr(rows).encode()).hexdigest()
    return result


def test_actual_read_schemas_nonempty_success_errors_aliases_and_no_cursor(tmp_path):
    with local_service(tmp_path) as (service, url, tokens):
        claim = seed(service.memory, "schema")
        pending = candidate(service.memory, "pending")
        service.memory.create_review_task(NAMESPACE, task_type="candidate_review", title="Review sample", description="Inspect source",
                                           target_type="candidate_claim", target_id=pending.id)
        document = request(url, "GET", "/v1/openapi.json")["body"]["data"]
        validate(read_document(document))
        for path, (_, _, _) in READ_PATHS.items():
            method = READ_PATHS[path][0].upper()
            actual = path.replace("{claim_id}", claim.id).replace("{target_type}", "claim").replace("{target_id}", claim.id)
            body = {"namespace": NAMESPACE, "query": "architecture", "mode": "lexical", "retrieval_mode": "lexical", "record_usage": False} if method == "POST" else None
            if path.endswith("overview"):
                actual += "?namespace=" + NAMESPACE
            response = request(url, method, actual, token=tokens["agent"], payload=body, headers=PROFILE)
            assert response["status"] == 200
            conform(document, path, response)
            if method == "POST":
                assert response["body"]["data"]
        for kind, target in [("candidate_claim", pending.id), ("candidate", pending.id), ("evidence", claim.evidence_ids[0]), ("event", claim.evidence_ids[0])]:
            response = request(url, "GET", f"/v1/audit/{kind}/{target}", token=tokens["reviewer"])
            assert response["status"] == 200
            conform(document, "/v1/audit/{target_type}/{target_id}", response)
        overview = request(url, "GET", f"/v1/dashboard/overview?namespace={NAMESPACE}", token=tokens["reviewer"])
        assert overview["body"]["data"]["candidates"] and overview["body"]["data"]["review_tasks"]
        conform(document, "/v1/dashboard/overview", overview)
        for path, actual, role, status in [
            ("/v1/claims/{claim_id}", "/v1/claims/missing", "agent", 404),
            ("/v1/claims/{claim_id}", f"/v1/claims/{claim.id}", None, 401),
            ("/v1/audit/{target_type}/{target_id}", f"/v1/audit/claim/{claim.id}", "reader", 403),
            ("/v1/audit/{target_type}/{target_id}", f"/v1/audit/unknown/{claim.id}", "agent", 404),
        ]:
            result = request(url, "GET", actual, token=tokens.get(role))
            assert result["status"] == status
            conform(document, path, result)


@pytest.mark.parametrize("privacy", ["private", "secret"])
def test_scope_and_privacy_apply_across_all_read_views(tmp_path, privacy):
    with local_service(tmp_path) as (service, url, tokens):
        visible = seed(service.memory, "allowed")
        hidden = seed(service.memory, "restricted-marker", privacy=privacy)
        other = seed(service.memory, "other-marker", namespace="user/other")
        for item in [hidden, other]:
            for path in [f"/v1/claims/{item.id}", f"/v1/claims/{item.id}/explain", f"/v1/audit/claim/{item.id}",
                         f"/v1/audit/evidence/{item.evidence_ids[0]}"]:
                result = request(url, "GET", path, token=tokens["agent"])
                assert result["status"] == 403 and item.object not in json.dumps(result["body"])
        for path in ["/v1/retrieve", "/v1/search", "/v1/context-pack", "/v1/context"]:
            result = request(url, "POST", path, token=tokens["agent"], payload={"namespace": NAMESPACE, "query": "architecture", "mode": "lexical", "retrieval_mode": "lexical"})
            assert result["status"] == 200
            text = json.dumps(result["body"])
            assert visible.id in text and hidden.id not in text and other.id not in text
            assert "restricted-marker" not in text and "other-marker" not in text
        overview = request(url, "GET", f"/v1/dashboard/overview?namespace={NAMESPACE}", token=tokens["reader"])["body"]["data"]
        assert overview["metrics"]["active_claim_count"] == 1
        assert overview["metrics"]["candidate_count"] is None
        assert overview["jobs"] == overview["service_requests"] == []
        assert overview["candidates"] == overview["review_tasks"] == []


def test_project_selection_is_checked_against_stored_provenance_and_sessions(tmp_path):
    with local_service(tmp_path) as (service, url, _):
        alpha = seed(service.memory, "alpha", project="alpha")
        beta = seed(service.memory, "beta", project="beta")
        _, token = credential(service, ["memory:admin"], grants=[NAMESPACE + "/projects/alpha"], privacy="public")
        # Admin does not lift the privacy ceiling.
        assert request(url, "GET", f"/v1/claims/{alpha.id}", token=token)["status"] == 403
        _, token = credential(service, ["memory:read", "memory:context", "memory:audit"], grants=[NAMESPACE + "/projects/alpha"])
        assert request(url, "GET", f"/v1/claims/{alpha.id}", token=token)["status"] == 200
        assert request(url, "GET", f"/v1/claims/{beta.id}?project_id=alpha", token=token)["status"] == 403
        for path in ["/v1/retrieve", "/v1/context-pack"]:
            result = request(url, "POST", path, token=token, payload={"namespace": NAMESPACE, "project_id": "alpha", "query": "architecture", "mode": "lexical", "retrieval_mode": "lexical"})
            assert result["status"] == 200 and alpha.id in json.dumps(result["body"]) and beta.id not in json.dumps(result["body"])
        session = service.memory.start_session(namespace=NAMESPACE, project_id="beta")
        result = request(url, "POST", "/v1/context-pack", token=token, payload={"namespace": NAMESPACE, "project_id": "alpha", "session_id": session.id})
        assert result["status"] == 403
        overview = request(url, "GET", f"/v1/dashboard/overview?namespace={NAMESPACE}&project_id=alpha", token=token)
        assert overview["status"] == 200 and overview["body"]["data"]["metrics"]["active_claim_count"] == 1


def test_candidate_audit_cannot_bypass_review_or_privacy(tmp_path):
    with local_service(tmp_path) as (service, url, tokens):
        pending = candidate(service.memory, "pending")
        hidden = candidate(service.memory, "restricted-candidate", privacy_level="secret")
        for kind in ["candidate", "candidate_claim"]:
            assert request(url, "GET", f"/v1/audit/{kind}/{pending.id}", token=tokens["agent"])["status"] == 403
            assert request(url, "GET", f"/v1/audit/{kind}/{hidden.id}", token=tokens["reviewer"])["status"] == 403
        assert request(url, "GET", f"/v1/candidates/{hidden.id}", token=tokens["reviewer"])["status"] == 403
        listing = request(url, "GET", f"/v1/candidates?namespace={NAMESPACE}", token=tokens["reviewer"])
        assert pending.id in json.dumps(listing["body"]) and hidden.id not in json.dumps(listing["body"])


def test_redaction_is_respected_by_detail_provenance_and_cached_post_reads(tmp_path):
    with local_service(tmp_path) as (service, url, tokens):
        claim = seed(service.memory, "erase-marker")
        body = {"namespace": NAMESPACE, "query": "architecture", "mode": "lexical", "retrieval_mode": "lexical"}
        for path in ["/v1/retrieve", "/v1/context-pack"]:
            assert claim.id in json.dumps(request(url, "POST", path, token=tokens["agent"], payload=body, headers={"Idempotency-Key": "read-key"})["body"])
        service.memory.redact(target_id=claim.evidence_ids[0], target_type="evidence", reason="Synthetic removal", dry_run=False)
        for path in [f"/v1/claims/{claim.id}", f"/v1/claims/{claim.id}/explain", f"/v1/audit/claim/{claim.id}"]:
            assert request(url, "GET", path, token=tokens["agent"])["status"] == 403
        for path in ["/v1/retrieve", "/v1/context-pack"]:
            result = request(url, "POST", path, token=tokens["agent"], payload=body, headers={"Idempotency-Key": "read-key"})
            assert result["status"] == 200 and "erase-marker" not in json.dumps(result["body"])
        assert service.memory.store.connection.execute("SELECT count(*) FROM idempotency_records").fetchone()[0] == 0


def test_context_warnings_omitted_ids_and_reflections_do_not_reveal_hidden_sources(tmp_path):
    with local_service(tmp_path) as (service, url, tokens):
        visible = seed(service.memory, "visible", subject="shared-subject")
        hidden = seed(service.memory, "secret-conflict-marker", privacy="secret", subject="shared-subject")
        reflection = service.memory.build_reflection(NAMESPACE, source_claim_ids=[hidden.id], title="Derived fixture",
                                                     text="derived-secret-marker", reason="Fixture", require_review=False)
        for budget in [1, 1500]:
            result = request(url, "POST", "/v1/context-pack", token=tokens["agent"], payload={"namespace": NAMESPACE,
                "query": "architecture", "retrieval_mode": "lexical", "include_reflections": True, "include_derivation_metadata": True, "token_budget": budget})
            assert result["status"] == 200
            text = json.dumps(result["body"])
            for marker in [hidden.id, reflection.id, "secret-conflict-marker", "derived-secret-marker"]:
                assert marker not in text
        explained = request(url, "GET", f"/v1/claims/{visible.id}/explain", token=tokens["agent"])
        assert explained["status"] == 200 and explained["body"]["data"]["conflicts"] == []
        assert all(row["details"] == "{}" for row in explained["body"]["data"]["audit"])


@pytest.mark.parametrize("path,bad", [("/v1/retrieve", {"limit": 201}), ("/v1/retrieve", {"limit": "10"}),
    ("/v1/retrieve", {"memory_types": "preference"}), ("/v1/retrieve", {"mode": "unknown"}),
    ("/v1/context-pack", {"token_budget": 0}), ("/v1/context-pack", {"record_usage": "false"})])
def test_opt_in_canonical_validation_and_legacy_coercion(tmp_path, path, bad):
    with local_service(tmp_path) as (_, url, tokens):
        result = request(url, "POST", path, token=tokens["agent"], payload={"namespace": NAMESPACE, **bad}, headers=PROFILE)
        assert result["status"] == 400
        conform(openapi_schema(), path, result)
        legacy = request(url, "POST", "/v1/retrieve", token=tokens["agent"], payload={"namespace": NAMESPACE, "mode": "lexical", "limit": "10", "future_extension": {"allowed": True}})
        assert legacy["status"] == 200


def test_polling_is_read_only_for_domain_state_and_concurrent_calls_finish(tmp_path):
    with local_service(tmp_path) as (service, url, tokens):
        claim = seed(service.memory, "polling")
        before = domain_state(service.memory)
        def poll(index):
            if index % 3 == 0:
                return request(url, "GET", f"/v1/dashboard/overview?namespace={NAMESPACE}", token=tokens["agent"])
            path = "/v1/retrieve" if index % 3 == 1 else "/v1/context-pack"
            return request(url, "POST", path, token=tokens["agent"], payload={"namespace": NAMESPACE, "mode": "lexical",
                "retrieval_mode": "lexical", "record_usage": False, "query": "architecture"}, headers=PROFILE)
        with ThreadPoolExecutor(max_workers=4) as pool:
            assert all(result["status"] == 200 for result in pool.map(poll, range(12)))
        after = domain_state(service.memory)
        assert before == after, [name for name in before if before[name] != after[name]]
        token, raw = credential(service, ["memory:read"])
        assert request(url, "POST", "/v1/retrieve", token=raw, payload={"namespace": NAMESPACE}, headers={"Idempotency-Key": "scope"})["status"] == 200
        with service.memory.store.transaction():
            service.memory.store.connection.execute("DELETE FROM capability_grants WHERE token_id = ?", (token.id,))
        assert request(url, "POST", "/v1/retrieve", token=raw, payload={"namespace": NAMESPACE}, headers={"Idempotency-Key": "scope"})["status"] == 403


def test_explicit_context_usage_records_only_delivered_memories(tmp_path):
    with local_service(tmp_path) as (service, url, tokens):
        visible = seed(service.memory, "visible-usage")
        hidden = seed(service.memory, "hidden-usage", privacy="secret")
        response = request(url, "POST", "/v1/context-pack", token=tokens["agent"], headers=PROFILE,
            payload={"namespace": NAMESPACE, "query": "architecture", "retrieval_mode": "lexical", "record_usage": True})
        assert response["status"] == 200
        conform(openapi_schema(), "/v1/context-pack", response)
        pack_id = response["body"]["data"]["context_pack_id"]
        rows = service.memory.store.connection.execute("SELECT target_id FROM memory_usage_events WHERE context_pack_id=?", (pack_id,)).fetchall()
        assert [row[0] for row in rows] == [visible.id]
        usage = service.memory.store.connection.execute("SELECT * FROM context_usage_events WHERE context_pack_id=?", (pack_id,)).fetchone()
        assert usage["item_count"] == 1
        assert visible.id in usage["metadata_json"] and hidden.id not in usage["metadata_json"]


def test_loopback_transport_rejects_untrusted_host_origin_and_reports_errors(tmp_path):
    from urllib.parse import urlparse
    with local_service(tmp_path) as (service, url, tokens):
        path = "/v1/retrieve"
        authority = urlparse(url).netloc
        for headers in [{"Host": "attacker.invalid"}, {"Host": authority + "/path"}, {"Host": "localhost:invalid"},
                        {"Host": "localhost:1"}, {"Origin": "https://attacker.invalid"}, {"Origin": "null"},
                        {"Origin": url + "/path"}, {"Origin": "http://localhost:" + authority.split(":")[-1]}]:
            response = request(url, "POST", path, token=tokens["agent"], headers=headers, payload={"namespace": NAMESPACE})
            assert response["status"] == 403
            conform(openapi_schema(), path, response)
            assert not any(key.lower().startswith("access-control-") for key in response["headers"])
        assert request(url, "POST", path, token=tokens["agent"], headers={"Origin": url}, payload={"namespace": NAMESPACE})["status"] == 200
        service.config = replace(service.config, max_request_bytes=32)
        response = request(url, "POST", path, token=tokens["agent"], payload={"namespace": NAMESPACE, "query": "x" * 64})
        assert response["status"] == 413
        conform(openapi_schema(), path, response)
        service.config = replace(service.config, max_request_bytes=1048576, rate_limit_enabled=True, rate_limit_per_minute=1)
        assert request(url, "POST", path, token=tokens["agent"], payload={"namespace": NAMESPACE})["status"] == 200
        response = request(url, "POST", path, token=tokens["agent"], payload={"namespace": NAMESPACE})
        assert response["status"] == 429
        conform(openapi_schema(), path, response)


def test_ranked_limit_empty_results_and_resource_type_are_explicit(tmp_path):
    with local_service(tmp_path) as (service, url, tokens):
        for name in ["first", "second", "third"]:
            seed(service.memory, name)
        pending = candidate(service.memory, "not-a-claim")
        for query, count in [("architecture", 2), ("zzzzdoesnotmatch", 0)]:
            response = request(url, "POST", "/v1/retrieve", token=tokens["agent"], headers=PROFILE,
                payload={"namespace": NAMESPACE, "query": query, "mode": "lexical", "limit": 2})
            assert response["status"] == 200 and len(response["body"]["data"]) == count
            conform(openapi_schema(), "/v1/retrieve", response)
        response = request(url, "GET", f"/v1/audit/claim/{pending.id}", token=tokens["reviewer"])
        assert response["status"] == 404
