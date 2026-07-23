"""M4 reasoned memory, inference, reflection, and derivation models."""

from __future__ import annotations

import json
from dataclasses import dataclass, field


@dataclass(frozen=True)
class InferenceRun:
    id: str
    namespace: str
    engines: list[str]
    project_id: str | None
    session_id: str | None
    target_claim_ids: list[str]
    target_evidence_ids: list[str]
    rule_ids: list[str]
    dry_run: bool
    inference_count: int
    persisted_count: int
    created_at: str
    warnings: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    @classmethod
    def from_row(cls, row) -> "InferenceRun":
        return cls(
            id=row["id"],
            namespace=row["namespace"],
            engines=json.loads(row["engines_json"] or "[]"),
            project_id=row["project_id"],
            session_id=row["session_id"],
            target_claim_ids=json.loads(row["target_claim_ids_json"] or "[]"),
            target_evidence_ids=json.loads(row["target_evidence_ids_json"] or "[]"),
            rule_ids=json.loads(row["rule_ids_json"] or "[]"),
            dry_run=bool(row["dry_run"]),
            inference_count=row["inference_count"],
            persisted_count=row["persisted_count"],
            created_at=row["created_at"],
            warnings=json.loads(row["warnings_json"] or "[]"),
            metadata=json.loads(row["metadata_json"] or "{}"),
        )


@dataclass(frozen=True)
class InferenceCandidate:
    id: str
    namespace: str
    inference_run_id: str
    inference_type: str
    subject: str | None
    predicate: str | None
    object: str | None
    text: str
    status: str
    source_claim_ids: list[str]
    source_evidence_ids: list[str]
    source_candidate_ids: list[str]
    rule_id: str | None
    engine: str
    derivation_confidence: float
    suggested_truth_confidence: float
    suggested_retrieval_salience: float
    inference_strength: str
    abstraction_level: int
    invalidation_policy: str
    created_at: str
    metadata: dict = field(default_factory=dict)

    @classmethod
    def from_row(
        cls,
        row,
        *,
        source_claim_ids: list[str] | None = None,
        source_evidence_ids: list[str] | None = None,
        source_candidate_ids: list[str] | None = None,
    ) -> "InferenceCandidate":
        return cls(
            id=row["id"],
            namespace=row["namespace"],
            inference_run_id=row["inference_run_id"],
            inference_type=row["inference_type"],
            subject=row["subject"],
            predicate=row["predicate"],
            object=row["object"],
            text=row["text"],
            status=row["status"],
            source_claim_ids=source_claim_ids or [],
            source_evidence_ids=source_evidence_ids or [],
            source_candidate_ids=source_candidate_ids or [],
            rule_id=row["rule_id"],
            engine=row["engine"],
            derivation_confidence=row["derivation_confidence"],
            suggested_truth_confidence=row["suggested_truth_confidence"],
            suggested_retrieval_salience=row["suggested_retrieval_salience"],
            inference_strength=row["inference_strength"],
            abstraction_level=row["abstraction_level"],
            invalidation_policy=row["invalidation_policy"],
            created_at=row["created_at"],
            metadata=json.loads(row["metadata_json"] or "{}"),
        )


@dataclass(frozen=True)
class InferenceDecision:
    id: str
    namespace: str
    inference_id: str
    decision: str
    reason: str
    reviewer: str
    edits: dict | None
    created_at: str

    @classmethod
    def from_row(cls, row) -> "InferenceDecision":
        return cls(
            id=row["id"],
            namespace=row["namespace"],
            inference_id=row["inference_id"],
            decision=row["decision"],
            reason=row["reason"],
            reviewer=row["reviewer"],
            edits=json.loads(row["edits_json"] or "null"),
            created_at=row["created_at"],
        )


@dataclass(frozen=True)
class InferenceRule:
    id: str
    namespace: str | None
    name: str
    rule_type: str
    description: str
    condition: dict
    conclusion: dict
    confidence_policy: dict
    enabled: bool
    created_at: str
    updated_at: str

    @classmethod
    def from_row(cls, row) -> "InferenceRule":
        return cls(
            id=row["id"],
            namespace=row["namespace"],
            name=row["name"],
            rule_type=row["rule_type"],
            description=row["description"],
            condition=json.loads(row["condition_json"] or "{}"),
            conclusion=json.loads(row["conclusion_json"] or "{}"),
            confidence_policy=json.loads(row["confidence_policy_json"] or "{}"),
            enabled=bool(row["enabled"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )


@dataclass(frozen=True)
class RuleExecutionResult:
    id: str
    rule_id: str
    namespace: str
    matched_count: int
    inference_count: int
    dry_run: bool
    created_at: str
    warnings: list[str] = field(default_factory=list)

    @classmethod
    def from_row(cls, row) -> "RuleExecutionResult":
        return cls(
            id=row["id"],
            rule_id=row["rule_id"],
            namespace=row["namespace"],
            matched_count=row["matched_count"],
            inference_count=row["inference_count"],
            dry_run=bool(row["dry_run"]),
            created_at=row["created_at"],
            warnings=json.loads(row["warnings_json"] or "[]"),
        )


@dataclass(frozen=True)
class DerivationEdge:
    id: str
    namespace: str
    source_id: str
    source_type: str
    target_id: str
    target_type: str
    relationship: str
    rule_id: str | None
    confidence: float
    created_at: str
    metadata: dict = field(default_factory=dict)

    @classmethod
    def from_row(cls, row) -> "DerivationEdge":
        return cls(
            id=row["id"],
            namespace=row["namespace"],
            source_id=row["source_id"],
            source_type=row["source_type"],
            target_id=row["target_id"],
            target_type=row["target_type"],
            relationship=row["relationship"],
            rule_id=row["rule_id"],
            confidence=row["confidence"],
            created_at=row["created_at"],
            metadata=json.loads(row["metadata_json"] or "{}"),
        )


@dataclass(frozen=True)
class Reflection:
    id: str
    namespace: str
    title: str
    text: str
    abstraction_level: int
    source_claim_ids: list[str]
    source_evidence_ids: list[str]
    source_reflection_ids: list[str]
    project_id: str | None
    status: str
    confidence_effective: float
    retrieval_salience: float
    builder: str
    created_at: str
    updated_at: str
    metadata: dict = field(default_factory=dict)

    @classmethod
    def from_row(
        cls,
        row,
        *,
        source_claim_ids: list[str] | None = None,
        source_evidence_ids: list[str] | None = None,
        source_reflection_ids: list[str] | None = None,
    ) -> "Reflection":
        return cls(
            id=row["id"],
            namespace=row["namespace"],
            title=row["title"],
            text=row["text"],
            abstraction_level=row["abstraction_level"],
            source_claim_ids=source_claim_ids or [],
            source_evidence_ids=source_evidence_ids or [],
            source_reflection_ids=source_reflection_ids or [],
            project_id=row["project_id"],
            status=row["status"],
            confidence_effective=row["confidence_effective"],
            retrieval_salience=row["retrieval_salience"],
            builder=row["builder"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            metadata=json.loads(row["metadata_json"] or "{}"),
        )


@dataclass(frozen=True)
class ReflectionExpansion:
    reflection_id: str
    reflection_text: str
    source_claims: list
    source_evidence: list
    derivation_edges: list[DerivationEdge]
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class AbstractionRecord:
    id: str
    namespace: str
    abstraction_text: str
    abstraction_level: int
    source_ids: list[str]
    source_type: str
    information_loss_policy: str
    status: str
    created_at: str
    metadata: dict = field(default_factory=dict)

    @classmethod
    def from_row(cls, row, source_ids: list[str] | None = None) -> "AbstractionRecord":
        return cls(
            id=row["id"],
            namespace=row["namespace"],
            abstraction_text=row["abstraction_text"],
            abstraction_level=row["abstraction_level"],
            source_ids=source_ids or [],
            source_type=row["source_type"],
            information_loss_policy=row["information_loss_policy"],
            status=row["status"],
            created_at=row["created_at"],
            metadata=json.loads(row["metadata_json"] or "{}"),
        )


@dataclass(frozen=True)
class SemanticCluster:
    id: str
    namespace: str
    label: str | None
    cluster_type: str
    created_by: str
    confidence: float
    member_ids: list[str]
    created_at: str
    updated_at: str
    metadata: dict = field(default_factory=dict)

    @classmethod
    def from_row(cls, row, member_ids: list[str] | None = None) -> "SemanticCluster":
        return cls(
            id=row["id"],
            namespace=row["namespace"],
            label=row["label"],
            cluster_type=row["cluster_type"],
            created_by=row["created_by"],
            confidence=row["confidence"],
            member_ids=member_ids or [],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            metadata=json.loads(row["metadata_json"] or "{}"),
        )


@dataclass(frozen=True)
class SemanticRelation:
    id: str
    namespace: str
    source_id: str
    source_type: str
    target_id: str
    target_type: str
    relation_type: str
    confidence: float
    created_at: str
    metadata: dict = field(default_factory=dict)

    @classmethod
    def from_row(cls, row) -> "SemanticRelation":
        return cls(
            id=row["id"],
            namespace=row["namespace"],
            source_id=row["source_id"],
            source_type=row["source_type"],
            target_id=row["target_id"],
            target_type=row["target_type"],
            relation_type=row["relation_type"],
            confidence=row["confidence"],
            created_at=row["created_at"],
            metadata=json.loads(row["metadata_json"] or "{}"),
        )


@dataclass(frozen=True)
class InvalidationEvent:
    id: str
    namespace: str
    source_id: str
    source_type: str
    affected_id: str
    affected_type: str
    action: str
    reason: str
    created_at: str
    metadata: dict = field(default_factory=dict)

    @classmethod
    def from_row(cls, row) -> "InvalidationEvent":
        return cls(
            id=row["id"],
            namespace=row["namespace"],
            source_id=row["source_id"],
            source_type=row["source_type"],
            affected_id=row["affected_id"],
            affected_type=row["affected_type"],
            action=row["action"],
            reason=row["reason"],
            created_at=row["created_at"],
            metadata=json.loads(row["metadata_json"] or "{}"),
        )


@dataclass(frozen=True)
class DerivationTrace:
    target_id: str
    target_type: str
    nodes: list[dict]
    edges: list[DerivationEdge]
    invalidation_risks: list[str]
    root_evidence_ids: list[str]


@dataclass(frozen=True)
class InferenceExplanation:
    inference_id: str
    inference: dict
    sources: list[dict] = field(default_factory=list)
    rule: dict | None = None
    confidence: dict | None = None
    invalidation: list[str] = field(default_factory=list)
    can_promote: bool = False
    promotion_failures: list[str] = field(default_factory=list)
    explanation: str = ""
