"""Installed documentation discovery for Aletheia."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class HelpDocument:
    slug: str
    filename: str
    title: str
    category: str
    summary: str
    path: str

    def to_dict(self) -> dict:
        return asdict(self)


_CATALOG: tuple[tuple[str, str, str, str, str], ...] = (
    ("index", "index.md", "Documentation Index", "start", "Complete map of the installed help system."),
    ("installation", "installation.md", "Installation", "start", "Install Aletheia, verify the CLI, and find installed docs."),
    ("introduction", "introduction.md", "Introduction", "start", "What Aletheia is, what it is not, and the trust boundaries."),
    ("architecture", "architecture.md", "Architecture", "system", "Implementation-grounded layer map and data flow."),
    ("core-concepts", "core_concepts.md", "Core Concepts", "system", "Namespaces, evidence, candidates, claims, context, confidence, and audit."),
    ("memory-lifecycle", "memory_lifecycle.md", "Memory Lifecycle", "system", "How data moves from evidence to governed recall and maintenance."),
    ("interfaces", "interfaces.md", "Interfaces", "interfaces", "Python, CLI, HTTP, SDK, MCP, console, plugin, and adapter usage."),
    ("cli-reference", "cli_reference.md", "CLI Reference", "interfaces", "Command groups, workflows, and where to inspect exact arguments."),
    ("http-api-reference", "http_api_reference.md", "HTTP API Reference", "interfaces", "Service routes, auth shape, and OpenAPI discovery."),
    ("mcp-reference", "mcp_reference.md", "MCP Reference", "interfaces", "MCP modes, tools, and local-agent behavior."),
    ("integration-guide", "integration_guide.md", "Integration Guide", "integration", "Patterns for embedding Aletheia in agents and tools."),
    ("plugin-developer-guide", "plugin_developer_guide.md", "Plugin Developer Guide", "integration", "Stable plugin contracts and governance expectations."),
    ("adapter-developer-guide", "adapter_developer_guide.md", "Adapter Developer Guide", "integration", "Building agent adapters against Aletheia interfaces."),
    ("examples", "examples.md", "Examples", "integration", "Example creation, testing, and docs build commands."),
    ("security-privacy-guide", "security_privacy_guide.md", "Security And Privacy Guide", "operations", "Auth, protected mode, token scopes, and privacy controls."),
    ("encryption-layer", "encryption_layer.md", "Encryption Layer", "operations", "Protected content encryption, key records, encrypted backups, and operational limits."),
    ("backup-restore-guide", "backup_restore_guide.md", "Backup And Restore Guide", "operations", "Encrypted archives, restore verification, and readiness checks."),
    ("migration-guide", "migration_guide.md", "Migration Guide", "operations", "Schema migration, verification, and compatibility notes."),
    ("operations-guide", "operations_guide.md", "Operations Guide", "operations", "Run, monitor, harden, diagnose, and release Aletheia locally."),
    ("troubleshooting", "troubleshooting.md", "Troubleshooting", "operations", "Common setup, service, retrieval, auth, and docs issues."),
    ("near-future-changes", "near_future_changes.md", "Near-Future Changes", "reference", "Current version status and expected changes."),
    ("v1-public-contracts", "v1_public_contracts.md", "v1 Public Contracts", "reference", "Stable public contracts and compatibility commitments."),
    ("concept", "Concept.md", "Original Concept", "reference", "Early product concept and design framing."),
    ("plan", "Plan.md", "Original Planning Notes", "reference", "Early implementation planning notes."),
    ("aletheia-phased-plan", "aletheia_phased_plan.md", "Phased Design Plan", "reference", "Historical phased build plan."),
    ("v1-3-0-baseline-remediation-plan", "v1_3_0_baseline_remediation_plan.md", "v1.3.0 Baseline Remediation Plan", "reference", "Release remediation plan for the generic baseline."),
    ("v1-3-0-postmortem-and-followups", "v1_3_0_postmortem_and_followups.md", "v1.3.0 Postmortem And Follow-Ups", "reference", "Postmortem and follow-up record for v1.3.0."),
    ("v1-3-0-review-closure-checklist", "v1_3_0_review_closure_checklist.md", "v1.3.0 Review Closure Checklist", "reference", "Review closure evidence for v1.3.0."),
    ("m0-contract", "m0_MVP_contract.md", "M0 MVP Contract", "contracts", "Historical MVP contract."),
    ("m1-contract", "m1_reliable_recall_contract.md", "M1 Reliable Recall Contract", "contracts", "Reliable recall and context continuity contract."),
    ("m2-contract", "m2_memory_integrity_contract.md", "M2 Memory Integrity Contract", "contracts", "Confidence, conflict, and integrity contract."),
    ("m3-contract", "m3_Intelligent_Ingestion_Semantic_Recall_contract.md", "M3 Intelligent Ingestion Contract", "contracts", "Ingestion, extraction, semantic recall, and review contract."),
    ("m4-contract", "m4_reasoned_memory_contract.md", "M4 Reasoned Memory Contract", "contracts", "Inference, reflections, derivation, and invalidation contract."),
    ("m5-contract", "m5_adaptive_memory_contract.md", "M5 Adaptive Memory Contract", "contracts", "Evaluation, learning, policy, and rollback contract."),
    ("m6-contract", "m6_memory_service_contract.md", "M6 Memory Service Contract", "contracts", "HTTP/MCP service and agent interoperability contract."),
    ("m7-contract", "m7_observability_contract.md", "M7 Observability Contract", "contracts", "Console, metrics, traces, review, and reporting contract."),
    ("m8-contract", "m8_production_hardening_contract.md", "M8 Production Hardening Contract", "contracts", "Backup, protected mode, retention, integrity, and release contract."),
    ("m9-contract", "m9_stable_platform_contract.md", "M9 Stable Platform Contract", "contracts", "Public contracts, plugins, conformance, compatibility, and doctor contract."),
    ("m10-contract", "m10_federated_memory_contract.md", "M10 Federated Memory Contract", "contracts", "Local-first federation and sync bundle contract."),
    ("m11-embedding-contract", "M11_Embedding_Integration_contract.md", "M11 Embedding Integration Contract", "contracts", "Semantic retrieval and embedding governance contract."),
    ("m11-m12-preface", "M11_M12_preface.md", "M11/M12 Preface", "contracts", "Governance principle for embeddings and LLMs."),
    ("m12-llm-contract", "M12_LLM_Integration_contract.md", "M12 LLM Integration Contract", "contracts", "Governed LLM memory formation contract."),
)


def docs_root() -> Path:
    """Return the installed docs root, falling back to the source checkout."""

    package_docs = Path(__file__).resolve().parent / "docs"
    if package_docs.exists():
        return package_docs
    return Path(__file__).resolve().parents[1] / "docs"


def iter_help_documents(*, include_uncataloged: bool = True) -> list[HelpDocument]:
    root = docs_root()
    documents: list[HelpDocument] = []
    known_filenames: set[str] = set()
    for slug, filename, title, category, summary in _CATALOG:
        path = root / filename
        known_filenames.add(filename)
        if path.exists():
            documents.append(
                HelpDocument(
                    slug=slug,
                    filename=filename,
                    title=title,
                    category=category,
                    summary=summary,
                    path=str(path),
                )
            )
    if include_uncataloged and root.exists():
        for path in sorted(root.glob("*.md")):
            if path.name in known_filenames:
                continue
            documents.append(
                HelpDocument(
                    slug=path.stem.replace("_", "-").lower(),
                    filename=path.name,
                    title=_read_title(path),
                    category="reference",
                    summary="Additional packaged documentation.",
                    path=str(path),
                )
            )
    return documents


def find_help_document(name: str) -> HelpDocument:
    normalized = _normalize(name)
    for document in iter_help_documents():
        candidates = {
            _normalize(document.slug),
            _normalize(document.filename),
            _normalize(Path(document.filename).stem),
            _normalize(document.title),
        }
        if normalized in candidates:
            return document
    available = ", ".join(document.slug for document in iter_help_documents())
    raise KeyError(f"Unknown help document '{name}'. Available documents: {available}")


def read_help_document(name: str = "index") -> str:
    document = find_help_document(name)
    return Path(document.path).read_text(encoding="utf-8")


def _read_title(path: Path) -> str:
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped.startswith("# "):
                return stripped[2:].strip()
    except OSError:
        pass
    return path.stem.replace("_", " ").title()


def _normalize(value: str) -> str:
    return value.strip().lower().replace("_", "-").removesuffix(".md")
