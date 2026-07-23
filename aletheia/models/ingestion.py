"""M3 ingestion, extraction, and candidate memory models."""

from __future__ import annotations

import json
from dataclasses import dataclass, field


@dataclass(frozen=True)
class IngestionBatch:
    id: str
    namespace: str
    source_type: str
    source_uri: str | None
    title: str | None
    project_id: str | None
    session_id: str | None
    evidence_ids: list[str]
    created_at: str
    metadata: dict = field(default_factory=dict)

    @classmethod
    def from_row(cls, row, evidence_ids: list[str] | None = None) -> "IngestionBatch":
        return cls(
            id=row["id"],
            namespace=row["namespace"],
            source_type=row["source_type"],
            source_uri=row["source_uri"],
            title=row["title"],
            project_id=row["project_id"],
            session_id=row["session_id"],
            evidence_ids=evidence_ids or [],
            created_at=row["created_at"],
            metadata=json.loads(row["metadata_json"] or "{}"),
        )


@dataclass(frozen=True)
class SourceDocument:
    id: str
    namespace: str
    batch_id: str
    title: str | None
    source_type: str
    source_uri: str | None
    content_hash: str
    created_at: str
    metadata: dict = field(default_factory=dict)

    @classmethod
    def from_row(cls, row) -> "SourceDocument":
        return cls(
            id=row["id"],
            namespace=row["namespace"],
            batch_id=row["batch_id"],
            title=row["title"],
            source_type=row["source_type"],
            source_uri=row["source_uri"],
            content_hash=row["content_hash"],
            created_at=row["created_at"],
            metadata=json.loads(row["metadata_json"] or "{}"),
        )


@dataclass(frozen=True)
class EvidenceSpan:
    evidence_id: str
    start_char: int
    end_char: int
    text: str
    role: str = "supporting"
    id: str | None = None
    created_at: str | None = None

    @classmethod
    def from_row(cls, row) -> "EvidenceSpan":
        return cls(
            id=row["id"],
            evidence_id=row["evidence_id"],
            start_char=row["start_char"],
            end_char=row["end_char"],
            text=row["span_text"],
            role=row["role"],
            created_at=row["created_at"],
        )


@dataclass(frozen=True)
class ExtractionPolicy:
    allowed_memory_types: list[str] = field(
        default_factory=lambda: [
            "preference",
            "project",
            "procedure",
            "fact",
            "decision",
            "correction",
            "session_summary",
            "inference",
        ]
    )
    max_candidates_per_event: int = 20
    require_evidence_spans: bool = True
    allow_inference_candidates: bool = True
    allow_preference_candidates: bool = True
    allow_procedure_candidates: bool = True
    allow_project_candidates: bool = True
    min_candidate_confidence: float = 0.50
    privacy_mode: str = "inherit_from_evidence"
    auto_promote: bool = False

    def to_dict(self) -> dict:
        return {
            "allowed_memory_types": list(self.allowed_memory_types),
            "max_candidates_per_event": self.max_candidates_per_event,
            "require_evidence_spans": self.require_evidence_spans,
            "allow_inference_candidates": self.allow_inference_candidates,
            "allow_preference_candidates": self.allow_preference_candidates,
            "allow_procedure_candidates": self.allow_procedure_candidates,
            "allow_project_candidates": self.allow_project_candidates,
            "min_candidate_confidence": self.min_candidate_confidence,
            "privacy_mode": self.privacy_mode,
            "auto_promote": self.auto_promote,
        }


@dataclass(frozen=True)
class ExtractionRun:
    id: str
    namespace: str
    extractor_name: str
    extractor_version: str
    batch_id: str | None
    evidence_ids: list[str]
    candidate_count: int
    stored_candidate_count: int
    dry_run: bool
    created_at: str
    warnings: list[str] = field(default_factory=list)

    @classmethod
    def from_row(cls, row, evidence_ids: list[str] | None = None) -> "ExtractionRun":
        return cls(
            id=row["id"],
            namespace=row["namespace"],
            extractor_name=row["extractor_name"],
            extractor_version=row["extractor_version"],
            batch_id=row["batch_id"],
            evidence_ids=evidence_ids or [],
            candidate_count=row["candidate_count"],
            stored_candidate_count=row["stored_candidate_count"],
            dry_run=bool(row["dry_run"]),
            created_at=row["created_at"],
            warnings=json.loads(row["warnings_json"] or "[]"),
        )


@dataclass(frozen=True)
class CandidateClaim:
    id: str
    namespace: str
    subject: str
    predicate: str
    object: str
    memory_type: str
    candidate_status: str
    extraction_run_id: str
    evidence_ids: list[str]
    evidence_spans: list[EvidenceSpan]
    suggested_confidence: float
    suggested_importance: float
    suggested_half_life_days: float | None
    suggested_scope: dict | None
    suggested_categories: list[str]
    suggested_entities: list[str]
    contradiction_risk: float
    duplicate_risk: float
    privacy_level: str
    created_at: str
    metadata: dict = field(default_factory=dict)

    @classmethod
    def from_row(
        cls,
        row,
        *,
        evidence_ids: list[str] | None = None,
        evidence_spans: list[EvidenceSpan] | None = None,
        suggested_categories: list[str] | None = None,
        suggested_entities: list[str] | None = None,
    ) -> "CandidateClaim":
        return cls(
            id=row["id"],
            namespace=row["namespace"],
            subject=row["subject"],
            predicate=row["predicate"],
            object=row["object"],
            memory_type=row["memory_type"],
            candidate_status=row["candidate_status"],
            extraction_run_id=row["extraction_run_id"],
            evidence_ids=evidence_ids or [],
            evidence_spans=evidence_spans or [],
            suggested_confidence=row["suggested_confidence"],
            suggested_importance=row["suggested_importance"],
            suggested_half_life_days=row["suggested_half_life_days"],
            suggested_scope=json.loads(row["suggested_scope_json"] or "null"),
            suggested_categories=suggested_categories or [],
            suggested_entities=suggested_entities or [],
            contradiction_risk=row["contradiction_risk"],
            duplicate_risk=row["duplicate_risk"],
            privacy_level=row["privacy_level"],
            created_at=row["created_at"],
            metadata=json.loads(row["metadata_json"] or "{}"),
        )


@dataclass(frozen=True)
class CandidateClaimDraft:
    subject: str
    predicate: str
    object: str
    memory_type: str
    evidence_spans: list[EvidenceSpan]
    suggested_confidence: float = 0.65
    suggested_importance: float = 0.5
    suggested_half_life_days: float | None = None
    suggested_scope: dict | None = None
    suggested_categories: list[str] = field(default_factory=list)
    suggested_entities: list[str] = field(default_factory=list)
    privacy_level: str = "personal"
    metadata: dict = field(default_factory=dict)


@dataclass(frozen=True)
class ExtractionDecision:
    id: str
    namespace: str
    candidate_id: str
    decision: str
    reason: str
    reviewer: str
    edits: dict | None
    created_at: str

    @classmethod
    def from_row(cls, row) -> "ExtractionDecision":
        return cls(
            id=row["id"],
            namespace=row["namespace"],
            candidate_id=row["candidate_id"],
            decision=row["decision"],
            reason=row["reason"],
            reviewer=row["reviewer"],
            edits=json.loads(row["edits_json"] or "null"),
            created_at=row["created_at"],
        )


@dataclass(frozen=True)
class ContentRiskFlag:
    id: str
    namespace: str
    evidence_id: str
    risk_type: str
    severity: str
    span_text: str | None
    start_char: int | None
    end_char: int | None
    note: str | None
    created_at: str

    @classmethod
    def from_row(cls, row) -> "ContentRiskFlag":
        return cls(
            id=row["id"],
            namespace=row["namespace"],
            evidence_id=row["evidence_id"],
            risk_type=row["risk_type"],
            severity=row["severity"],
            span_text=row["span_text"],
            start_char=row["start_char"],
            end_char=row["end_char"],
            note=row["note"],
            created_at=row["created_at"],
        )


PromptInjectionFlag = ContentRiskFlag
