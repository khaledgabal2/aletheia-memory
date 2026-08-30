"""Phase 0 scope integrity and authentic legacy SDK execution, not profile certification."""

import hashlib
import json
from pathlib import Path
import socket

import pytest

from scripts.v1_4_phase0 import NAMESPACE, lifecycle, load_legacy_client, local_service


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests/fixtures/v1_3_1"


def test_published_legacy_sdk_fixture_is_unmodified():
    provenance = json.loads((FIXTURES / "provenance.json").read_text())
    assert provenance["version"] == "1.3.1"
    assert hashlib.sha256((FIXTURES / "client.py").read_bytes()).hexdigest() == provenance["sha256"]


def test_profile_inventory_matches_baseline():
    inventory = json.loads((ROOT / "contracts/v1.4.0/profiles.json").read_text())
    schema = json.loads((FIXTURES / "openapi.json").read_text())
    responses = json.loads((FIXTURES / "responses.json").read_text())
    operations = {op["operation_id"]: op for op in inventory["operations"]}
    assert len(operations) == len(inventory["operations"])
    assert {profile["name"] for profile in inventory["profiles"]} == {
        "memory-read-v1", "memory-review-v1", "agent-onboarding-v1"}
    for profile in inventory["profiles"]:
        assert set(profile["operations"]) <= operations.keys()
    for op in operations.values():
        if op["availability"] != "proposed":
            assert op["method"].lower() in schema["paths"][op["path"]]
        assert op["owner"] == "Aletheia Memory"
        assert op["evidence"]["conformance_status"] == "planned; not passed"
        assert set(op["evidence"]["baseline_response_cases"]) <= responses.keys()
        assert "memory:promote" not in op["permission"]["any_of"]


def test_existing_model_free_lifecycle_never_connects_to_network(tmp_path, monkeypatch):
    def forbidden_connection(*args, **kwargs):
        pytest.fail("The model-free lifecycle attempted a network connection")
    monkeypatch.setattr(socket.socket, "connect", forbidden_connection)
    report = lifecycle(tmp_path / "demo.db")
    assert report["pending_results"] == 0
    assert report["evidence_preserved_after_reopen"] is True


def test_published_131_sdk_against_running_service(tmp_path):
    legacy = load_legacy_client()
    with local_service(tmp_path) as (_, base_url, tokens):
        agent = legacy(base_url, tokens["agent"])
        operator = legacy(base_url, tokens["reviewer"])
        assert agent.check_compatibility()["compatible"] is True
        payload = dict(namespace=NAMESPACE, memory_type="preference", subject="user",
                       predicate="prefers", object="reviewed architecture notes",
                       evidence_text="User prefers reviewed architecture notes.")
        first = agent.remember_candidate(idempotency_key="legacy-create", **payload)
        assert first["candidate"]["candidate_status"] == "pending_review"
        replay = agent.remember_candidate(idempotency_key="legacy-create", **payload)
        assert replay == first
        assert agent.retrieve(namespace=NAMESPACE, query="architecture", mode="lexical") == []
        claim = operator.promote_candidate(first["candidate"]["id"], reason="Explicit operator decision")
        hits = agent.retrieve(namespace=NAMESPACE, query="architecture", mode="lexical")
        assert hits[0]["claim_id"] == claim["id"]
        pack = agent.context_pack(namespace=NAMESPACE, query="architecture", retrieval_mode="lexical")
        assert claim["id"] in [item["claim_id"] for item in pack["items"]]
        assert agent.explain_claim(claim["id"])
        assert agent.audit("claim", claim["id"])["audit"]
