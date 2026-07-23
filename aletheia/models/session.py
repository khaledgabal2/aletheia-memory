"""Session model."""

from __future__ import annotations

import json
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Session:
    id: str
    namespace: str
    agent_id: str | None
    project_id: str | None
    title: str | None
    started_at: str
    ended_at: str | None
    metadata: dict = field(default_factory=dict)

    @classmethod
    def from_row(cls, row) -> "Session":
        return cls(
            id=row["id"],
            namespace=row["namespace"],
            agent_id=row["agent_id"],
            project_id=row["project_id"],
            title=row["title"],
            started_at=row["started_at"],
            ended_at=row["ended_at"],
            metadata=json.loads(row["metadata_json"] or "{}"),
        )
