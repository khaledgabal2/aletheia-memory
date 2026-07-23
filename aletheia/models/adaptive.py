"""M5 adaptive memory, evaluation, policy, job, and rollback models."""

from __future__ import annotations

import json
from dataclasses import dataclass, field


def _json(value: str | None, default):
    if value is None:
        return default
    return json.loads(value)


@dataclass(frozen=True)
class MemoryUsageEvent:
    id: str
    namespace: str
    target_id: str
    target_type: str
    usage_type: str
    query: str | None
    session_id: str | None
    project_id: str | None
    context_pack_id: str | None
    rank: int | None
    score: float | None
    created_at: str
    metadata: dict = field(default_factory=dict)

    @classmethod
    def from_row(cls, row) -> "MemoryUsageEvent":
        return cls(
            id=row["id"],
            namespace=row["namespace"],
            target_id=row["target_id"],
            target_type=row["target_type"],
            usage_type=row["usage_type"],
            query=row["query"],
            session_id=row["session_id"],
            project_id=row["project_id"],
            context_pack_id=row["context_pack_id"],
            rank=row["rank"],
            score=row["score"],
            created_at=row["created_at"],
            metadata=_json(row["metadata_json"], {}),
        )


@dataclass(frozen=True)
class ContextUsageEvent:
    id: str
    namespace: str
    context_pack_id: str
    query: str
    session_id: str | None
    project_id: str | None
    item_count: int
    token_estimate: int
    created_at: str
    metadata: dict = field(default_factory=dict)

    @classmethod
    def from_row(cls, row) -> "ContextUsageEvent":
        return cls(
            id=row["id"],
            namespace=row["namespace"],
            context_pack_id=row["context_pack_id"],
            query=row["query"],
            session_id=row["session_id"],
            project_id=row["project_id"],
            item_count=row["item_count"],
            token_estimate=row["token_estimate"],
            created_at=row["created_at"],
            metadata=_json(row["metadata_json"], {}),
        )


@dataclass(frozen=True)
class TaskOutcome:
    id: str
    namespace: str
    task_id: str
    outcome: str
    used_context_pack_id: str | None
    session_id: str | None
    project_id: str | None
    user_feedback: str | None
    score: float | None
    note: str | None
    created_at: str
    metadata: dict = field(default_factory=dict)

    @classmethod
    def from_row(cls, row) -> "TaskOutcome":
        return cls(
            id=row["id"],
            namespace=row["namespace"],
            task_id=row["task_id"],
            outcome=row["outcome"],
            used_context_pack_id=row["used_context_pack_id"],
            session_id=row["session_id"],
            project_id=row["project_id"],
            user_feedback=row["user_feedback"],
            score=row["score"],
            note=row["note"],
            created_at=row["created_at"],
            metadata=_json(row["metadata_json"], {}),
        )


@dataclass(frozen=True)
class RetrievalJudgment:
    id: str
    namespace: str
    query: str
    result_id: str
    result_type: str
    judgment: str
    judge: str
    reason: str | None
    expected_rank: int | None
    session_id: str | None
    project_id: str | None
    created_at: str
    metadata: dict = field(default_factory=dict)

    @classmethod
    def from_row(cls, row) -> "RetrievalJudgment":
        return cls(
            id=row["id"],
            namespace=row["namespace"],
            query=row["query"],
            result_id=row["result_id"],
            result_type=row["result_type"],
            judgment=row["judgment"],
            judge=row["judge"],
            reason=row["reason"],
            expected_rank=row["expected_rank"],
            session_id=row["session_id"],
            project_id=row["project_id"],
            created_at=row["created_at"],
            metadata=_json(row["metadata_json"], {}),
        )


@dataclass(frozen=True)
class EvaluationSet:
    id: str
    namespace: str
    name: str
    description: str | None
    project_id: str | None
    created_at: str
    updated_at: str
    metadata: dict = field(default_factory=dict)

    @classmethod
    def from_row(cls, row) -> "EvaluationSet":
        return cls(
            id=row["id"],
            namespace=row["namespace"],
            name=row["name"],
            description=row["description"],
            project_id=row["project_id"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            metadata=_json(row["metadata_json"], {}),
        )


@dataclass(frozen=True)
class EvaluationCase:
    id: str
    eval_set_id: str
    namespace: str
    query: str
    expected_claim_ids: list[str]
    expected_reflection_ids: list[str]
    forbidden_claim_ids: list[str]
    expected_sections: dict
    project_id: str | None
    session_id: str | None
    tags: list[str]
    note: str | None
    created_at: str

    @classmethod
    def from_row(cls, row) -> "EvaluationCase":
        return cls(
            id=row["id"],
            eval_set_id=row["eval_set_id"],
            namespace=row["namespace"],
            query=row["query"],
            expected_claim_ids=_json(row["expected_claim_ids_json"], []),
            expected_reflection_ids=_json(row["expected_reflection_ids_json"], []),
            forbidden_claim_ids=_json(row["forbidden_claim_ids_json"], []),
            expected_sections=_json(row["expected_sections_json"], {}),
            project_id=row["project_id"],
            session_id=row["session_id"],
            tags=_json(row["tags_json"], []),
            note=row["note"],
            created_at=row["created_at"],
        )


@dataclass(frozen=True)
class EvaluationRun:
    id: str
    namespace: str
    eval_set_id: str
    policy_version_id: str | None
    retrieval_mode: str
    case_count: int
    metrics: dict
    passed: bool
    created_at: str
    metadata: dict = field(default_factory=dict)

    @classmethod
    def from_row(cls, row) -> "EvaluationRun":
        return cls(
            id=row["id"],
            namespace=row["namespace"],
            eval_set_id=row["eval_set_id"],
            policy_version_id=row["policy_version_id"],
            retrieval_mode=row["retrieval_mode"],
            case_count=row["case_count"],
            metrics=_json(row["metrics_json"], {}),
            passed=bool(row["passed"]),
            created_at=row["created_at"],
            metadata=_json(row["metadata_json"], {}),
        )


@dataclass(frozen=True)
class EvaluationMetric:
    id: str
    evaluation_run_id: str
    metric_name: str
    metric_value: float
    threshold: float | None
    passed: bool | None
    created_at: str

    @classmethod
    def from_row(cls, row) -> "EvaluationMetric":
        return cls(
            id=row["id"],
            evaluation_run_id=row["evaluation_run_id"],
            metric_name=row["metric_name"],
            metric_value=row["metric_value"],
            threshold=row["threshold"],
            passed=None if row["passed"] is None else bool(row["passed"]),
            created_at=row["created_at"],
        )


@dataclass(frozen=True)
class RankingPolicy:
    id: str
    namespace: str | None
    name: str
    active_version_id: str | None
    created_at: str
    updated_at: str

    @classmethod
    def from_row(cls, row) -> "RankingPolicy":
        return cls(
            id=row["id"],
            namespace=row["namespace"],
            name=row["name"],
            active_version_id=row["active_version_id"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )


@dataclass(frozen=True)
class RankingPolicyVersion:
    id: str
    policy_id: str
    version: int
    weights: dict
    filters: dict
    thresholds: dict
    created_by: str
    created_at: str
    evaluation_summary: dict | None
    status: str

    @classmethod
    def from_row(cls, row) -> "RankingPolicyVersion":
        return cls(
            id=row["id"],
            policy_id=row["policy_id"],
            version=row["version"],
            weights=_json(row["weights_json"], {}),
            filters=_json(row["filters_json"], {}),
            thresholds=_json(row["thresholds_json"], {}),
            created_by=row["created_by"],
            created_at=row["created_at"],
            evaluation_summary=_json(row["evaluation_summary_json"], None),
            status=row["status"],
        )


@dataclass(frozen=True)
class PolicyProposal:
    id: str
    namespace: str
    policy_type: str
    target_policy_id: str | None
    proposed_config: dict
    reason: str
    source_run_id: str | None
    evaluation_run_id: str | None
    status: str
    created_at: str
    reviewed_at: str | None
    reviewer: str | None
    review_note: str | None

    @classmethod
    def from_row(cls, row) -> "PolicyProposal":
        return cls(
            id=row["id"],
            namespace=row["namespace"],
            policy_type=row["policy_type"],
            target_policy_id=row["target_policy_id"],
            proposed_config=_json(row["proposed_config_json"], {}),
            reason=row["reason"],
            source_run_id=row["source_run_id"],
            evaluation_run_id=row["evaluation_run_id"],
            status=row["status"],
            created_at=row["created_at"],
            reviewed_at=row["reviewed_at"],
            reviewer=row["reviewer"],
            review_note=row["review_note"],
        )


@dataclass(frozen=True)
class PolicyApplicationRecord:
    id: str
    namespace: str
    proposal_id: str
    policy_type: str
    old_version_id: str | None
    new_version_id: str
    reason: str
    applied_by: str
    created_at: str

    @classmethod
    def from_row(cls, row) -> "PolicyApplicationRecord":
        return cls(
            id=row["id"],
            namespace=row["namespace"],
            proposal_id=row["proposal_id"],
            policy_type=row["policy_type"],
            old_version_id=row["old_version_id"],
            new_version_id=row["new_version_id"],
            reason=row["reason"],
            applied_by=row["applied_by"],
            created_at=row["created_at"],
        )


@dataclass(frozen=True)
class ProcedureVersion:
    id: str
    namespace: str
    procedure_claim_id: str | None
    version: int
    title: str
    text: str
    status: str
    source_proposal_id: str | None
    created_at: str
    metadata: dict = field(default_factory=dict)

    @classmethod
    def from_row(cls, row) -> "ProcedureVersion":
        return cls(
            id=row["id"],
            namespace=row["namespace"],
            procedure_claim_id=row["procedure_claim_id"],
            version=row["version"],
            title=row["title"],
            text=row["text"],
            status=row["status"],
            source_proposal_id=row["source_proposal_id"],
            created_at=row["created_at"],
            metadata=_json(row["metadata_json"], {}),
        )


@dataclass(frozen=True)
class ProcedureUpdateProposal:
    id: str
    namespace: str
    procedure_claim_id: str | None
    title: str
    proposed_text: str
    reason: str
    source_ids: list[str]
    source_type: str | None
    evaluation_run_id: str | None
    status: str
    created_at: str
    reviewed_at: str | None
    reviewer: str | None
    review_note: str | None

    @classmethod
    def from_row(cls, row) -> "ProcedureUpdateProposal":
        return cls(
            id=row["id"],
            namespace=row["namespace"],
            procedure_claim_id=row["procedure_claim_id"],
            title=row["title"],
            proposed_text=row["proposed_text"],
            reason=row["reason"],
            source_ids=_json(row["source_ids_json"], []),
            source_type=row["source_type"],
            evaluation_run_id=row["evaluation_run_id"],
            status=row["status"],
            created_at=row["created_at"],
            reviewed_at=row["reviewed_at"],
            reviewer=row["reviewer"],
            review_note=row["review_note"],
        )


@dataclass(frozen=True)
class LearningRun:
    id: str
    namespace: str
    project_id: str | None
    learning_targets: list[str]
    eval_set_id: str | None
    dry_run: bool
    proposals_created: list[str]
    warnings: list[str]
    created_at: str
    metadata: dict = field(default_factory=dict)

    @classmethod
    def from_row(cls, row) -> "LearningRun":
        return cls(
            id=row["id"],
            namespace=row["namespace"],
            project_id=row["project_id"],
            learning_targets=_json(row["learning_targets_json"], []),
            eval_set_id=row["eval_set_id"],
            dry_run=bool(row["dry_run"]),
            proposals_created=_json(row["proposals_created_json"], []),
            warnings=_json(row["warnings_json"], []),
            created_at=row["created_at"],
            metadata=_json(row["metadata_json"], {}),
        )


@dataclass(frozen=True)
class OptimizationRun:
    id: str
    namespace: str
    optimization_type: str
    objective: str
    baseline_policy_version_id: str | None
    eval_set_id: str | None
    trial_count: int
    best_metrics: dict
    proposal_id: str | None
    dry_run: bool
    created_at: str
    metadata: dict = field(default_factory=dict)

    @classmethod
    def from_row(cls, row) -> "OptimizationRun":
        return cls(
            id=row["id"],
            namespace=row["namespace"],
            optimization_type=row["optimization_type"],
            objective=row["objective"],
            baseline_policy_version_id=row["baseline_policy_version_id"],
            eval_set_id=row["eval_set_id"],
            trial_count=row["trial_count"],
            best_metrics=_json(row["best_metrics_json"], {}),
            proposal_id=row["proposal_id"],
            dry_run=bool(row["dry_run"]),
            created_at=row["created_at"],
            metadata=_json(row["metadata_json"], {}),
        )


@dataclass(frozen=True)
class LocalJob:
    id: str
    namespace: str | None
    job_type: str
    payload: dict
    priority: float
    status: str
    run_after: str | None
    attempts: int
    max_attempts: int
    last_error: str | None
    created_at: str
    updated_at: str

    @classmethod
    def from_row(cls, row) -> "LocalJob":
        return cls(
            id=row["id"],
            namespace=row["namespace"],
            job_type=row["job_type"],
            payload=_json(row["payload_json"], {}),
            priority=row["priority"],
            status=row["status"],
            run_after=row["run_after"],
            attempts=row["attempts"],
            max_attempts=row["max_attempts"],
            last_error=row["last_error"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )


@dataclass(frozen=True)
class MemoryHealthReport:
    id: str
    namespace: str
    project_id: str | None
    generated_at: str
    metrics: dict
    warnings: list[str]
    recommendations: list[str]

    @classmethod
    def from_row(cls, row) -> "MemoryHealthReport":
        return cls(
            id=row["id"],
            namespace=row["namespace"],
            project_id=row["project_id"],
            metrics=_json(row["metrics_json"], {}),
            warnings=_json(row["warnings_json"], []),
            recommendations=_json(row["recommendations_json"], []),
            generated_at=row["generated_at"],
        )


@dataclass(frozen=True)
class RollbackRecord:
    id: str
    namespace: str
    target_type: str
    target_id: str
    from_version_id: str | None
    to_version_id: str | None
    reason: str
    rolled_back_by: str
    created_at: str
    metadata: dict = field(default_factory=dict)

    @classmethod
    def from_row(cls, row) -> "RollbackRecord":
        return cls(
            id=row["id"],
            namespace=row["namespace"],
            target_type=row["target_type"],
            target_id=row["target_id"],
            from_version_id=row["from_version_id"],
            to_version_id=row["to_version_id"],
            reason=row["reason"],
            rolled_back_by=row["rolled_back_by"],
            created_at=row["created_at"],
            metadata=_json(row["metadata_json"], {}),
        )
