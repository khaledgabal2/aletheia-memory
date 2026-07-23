"""Evidence event model."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EvidenceEvent:
    id: str
    namespace: str
    session_id: str | None
    source_type: str
    source_uri: str | None
    content: str
    content_hash: str
    created_at: str
    observed_at: str | None
    trust_level: str
    privacy_level: str
    retention_policy: str

    @classmethod
    def from_row(cls, row) -> "EvidenceEvent":
        return cls(
            id=row["id"],
            namespace=row["namespace"],
            session_id=row["session_id"],
            source_type=row["source_type"],
            source_uri=row["source_uri"],
            content=row["content"],
            content_hash=row["content_hash"],
            created_at=row["created_at"],
            observed_at=row["observed_at"],
            trust_level=row["trust_level"],
            privacy_level=row["privacy_level"],
            retention_policy=row["retention_policy"],
        )

