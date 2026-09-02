"""Agent creation profile and legacy compatibility through actual HTTP."""
import json
from urllib.parse import urlencode

import pytest
from jsonschema import Draft202012Validator
from openapi_spec_validator import validate

from aletheia.client import AletheiaClient, AletheiaUnsupportedFeatureError
from aletheia.service.http import openapi_schema
from aletheia.service.onboarding_contract import onboarding_document
from scripts.v1_4_phase0 import local_service, request, NAMESPACE
from tests.test_v1_4_reads import credential, domain_state

HEADERS = {"X-Aletheia-Contract": "agent-onboarding-v1", "Idempotency-Key": "agent-operation"}
BODY = {"namespace": NAMESPACE, "memory_type": "preference", "subject": "user", "predicate": "prefers",
        "object": "careful architecture notes", "evidence_text": "User prefers careful architecture notes.", "write_mode": "candidate"}


def send(url, raw, body=None, headers=None):
    return request(url, "POST", "/v1/remember", token=raw, payload=BODY if body is None else body, headers=HEADERS if headers is None else headers)


def conform(result):
    document = onboarding_document(openapi_schema())
    validate(document)
    shape = document["paths"]["/v1/remember"]["post"]["responses"][str(result["status"])]["content"]["application/json"]["schema"]
    Draft202012Validator({**shape, "components": document["components"]}).validate(result["body"])
    assert result["headers"]["Cache-Control"] == "no-store"
    assert result["headers"]["X-Request-ID"] == result["body"]["request_id"]


def test_candidate_profile_creates_no_claim_and_preserves_replay_identity(tmp_path):
    with local_service(tmp_path) as (service, url, tokens):
        first = send(url, tokens["agent"])
        assert first["status"] == 200
        conform(first)
        candidate = first["body"]["data"]["candidate"]
        assert candidate["candidate_status"] == "pending_review"
        assert service.memory.list_claims(namespace=NAMESPACE) == []
        before = domain_state(service.memory)
        replay = send(url, tokens["agent"], headers={**HEADERS, "X-Request-ID": "retry-transport"})
        assert first["body"]["data"] == replay["body"]["data"]
        assert first["body"]["request_id"] != replay["body"]["request_id"]
        assert before == domain_state(service.memory)
        assert send(url, tokens["agent"], {**BODY, "object": "changed"})["status"] == 409
        assert request(url, "GET", "/v1/candidates/" + candidate["id"], token=tokens["agent"])["status"] == 403


@pytest.mark.parametrize("bad", [{"write_mode": "active"}, {"confidence": float("inf")}, {"importance": True},
    {"half_life_days": 0}, {"scope": []}, {"memory_type": "invented"}, {"evidence_text": None}, {"expected_revision": "ignored?"}])
def test_profile_validation_rolls_back_every_domain_write(tmp_path, bad):
    with local_service(tmp_path) as (service, url, tokens):
        before = domain_state(service.memory)
        response = send(url, tokens["agent"], {**BODY, **bad})
        assert response["status"] == 400
        conform(response)
        assert before == domain_state(service.memory)


def test_missing_key_and_permissions_are_explicit(tmp_path):
    with local_service(tmp_path) as (service, url, tokens):
        missing = send(url, tokens["agent"], headers={"X-Aletheia-Contract": "agent-onboarding-v1"})
        assert missing["status"] == 400
        for raw, body in [(tokens["reader"], BODY), (tokens["agent"], {**BODY, "namespace": "user/elsewhere"}),
                          (tokens["agent"], {**BODY, "privacy_level": "secret"})]:
            denied = send(url, raw, body)
            assert denied["status"] == 403
            conform(denied)
        assert service.memory.list_candidates(NAMESPACE) == []


def test_public_creator_and_same_client_credentials_remain_separate(tmp_path):
    with local_service(tmp_path) as (service, url, _):
        client = service.auth.create_client(name="shared creator", client_type="test")
        tokens = [service.auth.create_token(client_id=client.id, namespace_grants=[NAMESPACE], privacy_ceiling="public",
            capabilities=["memory:write_candidate"])[1] for _ in range(2)]
        ids = []
        for raw in tokens:
            created = send(url, raw)
            assert created["status"] == 200
            item = created["body"]["data"]["candidate"]
            assert item["privacy_level"] == "public"
            assert service.memory.read_event(item["evidence_ids"][0]).privacy_level == "public"
            assert send(url, raw)["status"] == 200
            ids.append(item["id"])
        assert ids[0] != ids[1]


@pytest.mark.parametrize("legacy", [False, True])
def test_current_permissions_and_redaction_checked_before_creation_replay(tmp_path, legacy):
    with local_service(tmp_path) as (service, url, _):
        token, raw = credential(service, ["memory:write_candidate"])
        headers = {"Idempotency-Key": "legacy-create"} if legacy else HEADERS
        first = send(url, raw, headers=headers)
        assert first["status"] == 200
        item = first["body"]["data"]["candidate"]
        service.memory.redact(target_type="evidence", target_id=item["evidence_ids"][0], reason="Synthetic redaction", dry_run=False)
        assert send(url, raw, headers=headers)["status"] == 403
        service.auth.revoke_token(token.id)
        assert send(url, raw, headers=headers)["status"] == 401


def test_candidate_creation_failure_is_atomic_and_legacy_extensions_remain_accepted(tmp_path, monkeypatch):
    with local_service(tmp_path) as (service, url, tokens):
        original = service._idempotency_store
        def fail(**kwargs):
            raise RuntimeError("Injected receipt storage failure")
        monkeypatch.setattr(service, "_idempotency_store", fail)
        before = domain_state(service.memory)
        assert send(url, tokens["agent"])["status"] == 500
        assert before == domain_state(service.memory)
        monkeypatch.setattr(service, "_idempotency_store", original)
        assert send(url, tokens["agent"], {**BODY, "optional_legacy_extension": {"future": True}})["status"] == 200


def test_python_sdk_opts_in_and_never_turns_candidate_helper_into_active_write(tmp_path, monkeypatch):
    import aletheia.version as versions
    with local_service(tmp_path) as (_, url, tokens):
        client = AletheiaClient(url, tokens["agent"])
        payload = {key: value for key, value in BODY.items() if key != "write_mode"}
        monkeypatch.setattr(versions, "SUPPORTED_PROFILES", ("memory-read-v1", "memory-review-v1"))
        with pytest.raises(AletheiaUnsupportedFeatureError):
            client.remember_candidate(**payload, contract="agent-onboarding-v1", idempotency_key="sdk-agent")
        monkeypatch.setattr(versions, "SUPPORTED_PROFILES", (*versions.SUPPORTED_PROFILES, "agent-onboarding-v1"))
        result = client.remember_candidate(**payload, contract="agent-onboarding-v1", idempotency_key="sdk-agent")
        assert result["write_mode"] == "candidate"
        with pytest.raises(TypeError):
            client.remember_candidate(**payload, write_mode="active")


def test_lost_creation_receipt_and_concurrent_retries_create_one_candidate(tmp_path, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from http.client import RemoteDisconnected
    from aletheia.service.http import AletheiaRequestHandler
    original, dropped = AletheiaRequestHandler._send_payload, []
    def lose_receipt(handler, status, payload):
        if handler.command == "POST" and handler.path == "/v1/remember" and status == 200 and not dropped:
            dropped.append(payload["data"])
            handler.close_connection = True
            return
        return original(handler, status, payload)
    monkeypatch.setattr(AletheiaRequestHandler, "_send_payload", lose_receipt)
    with local_service(tmp_path) as (service, url, tokens):
        with pytest.raises(RemoteDisconnected):
            send(url, tokens["agent"])
        with ThreadPoolExecutor(2) as pool:
            results = list(pool.map(lambda _: send(url, tokens["agent"]), range(2)))
        assert all(result["status"] == 200 and result["body"]["data"] == dropped[0] for result in results)
        assert len(service.memory.list_candidates(NAMESPACE)) == 1
        assert service.memory.list_claims(namespace=NAMESPACE) == []


def test_foreign_project_session_cannot_authorize_candidate_creation(tmp_path):
    with local_service(tmp_path) as (service, url, _):
        _, token = credential(service, ["memory:write_candidate"], grants=[NAMESPACE + "/projects/alpha"])
        session = service.memory.start_session(namespace=NAMESPACE, project_id="beta")
        before = domain_state(service.memory)
        result = send(url, token, {**BODY, "project_id":"alpha", "session_id":session.id})
        assert result["status"] == 403
        assert domain_state(service.memory) == before
