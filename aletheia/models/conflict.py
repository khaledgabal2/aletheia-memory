"""Conflict model."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Conflict:
    id: str
    namespace: str
    subject: str
    predicate: str
    status: str
    active_claim_id: str | None
    resolution_note: str | None
    created_at: str
    resolved_at: str | None
    claim_ids: list[str] = field(default_factory=list)

    @classmethod
    def from_row(cls, row, claim_ids: list[str] | None = None) -> "Conflict":
        return cls(
            id=row["id"],
            namespace=row["namespace"],
            subject=row["subject"],
            predicate=row["predicate"],
            status=row["status"],
            active_claim_id=row["active_claim_id"],
            resolution_note=row["resolution_note"],
            created_at=row["created_at"],
            resolved_at=row["resolved_at"],
            claim_ids=claim_ids or [],
        )

