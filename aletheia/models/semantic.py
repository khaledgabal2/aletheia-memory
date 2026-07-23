"""M3 semantic indexing models."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class SemanticIndexRun:
    namespace: str
    target_type: str
    provider: str
    model: str
    indexed_count: int
    skipped_count: int
    blocked_count: int = 0
    stale_count: int = 0
    pruned_count: int = 0
    verified_count: int = 0
    provider_type: str = "unknown"
    vector_store: str = "sqlite_local"
    index_version: str | None = None
    status: str = "completed"
    target_ids: list[str] = field(default_factory=list)
    created_at: str | None = None
    warnings: list[str] = field(default_factory=list)
