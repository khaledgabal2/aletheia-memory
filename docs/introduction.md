# Aletheia Introduction

This document explains what Aletheia is and is not based on the current repository implementation.
The source of truth for this page is the code and tests in this repository, especially `aletheia/core/memory.py`, `aletheia/storage/migrations/schema.sql`, `aletheia/service/http.py`, `aletheia/service/mcp.py`, `aletheia/client.py`, `aletheia/adapters.py`, and the existing v1 docs under `docs/`.

## What Aletheia Is

Aletheia is a local, auditable memory system for AI agents.

The current implementation is a Python package named `aletheia-memory` with:

- An in-process memory kernel exposed by `aletheia.Memory`.
- A SQLite-backed store and migration schema at version `1.3.0`.
- A command-line interface named `aletheia`.
- A dependency-free local HTTP service under `/v1/*`.
- A Python HTTP client SDK, including sync and async clients.
- An MCP-style tool registry for local agents.
- A small generic HTTP agent adapter.
- Local plugin, conformance, compatibility, diagnostics, and v1 gate surfaces.
- Local production controls for backup, restore, protected mode, redaction, forget/tombstone, retention, integrity checks, import/export, support bundles, benchmarks, release manifests, and readiness checks.

Aletheia stores memory as evidence-backed records. Raw evidence, extracted candidates, promoted claims, conflicts, confidence snapshots, review decisions, context packs, audit records, operational traces, service logs, and platform records live in the configured SQLite database unless explicitly exported.

The core loop is:

```text
evidence -> candidate memory -> review/promotion -> claim -> retrieval/context -> feedback/audit
```

That loop is intentional. Candidate memories are not trusted facts. They become usable claims only after review or an explicitly authorized active write path.

## What Aletheia Is Not

Aletheia is not just a vector database. It includes SQLite FTS retrieval, governed semantic embeddings, provider-aware indexing, and a local SQLite vector store, but it is organized around provenance, claims, review, confidence, conflicts, context packs, and auditability rather than raw nearest-neighbor search.

Aletheia is not an agent framework. It does not decide how an agent plans, reasons, calls tools, or talks to users. It supplies memory context and governed write paths that other agents can use.

Aletheia is not a cloud memory service in this repository. The implemented service is local-first and defaults to local operation. Remote binding requires explicit configuration and authentication.

Aletheia is not an automatic truth engine. It stores evidence, claims, candidates, feedback, confidence, and conflicts, but it does not make all extracted or inferred content true by default.

Aletheia is not an ungoverned LLM truth engine. The repository includes rule-based, mock, and governed LLM extraction paths. LLM outputs are persisted as candidate memories, query expansions, entity/category/scope/merge suggestions, summaries, reflection drafts, or conflict explanations with provenance and review state; they do not become trusted claims automatically. Persistent LLM output records store metadata and hashes by default rather than full draft text.

Aletheia is federated memory only in the local-first M10 sense: explicit identities, peer trust, scoped share grants, encrypted `.aletsync` bundles, trust policies, conflicts, tombstones, workspaces, and agent groups. It is still not cloud sync, a global truth store, or automatic sharing.

## Current Implementation Philosophy

Aletheia is built around separation of evidence and belief.

Evidence events record where information came from. Claims are structured assertions backed by evidence. Candidates are extracted suggestions awaiting review. Reflections and inferences can be created, but they retain derivation metadata and do not erase the underlying sources.

The implementation also treats contradictions as state, not noise. Conflicting active claims are detected, grouped into conflict families, and resolved through curation decisions such as promoting, demoting, scoping, superseding, rejecting, or keeping a conflict unresolved.

Confidence is dynamic. The current kernel computes effective confidence from base confidence, half-life decay, source reliability, feedback, contradiction pressure, and verification factors. Retrieval salience is related but separate from truth confidence.

## Main User Groups

Aletheia is useful for:

- Local AI agents that need cross-session memory.
- Agent developers who want auditable memory without binding to one agent framework.
- Tool builders who want a local HTTP or MCP memory sidecar.
- Operators who need review queues, diagnostics, backups, readiness checks, and audit trails.
- Plugin authors who want to extend extraction, indexing, import/export, inference, keys, reports, or adapters while preserving Aletheia governance.

## Trust Boundaries

The important trust boundaries in the current code are:

- Raw ingested content is evidence, not truth.
- Candidate writes are the default service and MCP write behavior.
- Active writes require `memory:write_active`.
- Review and promotion require review capability or direct in-process code access.
- API tokens can be scoped by capability, namespace grant, and privacy ceiling.
- Console state-changing actions require authenticated sessions and CSRF checks.
- Plugins require manifest validation, install/enable steps, and explicit permission grants.
- LLM providers are optional, review-first, and blocked from secret evidence by default; external providers are also blocked from private and sensitive evidence unless an explicit policy path allows it.
- Forget and redaction workflows preserve tombstones and audit records.

## Where To Go Next

- For implementation architecture, read `docs/architecture.md`.
- For command-line, Python, HTTP, MCP, console, plugin, and adapter usage, read `docs/interfaces.md`.
- For integrating Aletheia into other systems, read `docs/integration_guide.md`.
- For expected near-future changes, read `docs/near_future_changes.md`.
