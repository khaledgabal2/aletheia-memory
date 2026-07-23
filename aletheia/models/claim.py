"""Claim model."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Claim:
    id: str
    namespace: str
    subject: str
    predicate: str
    object: str
    memory_type: str
    status: str
    confidence_base: float
    confidence_effective: float
    half_life_days: float
    importance: float
    volatility: str
    created_at: str
    last_verified_at: str | None
    last_accessed_at: str | None
    valid_from: str | None
    valid_to: str | None
    evidence_ids: list[str] = field(default_factory=list)

    @classmethod
    def from_row(cls, row, evidence_ids: list[str] | None = None) -> "Claim":
        return cls(
            id=row["id"],
            namespace=row["namespace"],
            subject=row["subject"],
            predicate=row["predicate"],
            object=row["object"],
            memory_type=row["memory_type"],
            status=row["status"],
            confidence_base=row["confidence_base"],
            confidence_effective=row["confidence_effective"],
            half_life_days=row["half_life_days"],
            importance=row["importance"],
            volatility=row["volatility"],
            created_at=row["created_at"],
            last_verified_at=row["last_verified_at"],
            last_accessed_at=row["last_accessed_at"],
            valid_from=row["valid_from"],
            valid_to=row["valid_to"],
            evidence_ids=evidence_ids or [],
        )

