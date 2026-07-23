# Aletheia Architecture

This document describes the current architecture from the implementation in this repository. It does not describe unimplemented roadmap features as if they already exist.

Primary implementation files:

- `aletheia/core/memory.py`: public memory kernel.
- `aletheia/storage/sqlite.py`: SQLite connection and migrations.
- `aletheia/storage/migrations/schema.sql`: database schema.
- `aletheia/retrieval/lexical.py`: SQLite FTS retrieval and deterministic ranking.
- `aletheia/extraction.py`: rule-based, mock, and governed LLM extraction interfaces.
- `aletheia/llm.py`: governed LLM provider adapters, deterministic mock provider, and local plugin-provider entrypoint support.
- `aletheia/semantic.py`: embedding providers, semantic index versioning, and local vector-store helpers.
- `aletheia/service/http.py`: local HTTP service, console HTML, routing, auth enforcement, request logging, idempotency, and rate limits.
- `aletheia/service/mcp.py`: MCP-style tool registry.
- `aletheia/client.py`: sync and async Python HTTP clients.
- `aletheia/adapters.py`: generic agent adapter interface and HTTP adapter.
- `aletheia/core/crypto.py`: AES-GCM encryption, PBKDF2 key derivation, secret hashing, and legacy encrypted payload compatibility.
- `aletheia/core/hardening.py`: backup, restore, protected mode, redaction, forget, retention, integrity, import/export, diagnostics, benchmarks, release/readiness.
- `aletheia/core/platform.py`: public contracts, plugins, conformance, compatibility, docs, examples, doctor, v1 gate, adapter certification.

## System Shape

```text
CLI / Python / HTTP SDK / MCP / Console / Plugins / Adapters
                         |
                         v
                 Aletheia Memory Kernel
                         |
          +--------------+--------------+
          |              |              |
   Evidence and Claims   Retrieval      Governance
   Candidates            Context Packs  Audit/Confidence/Conflicts
          |              |              |
          +--------------+--------------+
                         |
                  SQLiteStore
                         |
              SQLite schema 1.3.0
```

The implementation is local-first. The main durable dependency is SQLite. The HTTP service uses Python's standard `http.server` stack. The package declares no required runtime dependencies in `pyproject.toml`; `pytest` is a development extra.

## Storage Layer

`SQLiteStore.open()` creates parent directories, opens SQLite with `check_same_thread=False`, enables foreign keys, sets a busy timeout, and uses WAL mode for file databases. `SQLiteStore.migrate()` executes `schema.sql`, applies compatibility/backfill routines, and records `schema_version = "1.3.0"`.

The schema includes tables for:

- Evidence, claims, claim/evidence links, audit log, feedback.
- Confidence snapshots/events and half-life policies.
- Conflict families, conflict resolutions, scopes, relationships, curation queues and decisions.
- SQLite FTS via `claims_fts`.
- Projects, sessions, project/session claim links.
- Ingestion batches, source documents, evidence spans, extraction runs, candidate claims, extraction decisions.
- Entities, aliases, mentions, categories, semantic index records, embeddings, content risk flags.
- LLM prompts, prompt versions, runs, outputs, and safety flags.
- Inference runs, inference candidates, rules, derivation edges, reflections, abstractions, semantic clusters/relations, invalidations, refresh queue.
- Usage, outcomes, retrieval judgments, evaluation sets/runs/results, ranking/context policies, learning runs, jobs, health reports, rollbacks.
- API clients/tokens, capability grants, namespace grants, service logs, MCP invocation logs, idempotency, rate limits, service config/instance logs.
- Console sessions, review tasks, notifications, dashboard views/preferences, metric snapshots, traces, reports.
- Backup/restore, encryption keys, protected mode, redactions, tombstones, retention, integrity, migrations, compaction, import/export, support bundles, benchmarks, release/readiness.
- Public contracts, API contract versions, deprecations, compatibility, plugins, conformance, adapter certifications, SDK releases, docs, examples, doctor runs, v1 gate runs.

## Memory Kernel

`Memory` is the public center of the system.

Core methods include:

- `Memory.open()`, `migrate()`, `health()`, and `close()`.
- `write_event()`, `read_event()`, and `list_events()`.
- `write_claim()`, `remember()`, `read_claim()`, `list_claims()`, and `resolve_claim()`.
- `retrieve()` and `context_pack()`.
- `ingest()`, `extract_candidates()`, `list_candidates()`, `review_candidate()`, `promote_candidate()`, and `reject_candidate()`.
- LLM task helpers: `list_llm_runs()`, `read_llm_run()`, `expand_query()`, `summarize_evidence()`, `suggest_entities()`, `suggest_categories()`, `suggest_scope_with_llm()`, `suggest_duplicate_merge_with_llm()`, `draft_reflection_with_llm()`, and `explain_conflict_with_llm()`.
- Project and session methods: `create_project()`, `start_session()`, `end_session()`, list/get helpers.
- Governance methods: `compute_confidence()`, `recompute_confidence()`, `detect_conflicts()`, `resolve_conflict()`, `promote_claim()`, `demote_claim()`, `scope_claim()`, `curate()`, `explain_claim()`, `audit()`.
- Reasoning methods: `run_inference()`, inference review/promotion/rejection, rules, reflections, abstractions, derivation tracing, invalidation, clusters, semantic relations.
- Evaluation and learning methods: usage/outcome logging, retrieval judgments, eval sets/cases/runs, retrieval optimization, policy proposals/applications, procedure update/versioning, learning runs, jobs, health reports, rollback.
- Production and platform methods delegated to `hardening.py` and `platform.py`.

`remember()` is a convenience path. It writes an evidence event and then writes a claim backed by that evidence. `write_claim()` rejects claims without evidence IDs.

## Evidence, Candidates, And Claims

Evidence is stored by `write_event()` and `ingest()`.

`write_event()` creates a stable event ID from namespace, session, source type, source URI, and content. It stores content hash, source/trust/privacy/retention metadata, and an audit record. Protected mode can transform stored content through `hardening.protect_content_for_storage()`.

`ingest()` wraps `write_event()` with an ingestion batch and source document record, links the evidence, writes audit records, and scans content for built-in risk patterns such as prompt injection or memory poisoning phrases.

`extract_candidates()` reads evidence, runs an extractor, and stores candidate claims plus evidence spans unless `dry_run=True`. Candidates are separate from claims. When the extractor is governed LLM-backed, the kernel also records prompt, run, output, and safety provenance. `promote_candidate()` validates integrity gates, writes a claim, links candidate to claim, copies categories/entities, writes decisions and audit records, and optionally applies suggested scope.

## Retrieval And Context

Lexical retrieval is implemented by `SQLiteFTSRetriever` over `claims_fts`.

The deterministic ranking combines lexical match, effective confidence, memory type priority, status priority, project relevance, recency, importance, conflict penalty, and staleness penalty.

`Memory.retrieve()` supports:

- Modes: `lexical`, `semantic`, `hybrid`.
- Filters: memory types, statuses, subject, predicate, project, session, minimum confidence, categories.
- Inclusion switches for disputed, archived, and candidate records.
- Scope filtering after retrieval.
- Retrieval logging.

Semantic and hybrid retrieval use `semantic.py`. The bundled `MockEmbeddingProvider` remains the deterministic default for tests and demos. M11 also adds a configurable `local_hash` provider, OpenAI-compatible/local HTTP provider adapters, semantic index versioning, stale-vector handling, and the embedded `sqlite_local` vector store. Semantic results still pass through claim status, namespace, conflict, privacy, and scope governance before they can enter retrieval results or context packs.

## Governed LLM Tasks

M12 LLM support is optional and review-first. `aletheia.llm` provides deterministic `mock_llm` behavior for tests plus configurable `local_http`, `ollama_style`, `openai_compatible`, and `plugin` adapters. `LLMExtractor` produces candidate claims only; it does not write active claims, and it applies the same `ExtractionPolicy` gates as other extractors before storing candidates.

LLM task provenance is stored in `llm_prompts`, `llm_prompt_versions`, `llm_runs`, `llm_outputs`, and `llm_safety_flags`. The kernel records provider, provider type, model, prompt template/version, schema version, temperature, input/output hashes, evidence backlinks, warnings, and output status. Persistent `llm_outputs` use metadata-only storage by default: output hashes, keys, review state, and source ids are stored without full draft text unless `ALETHEIA_LLM_OUTPUT_STORAGE=full` is set for trusted local debugging.

Privacy gates are applied before evidence-backed LLM tasks. Secret evidence is blocked by default. Private and sensitive evidence are blocked for external providers by default. Query expansion accepts an explicit privacy label and does not create memory. Entity, category, scope, duplicate-merge, summary, and reflection outputs remain reviewable suggestions or drafts with source backlinks. Conflict explanations are recorded as draft outputs and never resolve conflicts automatically.

## Context Packs

`context_pack()` builds structured context for agents. The returned `ContextPack` can contain:

- Core memory.
- Project memory.
- Session memory.
- Procedural memory.
- Reflections.
- Relevant memory.
- Warnings.
- Omitted memories due to token budget.

It records policy version IDs, evidence source IDs, generated-at time, and optional usage records. The Markdown rendering is generated by `ContextPack.to_markdown()`.

## Governance

The kernel contains explicit governance mechanics:

- Confidence computation uses half-life decay, source reliability, feedback, contradiction pressure, and verification factors.
- Assistant self-confirmation is downweighted in `feedback()` when it lacks evidence.
- Active/core claims can conflict by subject and predicate with different objects.
- Conflict detection creates or updates conflict families and can mark conflicting claims disputed.
- Conflict resolution can select active claims, supersede, reject, scope, merge duplicates, or keep unresolved.
- Curation decisions and status history are persisted.
- Audit records are written for important mutations.

The practical rule is that Aletheia does not silently overwrite memory. It tracks status, provenance, and review decisions.

## Encryption Layer

The encryption layer is part of production hardening and is implemented by
`crypto.py` and `hardening.py`.

Protected mode can encrypt secret-tier evidence content before it is stored.
The current content format is `enc:v2:<key_id>:<salt>:<nonce>:<ciphertext>`.
It uses AES-256-GCM with PBKDF2-HMAC-SHA256-derived local key material. Legacy
`enc:v1` XOR/HMAC content remains readable for compatibility.

Key records are stored in `encryption_key_records`, but raw key material is not
stored there. Protected content key material is resolved from
`ALETHEIA_KEY_<key_id>` or `ALETHEIA_PROTECTED_KEY`. Backup/export encryption
uses explicit `--passphrase`, `ALETHEIA_KEY_<key_id>`, or
`ALETHEIA_BACKUP_PASSPHRASE`.

Protected mode also requires encrypted backups, uses metadata-only request
logging, and applies the default secret-safe indexing policy
`index_public_and_personal_only`. Redaction and forget flows preserve audit
records and tombstones, and mark affected semantic indexes stale when needed.

For operator details, read `docs/encryption_layer.md`.

## Service Layer

`AletheiaService` wraps `Memory` with a local HTTP API.

Implemented service behavior includes:

- Public unauthenticated endpoints: `GET /v1/health`, `GET /v1/ready`, `GET /v1/version`, `GET /v1/openapi.json`.
- Authenticated `/v1/*` routes for context, retrieval, candidate/active remember, feedback, outcomes, ingestion, extraction, review, claims, audit, projects, sessions, conflicts, confidence, curation, reasoning, eval/learning/jobs, console/observability, hardening, and stable-platform operations.
- Capability checks through `AuthService`.
- Namespace grants and privacy ceilings.
- Optional rate limiting per client.
- Idempotency-key replay for state-changing requests.
- Request logging with hashed bodies/responses when configured.
- Console session authentication and CSRF checks for state-changing console calls.

The console HTML and CSS are embedded in `service/http.py` and served at `/console` when console support is enabled.

## MCP Layer

`McpToolRegistry` publishes MCP-style tools and maps them to HTTP service routes. Current tools include context packing, search, candidate-first remember, feedback, audit, claim explanation, health, ingest, extraction, candidate review, derivation tracing, and outcome recording.

MCP modes are:

- `read_only`
- `read_write_candidate`
- `read_write_active`
- `admin`

The default mode in `config_for_mcp()` is `read_write_candidate`.

## SDK And Adapters

`AletheiaClient` is a small HTTP client built on `urllib.request`. It sends JSON requests, bearer tokens, request IDs, and idempotency keys. It unwraps the service response envelope and maps service error codes to typed Python exceptions.

`AsyncAletheiaClient` wraps the sync client with `asyncio.to_thread()`.

`AgentMemoryAdapter` defines three hooks:

- `before_agent_call()`
- `after_agent_call()`
- `remember_candidate()`

`HttpAgentMemoryAdapter` implements those hooks by calling `context_pack()`, `record_outcome()`, and candidate-first `remember()`.

## Plugins And Stable Platform

`plugins.py` defines stable v1 plugin protocols for extractors, embedding providers, vector indexes, importers, exporters, inference engines, key providers, report generators, and agent adapters.

`platform.py` implements plugin manifest discovery/install/enable/disable/list/show/log/run operations. Plugin manifests are `aletheia-plugin.toml` files. Plugins cannot bypass candidate-first governance through the stable operation runner; direct active writes are blocked and logged there.

The stable platform also implements:

- Public contract registration/listing.
- Deprecation checks.
- Compatibility reports and matrices.
- Conformance suites/runs/results.
- Adapter scaffolding and certification.
- Docs/example build and test helpers.
- Doctor diagnostics.
- v1 release gate runs.

## What Is Not In The Current Architecture

The current implementation does not include:

- Cloud-hosted sync or a central federation relay.
- Automatic peer discovery.
- A production semantic model or external vector database dependency.
- A bundled LLM extractor implementation.
- A browser-based app beyond the embedded local operational console.
