"""Retrieval result model."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class RetrievalResult:
    claim_id: str
    namespace: str
    text: str
    subject: str
    predicate: str
    object: str
    memory_type: str
    status: str
    score: float
    lexical_score: float
    confidence_base: float
    confidence_effective: float
    importance: float
    created_at: str
    last_verified_at: str | None
    evidence_ids: list[str] = field(default_factory=list)
    conflict_ids: list[str] = field(default_factory=list)
    project_ids: list[str] = field(default_factory=list)
    semantic_score: float = 0.0
    retrieval_mode: str = "lexical"
