"""Project model."""

from __future__ import annotations

import json
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Project:
    id: str
    namespace: str
    title: str
    description: str | None
    status: str
    created_at: str
    updated_at: str
    metadata: dict = field(default_factory=dict)

    @classmethod
    def from_row(cls, row) -> "Project":
        return cls(
            id=row["id"],
            namespace=row["namespace"],
            title=row["title"],
            description=row["description"],
            status=row["status"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            metadata=json.loads(row["metadata_json"] or "{}"),
        )
