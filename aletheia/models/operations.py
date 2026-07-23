"""M7 operational console, review, trace, metrics, and report models."""

from __future__ import annotations

import json
from dataclasses import dataclass, field


def _json(value: str | None, default):
    if value is None:
        return default
    return json.loads(value)


@dataclass(frozen=True)
class ConsoleSession:
    id: str
    client_id: str | None
    token_id: str | None
    namespace_grants: list[str]
    capabilities: list[str]
    privacy_ceiling: str
    created_at: str
    expires_at: str
    revoked_at: str | None
    metadata: dict = field(default_factory=dict)

    @classmethod
    def from_row(cls, row) -> "ConsoleSession":
        return cls(
            id=row["id"],
            client_id=row["client_id"],
            token_id=row["token_id"],
            namespace_grants=_json(row["namespace_grants_json"], []),
            capabilities=_json(row["capabilities_json"], []),
            privacy_ceiling=row["privacy_ceiling"],
            created_at=row["created_at"],
            expires_at=row["expires_at"],
            revoked_at=row["revoked_at"],
            metadata=_json(row["metadata_json"], {}),
        )


@dataclass(frozen=True)
class ConsoleActionConfirmation:
    id: str
    namespace: str | None
    action_type: str
    target_id: str | None
    target_type: str | None
    confirmation_text: str | None
    reason: str
    actor: str
    created_at: str
    metadata: dict = field(default_factory=dict)

    @classmethod
    def from_row(cls, row) -> "ConsoleActionConfirmation":
        return cls(
            id=row["id"],
            namespace=row["namespace"],
            action_type=row["action_type"],
            target_id=row["target_id"],
            target_type=row["target_type"],
            confirmation_text=row["confirmation_text"],
            reason=row["reason"],
            actor=row["actor"],
            created_at=row["created_at"],
            metadata=_json(row["metadata_json"], {}),
        )


@dataclass(frozen=True)
class ReviewTask:
    id: str
    namespace: str
    task_type: str
    title: str
    description: str
    target_id: str
    target_type: str
    priority: float
    severity: str
    status: str
    recommended_action: str | None
    created_at: str
    updated_at: str
    due_at: str | None
    metadata: dict = field(default_factory=dict)

    @classmethod
    def from_row(cls, row) -> "ReviewTask":
        return cls(
            id=row["id"],
            namespace=row["namespace"],
            task_type=row["task_type"],
            title=row["title"],
            description=row["description"],
            target_id=row["target_id"],
            target_type=row["target_type"],
            priority=row["priority"],
            severity=row["severity"],
            status=row["status"],
            recommended_action=row["recommended_action"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            due_at=row["due_at"],
            metadata=_json(row["metadata_json"], {}),
        )


@dataclass(frozen=True)
class ReviewTaskEvent:
    id: str
    review_task_id: str
    event_type: str
    actor: str
    note: str | None
    created_at: str
    metadata: dict = field(default_factory=dict)

    @classmethod
    def from_row(cls, row) -> "ReviewTaskEvent":
        return cls(
            id=row["id"],
            review_task_id=row["review_task_id"],
            event_type=row["event_type"],
            actor=row["actor"],
            note=row["note"],
            created_at=row["created_at"],
            metadata=_json(row["metadata_json"], {}),
        )


@dataclass(frozen=True)
class NotificationEvent:
    id: str
    namespace: str | None
    notification_type: str
    title: str
    message: str
    severity: str
    status: str
    target_id: str | None
    target_type: str | None
    created_at: str
    dismissed_at: str | None
    snoozed_until: str | None
    metadata: dict = field(default_factory=dict)

    @classmethod
    def from_row(cls, row) -> "NotificationEvent":
        return cls(
            id=row["id"],
            namespace=row["namespace"],
            notification_type=row["notification_type"],
            title=row["title"],
            message=row["message"],
            severity=row["severity"],
            status=row["status"],
            target_id=row["target_id"],
            target_type=row["target_type"],
            created_at=row["created_at"],
            dismissed_at=row["dismissed_at"],
            snoozed_until=row["snoozed_until"],
            metadata=_json(row["metadata_json"], {}),
        )


@dataclass(frozen=True)
class DashboardSavedView:
    id: str
    namespace: str | None
    name: str
    view_type: str
    filters: dict
    sort: dict | None
    created_at: str
    updated_at: str
    metadata: dict = field(default_factory=dict)

    @classmethod
    def from_row(cls, row) -> "DashboardSavedView":
        return cls(
            id=row["id"],
            namespace=row["namespace"],
            name=row["name"],
            view_type=row["view_type"],
            filters=_json(row["filters_json"], {}),
            sort=_json(row["sort_json"], None),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            metadata=_json(row["metadata_json"], {}),
        )


@dataclass(frozen=True)
class MetricSnapshot:
    id: str
    namespace: str | None
    project_id: str | None
    metrics: dict
    source: str
    generated_at: str
    metadata: dict = field(default_factory=dict)

    @classmethod
    def from_row(cls, row) -> "MetricSnapshot":
        return cls(
            id=row["id"],
            namespace=row["namespace"],
            project_id=row["project_id"],
            metrics=_json(row["metrics_json"], {}),
            source=row["source"],
            generated_at=row["generated_at"],
            metadata=_json(row["metadata_json"], {}),
        )


@dataclass(frozen=True)
class TraceRun:
    id: str
    namespace: str
    trace_type: str
    query: str | None
    project_id: str | None
    session_id: str | None
    retrieval_mode: str | None
    policy_version_id: str | None
    duration_ms: int | None
    created_at: str
    metadata: dict = field(default_factory=dict)

    @classmethod
    def from_row(cls, row) -> "TraceRun":
        return cls(
            id=row["id"],
            namespace=row["namespace"],
            trace_type=row["trace_type"],
            query=row["query"],
            project_id=row["project_id"],
            session_id=row["session_id"],
            retrieval_mode=row["retrieval_mode"],
            policy_version_id=row["policy_version_id"],
            duration_ms=row["duration_ms"],
            created_at=row["created_at"],
            metadata=_json(row["metadata_json"], {}),
        )


@dataclass(frozen=True)
class TraceEvent:
    id: str
    trace_run_id: str
    event_type: str
    message: str
    created_at: str
    metadata: dict = field(default_factory=dict)

    @classmethod
    def from_row(cls, row) -> "TraceEvent":
        return cls(
            id=row["id"],
            trace_run_id=row["trace_run_id"],
            event_type=row["event_type"],
            message=row["message"],
            created_at=row["created_at"],
            metadata=_json(row["metadata_json"], {}),
        )


@dataclass(frozen=True)
class RetrievalTraceItem:
    id: str
    trace_run_id: str
    target_id: str
    target_type: str
    final_score: float | None
    lexical_score: float | None
    semantic_score: float | None
    confidence_score: float | None
    salience_score: float | None
    included: bool
    omission_reason: str | None
    rank: int | None
    metadata: dict = field(default_factory=dict)

    @classmethod
    def from_row(cls, row) -> "RetrievalTraceItem":
        return cls(
            id=row["id"],
            trace_run_id=row["trace_run_id"],
            target_id=row["target_id"],
            target_type=row["target_type"],
            final_score=row["final_score"],
            lexical_score=row["lexical_score"],
            semantic_score=row["semantic_score"],
            confidence_score=row["confidence_score"],
            salience_score=row["salience_score"],
            included=bool(row["included"]),
            omission_reason=row["omission_reason"],
            rank=row["rank"],
            metadata=_json(row["metadata_json"], {}),
        )


@dataclass(frozen=True)
class ContextTraceItem:
    id: str
    trace_run_id: str
    target_id: str
    target_type: str
    section: str | None
    included: bool
    omission_reason: str | None
    token_estimate: int | None
    rank: int | None
    metadata: dict = field(default_factory=dict)

    @classmethod
    def from_row(cls, row) -> "ContextTraceItem":
        return cls(
            id=row["id"],
            trace_run_id=row["trace_run_id"],
            target_id=row["target_id"],
            target_type=row["target_type"],
            section=row["section"],
            included=bool(row["included"]),
            omission_reason=row["omission_reason"],
            token_estimate=row["token_estimate"],
            rank=row["rank"],
            metadata=_json(row["metadata_json"], {}),
        )


@dataclass(frozen=True)
class ReportExport:
    id: str
    namespace: str | None
    report_type: str
    format: str
    file_path: str
    created_at: str
    metadata: dict = field(default_factory=dict)

    @classmethod
    def from_row(cls, row) -> "ReportExport":
        return cls(
            id=row["id"],
            namespace=row["namespace"],
            report_type=row["report_type"],
            format=row["format"],
            file_path=row["file_path"],
            created_at=row["created_at"],
            metadata=_json(row["metadata_json"], {}),
        )
