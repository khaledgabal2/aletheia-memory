from __future__ import annotations

import json
import threading
import time
from types import MethodType

import pytest

from aletheia import Memory
from aletheia.cli.main import main
from aletheia.core.errors import ValidationError


NAMESPACE = "user/default"

REQUIRED_M5_TABLES = {
    "memory_usage_events",
    "context_usage_events",
    "task_outcomes",
    "retrieval_judgments",
    "evaluation_sets",
    "evaluation_cases",
    "evaluation_runs",
    "evaluation_results",
    "evaluation_metrics",
    "ranking_policies",
    "ranking_policy_versions",
    "context_pack_policies",
    "context_pack_policy_versions",
    "policy_proposals",
    "policy_application_history",
    "procedure_versions",
    "procedure_update_proposals",
    "learning_runs",
    "optimization_runs",
    "learning_gate_results",
    "local_jobs",
    "memory_health_snapshots",
    "rollback_records",
}

REQUIRED_EVAL_METRICS = {
    "recall_at_1",
    "recall_at_3",
    "recall_at_5",
    "precision_at_5",
    "mean_reciprocal_rank",
    "forbidden_memory_leak_rate",
    "disputed_memory_leak_rate",
    "superseded_memory_leak_rate",
    "stale_memory_leak_rate",
    "provenance_preservation_rate",
    "context_section_accuracy",
    "token_efficiency",
    "average_latency_ms",
}


def _seed_contract_memories(memory: Memory) -> tuple[str, str]:
    memory.create_project(NAMESPACE, "aletheia", title="Aletheia Memory Library")
    architecture = memory.remember(
        namespace=NAMESPACE,
        memory_type="preference",
        subject="user.architecture",
        predicate="prefers_response_style",
        object="comprehensive architecture and design contract explanations",
        confidence=0.94,
        importance=0.9,
        project_id="aletheia",
    )
    progress = memory.remember(
        namespace=NAMESPACE,
        memory_type="preference",
        subject="user.progress",
        predicate="prefers_response_style",
        object="concise progress updates only",
        confidence=0.90,
        importance=0.8,
    )
    return architecture.id, progress.id


def _create_passing_eval(memory: Memory, expected_claim_id: str):
    eval_set = memory.create_eval_set(
        NAMESPACE,
        name="m5_contracts",
        description="Golden adaptive-memory checks for M5.",
        project_id="aletheia",
    )
    memory.add_eval_case(
        eval_set.id,
        query="architecture design contract explanations",
        expected_claim_ids=[expected_claim_id],
        expected_sections={
            "project_memory": ["comprehensive architecture"],
        },
        project_id="aletheia",
        tags=["golden"],
    )
    return eval_set


def test_m5_migration_creates_default_policies_and_no_learning_runs(tmp_path):
    db_path = str(tmp_path / "aletheia.db")
    memory = Memory.open(db_path, namespace=NAMESPACE)
    memory.close()

    memory = Memory.open(db_path, namespace=NAMESPACE)
    try:
        assert memory.health()["schema_version"] == "1.3.0"
        rows = memory.store.connection.execute(
            "SELECT name FROM sqlite_master WHERE type IN ('table', 'virtual table')"
        ).fetchall()
        names = {row["name"] for row in rows}
        assert REQUIRED_M5_TABLES.issubset(names)

        policies = memory.list_ranking_policies(namespace=NAMESPACE)
        assert [policy.id for policy in policies] == ["rpol_default"]
        assert policies[0].active_version_id == "rpv_default_v1"
        assert memory.get_ranking_policy_version("rpv_default_v1").status == "active"
        memory.store.connection.execute(
            """
            INSERT INTO ranking_policies (id, namespace, name, active_version_id, created_at, updated_at)
            VALUES ('rpol_alt', ?, 'Alternate Ranking', 'rpv_alt_v1', '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z')
            """,
            (NAMESPACE,),
        )
        memory.store.connection.execute(
            """
            INSERT INTO ranking_policy_versions (
                id, policy_id, version, weights_json, filters_json, thresholds_json,
                created_by, status, evaluation_summary_json, created_at
            )
            VALUES (
                'rpv_alt_v1', 'rpol_alt', 1, '{"recency": 1.0}', '{}', '{}',
                'pytest', 'active', '{}', '2026-01-01T00:00:00Z'
            )
            """
        )
        assert memory._active_ranking_policy_version_id("rpol_alt") == "rpv_alt_v1"
        assert memory._active_ranking_policy_version_id() == "rpv_default_v1"

        context_policy = memory.store.connection.execute(
            "SELECT active_version_id FROM context_pack_policies WHERE id = 'cpol_default'"
        ).fetchone()
        assert context_policy["active_version_id"] == "cpv_default_v1"
        assert memory.list_learning_runs(namespace=NAMESPACE) == []
        assert memory.store.connection.execute("SELECT count(*) AS count FROM optimization_runs").fetchone()[
            "count"
        ] == 0

        memory.store.migrate()
        assert memory.health()["schema_version"] == "1.3.0"
        assert len(memory.list_ranking_policy_versions("rpol_default")) == 1
    finally:
        memory.close()


def test_usage_outcome_and_retrieval_judgment_do_not_confirm_truth(tmp_path):
    memory = Memory.open(str(tmp_path / "aletheia.db"), namespace=NAMESPACE)
    try:
        claim_id, _ = _seed_contract_memories(memory)
        before = memory.read_claim(claim_id)

        pack = memory.context_pack(
            namespace=NAMESPACE,
            project_id="aletheia",
            query="architecture design contract",
            retrieval_mode="hybrid",
            record_usage=True,
            explain_policy=True,
        )
        assert pack.id
        assert pack.ranking_policy_version_id == "rpv_default_v1"
        assert pack.context_policy_version_id == "cpv_default_v1"
        assert claim_id in pack.metadata["included_item_ids"]

        context_events = memory.store.connection.execute(
            "SELECT * FROM context_usage_events WHERE context_pack_id = ?",
            (pack.id,),
        ).fetchall()
        assert len(context_events) == 1
        usage_events = memory.list_usage(context_pack_id=pack.id)
        assert any(event.target_id == claim_id for event in usage_events)

        explicit_usage = memory.record_usage(
            NAMESPACE,
            target_id=claim_id,
            target_type="claim",
            usage_type="used_by_agent",
            query="architecture design contract",
            context_pack_id=pack.id,
            rank=1,
        )
        assert memory.read_usage(explicit_usage.id).target_id == claim_id

        outcome = memory.record_outcome(
            NAMESPACE,
            task_id="task_m5_success",
            outcome="success",
            used_context_pack_id=pack.id,
            project_id="aletheia",
            note="Context pack included the right M5 project state.",
        )
        assert outcome.used_context_pack_id == pack.id
        assert memory.read_claim(claim_id).confidence_base == before.confidence_base

        judgment = memory.judge_retrieval(
            NAMESPACE,
            query="architecture design contract",
            result_id=claim_id,
            result_type="claim",
            judgment="useful",
            expected_rank=1,
        )
        assert judgment.query == "architecture design contract"
        assert memory.list_retrieval_judgments(namespace=NAMESPACE, result_id=claim_id)[0].id == judgment.id
        assert memory.read_claim(claim_id).confidence_base == before.confidence_base
    finally:
        memory.close()


def test_evaluation_optimization_policy_application_and_bad_gate(tmp_path):
    memory = Memory.open(str(tmp_path / "aletheia.db"), namespace=NAMESPACE)
    try:
        expected_id, forbidden_id = _seed_contract_memories(memory)
        eval_set = _create_passing_eval(memory, expected_id)

        run = memory.run_evaluation(NAMESPACE, eval_set_id=eval_set.id, retrieval_mode="hybrid")
        assert run.passed is True
        assert REQUIRED_EVAL_METRICS.issubset(run.metrics)
        assert run.metrics["recall_at_5"] == pytest.approx(1.0)
        assert memory.store.connection.execute(
            "SELECT count(*) AS count FROM evaluation_results WHERE evaluation_run_id = ?",
            (run.id,),
        ).fetchone()["count"] == 1
        assert memory.store.connection.execute(
            "SELECT count(*) AS count FROM evaluation_metrics WHERE evaluation_run_id = ?",
            (run.id,),
        ).fetchone()["count"] >= len(REQUIRED_EVAL_METRICS)

        baseline = memory.get_ranking_policy("rpol_default").active_version_id
        dry = memory.optimize_retrieval(NAMESPACE, eval_set_id=eval_set.id, dry_run=True)
        assert dry.proposal_id is None
        assert memory.get_ranking_policy("rpol_default").active_version_id == baseline

        optimization = memory.optimize_retrieval(NAMESPACE, eval_set_id=eval_set.id, dry_run=False)
        proposal = memory.get_policy_proposal(optimization.proposal_id)
        assert proposal.status == "pending_review"
        assert proposal.proposed_config["evaluation_summary"]["passed"] is True
        assert memory.get_ranking_policy("rpol_default").active_version_id == baseline
        with pytest.raises(ValidationError):
            memory.apply_policy_proposal(proposal.id, reason="Not reviewed.")

        approved = memory.review_policy_proposal(
            proposal.id,
            decision="approve",
            reason="Passed golden retrieval evaluation.",
        )
        assert approved.status == "approved"
        application = memory.apply_policy_proposal(proposal.id, reason="Activate approved ranking.")
        assert application.old_version_id == baseline
        assert application.new_version_id != baseline
        assert memory.get_ranking_policy("rpol_default").active_version_id == application.new_version_id
        assert memory.list_policy_applications(namespace=NAMESPACE)[0].id == application.id

        rollback = memory.rollback_policy(
            NAMESPACE,
            policy_id="rpol_default",
            target_version_id=baseline,
            reason="Rollback test.",
        )
        assert rollback.to_version_id == baseline
        assert memory.get_ranking_policy("rpol_default").active_version_id == baseline
        assert memory.get_policy_proposal(proposal.id).status == "applied"

        bad_eval = memory.create_eval_set(NAMESPACE, name="m5_bad_policy")
        memory.add_eval_case(
            bad_eval.id,
            query="architecture progress",
            expected_claim_ids=[expected_id],
            forbidden_claim_ids=[forbidden_id],
        )
        bad_run = memory.run_evaluation(NAMESPACE, eval_set_id=bad_eval.id, retrieval_mode="hybrid")
        assert bad_run.passed is False
        assert bad_run.metrics["forbidden_memory_leak_rate"] > 0
        bad_proposal = memory.propose_policy_update(
            NAMESPACE,
            policy_type="ranking",
            target_policy_id="rpol_default",
            proposed_config={"weights": {"semantic_score": 0.9}},
            reason="Intentionally bad policy for gate test.",
            evaluation_run_id=bad_run.id,
        )
        memory.review_policy_proposal(bad_proposal.id, decision="approve", reason="Human approval cannot skip gate.")
        with pytest.raises(ValidationError):
            memory.apply_policy_proposal(bad_proposal.id, reason="Should be blocked.")
    finally:
        memory.close()


def test_procedure_updates_are_reviewed_versioned_source_backed_and_rollbackable(tmp_path):
    memory = Memory.open(str(tmp_path / "aletheia.db"), namespace=NAMESPACE)
    try:
        procedure_claim = memory.remember(
            namespace=NAMESPACE,
            memory_type="procedure",
            subject="procedure:contracts",
            predicate="has_steps",
            object="Include scope and acceptance criteria.",
            confidence=0.9,
        )
        outcome = memory.record_outcome(
            NAMESPACE,
            task_id="task_contract_procedure",
            outcome="success",
            note="The milestone contract structure worked well.",
        )

        manual = memory.propose_procedure_update(
            NAMESPACE,
            title="Manual lineage procedure",
            proposed_text="Manual reason proposals still require review.",
            reason="Manual reason is an accepted lineage source.",
        )
        assert manual.source_type == "manual_reason"
        assert manual.source_ids

        proposal = memory.propose_procedure_update(
            NAMESPACE,
            procedure_claim_id=procedure_claim.id,
            title="Architecture contract response procedure",
            proposed_text=(
                "For architecture milestone contracts, include scope, APIs, storage, CLI, "
                "tests, migration, acceptance criteria, and demo script."
            ),
            reason="Derived from successful M5 contract outcome.",
            source_ids=[outcome.id],
            source_type="task_outcome",
        )
        assert proposal.status == "pending_review"
        assert proposal.source_ids == [outcome.id]
        with pytest.raises(ValidationError):
            memory.apply_procedure_update(proposal.id, reason="Not reviewed.")
        with pytest.raises(ValidationError):
            memory.propose_procedure_update(
                NAMESPACE,
                title="Unsafe automation",
                proposed_text="Automatically delete evidence after tool execution.",
                reason="Bad idea.",
                require_review=False,
            )

        memory.review_procedure_update(proposal.id, decision="approve", reason="Matches the contract style.")
        version_one = memory.apply_procedure_update(proposal.id, reason="Approved.")
        assert version_one.version == 1
        assert version_one.status == "active"
        assert memory.read_claim(procedure_claim.id).object == version_one.text

        second = memory.propose_procedure_update(
            NAMESPACE,
            procedure_claim_id=procedure_claim.id,
            title="Architecture contract response procedure",
            proposed_text="Include scope, APIs, storage, CLI, tests, migration, acceptance criteria, demo script, and rollback notes.",
            reason="Expanded after another successful outcome.",
            source_ids=[outcome.id],
            source_type="task_outcome",
        )
        memory.review_procedure_update(second.id, decision="approve", reason="Accepted.")
        version_two = memory.apply_procedure_update(second.id, reason="Approved second version.")
        versions = memory.list_procedure_versions(namespace=NAMESPACE, procedure_claim_id=procedure_claim.id)
        assert [version.version for version in versions] == [1, 2]
        assert version_two.status == "active"
        assert memory.get_procedure_version(version_one.id).status == "superseded"

        rollback = memory.rollback_procedure(
            NAMESPACE,
            procedure_claim_id=procedure_claim.id,
            target_version_id=version_one.id,
            reason="Restore first version.",
        )
        assert rollback.to_version_id == version_one.id
        assert memory.get_procedure_version(version_one.id).status == "active"
        assert memory.get_procedure_update_proposal(second.id).status == "applied"
    finally:
        memory.close()


def test_learning_jobs_and_health_are_local_auditable_and_inspectable(tmp_path):
    memory = Memory.open(str(tmp_path / "aletheia.db"), namespace=NAMESPACE)
    try:
        expected_id, _ = _seed_contract_memories(memory)
        eval_set = _create_passing_eval(memory, expected_id)
        pack = memory.context_pack(namespace=NAMESPACE, query="architecture design", record_usage=True)
        memory.record_outcome(
            NAMESPACE,
            task_id="task_learning_seed",
            outcome="success",
            used_context_pack_id=pack.id,
            project_id="aletheia",
        )

        dry = memory.run_learning(
            NAMESPACE,
            learning_targets=["retrieval_policy", "procedure_memory"],
            eval_set_id=eval_set.id,
            dry_run=True,
        )
        assert dry.proposals_created == []
        assert memory.list_learning_runs(namespace=NAMESPACE) == []

        baseline = memory.get_ranking_policy("rpol_default").active_version_id
        learning = memory.run_learning(
            NAMESPACE,
            project_id="aletheia",
            learning_targets=["retrieval_policy", "procedure_memory"],
            eval_set_id=eval_set.id,
            dry_run=False,
        )
        assert len(learning.proposals_created) == 2
        assert memory.read_learning_run(learning.id).id == learning.id
        assert memory.get_ranking_policy("rpol_default").active_version_id == baseline

        batch = memory.ingest(
            NAMESPACE,
            source_type="conversation_transcript",
            content=(
                "User: For progress updates, keep it concise. "
                "User: For architecture contracts, I want comprehensive detail. "
                "User: Aletheia M5 should focus on adaptive memory."
            ),
        )
        memory.extract_candidates(NAMESPACE, batch_id=batch.id)
        memory.remember(
            namespace=NAMESPACE,
            memory_type="preference",
            subject="user.conflict",
            predicate="prefers_detail",
            object="short",
            confidence=0.8,
        )
        memory.remember(
            namespace=NAMESPACE,
            memory_type="preference",
            subject="user.conflict",
            predicate="prefers_detail",
            object="long",
            confidence=0.8,
        )

        health_job = memory.enqueue_job(
            NAMESPACE,
            job_type="memory_health_check",
            payload={"project_id": "aletheia"},
            priority=0.9,
        )
        failed_job = memory.enqueue_job(
            NAMESPACE,
            job_type="run_evaluation",
            payload={"max_attempts": 1},
            priority=0.1,
        )
        completed = memory.run_jobs(namespace=NAMESPACE, max_jobs=10)
        by_id = {job.id: job for job in completed}
        assert by_id[health_job.id].status == "completed"
        assert by_id[failed_job.id].status == "failed"
        assert by_id[failed_job.id].last_error
        assert memory.list_jobs(namespace=NAMESPACE, job_type="memory_health_check")[0].id == health_job.id

        report = memory.health_report(NAMESPACE, project_id="aletheia")
        assert report.metrics["unresolved_conflict_count"] >= 1
        assert report.metrics["pending_review_count"] >= 1
        assert report.metrics["retrieval_judgment_count"] >= 0
        assert report.warnings
        assert report.recommendations
        assert memory.read_health_report(report.id).metrics == report.metrics

        audit_actions = [
            row["action"]
            for row in memory.store.connection.execute(
                "SELECT action FROM audit_log WHERE target_id IN (?, ?)",
                (health_job.id, failed_job.id),
            ).fetchall()
        ]
        assert "job.completed" in audit_actions
        assert "job.failed" in audit_actions
    finally:
        memory.close()


def test_job_claim_is_atomic_for_two_workers(tmp_path):
    memory = Memory.open(str(tmp_path / "aletheia.db"), namespace=NAMESPACE)
    try:
        job = memory.enqueue_job(
            NAMESPACE,
            job_type="memory_health_check",
            payload={},
        )
        calls: list[str] = []
        call_lock = threading.Lock()

        def fake_execute(self: Memory, claimed_job):
            with call_lock:
                calls.append(claimed_job.id)
            time.sleep(0.05)

        memory._execute_job = MethodType(fake_execute, memory)
        workers = [
            threading.Thread(target=memory._run_single_job, args=(job,))
            for _ in range(2)
        ]
        for worker in workers:
            worker.start()
        for worker in workers:
            worker.join()

        assert calls == [job.id]
        stored = memory.get_job(job.id)
        assert stored.status == "completed"
        assert stored.attempts == 1
    finally:
        memory.close()


def test_cli_m5_commands_cover_contract_examples(tmp_path, capsys):
    db_path = str(tmp_path / "aletheia.db")
    assert main(["init", "--db", db_path]) == 0
    assert '"schema_version": "1.3.0"' in capsys.readouterr().out

    assert main(
        [
            "remember",
            "--db",
            db_path,
            "--namespace",
            NAMESPACE,
            "--type",
            "preference",
            "--subject",
            "user.architecture",
            "--predicate",
            "prefers_response_style",
            "--object",
            "comprehensive architecture contract explanations",
            "--project",
            "aletheia",
        ]
    ) == 0
    capsys.readouterr()
    memory = Memory.open(db_path, namespace=NAMESPACE)
    try:
        claim = next(
            item
            for item in memory.list_claims(namespace=NAMESPACE)
            if item.subject == "user.architecture"
        )
        claim_id = claim.id
    finally:
        memory.close()

    assert main(
        [
            "context",
            "--db",
            db_path,
            "--namespace",
            NAMESPACE,
            "--query",
            "architecture contract",
            "--record-usage",
            "--json",
        ]
    ) == 0
    pack = json.loads(capsys.readouterr().out)

    assert main(["usage", "list", "--db", db_path, "--namespace", NAMESPACE]) == 0
    assert pack["id"] in capsys.readouterr().out

    assert main(
        [
            "outcome",
            "record",
            "--db",
            db_path,
            "--namespace",
            NAMESPACE,
            "--task",
            "task_cli",
            "--outcome",
            "success",
            "--context",
            pack["id"],
            "--note",
            "CLI context worked.",
        ]
    ) == 0
    outcome = json.loads(capsys.readouterr().out)

    assert main(
        [
            "eval",
            "create",
            "--db",
            db_path,
            "--namespace",
            NAMESPACE,
            "--name",
            "cli_m5",
            "--project",
            "aletheia",
        ]
    ) == 0
    eval_set = json.loads(capsys.readouterr().out)
    assert main(
        [
            "eval",
            "add-case",
            "--db",
            db_path,
            "--set",
            eval_set["id"],
            "--query",
            "architecture contract",
            "--expected",
            claim_id,
            "--project",
            "aletheia",
        ]
    ) == 0
    capsys.readouterr()
    assert main(["eval", "run", "--db", db_path, "--namespace", NAMESPACE, "--set", eval_set["id"]]) == 0
    eval_run = json.loads(capsys.readouterr().out)
    assert eval_run["passed"] is True
    assert main(["eval", "report", eval_run["id"], "--db", db_path]) == 0
    assert eval_run["id"] in capsys.readouterr().out

    assert main(
        [
            "optimize",
            "retrieval",
            "--db",
            db_path,
            "--namespace",
            NAMESPACE,
            "--eval-set",
            eval_set["id"],
            "--dry-run",
        ]
    ) == 0
    dry = json.loads(capsys.readouterr().out)
    assert dry["proposal_id"] is None

    assert main(
        [
            "optimize",
            "retrieval",
            "--db",
            db_path,
            "--namespace",
            NAMESPACE,
            "--eval-set",
            eval_set["id"],
            "--apply-proposal",
        ]
    ) == 0
    optimization = json.loads(capsys.readouterr().out)
    assert optimization["proposal_id"]

    assert main(["policies", "show", optimization["proposal_id"], "--db", db_path]) == 0
    assert optimization["proposal_id"] in capsys.readouterr().out
    assert main(
        [
            "policies",
            "approve",
            optimization["proposal_id"],
            "--db",
            db_path,
            "--reason",
            "Passed CLI eval.",
        ]
    ) == 0
    capsys.readouterr()
    assert main(
        [
            "policies",
            "apply",
            optimization["proposal_id"],
            "--db",
            db_path,
            "--reason",
            "Activate CLI policy.",
        ]
    ) == 0
    application = json.loads(capsys.readouterr().out)

    assert main(
        [
            "learn",
            "run",
            "--db",
            db_path,
            "--namespace",
            NAMESPACE,
            "--project",
            "aletheia",
            "--targets",
            "retrieval_policy,procedure_memory",
            "--eval-set",
            eval_set["id"],
            "--dry-run",
        ]
    ) == 0
    assert json.loads(capsys.readouterr().out)["dry_run"] is True

    assert main(
        [
            "procedures",
            "propose",
            "--db",
            db_path,
            "--namespace",
            NAMESPACE,
            "--title",
            "Architecture contract response procedure",
            "--text",
            "Include APIs, storage, CLI, tests, migration, acceptance criteria, and demo script.",
            "--reason",
            "Manual CLI proposal.",
        ]
    ) == 0
    proc_proposal = json.loads(capsys.readouterr().out)
    assert main(
        [
            "procedures",
            "approve",
            proc_proposal["id"],
            "--db",
            db_path,
            "--reason",
            "Approved CLI procedure.",
        ]
    ) == 0
    capsys.readouterr()
    assert main(
        [
            "procedures",
            "apply",
            proc_proposal["id"],
            "--db",
            db_path,
            "--reason",
            "Apply CLI procedure.",
        ]
    ) == 0
    proc_version = json.loads(capsys.readouterr().out)

    assert main(
        [
            "jobs",
            "enqueue",
            "--db",
            db_path,
            "--namespace",
            NAMESPACE,
            "--type",
            "memory_health_check",
        ]
    ) == 0
    job = json.loads(capsys.readouterr().out)
    assert main(["jobs", "show", job["id"], "--db", db_path]) == 0
    assert job["id"] in capsys.readouterr().out
    assert main(["jobs", "run", "--db", db_path, "--namespace", NAMESPACE]) == 0
    assert json.loads(capsys.readouterr().out)[0]["status"] == "completed"

    assert main(["health", "report", "--db", db_path, "--namespace", NAMESPACE]) == 0
    assert "active_claim_count" in capsys.readouterr().out

    assert main(
        [
            "rollback",
            "policy",
            "--db",
            db_path,
            "--namespace",
            NAMESPACE,
            "--policy",
            "rpol_default",
            "--to-version",
            application["old_version_id"],
            "--reason",
            "Rollback CLI policy.",
        ]
    ) == 0
    assert application["old_version_id"] in capsys.readouterr().out

    assert main(
        [
            "rollback",
            "procedure",
            "--db",
            db_path,
            "--namespace",
            NAMESPACE,
            "--to-version",
            proc_version["id"],
            "--reason",
            "Rollback CLI procedure to same version.",
        ]
    ) == 0
    assert proc_version["id"] in capsys.readouterr().out
