"""M1 structured context pack models."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass(frozen=True)
class ContextItem:
    text: str
    claim_id: str
    memory_type: str
    confidence_effective: float
    status: str
    evidence_ids: list[str] = field(default_factory=list)
    reason: str = "relevant"
    scope: str | None = None
    source_kind: str = "direct_claim"
    reflection_id: str | None = None
    inference_id: str | None = None
    abstraction_level: int | None = None
    is_inferred: bool = False
    is_reflected: bool = False
    is_stale: bool = False
    derivation: dict | None = None

    def __contains__(self, value: str) -> bool:
        return value in self.text


@dataclass(frozen=True)
class ContextWarning:
    text: str
    warning_type: str
    claim_ids: list[str] = field(default_factory=list)
    conflict_ids: list[str] = field(default_factory=list)

    def __contains__(self, value: str) -> bool:
        return value in self.text


@dataclass(frozen=True)
class OmittedMemory:
    claim_id: str
    reason: str
    score: float


@dataclass(frozen=True)
class ContextPack:
    namespace: str
    query: str
    session_id: str | None
    project_id: str | None
    token_budget: int
    generated_at: str
    id: str | None = None
    ranking_policy_version_id: str | None = None
    context_policy_version_id: str | None = None
    metadata: dict = field(default_factory=dict)
    core_memory: list[ContextItem] = field(default_factory=list)
    project_memory: list[ContextItem] = field(default_factory=list)
    session_memory: list[ContextItem] = field(default_factory=list)
    procedural_memory: list[ContextItem] = field(default_factory=list)
    reflection_memory: list[ContextItem] = field(default_factory=list)
    relevant_memory: list[ContextItem] = field(default_factory=list)
    warnings: list[ContextWarning] = field(default_factory=list)
    omitted: list[OmittedMemory] = field(default_factory=list)

    @property
    def sources(self) -> list[str]:
        evidence_ids: set[str] = set()
        for item in self.items():
            evidence_ids.update(item.evidence_ids)
        return sorted(evidence_ids)

    def items(self) -> list[ContextItem]:
        return [
            *self.core_memory,
            *self.project_memory,
            *self.session_memory,
            *self.procedural_memory,
            *self.reflection_memory,
            *self.relevant_memory,
        ]

    def to_dict(self) -> dict:
        return {
            "namespace": self.namespace,
            "query": self.query,
            "session_id": self.session_id,
            "project_id": self.project_id,
            "token_budget": self.token_budget,
            "generated_at": self.generated_at,
            "id": self.id,
            "ranking_policy_version_id": self.ranking_policy_version_id,
            "context_policy_version_id": self.context_policy_version_id,
            "metadata": self.metadata,
            "core_memory": [asdict(item) for item in self.core_memory],
            "project_memory": [asdict(item) for item in self.project_memory],
            "session_memory": [asdict(item) for item in self.session_memory],
            "procedural_memory": [asdict(item) for item in self.procedural_memory],
            "reflection_memory": [asdict(item) for item in self.reflection_memory],
            "relevant_memory": [asdict(item) for item in self.relevant_memory],
            "warnings": [asdict(warning) for warning in self.warnings],
            "omitted": [asdict(omitted) for omitted in self.omitted],
            "sources": self.sources,
        }

    def as_dict(self) -> dict:
        return self.to_dict()

    def to_markdown(self, include_confidence: bool = True) -> str:
        lines = ["## Memory Context"]
        sections = [
            ("Core Memory", self.core_memory),
            ("Project Memory", self.project_memory),
            ("Session Memory", self.session_memory),
            ("Procedural Memory", self.procedural_memory),
            ("Reflections", self.reflection_memory),
            ("Relevant Memory", self.relevant_memory),
        ]
        for title, items in sections:
            if not items:
                continue
            lines.append(f"### {title}")
            for item in items:
                label = ""
                if item.source_kind != "direct_claim":
                    label = f"[{item.source_kind}] "
                lines.append(f"- {label}{item.text}")
                if include_confidence:
                    detail = (
                        f"confidence: {item.confidence_effective:.2f} | "
                        f"claim: {item.claim_id} | reason: {item.reason}"
                    )
                    if item.scope:
                        detail = f"scope: {item.scope} | " + detail
                    lines.append(
                        "  " + detail
                    )
        if self.warnings:
            lines.append("### Warnings")
            for warning in self.warnings:
                lines.append(f"- {warning.text}")
                details = []
                if warning.claim_ids:
                    details.append(f"claims: {', '.join(warning.claim_ids)}")
                if warning.conflict_ids:
                    details.append(f"conflicts: {', '.join(warning.conflict_ids)}")
                if details:
                    lines.append("  " + " | ".join(details))
        if self.omitted:
            lines.append("### Omitted")
            for omitted in self.omitted:
                lines.append(
                    f"- {omitted.claim_id}: {omitted.reason} "
                    f"(score: {omitted.score:.3f})"
                )
        return "\n".join(lines)

    def render_markdown(self) -> str:
        return self.to_markdown()
