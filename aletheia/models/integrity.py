"""M2 memory integrity models."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ClaimRelationship:
    id: str
    namespace: str
    source_claim_id: str
    target_claim_id: str
    relationship_type: str
    confidence: float
    reason: str | None
    created_at: str

    @classmethod
    def from_row(cls, row) -> "ClaimRelationship":
        return cls(
            id=row["id"],
            namespace=row["namespace"],
            source_claim_id=row["source_claim_id"],
            target_claim_id=row["target_claim_id"],
            relationship_type=row["relationship_type"],
            confidence=row["confidence"],
            reason=row["reason"],
            created_at=row["created_at"],
        )


@dataclass(frozen=True)
class ClaimScope:
    id: str
    namespace: str
    claim_id: str
    scope_type: str
    applies_when: str | None
    valid_from: str | None
    valid_to: str | None
    reason: str
    created_at: str

    @classmethod
    def from_row(cls, row) -> "ClaimScope":
        return cls(
            id=row["id"],
            namespace=row["namespace"],
            claim_id=row["claim_id"],
            scope_type=row["scope_type"],
            applies_when=row["applies_when"],
            valid_from=row["valid_from"],
            valid_to=row["valid_to"],
            reason=row["reason"],
            created_at=row["created_at"],
        )


@dataclass(frozen=True)
class ConflictFamily:
    id: str
    namespace: str
    subject: str | None
    predicate: str | None
    conflict_type: str
    status: str
    active_claim_id: str | None
    resolution_strategy: str | None
    resolution_note: str | None
    created_at: str
    updated_at: str
    resolved_at: str | None
    claim_ids: list[str] = field(default_factory=list)

    @classmethod
    def from_row(cls, row, claim_ids: list[str] | None = None) -> "ConflictFamily":
        return cls(
            id=row["id"],
            namespace=row["namespace"],
            subject=row["subject"],
            predicate=row["predicate"],
            conflict_type=row["conflict_type"],
            status=row["status"],
            active_claim_id=row["active_claim_id"],
            resolution_strategy=row["resolution_strategy"],
            resolution_note=row["resolution_note"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            resolved_at=row["resolved_at"],
            claim_ids=claim_ids or [],
        )


@dataclass(frozen=True)
class ConflictResolution:
    id: str
    namespace: str
    conflict_id: str
    strategy: str
    active_claim_id: str | None
    superseded_claim_ids: list[str]
    rejected_claim_ids: list[str]
    scoped_claims: list[dict]
    note: str
    created_at: str
    status: str = "resolved"

    @classmethod
    def from_row(cls, row) -> "ConflictResolution":
        import json

        metadata = json.loads(row["metadata_json"] or "{}")
        return cls(
            id=row["id"],
            namespace=row["namespace"],
            conflict_id=row["conflict_id"],
            strategy=row["strategy"],
            active_claim_id=row["active_claim_id"],
            superseded_claim_ids=json.loads(row["superseded_claim_ids_json"] or "[]"),
            rejected_claim_ids=json.loads(row["rejected_claim_ids_json"] or "[]"),
            scoped_claims=json.loads(row["scoped_claims_json"] or "[]"),
            note=row["note"],
            created_at=row["created_at"],
            status=metadata.get("family_status") or "resolved",
        )


@dataclass(frozen=True)
class CurationDecision:
    id: str
    namespace: str
    claim_id: str | None
    decision_type: str
    target_status: str | None
    reason: str
    confidence_before: float | None
    confidence_after: float | None
    dry_run: bool
    applied: bool
    force: bool
    metadata: dict
    created_at: str

    @classmethod
    def from_row(cls, row) -> "CurationDecision":
        import json

        return cls(
            id=row["id"],
            namespace=row["namespace"],
            claim_id=row["claim_id"],
            decision_type=row["decision_type"],
            target_status=row["target_status"],
            reason=row["reason"],
            confidence_before=row["confidence_before"],
            confidence_after=row["confidence_after"],
            dry_run=bool(row["dry_run"]),
            applied=bool(row["applied"]),
            force=bool(row["force"]),
            metadata=json.loads(row["metadata_json"] or "{}"),
            created_at=row["created_at"],
        )


@dataclass(frozen=True)
class ClaimExplanation:
    claim_id: str
    claim: dict
    evidence: list[dict] = field(default_factory=list)
    confidence: dict | None = None
    conflicts: list[dict] = field(default_factory=list)
    relationships: list[dict] = field(default_factory=list)
    scopes: list[dict] = field(default_factory=list)
    history: list[dict] = field(default_factory=list)
    audit: list[dict] = field(default_factory=list)
