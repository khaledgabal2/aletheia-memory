"""M3 entity and category models."""

from __future__ import annotations

import json
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Entity:
    id: str
    namespace: str
    canonical_name: str
    entity_type: str
    aliases: list[str]
    created_at: str
    updated_at: str
    metadata: dict = field(default_factory=dict)

    @classmethod
    def from_row(cls, row, aliases: list[str] | None = None) -> "Entity":
        return cls(
            id=row["id"],
            namespace=row["namespace"],
            canonical_name=row["canonical_name"],
            entity_type=row["entity_type"],
            aliases=aliases or [],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            metadata=json.loads(row["metadata_json"] or "{}"),
        )


@dataclass(frozen=True)
class EntityAlias:
    id: str
    namespace: str
    entity_id: str
    alias: str
    created_at: str

    @classmethod
    def from_row(cls, row) -> "EntityAlias":
        return cls(
            id=row["id"],
            namespace=row["namespace"],
            entity_id=row["entity_id"],
            alias=row["alias"],
            created_at=row["created_at"],
        )


@dataclass(frozen=True)
class EntityMention:
    id: str
    namespace: str
    entity_id: str | None
    evidence_id: str
    mention_text: str
    start_char: int | None
    end_char: int | None
    confidence: float
    created_at: str

    @classmethod
    def from_row(cls, row) -> "EntityMention":
        return cls(
            id=row["id"],
            namespace=row["namespace"],
            entity_id=row["entity_id"],
            evidence_id=row["evidence_id"],
            mention_text=row["mention_text"],
            start_char=row["start_char"],
            end_char=row["end_char"],
            confidence=row["confidence"],
            created_at=row["created_at"],
        )


@dataclass(frozen=True)
class CategoryLabel:
    id: str
    namespace: str
    target_id: str
    target_type: str
    label: str
    confidence: float
    reason: str | None
    created_at: str

    @classmethod
    def from_row(cls, row) -> "CategoryLabel":
        return cls(
            id=row["id"],
            namespace=row["namespace"],
            target_id=row["target_id"],
            target_type=row["target_type"],
            label=row["label"],
            confidence=row["confidence"],
            reason=row["reason"],
            created_at=row["created_at"],
        )
