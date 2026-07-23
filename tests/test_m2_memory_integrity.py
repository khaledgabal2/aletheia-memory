from __future__ import annotations

import json
import re
from datetime import timedelta

import pytest

from aletheia import Memory
from aletheia.cli.main import main
from aletheia.core.errors import ValidationError
from aletheia.core.time import utc_now


def test_compute_confidence_applies_half_life_decay_and_policy(tmp_path):
    memory = Memory.open(str(tmp_path / "aletheia.db"))
    try:
        claim = memory.remember(
            namespace="user/default",
            memory_type="preference",
            subject="user",
            predicate="prefers_response_style",
            object="direct",
            confidence=0.9,
        )
        memory.set_half_life_policy(
            namespace="user/default",
            memory_type="preference",
            half_life_days=1,
            reason="Test rapid decay.",
        )
        old = (utc_now() - timedelta(days=2)).isoformat()
        memory.store.connection.execute(
            "UPDATE claims SET created_at = ?, last_verified_at = NULL WHERE id = ?",
            (old, claim.id),
        )

        snapshot = memory.compute_confidence(claim.id, explain=True)

        assert snapshot.half_life_days == 1
        assert snapshot.decay_factor < 0.30
        assert snapshot.effective_confidence < claim.confidence_effective
        assert "decay" in snapshot.explanation
    finally:
        memory.close()


def test_feedback_affects_truth_and_salience_with_assistant_guard(tmp_path):
    memory = Memory.open(str(tmp_path / "aletheia.db"))
    try:
        claim = memory.remember(
            namespace="user/default",
            memory_type="preference",
            subject="user",
            predicate="prefers_editor",
            object="vim",
            confidence=0.6,
        )
        before = memory.compute_confidence(claim.id)
        useful = memory.feedback(claim.id, signal="useful", source="user")
        useful_snapshot = memory.compute_confidence(claim.id)
        assert useful.signal == "useful"
        assert useful_snapshot.truth_confidence == pytest.approx(before.truth_confidence)
        assert useful_snapshot.retrieval_salience > before.retrieval_salience

        confirmed = memory.feedback(claim.id, signal="confirmed", source="user")
        confirmed_snapshot = memory.compute_confidence(claim.id)
        assert confirmed.signal == "confirmed"
        assert confirmed_snapshot.truth_confidence > useful_snapshot.truth_confidence

        guarded = memory.remember(
            namespace="user/default",
            memory_type="preference",
            subject="assistant",
            predicate="should_not_self_confirm",
            object="yes",
            confidence=0.6,
        )
        guarded_before = memory.compute_confidence(guarded.id)
        record = memory.feedback(guarded.id, signal="confirmed", source="assistant")
        guarded_after = memory.compute_confidence(guarded.id)
        assert record.strength <= 0.05
        assert memory.read_claim(guarded.id).last_verified_at is None
        assert guarded_after.truth_confidence - guarded_before.truth_confidence < 0.02
    finally:
        memory.close()


def test_confidence_snapshot_and_events_are_persisted(tmp_path):
    memory = Memory.open(str(tmp_path / "aletheia.db"))
    try:
        claim = memory.remember(
            namespace="user/default",
            memory_type="project",
            subject="project:aletheia",
            predicate="current_milestone",
            object="M2",
            confidence=0.85,
        )
        snapshots = memory.recompute_confidence(claim_id=claim.id)

        assert snapshots[0].claim_id == claim.id
        snapshot_count = memory.store.connection.execute(
            "SELECT count(*) AS count FROM confidence_snapshots WHERE claim_id = ?",
            (claim.id,),
        ).fetchone()["count"]
        event_count = memory.store.connection.execute(
            "SELECT count(*) AS count FROM confidence_events WHERE claim_id = ?",
            (claim.id,),
        ).fetchone()["count"]
        assert snapshot_count >= 1
        assert event_count >= 1
    finally:
        memory.close()


def test_conflict_family_detection_and_resolution_preserve_evidence(tmp_path):
    memory = Memory.open(str(tmp_path / "aletheia.db"))
    try:
        first = memory.remember(
            namespace="user/default",
            memory_type="preference",
            subject="user",
            predicate="prefers_response_style",
            object="concise",
            confidence=0.82,
        )
        second = memory.remember(
            namespace="user/default",
            memory_type="preference",
            subject="user",
            predicate="prefers_response_style",
            object="detailed",
            confidence=0.91,
        )

        families = memory.list_conflict_families(namespace="user/default")
        assert len(families) == 1
        assert families[0].conflict_type == "contextual_preference_conflict"
        assert set(families[0].claim_ids) == {first.id, second.id}
        assert memory.retrieve(namespace="user/default", query="response style") == []
        assert memory.context_pack(
            namespace="user/default", query="response style"
        ).warnings

        resolution = memory.resolve_conflict(
            families[0].id,
            strategy="highest_confidence_wins",
            note="Prefer higher confidence.",
        )
        assert resolution.active_claim_id == second.id
        assert memory.read_claim(second.id).status == "active"
        assert memory.read_claim(first.id).status == "superseded"
        assert memory.read_claim(first.id).evidence_ids
        assert memory.list_claim_relationships(first.id)
    finally:
        memory.close()


def test_context_scope_resolution_controls_context_pack(tmp_path):
    memory = Memory.open(str(tmp_path / "aletheia.db"))
    try:
        concise = memory.remember(
            namespace="user/default",
            memory_type="preference",
            subject="user",
            predicate="prefers_response_style",
            object="concise progress updates",
            confidence=0.88,
        )
        detailed = memory.remember(
            namespace="user/default",
            memory_type="preference",
            subject="user",
            predicate="prefers_response_style",
            object="comprehensive architecture explanations",
            confidence=0.90,
        )
        family = memory.list_conflict_families(namespace="user/default")[0]
        memory.resolve_conflict(
            family.id,
            strategy="context_scope",
            note="Concise for progress, comprehensive for architecture.",
        )
        memory.scope_claim(
            detailed.id,
            scope_type="contextual",
            applies_when="architecture_or_design_request",
            reason="Applies to architecture/design requests.",
        )

        architecture_pack = memory.context_pack(
            namespace="user/default",
            query="write an architecture contract and design plan",
        )
        progress_pack = memory.context_pack(
            namespace="user/default",
            query="give a progress update",
        )
        assert any("comprehensive architecture" in item.text for item in architecture_pack.items())
        assert not any("comprehensive architecture" in item.text for item in progress_pack.items())
        assert memory.read_claim(concise.id).status == "disputed"
    finally:
        memory.close()


def test_conflict_resolution_status_reflects_family_state(tmp_path):
    memory = Memory.open(str(tmp_path / "aletheia.db"))
    try:
        first = memory.remember(
            namespace="user/default",
            memory_type="preference",
            subject="user",
            predicate="prefers_response_style",
            object="concise",
            confidence=0.8,
        )
        second = memory.remember(
            namespace="user/default",
            memory_type="preference",
            subject="user",
            predicate="prefers_response_style",
            object="comprehensive",
            confidence=0.8,
        )
        family = memory.list_conflict_families(namespace="user/default")[0]

        unresolved = memory.resolve_conflict(
            family.id,
            strategy="mark_unresolved",
            note="Leave this conflict open for explicit review.",
        )

        assert set(family.claim_ids) == {first.id, second.id}
        assert unresolved.status == "unresolved"
        assert memory.read_conflict_family(family.id).status == "unresolved"
    finally:
        memory.close()


def test_nested_transaction_rolls_back_conflict_resolution(tmp_path):
    memory = Memory.open(str(tmp_path / "aletheia.db"))
    try:
        first = memory.remember(
            namespace="user/default",
            memory_type="preference",
            subject="user",
            predicate="prefers_response_style",
            object="concise",
            confidence=0.8,
        )
        second = memory.remember(
            namespace="user/default",
            memory_type="preference",
            subject="user",
            predicate="prefers_response_style",
            object="comprehensive",
            confidence=0.9,
        )
        family = memory.list_conflict_families(namespace="user/default")[0]

        with pytest.raises(RuntimeError):
            with memory.store.transaction():
                memory.resolve_conflict(
                    family.id,
                    strategy="highest_confidence_wins",
                    note="This nested write should roll back.",
                )
                raise RuntimeError("rollback outer transaction")

        assert memory.read_conflict_family(family.id).status == "unresolved"
        assert memory.read_claim(first.id).status == "disputed"
        assert memory.read_claim(second.id).status == "disputed"
    finally:
        memory.close()


def test_promotion_demotion_status_history_and_core_governance(tmp_path):
    memory = Memory.open(str(tmp_path / "aletheia.db"))
    try:
        candidate = memory.remember(
            namespace="user/default",
            memory_type="preference",
            subject="user",
            predicate="prefers_testing",
            object="live tests after milestones",
            confidence=0.92,
            importance=0.80,
            status="candidate",
        )

        active_decision = memory.promote_claim(
            candidate.id,
            "active",
            reason="Confirmed testing discipline.",
        )
        core_decision = memory.promote_claim(
            candidate.id,
            "core",
            reason="Durable high-confidence workflow preference.",
        )
        archived_decision = memory.demote_claim(
            candidate.id,
            "archived",
            reason="Exercise demotion audit path.",
        )

        assert active_decision.applied
        assert core_decision.decision_type == "promote_to_core"
        assert archived_decision.target_status == "archived"
        history = memory.claim_history(candidate.id)
        assert [row["new_status"] for row in history][-3:] == [
            "active",
            "core",
            "archived",
        ]

        weak = memory.remember(
            namespace="user/default",
            memory_type="preference",
            subject="user",
            predicate="prefers_color",
            object="blue",
            confidence=0.9,
            importance=0.2,
        )
        with pytest.raises(ValidationError):
            memory.promote_claim(weak.id, "core", reason="Too weak for core.")
    finally:
        memory.close()


def test_curate_preview_is_dry_and_apply_mutates(tmp_path):
    memory = Memory.open(str(tmp_path / "aletheia.db"))
    try:
        claim = memory.remember(
            namespace="user/default",
            memory_type="preference",
            subject="user",
            predicate="prefers_ci",
            object="unit plus live tests",
            confidence=0.9,
            importance=0.5,
            status="candidate",
        )
        preview = memory.curate(namespace="user/default", dry_run=True)
        assert preview
        assert memory.read_claim(claim.id).status == "candidate"
        row_count = memory.store.connection.execute(
            "SELECT count(*) AS count FROM curation_decisions"
        ).fetchone()["count"]
        assert row_count == 0

        applied = memory.curate(
            namespace="user/default",
            dry_run=False,
            max_decisions=1,
        )
        assert applied[0].applied
        assert memory.read_claim(claim.id).status == "active"
    finally:
        memory.close()


def test_curate_does_not_force_core_promotion_when_gates_fail(tmp_path):
    memory = Memory.open(str(tmp_path / "aletheia.db"))
    try:
        claim = memory.remember(
            namespace="user/default",
            memory_type="task",
            subject="phase2",
            predicate="needs",
            object="temporary implementation task",
            confidence=0.95,
            importance=0.9,
        )

        decisions = memory.curate(namespace="user/default", dry_run=False, max_decisions=1)

        assert decisions[0].decision_type == "promote_to_core"
        assert decisions[0].applied is False
        assert decisions[0].force is False
        assert "not durable enough for core" in decisions[0].metadata["skipped_reason"]
        assert memory.read_claim(claim.id).status == "active"
    finally:
        memory.close()


def test_duplicate_detection_creates_relationship_without_dispute(tmp_path):
    memory = Memory.open(str(tmp_path / "aletheia.db"))
    try:
        first = memory.remember(
            namespace="user/default",
            memory_type="project",
            subject="project:aletheia",
            predicate="uses_language",
            object="Python",
        )
        second = memory.remember(
            namespace="user/default",
            memory_type="project",
            subject="project:aletheia",
            predicate="uses_language",
            object="Python",
        )

        families = memory.detect_conflicts(namespace="user/default")
        duplicates = [family for family in families if family.conflict_type == "duplicate_claim"]
        assert duplicates
        assert memory.read_claim(first.id).status == "active"
        assert memory.read_claim(second.id).status == "active"
        assert any(
            relationship.relationship_type == "duplicate_of"
            for relationship in memory.list_claim_relationships(second.id)
        )
    finally:
        memory.close()


def test_explain_claim_answers_integrity_questions(tmp_path):
    memory = Memory.open(str(tmp_path / "aletheia.db"))
    try:
        claim = memory.remember(
            namespace="user/default",
            memory_type="procedure",
            subject="assistant",
            predicate="uses_testing_policy",
            object="run live tests after milestones",
            confidence=0.9,
            importance=0.8,
        )
        memory.feedback(claim.id, signal="verified", source="user")
        memory.scope_claim(
            claim.id,
            scope_type="contextual",
            applies_when="implementation_request",
            reason="Testing applies during implementation.",
        )
        explanation = memory.explain_claim(claim.id)

        assert explanation.claim["id"] == claim.id
        assert explanation.evidence
        assert explanation.confidence["truth_confidence"] > 0
        assert explanation.scopes
        assert explanation.history
        assert explanation.audit
    finally:
        memory.close()


def test_m2_cli_confidence_decay_curate_conflicts_and_claim_history(tmp_path, capsys):
    db = str(tmp_path / "aletheia.db")
    assert main(["init", "--db", db]) == 0
    assert main(
        [
            "remember",
            "--db",
            db,
            "--namespace",
            "user/default",
            "--type",
            "preference",
            "--subject",
            "user",
            "--predicate",
            "prefers_response_style",
            "--object",
            "comprehensive architecture explanations",
            "--confidence",
            "0.92",
            "--importance",
            "0.80",
        ]
    ) == 0
    first_output = capsys.readouterr().out
    first_claim_id = re.search(r"\[(clm_[^\]]+)\]", first_output).group(1)

    assert main(["confidence", "show", first_claim_id, "--db", db, "--explain"]) == 0
    confidence_output = capsys.readouterr().out
    assert "truth_confidence:" in confidence_output
    assert "explanation:" in confidence_output

    assert main(
        [
            "confidence",
            "policy",
            "set",
            "--db",
            db,
            "--namespace",
            "user/default",
            "--memory-type",
            "preference",
            "--half-life-days",
            "180",
            "--reason",
            "Preference policy.",
        ]
    ) == 0
    assert "half_life_days: 180.0" in capsys.readouterr().out

    assert main(["decay", "preview", "--db", db, "--namespace", "user/default"]) == 0
    assert "Previewed decay" in capsys.readouterr().out
    assert main(["decay", "run", "--db", db, "--namespace", "user/default"]) == 0
    assert "Persisted decay" in capsys.readouterr().out

    assert main(
        [
            "claims",
            "scope",
            first_claim_id,
            "--db",
            db,
            "--type",
            "contextual",
            "--applies-when",
            "architecture_or_design_request",
            "--reason",
            "Architecture scope.",
        ]
    ) == 0
    assert "architecture_or_design_request" in capsys.readouterr().out

    assert main(["curate", "preview", "--db", db, "--namespace", "user/default"]) == 0
    assert "promote_to_core" in capsys.readouterr().out
    assert main(
        [
            "claims",
            "promote",
            first_claim_id,
            "--db",
            db,
            "--to",
            "core",
            "--reason",
            "Stable scoped architecture preference.",
        ]
    ) == 0
    assert "status: core" in capsys.readouterr().out
    assert main(["claims", "history", first_claim_id, "--db", db]) == 0
    assert "active -> core" in capsys.readouterr().out

    assert main(
        [
            "remember",
            "--db",
            db,
            "--namespace",
            "user/default",
            "--type",
            "preference",
            "--subject",
            "user",
            "--predicate",
            "prefers_response_style",
            "--object",
            "concise progress updates",
        ]
    ) == 0
    capsys.readouterr()
    assert main(["conflicts", "detect", "--db", db, "--namespace", "user/default"]) == 0
    detect_output = capsys.readouterr().out
    assert "conf_" in detect_output

    assert main(["claims", "show", first_claim_id, "--db", db]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["id"] == first_claim_id
