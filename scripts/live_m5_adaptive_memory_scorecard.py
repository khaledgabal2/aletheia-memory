"""Live M5 scorecard: Adaptive Memory, Evaluation, and Self-Improvement."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from aletheia import Memory
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


@dataclass
class CaseResult:
    category: str
    case: str
    interface: str
    passed: bool
    details: str


class M5Runner:
    def __init__(self, db_path: Path, verbose: bool = False):
        self.db_path = db_path
        self.verbose = verbose
        self.results: list[CaseResult] = []
        self.ids: dict[str, str] = {}

    def run(self) -> list[CaseResult]:
        cases: list[tuple[str, str, str, Callable[[], str]]] = [
            ("Migration", "Initialize schema 1.3.0 with M5 tables and default policies", "CLI/API", self.case_init_schema),
            ("Migration", "Migration is idempotent and runs no learning or optimization automatically", "API", self.case_migration_idempotence),
            ("Setup", "Create project memories, a procedure memory, and golden evaluation fixtures", "API", self.case_seed_memory),
            ("Usage", "Context pack records context usage and included memory usage", "API", self.case_context_usage_logging),
            ("Usage", "Explicit memory usage is inspectable", "API", self.case_explicit_usage_logging),
            ("Usage", "Task outcome links to context pack without confirming truth", "API", self.case_outcome_is_not_truth),
            ("Usage", "Retrieval judgment stores query, result, and rank signal", "API", self.case_retrieval_judgment),
            ("Evaluation", "Evaluation sets and cases are stored", "API", self.case_eval_set_and_cases),
            ("Evaluation", "Evaluation run computes required metrics and persists results", "API", self.case_eval_run_metrics),
            ("Evaluation", "Golden forbidden-memory case fails and becomes auditable", "API", self.case_bad_eval_detects_leak),
            ("Optimization", "Retrieval optimization dry-run creates no proposal and no policy change", "API", self.case_optimization_dry_run),
            ("Optimization", "Retrieval optimization creates a pending proposal with evaluation summary", "API", self.case_optimization_proposal),
            ("Optimization", "Policy proposal requires review before application", "API", self.case_policy_requires_review),
            ("Optimization", "Approved policy application creates version and application history", "API", self.case_apply_policy),
            ("Optimization", "Bad policy is blocked by evaluation gate", "API", self.case_bad_policy_blocked),
            ("Procedure", "Procedure proposal preserves source lineage and requires review by default", "API", self.case_procedure_proposal),
            ("Procedure", "High-risk procedure cannot bypass explicit review", "API", self.case_high_risk_procedure_gate),
            ("Procedure", "Procedure application creates version and updates linked procedure memory", "API", self.case_apply_procedure),
            ("Procedure", "Procedure versions are ordered and supersede prior active version", "API", self.case_second_procedure_version),
            ("Learning", "run_learning dry-run mutates nothing", "API", self.case_learning_dry_run),
            ("Learning", "run_learning creates proposals without activating learned behavior", "API", self.case_learning_creates_proposals),
            ("Jobs", "Jobs can be enqueued, listed, and inspected", "API", self.case_enqueue_jobs),
            ("Jobs", "Local job runner records success and failure with audit events", "API", self.case_run_jobs),
            ("Health", "Health report identifies conflicted and unreviewed memory", "API", self.case_health_report),
            ("Rollback", "Policy rollback restores prior version and preserves history", "API", self.case_policy_rollback),
            ("Rollback", "Procedure rollback restores prior version and writes rollback record", "API", self.case_procedure_rollback),
            ("CLI", "M5 usage, outcome, eval, optimize, learn, policies, procedures, jobs, health, rollback commands work", "CLI", self.case_cli_groups),
            ("Compatibility", "Existing M4 search/context behavior still works after M5", "CLI/API", self.case_m4_compatibility),
        ]
        for category, case, interface, fn in cases:
            try:
                self.results.append(CaseResult(category, case, interface, True, fn()))
            except Exception as exc:  # noqa: BLE001 - live scorecard should continue.
                self.results.append(CaseResult(category, case, interface, False, str(exc)))
        return self.results

    def case_init_schema(self) -> str:
        health = json.loads(self.cli("init", "--db", str(self.db_path)).stdout)
        assert health["schema_version"] == "1.3.0"
        memory = Memory.open(str(self.db_path), namespace=NAMESPACE)
        try:
            names = {
                row["name"]
                for row in memory.store.connection.execute(
                    "SELECT name FROM sqlite_master WHERE type IN ('table', 'virtual table')"
                ).fetchall()
            }
            assert REQUIRED_M5_TABLES.issubset(names)
            assert memory.get_ranking_policy("rpol_default").active_version_id == "rpv_default_v1"
            context_policy = memory.store.connection.execute(
                "SELECT active_version_id FROM context_pack_policies WHERE id = 'cpol_default'"
            ).fetchone()
            assert context_policy["active_version_id"] == "cpv_default_v1"
            return "schema_version=1.3.0, default ranking/context policies active"
        finally:
            memory.close()

    def case_migration_idempotence(self) -> str:
        memory = Memory.open(str(self.db_path), namespace=NAMESPACE)
        try:
            before_versions = len(memory.list_ranking_policy_versions("rpol_default"))
            memory.store.migrate()
            after_versions = len(memory.list_ranking_policy_versions("rpol_default"))
            assert before_versions == after_versions == 1
            assert memory.list_learning_runs(namespace=NAMESPACE) == []
            optimization_count = memory.store.connection.execute(
                "SELECT count(*) AS count FROM optimization_runs"
            ).fetchone()["count"]
            assert optimization_count == 0
            return f"policy_versions={after_versions}, learning_runs=0, optimization_runs=0"
        finally:
            memory.close()

    def case_seed_memory(self) -> str:
        memory = Memory.open(str(self.db_path), namespace=NAMESPACE)
        try:
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
            procedure = memory.remember(
                namespace=NAMESPACE,
                memory_type="procedure",
                subject="procedure:contracts",
                predicate="has_steps",
                object="Include scope and acceptance criteria.",
                confidence=0.9,
            )
            eval_set = memory.create_eval_set(
                NAMESPACE,
                name="m5_contracts",
                description="Golden adaptive-memory checks for M5.",
                project_id="aletheia",
            )
            memory.add_eval_case(
                eval_set.id,
                query="architecture design contract explanations",
                expected_claim_ids=[architecture.id],
                expected_sections={"project_memory": ["comprehensive architecture"]},
                project_id="aletheia",
                tags=["golden"],
            )
            bad_eval = memory.create_eval_set(NAMESPACE, name="m5_bad_policy")
            memory.add_eval_case(
                bad_eval.id,
                query="architecture progress",
                expected_claim_ids=[architecture.id],
                forbidden_claim_ids=[progress.id],
                tags=["golden", "bad_policy"],
            )
            self.ids.update(
                {
                    "architecture": architecture.id,
                    "forbidden": progress.id,
                    "procedure_claim": procedure.id,
                    "eval_set": eval_set.id,
                    "bad_eval": bad_eval.id,
                }
            )
            return f"claims={architecture.id},{progress.id},{procedure.id}; eval_sets=2"
        finally:
            memory.close()

    def case_context_usage_logging(self) -> str:
        memory = Memory.open(str(self.db_path), namespace=NAMESPACE)
        try:
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
            assert self.ids["architecture"] in pack.metadata["included_item_ids"]
            context_usage = memory.store.connection.execute(
                "SELECT * FROM context_usage_events WHERE context_pack_id = ?",
                (pack.id,),
            ).fetchall()
            usage = memory.list_usage(context_pack_id=pack.id)
            assert len(context_usage) == 1
            assert any(event.target_id == self.ids["architecture"] for event in usage)
            self.ids["context_pack"] = pack.id
            return f"context_pack={pack.id}, memory_usage_events={len(usage)}"
        finally:
            memory.close()

    def case_explicit_usage_logging(self) -> str:
        memory = Memory.open(str(self.db_path), namespace=NAMESPACE)
        try:
            usage = memory.record_usage(
                NAMESPACE,
                target_id=self.ids["architecture"],
                target_type="claim",
                usage_type="used_by_agent",
                query="architecture design contract",
                context_pack_id=self.ids["context_pack"],
                rank=1,
            )
            assert memory.read_usage(usage.id).usage_type == "used_by_agent"
            return f"usage_id={usage.id}"
        finally:
            memory.close()

    def case_outcome_is_not_truth(self) -> str:
        memory = Memory.open(str(self.db_path), namespace=NAMESPACE)
        try:
            before = memory.read_claim(self.ids["architecture"]).confidence_base
            outcome = memory.record_outcome(
                NAMESPACE,
                task_id="task_m5_live_success",
                outcome="success",
                used_context_pack_id=self.ids["context_pack"],
                project_id="aletheia",
                note="Context included the correct M5 project state.",
            )
            after = memory.read_claim(self.ids["architecture"]).confidence_base
            assert after == before
            self.ids["outcome"] = outcome.id
            return f"outcome={outcome.id}, confidence_base={after:.2f}"
        finally:
            memory.close()

    def case_retrieval_judgment(self) -> str:
        memory = Memory.open(str(self.db_path), namespace=NAMESPACE)
        try:
            judgment = memory.judge_retrieval(
                NAMESPACE,
                query="architecture design contract",
                result_id=self.ids["architecture"],
                result_type="claim",
                judgment="useful",
                expected_rank=1,
            )
            assert memory.list_retrieval_judgments(namespace=NAMESPACE, result_id=self.ids["architecture"])
            return f"judgment={judgment.id}"
        finally:
            memory.close()

    def case_eval_set_and_cases(self) -> str:
        memory = Memory.open(str(self.db_path), namespace=NAMESPACE)
        try:
            assert memory.get_eval_set(self.ids["eval_set"]).name == "m5_contracts"
            assert len(memory.list_eval_cases(self.ids["eval_set"])) == 1
            assert len(memory.list_eval_cases(self.ids["bad_eval"])) == 1
            return "eval_sets=2, eval_cases=2"
        finally:
            memory.close()

    def case_eval_run_metrics(self) -> str:
        memory = Memory.open(str(self.db_path), namespace=NAMESPACE)
        try:
            run = memory.run_evaluation(NAMESPACE, eval_set_id=self.ids["eval_set"], retrieval_mode="hybrid")
            assert run.passed
            assert REQUIRED_EVAL_METRICS.issubset(run.metrics)
            assert run.metrics["recall_at_5"] == 1.0
            results = memory.store.connection.execute(
                "SELECT count(*) AS count FROM evaluation_results WHERE evaluation_run_id = ?",
                (run.id,),
            ).fetchone()["count"]
            metrics = memory.store.connection.execute(
                "SELECT count(*) AS count FROM evaluation_metrics WHERE evaluation_run_id = ?",
                (run.id,),
            ).fetchone()["count"]
            assert results == 1
            assert metrics >= len(REQUIRED_EVAL_METRICS)
            self.ids["eval_run"] = run.id
            return f"eval_run={run.id}, metrics={len(run.metrics)}"
        finally:
            memory.close()

    def case_bad_eval_detects_leak(self) -> str:
        memory = Memory.open(str(self.db_path), namespace=NAMESPACE)
        try:
            run = memory.run_evaluation(NAMESPACE, eval_set_id=self.ids["bad_eval"], retrieval_mode="hybrid")
            assert not run.passed
            assert run.metrics["forbidden_memory_leak_rate"] > 0.0
            self.ids["bad_eval_run"] = run.id
            return f"bad_eval={run.id}, forbidden_leak={run.metrics['forbidden_memory_leak_rate']:.2f}"
        finally:
            memory.close()

    def case_optimization_dry_run(self) -> str:
        memory = Memory.open(str(self.db_path), namespace=NAMESPACE)
        try:
            baseline = memory.get_ranking_policy("rpol_default").active_version_id
            run = memory.optimize_retrieval(NAMESPACE, eval_set_id=self.ids["eval_set"], dry_run=True)
            assert run.proposal_id is None
            assert memory.get_ranking_policy("rpol_default").active_version_id == baseline
            self.ids["baseline_policy_version"] = baseline
            return f"dry_run={run.id}, active_policy={baseline}"
        finally:
            memory.close()

    def case_optimization_proposal(self) -> str:
        memory = Memory.open(str(self.db_path), namespace=NAMESPACE)
        try:
            run = memory.optimize_retrieval(NAMESPACE, eval_set_id=self.ids["eval_set"], dry_run=False)
            proposal = memory.get_policy_proposal(run.proposal_id)
            assert proposal.status == "pending_review"
            assert proposal.proposed_config["evaluation_summary"]["passed"] is True
            assert memory.get_ranking_policy("rpol_default").active_version_id == self.ids["baseline_policy_version"]
            self.ids["optimization"] = run.id
            self.ids["policy_proposal"] = proposal.id
            return f"optimization={run.id}, proposal={proposal.id}"
        finally:
            memory.close()

    def case_policy_requires_review(self) -> str:
        memory = Memory.open(str(self.db_path), namespace=NAMESPACE)
        try:
            try:
                memory.apply_policy_proposal(self.ids["policy_proposal"], reason="Not reviewed.")
            except ValidationError as exc:
                assert "approved" in str(exc)
                return "unapproved proposal blocked"
            raise AssertionError("Unapproved policy proposal applied unexpectedly.")
        finally:
            memory.close()

    def case_apply_policy(self) -> str:
        memory = Memory.open(str(self.db_path), namespace=NAMESPACE)
        try:
            memory.review_policy_proposal(
                self.ids["policy_proposal"],
                decision="approve",
                reason="Passed golden evaluation.",
            )
            app = memory.apply_policy_proposal(self.ids["policy_proposal"], reason="Activate approved policy.")
            assert app.old_version_id == self.ids["baseline_policy_version"]
            assert app.new_version_id != app.old_version_id
            assert memory.get_ranking_policy("rpol_default").active_version_id == app.new_version_id
            assert memory.list_policy_applications(namespace=NAMESPACE)[0].id == app.id
            self.ids["policy_application"] = app.id
            self.ids["new_policy_version"] = app.new_version_id
            return f"application={app.id}, new_version={app.new_version_id}"
        finally:
            memory.close()

    def case_bad_policy_blocked(self) -> str:
        memory = Memory.open(str(self.db_path), namespace=NAMESPACE)
        try:
            proposal = memory.propose_policy_update(
                NAMESPACE,
                policy_type="ranking",
                target_policy_id="rpol_default",
                proposed_config={"weights": {"semantic_score": 0.9}},
                reason="Intentionally leaky policy.",
                evaluation_run_id=self.ids["bad_eval_run"],
            )
            memory.review_policy_proposal(proposal.id, decision="approve", reason="Human review cannot skip gate.")
            try:
                memory.apply_policy_proposal(proposal.id, reason="Should be blocked.")
            except ValidationError as exc:
                assert "evaluation gate" in str(exc)
                self.ids["bad_policy_proposal"] = proposal.id
                return f"blocked={proposal.id}"
            raise AssertionError("Bad policy proposal applied unexpectedly.")
        finally:
            memory.close()

    def case_procedure_proposal(self) -> str:
        memory = Memory.open(str(self.db_path), namespace=NAMESPACE)
        try:
            proposal = memory.propose_procedure_update(
                NAMESPACE,
                procedure_claim_id=self.ids["procedure_claim"],
                title="Architecture contract response procedure",
                proposed_text=(
                    "For architecture milestone contracts, include scope, APIs, storage, CLI, "
                    "tests, migration, acceptance criteria, and demo script."
                ),
                reason="Derived from successful M5 task outcome.",
                source_ids=[self.ids["outcome"]],
                source_type="task_outcome",
            )
            assert proposal.status == "pending_review"
            assert proposal.source_ids == [self.ids["outcome"]]
            self.ids["procedure_proposal"] = proposal.id
            return f"procedure_proposal={proposal.id}"
        finally:
            memory.close()

    def case_high_risk_procedure_gate(self) -> str:
        memory = Memory.open(str(self.db_path), namespace=NAMESPACE)
        try:
            try:
                memory.propose_procedure_update(
                    NAMESPACE,
                    title="Unsafe automation",
                    proposed_text="Automatically delete evidence after tool execution.",
                    reason="High-risk bypass test.",
                    require_review=False,
                )
            except ValidationError as exc:
                assert "explicit review" in str(exc)
                return "high-risk no-review proposal blocked"
            raise AssertionError("High-risk procedure bypassed review unexpectedly.")
        finally:
            memory.close()

    def case_apply_procedure(self) -> str:
        memory = Memory.open(str(self.db_path), namespace=NAMESPACE)
        try:
            memory.review_procedure_update(
                self.ids["procedure_proposal"],
                decision="approve",
                reason="Matches user preference and eval cases.",
            )
            version = memory.apply_procedure_update(self.ids["procedure_proposal"], reason="Approved procedure.")
            assert version.version == 1
            assert version.status == "active"
            assert memory.read_claim(self.ids["procedure_claim"]).object == version.text
            self.ids["procedure_v1"] = version.id
            return f"procedure_v1={version.id}"
        finally:
            memory.close()

    def case_second_procedure_version(self) -> str:
        memory = Memory.open(str(self.db_path), namespace=NAMESPACE)
        try:
            proposal = memory.propose_procedure_update(
                NAMESPACE,
                procedure_claim_id=self.ids["procedure_claim"],
                title="Architecture contract response procedure",
                proposed_text="Include scope, APIs, storage, CLI, tests, migration, acceptance criteria, demo script, and rollback notes.",
                reason="Expanded after live M5 review.",
                source_ids=[self.ids["outcome"]],
                source_type="task_outcome",
            )
            memory.review_procedure_update(proposal.id, decision="approve", reason="Accepted.")
            version = memory.apply_procedure_update(proposal.id, reason="Approved second version.")
            versions = memory.list_procedure_versions(namespace=NAMESPACE, procedure_claim_id=self.ids["procedure_claim"])
            assert [item.version for item in versions] == [1, 2]
            assert version.status == "active"
            assert memory.get_procedure_version(self.ids["procedure_v1"]).status == "superseded"
            self.ids["procedure_v2"] = version.id
            return f"procedure_versions={[item.id for item in versions]}"
        finally:
            memory.close()

    def case_learning_dry_run(self) -> str:
        memory = Memory.open(str(self.db_path), namespace=NAMESPACE)
        try:
            before = len(memory.list_policy_proposals(namespace=NAMESPACE))
            run = memory.run_learning(
                NAMESPACE,
                learning_targets=["retrieval_policy", "procedure_memory"],
                eval_set_id=self.ids["eval_set"],
                dry_run=True,
            )
            after = len(memory.list_policy_proposals(namespace=NAMESPACE))
            assert run.dry_run
            assert run.proposals_created == []
            assert before == after
            assert all(item.id != run.id for item in memory.list_learning_runs(namespace=NAMESPACE))
            return "dry_run: no persisted learning run, no proposals"
        finally:
            memory.close()

    def case_learning_creates_proposals(self) -> str:
        memory = Memory.open(str(self.db_path), namespace=NAMESPACE)
        try:
            active_before = memory.get_ranking_policy("rpol_default").active_version_id
            run = memory.run_learning(
                NAMESPACE,
                project_id="aletheia",
                learning_targets=["retrieval_policy", "procedure_memory"],
                eval_set_id=self.ids["eval_set"],
                dry_run=False,
            )
            assert len(run.proposals_created) >= 2
            assert memory.read_learning_run(run.id).id == run.id
            assert memory.get_ranking_policy("rpol_default").active_version_id == active_before
            self.ids["learning_run"] = run.id
            return f"learning_run={run.id}, proposals={len(run.proposals_created)}"
        finally:
            memory.close()

    def case_enqueue_jobs(self) -> str:
        memory = Memory.open(str(self.db_path), namespace=NAMESPACE)
        try:
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
            assert memory.get_job(health_job.id).status == "pending"
            assert len(memory.list_jobs(namespace=NAMESPACE)) >= 2
            self.ids["health_job"] = health_job.id
            self.ids["failed_job"] = failed_job.id
            return f"jobs={health_job.id},{failed_job.id}"
        finally:
            memory.close()

    def case_run_jobs(self) -> str:
        memory = Memory.open(str(self.db_path), namespace=NAMESPACE)
        try:
            jobs = memory.run_jobs(namespace=NAMESPACE, max_jobs=10)
            by_id = {job.id: job for job in jobs}
            assert by_id[self.ids["health_job"]].status == "completed"
            assert by_id[self.ids["failed_job"]].status == "failed"
            actions = [
                row["action"]
                for row in memory.store.connection.execute(
                    "SELECT action FROM audit_log WHERE target_id IN (?, ?)",
                    (self.ids["health_job"], self.ids["failed_job"]),
                ).fetchall()
            ]
            assert "job.completed" in actions
            assert "job.failed" in actions
            return f"completed={self.ids['health_job']}, failed={self.ids['failed_job']}"
        finally:
            memory.close()

    def case_health_report(self) -> str:
        memory = Memory.open(str(self.db_path), namespace=NAMESPACE)
        try:
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
            report = memory.health_report(NAMESPACE, project_id="aletheia")
            assert report.metrics["unresolved_conflict_count"] >= 1
            assert report.metrics["pending_review_count"] >= 1
            assert report.warnings
            assert report.recommendations
            assert memory.read_health_report(report.id).id == report.id
            self.ids["health_report"] = report.id
            return (
                f"health={report.id}, conflicts={report.metrics['unresolved_conflict_count']}, "
                f"pending={report.metrics['pending_review_count']}"
            )
        finally:
            memory.close()

    def case_policy_rollback(self) -> str:
        memory = Memory.open(str(self.db_path), namespace=NAMESPACE)
        try:
            record = memory.rollback_policy(
                NAMESPACE,
                policy_id="rpol_default",
                target_version_id=self.ids["baseline_policy_version"],
                reason="Rollback live M5 policy.",
            )
            assert record.to_version_id == self.ids["baseline_policy_version"]
            assert memory.get_ranking_policy("rpol_default").active_version_id == self.ids["baseline_policy_version"]
            assert memory.get_policy_proposal(self.ids["policy_proposal"]).status == "applied"
            actions = [
                row["action"]
                for row in memory.store.connection.execute(
                    "SELECT action FROM audit_log WHERE target_id = 'rpol_default'"
                ).fetchall()
            ]
            assert "policy.rollback" in actions
            return f"policy_rollback={record.id}"
        finally:
            memory.close()

    def case_procedure_rollback(self) -> str:
        memory = Memory.open(str(self.db_path), namespace=NAMESPACE)
        try:
            record = memory.rollback_procedure(
                NAMESPACE,
                procedure_claim_id=self.ids["procedure_claim"],
                target_version_id=self.ids["procedure_v1"],
                reason="Rollback live M5 procedure.",
            )
            assert record.to_version_id == self.ids["procedure_v1"]
            assert memory.get_procedure_version(self.ids["procedure_v1"]).status == "active"
            assert memory.get_procedure_version(self.ids["procedure_v2"]).status == "rolled_back"
            return f"procedure_rollback={record.id}"
        finally:
            memory.close()

    def case_cli_groups(self) -> str:
        usage = json.loads(
            self.cli("usage", "list", "--db", str(self.db_path), "--namespace", NAMESPACE).stdout
        )
        outcome = json.loads(
            self.cli("outcome", "list", "--db", str(self.db_path), "--namespace", NAMESPACE).stdout
        )
        eval_sets = json.loads(
            self.cli("eval", "list", "--db", str(self.db_path), "--namespace", NAMESPACE).stdout
        )
        eval_report = json.loads(
            self.cli("eval", "report", self.ids["eval_run"], "--db", str(self.db_path)).stdout
        )
        opt = json.loads(
            self.cli(
                "optimize",
                "retrieval",
                "--db",
                str(self.db_path),
                "--namespace",
                NAMESPACE,
                "--eval-set",
                self.ids["eval_set"],
                "--dry-run",
            ).stdout
        )
        learn = json.loads(
            self.cli(
                "learn",
                "run",
                "--db",
                str(self.db_path),
                "--namespace",
                NAMESPACE,
                "--targets",
                "retrieval_policy,procedure_memory",
                "--eval-set",
                self.ids["eval_set"],
                "--dry-run",
            ).stdout
        )
        policies = json.loads(
            self.cli("policies", "proposals", "--db", str(self.db_path), "--namespace", NAMESPACE).stdout
        )
        procedures = json.loads(
            self.cli("procedures", "versions", "--db", str(self.db_path), "--namespace", NAMESPACE).stdout
        )
        job = json.loads(
            self.cli(
                "jobs",
                "enqueue",
                "--db",
                str(self.db_path),
                "--namespace",
                NAMESPACE,
                "--type",
                "memory_health_check",
            ).stdout
        )
        job_show = json.loads(self.cli("jobs", "show", job["id"], "--db", str(self.db_path)).stdout)
        health = json.loads(
            self.cli("health", "report", "--db", str(self.db_path), "--namespace", NAMESPACE).stdout
        )
        rollback = json.loads(
            self.cli(
                "rollback",
                "policy",
                "--db",
                str(self.db_path),
                "--namespace",
                NAMESPACE,
                "--policy",
                "rpol_default",
                "--to-version",
                self.ids["baseline_policy_version"],
                "--reason",
                "CLI rollback no-op.",
            ).stdout
        )
        assert usage
        assert outcome
        assert eval_sets
        assert eval_report["id"] == self.ids["eval_run"]
        assert opt["proposal_id"] is None
        assert learn["dry_run"] is True
        assert policies
        assert procedures
        assert job_show["id"] == job["id"]
        assert health["metrics"]["active_claim_count"] >= 1
        assert rollback["to_version_id"] == self.ids["baseline_policy_version"]
        return "usage/outcome/eval/optimize/learn/policies/procedures/jobs/health/rollback ok"

    def case_m4_compatibility(self) -> str:
        search = self.cli(
            "search",
            "--db",
            str(self.db_path),
            "--namespace",
            NAMESPACE,
            "--mode",
            "hybrid",
            "architecture contract",
        ).stdout
        context = self.cli(
            "context",
            "--db",
            str(self.db_path),
            "--namespace",
            NAMESPACE,
            "--query",
            "architecture contract",
            "--mode",
            "hybrid",
        ).stdout
        memory = Memory.open(str(self.db_path), namespace=NAMESPACE)
        try:
            assert self.ids["architecture"] in search
            assert "## Memory Context" in context
            assert memory.retrieve(namespace=NAMESPACE, query="architecture contract", mode="hybrid")
            return "search/context/retrieve remain compatible"
        finally:
            memory.close()

    def cli(self, *args: str) -> subprocess.CompletedProcess[str]:
        command = [sys.executable, "-m", "aletheia.cli.main", *args]
        result = subprocess.run(
            command,
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        if self.verbose or result.returncode != 0:
            print("$", " ".join(command))
            if result.stdout:
                print(result.stdout)
            if result.stderr:
                print(result.stderr, file=sys.stderr)
        result.check_returncode()
        return result


def print_scorecard(results: list[CaseResult]) -> None:
    passed = sum(1 for result in results if result.passed)
    print("M5 Live Scorecard: Adaptive Memory, Evaluation, and Self-Improvement")
    print(f"Passed {passed}/{len(results)} cases")
    print()
    current_category = None
    for result in results:
        if result.category != current_category:
            current_category = result.category
            print(f"[{current_category}]")
        mark = "PASS" if result.passed else "FAIL"
        print(f"  {mark} | {result.case} ({result.interface})")
        print(f"       {result.details}")
    print()
    print(json.dumps([result.__dict__ for result in results], indent=2))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db")
    parser.add_argument("--keep-db", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    if args.db:
        runner = M5Runner(Path(args.db), verbose=args.verbose)
        results = runner.run()
        print_scorecard(results)
        return 0 if all(result.passed for result in results) else 1

    with tempfile.TemporaryDirectory(prefix="aletheia_m5_live_") as tmp:
        db_path = Path(tmp) / "aletheia.db"
        runner = M5Runner(db_path, verbose=args.verbose)
        results = runner.run()
        print_scorecard(results)
        if args.keep_db:
            print(f"Database retained until temp cleanup: {db_path}")
        return 0 if all(result.passed for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
