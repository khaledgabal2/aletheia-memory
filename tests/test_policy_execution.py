"""Applied policy versions must change observable reads and evaluation."""
from contextlib import closing
import json

import pytest

from aletheia import Memory
from aletheia.core.errors import ValidationError
from aletheia.models import ServiceConfig
from aletheia.service.http import AletheiaService

NS = "audit/policy"
QUERY = "policyneedle"


@pytest.fixture
def memory(tmp_path):
    with closing(Memory.open(str(tmp_path / "memory.db"), namespace=NS)) as value:
        yield value


def seed(memory):
    rows = []
    for name, confidence, importance in [("reliable", .99, .01), ("important", .25, 1.0)]:
        event = memory.write_event(namespace=NS, source_type="fixture", content=QUERY + " " + name)
        rows.append(memory.write_claim(namespace=NS, subject=name, predicate="records", object=QUERY,
            memory_type="fact", evidence_ids=[event.id], confidence=confidence, importance=importance))
    memory.index_semantic(NS, provider="mock")
    return rows


def proposal(memory, config, kind="ranking", evaluation=None):
    item = memory.propose_policy_update(NS, policy_type=kind,
        target_policy_id="rpol_default" if kind == "ranking" else "cpol_default",
        proposed_config=config, reason="synthetic policy", evaluation_run_id=evaluation)
    return memory.review_policy_proposal(item.id, decision="approve", reason="synthetic approval")


def apply(memory, config, kind="ranking"):
    item = proposal(memory, config, kind)
    return memory.apply_policy_proposal(item.id, reason="synthetic application", require_evaluation_pass=False)


def weights(memory, **selected):
    baseline = memory.get_ranking_policy_version("rpv_default_v1")
    return {**dict.fromkeys(baseline.weights, 0.0), **selected}


@pytest.mark.parametrize("mode", ["lexical", "semantic", "hybrid"])
def test_applied_zero_weights_change_scores_in_every_mode(memory, mode):
    seed(memory)
    assert any(row.score > 0 for row in memory.retrieve(NS, QUERY, mode=mode))
    apply(memory, {"weights": weights(memory)})
    results = memory.retrieve(NS, QUERY, mode=mode)
    assert len(results) == 2
    assert [row.score for row in results] == [0.0, 0.0]


@pytest.mark.parametrize("mode", ["lexical", "semantic", "hybrid"])
def test_versions_change_order_and_explicit_version_and_rollback_restore_it(memory, mode):
    reliable, important = seed(memory)
    first = apply(memory, {"weights": weights(memory, effective_confidence=1.0)})
    assert memory.retrieve(NS, QUERY, mode=mode, limit=1)[0].claim_id == reliable.id
    second = apply(memory, {"weights": weights(memory, retrieval_salience=1.0)})
    assert memory.retrieve(NS, QUERY, mode=mode, limit=1)[0].claim_id == important.id
    assert memory.retrieve(NS, QUERY, mode=mode, limit=1, policy_version_id=first.new_version_id)[0].claim_id == reliable.id
    memory.rollback_policy(NS, policy_id="rpol_default", target_version_id=first.new_version_id, reason="fixture")
    assert memory.retrieve(NS, QUERY, mode=mode, limit=1)[0].claim_id == reliable.id
    assert memory.get_ranking_policy_version(second.new_version_id).weights["retrieval_salience"] == 1.0


def test_evaluation_executes_the_selected_version_and_records_it(memory):
    reliable, important = seed(memory)
    first = apply(memory, {"weights": weights(memory, effective_confidence=1.0)})
    apply(memory, {"weights": weights(memory, retrieval_salience=1.0)})
    evaluation = memory.create_eval_set(NS, name="policy selection")
    memory.add_eval_case(evaluation.id, query=QUERY, expected_claim_ids=[reliable.id])
    run = memory.run_evaluation(NS, eval_set_id=evaluation.id, policy_version_id=first.new_version_id,
        retrieval_mode="hybrid", context_pack=False, limit=1)
    assert run.passed and run.metrics["recall_at_1"] == 1.0
    row = memory.store.connection.execute("SELECT retrieved_ids_json FROM evaluation_results WHERE evaluation_run_id = ?", (run.id,)).fetchone()
    assert json.loads(row[0]) == [reliable.id]
    assert run.policy_version_id == first.new_version_id


def test_context_selection_uses_ranking_and_context_configuration(memory):
    reliable, important = seed(memory)
    first = apply(memory, {"weights": weights(memory, effective_confidence=1.0)})
    apply(memory, {"weights": weights(memory, retrieval_salience=1.0)})
    pack = memory.context_pack(NS, QUERY, policy_version_id=first.new_version_id, token_budget=10)
    assert pack.items()[0].claim_id == reliable.id
    context = apply(memory, {"token_budget": 1, "include_reflections": False}, "context_pack")
    pack = memory.context_pack(NS, QUERY)
    assert pack.context_policy_version_id == context.new_version_id
    assert pack.token_budget == 1 and not pack.items()
    assert memory.context_pack(NS, QUERY, token_budget=200).items()


@pytest.mark.parametrize("config", [
    {"weights": {"lexical_score": -1}}, {"weights": {"lexical_score": float("nan")}},
    {"weights": {"lexical_score": float("inf")}}, {"weights": {"lexical_score": True}},
    {"weights": {"lexical_score": 10 ** 1000}}, {"weights": {"lexical_score": 1e308, "semantic_score": 1e308}},
    {"weights": {"lexcial_score": 1}}, {"weights": {"lexical_score": "1"}},
    {"filters": {"exclude_rejected": False}}, {"unknown_option": 1},
])
def test_invalid_or_unsupported_policy_is_not_activated(memory, config):
    item = proposal(memory, config)
    before = memory.get_ranking_policy("rpol_default").active_version_id
    with pytest.raises(ValidationError):
        memory.apply_policy_proposal(item.id, reason="fixture", require_evaluation_pass=False)
    assert memory.get_ranking_policy("rpol_default").active_version_id == before
    assert memory.get_policy_proposal(item.id).status == "approved"
    assert not memory.list_policy_applications(namespace=NS)


def test_policy_application_is_atomic_on_failure(memory, monkeypatch):
    item = proposal(memory, {"weights": weights(memory, retrieval_salience=1.0)})
    tables = ("ranking_policy_versions", "ranking_policies", "policy_proposals", "policy_application_history", "rollback_records", "audit_log")
    snapshot = lambda: {name:[tuple(row) for row in memory.store.connection.execute("SELECT * FROM " + name)] for name in tables}
    before = snapshot()
    original = memory._write_audit
    def fail(**kwargs):
        if kwargs["action"] == "policy.apply":
            raise RuntimeError("synthetic audit failure")
        return original(**kwargs)
    monkeypatch.setattr(memory, "_write_audit", fail)
    with pytest.raises(RuntimeError, match="synthetic audit failure"):
        memory.apply_policy_proposal(item.id, reason="fixture", require_evaluation_pass=False)
    assert snapshot() == before


def test_apply_evaluates_the_proposed_version_instead_of_reusing_baseline_success(memory):
    reliable, _ = seed(memory)
    evaluation = memory.create_eval_set(NS, name="application gate")
    memory.add_eval_case(evaluation.id, query=QUERY, expected_claim_ids=[reliable.id])
    baseline = memory.run_evaluation(NS, eval_set_id=evaluation.id)
    item = proposal(memory, {"weights": weights(memory, retrieval_salience=1.0)}, evaluation=baseline.id)
    applied = memory.apply_policy_proposal(item.id, reason="fixture")
    version = memory.get_ranking_policy_version(applied.new_version_id)
    checked = memory.read_evaluation_run(version.evaluation_summary["evaluation_run_id"])
    assert checked.id != baseline.id
    assert checked.policy_version_id == version.id
    assert checked.metrics["recall_at_1"] == 0.0


def test_gate_failure_rolls_back_version_activation_and_evaluation_effects(memory):
    reliable, orphan = seed(memory)
    with memory.store.transaction():
        memory.store.connection.execute("DELETE FROM claim_evidence_links WHERE claim_id = ?", (orphan.id,))
    evaluation = memory.create_eval_set(NS, name="governance gate")
    memory.add_eval_case(evaluation.id, query=QUERY, expected_claim_ids=[reliable.id], forbidden_claim_ids=[orphan.id])
    baseline = memory.run_evaluation(NS, eval_set_id=evaluation.id)
    assert baseline.passed
    item = proposal(memory, {"filters": {"require_provenance": False}}, evaluation=baseline.id)
    before = memory.get_ranking_policy("rpol_default").active_version_id
    runs = memory.list_evaluation_runs(namespace=NS)
    with pytest.raises(ValidationError, match="proposed policy version failed"):
        memory.apply_policy_proposal(item.id, reason="fixture")
    assert memory.get_ranking_policy("rpol_default").active_version_id == before
    assert memory.get_policy_proposal(item.id).status == "approved"
    assert not memory.list_policy_applications(namespace=NS)
    assert memory.list_evaluation_runs(namespace=NS) == runs


def test_context_versions_are_used_by_evaluation_and_rollback(memory, monkeypatch):
    seed(memory)
    original_id = memory.context_pack(NS, QUERY).context_policy_version_id
    applied = apply(memory, {"token_budget": 1}, "context_pack")
    packs = []
    original = memory.context_pack
    def capture(*args, **kwargs):
        result = original(*args, **kwargs)
        packs.append(result)
        return result
    monkeypatch.setattr(memory, "context_pack", capture)
    evaluation = memory.create_eval_set(NS, name="context defaults")
    memory.add_eval_case(evaluation.id, query=QUERY)
    run = memory.run_evaluation(NS, eval_set_id=evaluation.id)
    assert packs and all(pack.token_budget == 1 and not pack.items() for pack in packs)
    assert run.metadata["context_policy_version_id"] == applied.new_version_id
    assert memory.context_pack(NS, QUERY, context_policy_version_id=original_id).items()
    memory.rollback_policy(NS, policy_id="cpol_default", target_version_id=original_id, reason="fixture")
    assert memory.context_pack(NS, QUERY).items()


@pytest.mark.parametrize("config", [{"token_budget": 0}, {"token_budget": True}, {"token_budget": 12001},
                                    {"include_reflections": "false"}, {"preserve_governance": False},
                                    {"filters": {"exclude_invalid": False}}])
def test_invalid_context_config_is_not_applied(memory, config):
    before = memory.context_pack(NS, QUERY).context_policy_version_id
    item = proposal(memory, config, "context_pack")
    with pytest.raises(ValidationError):
        memory.apply_policy_proposal(item.id, reason="fixture", require_evaluation_pass=False)
    assert memory.context_pack(NS, QUERY).context_policy_version_id == before


@pytest.mark.parametrize("mode", ["lexical", "semantic", "hybrid"])
def test_configured_duplicate_penalty_changes_actual_score(memory, mode):
    reliable, _ = seed(memory)
    peer = memory.remember(namespace=NS, memory_type="fact", subject="unrelated", predicate="is", object="fixture")
    with memory.store.transaction():
        memory._create_relationship(source_claim_id=reliable.id, target_claim_id=peer.id,
                                    relationship_type="duplicate_of", reason="fixture")
    apply(memory, {"weights": weights(memory, duplicate_penalty=1.0)})
    result = next(row for row in memory.retrieve(NS, QUERY, mode=mode) if row.claim_id == reliable.id)
    assert result.score == -1.0


@pytest.mark.parametrize("global_access", [False, True])
def test_http_global_policy_application_requires_global_authority(memory, global_access):
    seed(memory)
    item = proposal(memory, {"token_budget": 1}, "context_pack")
    service = AletheiaService(memory, ServiceConfig(db_path=memory.store.path, rate_limit_enabled=False))
    principal = service.auth.create_client(name="fixture", client_type="test")
    _, token = service.auth.create_token(client_id=principal.id, capabilities=["memory:policy", "memory:context"],
        namespace_grants=["*" if global_access else NS])
    headers = {"Authorization": f"Bearer {token}"}
    status, response = service.handle_http(method="POST", path=f"/v1/policies/proposals/{item.id}/apply", headers=headers,
        body=json.dumps({"reason": "fixture", "require_evaluation_pass": False}).encode())
    assert status == (200 if global_access else 403), response
    if global_access:
        status, response = service.handle_http(method="POST", path="/v1/context-pack", headers=headers,
            body=json.dumps({"namespace": NS, "query": QUERY}).encode())
        assert status == 200 and all(not items for items in response["data"]["sections"].values()), response
    else:
        assert memory.get_policy_proposal(item.id).status == "approved"


@pytest.mark.parametrize("command", ["context", "context-pack"])
def test_cli_context_omitted_budget_uses_applied_policy(memory, capsys, command):
    from aletheia.cli.main import main
    seed(memory)
    apply(memory, {"token_budget": 1}, "context_pack")
    query_args = ["--query", QUERY] if command == "context" else [QUERY]
    assert main([command, *query_args, "--db", memory.store.path, "--namespace", NS, "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["token_budget"] == 1
