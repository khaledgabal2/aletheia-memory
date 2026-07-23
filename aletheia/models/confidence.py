"""M2 confidence and feedback models."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ConfidenceSnapshot:
    claim_id: str
    truth_confidence: float
    retrieval_salience: float
    base_confidence: float
    effective_confidence: float
    decay_factor: float
    source_reliability_factor: float
    feedback_factor: float
    contradiction_factor: float
    verification_factor: float
    half_life_days: float
    age_days: float
    computed_at: str
    explanation: str | None = None

    @classmethod
    def from_row(cls, row) -> "ConfidenceSnapshot":
        return cls(
            claim_id=row["claim_id"],
            truth_confidence=row["truth_confidence"],
            retrieval_salience=row["retrieval_salience"],
            base_confidence=row["base_confidence"],
            effective_confidence=row["effective_confidence"],
            decay_factor=row["decay_factor"],
            source_reliability_factor=row["source_reliability_factor"],
            feedback_factor=row["feedback_factor"],
            contradiction_factor=row["contradiction_factor"],
            verification_factor=row["verification_factor"],
            half_life_days=row["half_life_days"],
            age_days=row["age_days"],
            computed_at=row["computed_at"],
            explanation=row["explanation"],
        )


@dataclass(frozen=True)
class FeedbackRecord:
    id: str
    namespace: str
    target_type: str
    target_id: str
    signal: str
    source: str
    note: str | None
    evidence_id: str | None
    strength: float
    created_at: str

    @classmethod
    def from_row(cls, row) -> "FeedbackRecord":
        return cls(
            id=row["id"],
            namespace=row["namespace"],
            target_type=row["target_type"],
            target_id=row["target_id"],
            signal=row["signal"],
            source=row["source"],
            note=row["note"],
            evidence_id=row["evidence_id"],
            strength=row["strength"],
            created_at=row["created_at"],
        )


@dataclass(frozen=True)
class HalfLifePolicy:
    id: str
    namespace: str | None
    memory_type: str | None
    predicate: str | None
    half_life_days: float
    reason: str
    created_at: str
    updated_at: str

    @classmethod
    def from_row(cls, row) -> "HalfLifePolicy":
        return cls(
            id=row["id"],
            namespace=row["namespace"],
            memory_type=row["memory_type"],
            predicate=row["predicate"],
            half_life_days=row["half_life_days"],
            reason=row["reason"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
