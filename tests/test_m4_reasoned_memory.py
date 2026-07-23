from __future__ import annotations

import json
import re

import pytest

from aletheia import Memory
from aletheia.cli.main import main
from aletheia.core.errors import ValidationError


NAMESPACE = "user/default"


def _project_memory(memory: Memory):
    milestone = memory.remember(
        namespace=NAMESPACE,
        memory_type="project",
        subject="project:aletheia",
        predicate="current_milestone",
        object="M4",
        confidence=0.92,
        project_id="aletheia",
    )
    name = memory.remember(
        namespace=NAMESPACE,
        memory_type="project",
        subject="M4",
        predicate="name",
        object="Reasoned Memory",
        confidence=0.91,
        project_id="aletheia",
    )
    return milestone, name


def _style_memory(memory: Memory):
    progress = memory.remember(
        namespace=NAMESPACE,
        memory_type="preference",
        subject="user.progress",
        predicate="prefers_response_style",
        object="concise progress updates",
        confidence=0.90,
    )
    architecture = memory.remember(
        namespace=NAMESPACE,
        memory_type="preference",
        subject="user.architecture",
        predicate="prefers_response_style",
        object="comprehensive architecture explanations",
        confidence=0.88,
    )
    return progress, architecture


def test_inference_run_creates_candidates_relations_lineage_and_logs(tmp_path):
    memory = Memory.open(str(tmp_path / "aletheia.db"), namespace=NAMESPACE)
    try:
        _project_memory(memory)
        _style_memory(memory)

        dry = memory.run_inference(
            NAMESPACE,
            engines=["logical", "semantic", "factual", "reflection"],
            project_id="aletheia",
            dry_run=True,
        )
        assert dry.inference_count >= 3
        assert dry.persisted_count == 0
        assert memory.list_inferences(NAMESPACE) == []

        run = memory.run_inference(
            NAMESPACE,
            engines=["logical", "semantic", "factual", "reflection"],
            project_id="aletheia",
            dry_run=False,
        )
        inferences = memory.list_inferences(NAMESPACE)
        assert run.persisted_count == run.inference_count
        assert {item.engine for item in inferences} >= {"logical", "factual"}
        assert any(item.inference_type == "reflection" for item in inferences)
        assert all(item.status == "pending_review" for item in inferences)
        assert all(item.source_claim_ids or item.source_evidence_ids for item in inferences)

        factual = next(item for item in inferences if item.engine == "factual")
        assert factual.inference_strength == "entailed"
        assert factual.suggested_truth_confidence <= factual.derivation_confidence
        assert factual.source_claim_ids

        relations = memory.list_semantic_relations(namespace=NAMESPACE)
        assert relations
        assert relations[0].relation_type == "related_to"
        assert relations[0].metadata["truth_effect"] == "none"
        assert not any(claim.memory_type == "inference" for claim in memory.list_claims(namespace=NAMESPACE))

        logs = memory.store.connection.execute(
            "SELECT rule_id, inference_count FROM rule_execution_log"
        ).fetchall()
        assert {row["rule_id"] for row in logs} >= {
            "rule_m4_superseded_not_current",
            "rule_m4_semantic_relation",
            "rule_m4_project_focus_factual",
            "rule_m4_reflection_suggestion",
        }
    finally:
        memory.close()


def test_inference_review_promotion_gates_and_explanation(tmp_path):
    memory = Memory.open(str(tmp_path / "aletheia.db"), namespace=NAMESPACE)
    try:
        _project_memory(memory)
        memory.run_inference(NAMESPACE, engines=["factual"], project_id="aletheia", dry_run=False)
        inference = memory.list_inferences(NAMESPACE, engine="factual")[0]

        with pytest.raises(ValidationError):
            memory.promote_inference(inference.id, reason="Unreviewed inference should fail.")

        decision = memory.review_inference(
            inference.id,
            decision="validate",
            reason="Directly supported by active project claims.",
        )
        assert decision.decision == "validate"

        claim = memory.promote_inference(
            inference.id,
            reason="Promote validated entailed M4 focus.",
        )
        assert claim.memory_type == "inference"
        assert claim.status == "active"
        assert memory.read_inference(inference.id).status == "promoted"
        trace = memory.trace_derivation(claim.id, target_type="claim")
        assert any(edge.source_id == inference.id for edge in trace.edges)
        assert trace.root_evidence_ids

        explanation = memory.explain_inference(inference.id)
        assert explanation.can_promote is False
        assert explanation.sources
        assert explanation.rule["id"] == "rule_m4_project_focus_factual"
        explanation_rows = memory.store.connection.execute(
            "SELECT inference_id FROM inference_explanations WHERE inference_id = ?",
            (inference.id,),
        ).fetchall()
        assert explanation_rows

        _style_memory(memory)
        memory.run_inference(NAMESPACE, engines=["reflection"], dry_run=False)
        reflection_inference = memory.list_inferences(
            NAMESPACE,
            engine="reflection",
            status="pending_review",
        )[0]
        memory.review_inference(
            reflection_inference.id,
            decision="mark_speculative",
            reason="Needs human review.",
        )
        with pytest.raises(ValidationError):
            memory.promote_inference(reflection_inference.id, target_type="reflection", reason="Nope.")
    finally:
        memory.close()


def test_inference_edits_cannot_bypass_review_or_validation_gates(tmp_path):
    memory = Memory.open(str(tmp_path / "aletheia.db"), namespace=NAMESPACE)
    try:
        _project_memory(memory)
        memory.run_inference(NAMESPACE, engines=["factual"], project_id="aletheia", dry_run=False)
        inference = memory.list_inferences(NAMESPACE, engine="factual")[0]

        with pytest.raises(ValidationError):
            memory.review_inference(
                inference.id,
                decision="edit",
                reason="Attempt terminal status bypass.",
                edits={"status": "promoted"},
            )
        with pytest.raises(ValidationError):
            memory.review_inference(
                inference.id,
                decision="edit",
                reason="Attempt invalid confidence.",
                edits={"derivation_confidence": 1.5},
            )
        assert memory.read_inference(inference.id).status == "pending_review"
    finally:
        memory.close()


def test_rules_register_toggle_execute_and_repeat_safely(tmp_path):
    memory = Memory.open(str(tmp_path / "aletheia.db"), namespace=NAMESPACE)
    try:
        claim, _ = _project_memory(memory)
        rule = memory.define_rule(
            NAMESPACE,
            name="project_claim_is_current",
            rule_type="logical",
            description="A project claim can be inspected for currentness.",
            condition={"status": "active"},
            conclusion={"predicate": "is_current"},
        )
        assert rule.enabled is True
        assert memory.set_rule_enabled(rule.id, enabled=False).enabled is False
        assert memory.set_rule_enabled(rule.id, enabled=True).enabled is True

        first = memory.run_rule(rule.id, namespace=NAMESPACE, target_claim_ids=[claim.id], dry_run=False)
        second = memory.run_rule(rule.id, namespace=NAMESPACE, target_claim_ids=[claim.id], dry_run=False)
        assert first.inference_count == second.inference_count
        assert len(memory.list_inferences(NAMESPACE, source_claim_id=claim.id)) >= 1
        default_rule_ids = {item.id for item in memory.list_rules(namespace=NAMESPACE)}
        assert "rule_m4_source_invalidation_propagates" in default_rule_ids
    finally:
        memory.close()


def test_reflection_abstraction_context_and_derivation_metadata(tmp_path):
    memory = Memory.open(str(tmp_path / "aletheia.db"), namespace=NAMESPACE)
    try:
        progress, architecture = _style_memory(memory)
        reflection = memory.build_reflection(
            NAMESPACE,
            source_claim_ids=[progress.id, architecture.id],
            title="Context-sensitive response depth",
            text="User prefers concise progress updates and comprehensive architecture explanations.",
            abstraction_level=2,
            reason="Combines response-style preferences.",
            require_review=False,
        )
        assert reflection.status == "active"
        assert reflection.source_claim_ids == sorted([progress.id, architecture.id])
        assert reflection.confidence_effective == pytest.approx(
            min(
                memory.compute_confidence(progress.id).effective_confidence,
                memory.compute_confidence(architecture.id).effective_confidence,
            )
        )

        expansion = memory.expand_reflection(reflection.id)
        assert {claim.id for claim in expansion.source_claims} == {progress.id, architecture.id}
        assert expansion.source_evidence
        assert expansion.derivation_edges

        abstraction = memory.create_abstraction(
            NAMESPACE,
            source_ids=[reflection.id],
            source_type="reflection",
            abstraction_text="Response depth is context-sensitive.",
            abstraction_level=3,
            reason="Higher-level pattern.",
        )
        assert abstraction.information_loss_policy == "lossless_via_backlinks"
        assert abstraction.source_ids == [reflection.id]

        pack = memory.context_pack(
            namespace=NAMESPACE,
            query="architecture explanations",
            include_derivation_metadata=True,
        )
        assert any(item.reflection_id == reflection.id for item in pack.reflection_memory)
        reflected = pack.reflection_memory[0]
        assert reflected.source_kind == "reflection"
        assert reflected.derivation["root_evidence_ids"]
        assert all(item.source_kind != "inference" for item in pack.items())
    finally:
        memory.close()


def test_invalidation_propagates_to_reflections_queue_and_context(tmp_path):
    memory = Memory.open(str(tmp_path / "aletheia.db"), namespace=NAMESPACE)
    try:
        progress, architecture = _style_memory(memory)
        reflection = memory.build_reflection(
            NAMESPACE,
            source_claim_ids=[progress.id, architecture.id],
            title="Context-sensitive response depth",
            text="User prefers context-sensitive response depth.",
            reason="Source-backed reflection.",
            require_review=False,
        )
        replacement = memory.remember(
            namespace=NAMESPACE,
            memory_type="preference",
            subject=progress.subject,
            predicate=progress.predicate,
            object="concise progress updates but detailed milestone contracts",
            confidence=0.93,
        )
        memory.supersede_claim(progress.id, replacement.id, reason="Newer refined preference.")

        stale = memory.get_reflection(reflection.id)
        assert stale.status == "stale"
        invalidations = memory.list_invalidations(namespace=NAMESPACE, target_id=reflection.id, target_type="reflection")
        assert invalidations
        queued = memory.store.connection.execute(
            "SELECT * FROM refresh_queue WHERE target_id = ? AND target_type = 'reflection'",
            (reflection.id,),
        ).fetchall()
        assert queued

        pack = memory.context_pack(namespace=NAMESPACE, query="response depth")
        assert all(item.reflection_id != reflection.id for item in pack.reflection_memory)
        assert any(warning.warning_type == "reflection_stale" for warning in pack.warnings)
    finally:
        memory.close()


def test_m4_migration_is_idempotent_and_does_not_auto_reason(tmp_path):
    db = str(tmp_path / "aletheia.db")
    first = Memory.open(db, namespace=NAMESPACE)
    try:
        first.remember(
            namespace=NAMESPACE,
            memory_type="preference",
            subject="user",
            predicate="prefers_response_style",
            object="practical and direct",
        )
        assert first.health()["schema_version"] == "1.3.0"
    finally:
        first.close()

    second = Memory.open(db, namespace=NAMESPACE)
    try:
        assert second.health()["schema_version"] == "1.3.0"
        assert second.retrieve(namespace=NAMESPACE, query="practical and direct")
        assert second.list_inferences(NAMESPACE) == []
        assert second.list_reflections(namespace=NAMESPACE) == []
        assert {rule.id for rule in second.list_rules(namespace=NAMESPACE)} >= {
            "rule_m4_superseded_not_current",
            "rule_m4_semantic_relation",
            "rule_m4_project_focus_factual",
        }
    finally:
        second.close()


def test_m4_cli_groups_work(tmp_path, capsys):
    db = str(tmp_path / "aletheia.db")
    assert main(["init", "--db", db]) == 0
    assert '"schema_version": "1.3.0"' in capsys.readouterr().out

    assert main(
        [
            "remember",
            "--db",
            db,
            "--namespace",
            NAMESPACE,
            "--type",
            "preference",
            "--subject",
            "user.progress",
            "--predicate",
            "prefers_response_style",
            "--object",
            "concise progress updates",
        ]
    ) == 0
    progress_id = re.search(r"\[(clm_[^\]]+)\]", capsys.readouterr().out).group(1)
    assert main(
        [
            "remember",
            "--db",
            db,
            "--namespace",
            NAMESPACE,
            "--type",
            "preference",
            "--subject",
            "user.architecture",
            "--predicate",
            "prefers_response_style",
            "--object",
            "comprehensive architecture explanations",
        ]
    ) == 0
    architecture_id = re.search(r"\[(clm_[^\]]+)\]", capsys.readouterr().out).group(1)

    assert main(
        [
            "reflect",
            "build",
            "--db",
            db,
            "--namespace",
            NAMESPACE,
            "--title",
            "Context-sensitive response depth",
            "--claims",
            f"{progress_id},{architecture_id}",
            "--text",
            "User prefers response depth to match context.",
            "--reason",
            "Combines response-style memories.",
            "--json",
        ]
    ) == 0
    reflection = json.loads(capsys.readouterr().out)
    assert reflection["status"] == "active"

    assert main(
        [
            "infer",
            "run",
            "--db",
            db,
            "--namespace",
            NAMESPACE,
            "--engines",
            "logical,semantic,reflection",
            "--apply",
            "--json",
        ]
    ) == 0
    run = json.loads(capsys.readouterr().out)
    assert run["persisted_count"] > 0

    assert main(["rules", "list", "--db", db, "--namespace", NAMESPACE, "--json"]) == 0
    assert any(rule["id"] == "rule_m4_semantic_relation" for rule in json.loads(capsys.readouterr().out))

    assert main(["clusters", "relations", "--db", db, "--namespace", NAMESPACE, "--json"]) == 0
    assert json.loads(capsys.readouterr().out)

    assert main(
        [
            "abstractions",
            "create",
            "--db",
            db,
            "--namespace",
            NAMESPACE,
            "--sources",
            reflection["id"],
            "--source-type",
            "reflection",
            "--text",
            "Response depth is context-sensitive.",
            "--level",
            "3",
            "--reason",
            "Compress reflection.",
            "--json",
        ]
    ) == 0
    abstraction = json.loads(capsys.readouterr().out)
    assert abstraction["information_loss_policy"] == "lossless_via_backlinks"

    assert main(
        [
            "derivation",
            "trace",
            reflection["id"],
            "--db",
            db,
            "--type",
            "reflection",
            "--json",
        ]
    ) == 0
    assert json.loads(capsys.readouterr().out)["root_evidence_ids"]
