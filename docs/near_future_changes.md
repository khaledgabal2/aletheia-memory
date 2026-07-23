# Near-Future Changes

This document separates the current v1.3.0 implementation from likely future directions.

Current implementation source:

- `pyproject.toml` declares package version `1.3.0`.
- `aletheia/storage/sqlite.py` declares `SCHEMA_VERSION = "1.3.0"`.
- `docs/v1_public_contracts.md` defines stable v1 surfaces and semver policy.
- `docs/m10_federated_memory_contract.md` is implemented as the M10 federation-beta milestone.
- `docs/M11_Embedding_Integration_contract.md` is implemented as the M11 production semantic retrieval milestone.
- `docs/M12_LLM_Integration_contract.md` is implemented as the M12 governed LLM memory formation milestone.
- The current CLI, schema, HTTP routes, SDK, tests, and live scorecards include M10 federation, M11 semantic retrieval, and M12 LLM governance.

## Stable In v1.3.0

The repository treats these as stable public contracts:

- Python package API: `Memory`, `AletheiaClient`, `AsyncAletheiaClient`, and plugin protocols in `aletheia.plugins`.
- HTTP API: `/v1/*` routes published by `aletheia api openapi`.
- MCP tool names and request shapes published by `aletheia mcp --list-tools`.
- Stable-platform CLI groups: `doctor`, `compatibility`, `plugins`, `conformance`, `adapters`, `docs`, `examples`, `contracts`, `deprecations`, and `v1-gate`.
- Archive and context-pack formats.
- Database migration behavior from `1.0.x` to `1.3.0`.

M10 federation is present as an experimental federation-beta surface. It is additive and local-first.

M11 production semantic retrieval is present as an additive local-first surface. `MockEmbeddingProvider` remains the deterministic default for tests, while `local_hash`, OpenAI-compatible/local HTTP providers, semantic index versioning, `sqlite_local` vector storage, reindex/resume, verification, stale pruning, and protected-mode semantic policies are available through the kernel and CLI.

M12 governed LLM memory formation is present as an additive review-first surface. `mock_llm` remains the deterministic default for tests, while local HTTP, Ollama-style, OpenAI-compatible, and local plugin providers can produce candidate memories, query expansions, entity/category/scope/duplicate-merge suggestions, summaries, reflection drafts, and conflict explanations with prompt/run/output provenance and privacy safety flags.

## Implemented M10 Federation

M10 adds:

- Federation identities and private-key-safe identity export.
- Trusted peer devices and trust domains.
- Share grants and share recipients.
- Sync collections, changesets, change items, runs, and replication cursors.
- Encrypted `.aletsync` share packages.
- Import trust policies.
- Candidate-first remote imports and trusted-device active imports that never import remote core as local core.
- Sync conflict detection, review tasks, and explicit resolution records.
- Consent, revocation, federation audit, and sync tombstone records.
- Workspace and multi-agent governance records.
- Federation conformance tests and `scripts/live_m10_federated_memory_scorecard.py`.

M10 CLI groups include:

- `aletheia federation`
- `aletheia peers`
- `aletheia shares`
- `aletheia sync`
- `aletheia workspaces`
- `aletheia grants`
- `aletheia revocations`
- `aletheia federation-conformance`

M10 HTTP route families include:

- `/v1/federation/*`
- `/v1/peers/*`
- `/v1/shares/*`
- `/v1/sync/*`
- `/v1/workspaces/*`
- `/v1/grants/*`
- `/v1/revocations/*`

The sync and async Python SDKs expose federation helpers for identity status, peers, shares, sync, workspaces, and revocations.

## Implemented M11 Semantic Retrieval

M11 adds:

- Provider metadata for embedding providers.
- Configurable `local_hash`, `local_http`, `ollama_style`, and `openai_compatible` provider adapters.
- Embedded `sqlite_local` vector-store abstraction over the `embeddings` table.
- Semantic index versioning based on provider, model, dimension, chunking policy, and redaction policy.
- Reindex/resume behavior that skips unchanged inputs and marks older index versions stale.
- Status, verify, mark-stale, and prune-stale operations.
- Protected-mode semantic indexing policies that block private/sensitive/secret content by default.
- Redaction/forget hooks that stale affected vectors.
- Provider-aware semantic search with `--semantic-provider`.

## Implemented M12 Governed LLM Memory Formation

M12 adds:

- A configurable governed LLM provider interface with deterministic `mock_llm`, local HTTP, Ollama-style, OpenAI-compatible, and plugin-entrypoint adapters.
- `LLMExtractor` as a structured-output extractor that stores candidate memories only and enforces extraction policy before storage.
- Prompt, prompt-version, run, output, and safety-flag provenance tables.
- Metadata-only persistent LLM output storage by default, with full output storage reserved for explicit local debugging.
- Privacy gates that block secret evidence for LLM tasks and block private/sensitive evidence from external providers by default.
- Query expansion, evidence summarization, reflection drafting, and conflict explanation helpers.
- CLI inspection through `aletheia llm expand-query`, `summarize-evidence`, `draft-reflection`, `explain-conflict`, `runs`, and `show`.
- LLM governance conformance coverage and `scripts/live_m12_governed_llm_memory_scorecard.py`.

## Still Not Goals

Aletheia is still not:

- Cloud Aletheia.
- A global truth store.
- Automatic sharing of all memory.
- Default sync.
- Remote peers bypassing local governance.
- Guaranteed remote erasure from untrusted peers.

Revocation prevents future sync and records the limit honestly; it cannot forcibly erase data already received by another peer.

## Likely Future Areas

Future milestones may add relay transports, richer peer discovery, stronger cryptographic key management, richer console federation workflows, richer vector-store plugins, richer provider-specific LLM policies, or richer LLM review workflows. Those should remain explicit, governed, and compatible with existing v1 public contracts.

## Practical Guidance For Integrators

- Tolerate unknown JSON response fields.
- Prefer the SDK or OpenAPI over hard-coded request shapes.
- Use namespaces consistently, because federation is namespace-scoped.
- Keep candidate-first write behavior in integrations.
- Preserve request IDs, context pack IDs, claim IDs, candidate IDs, evidence IDs, peer IDs, share IDs, and sync run IDs when possible.
- Avoid direct SQLite writes; use the kernel, CLI, HTTP API, or SDK.
- Keep backups verified before testing federation migrations.

## Short Version

Aletheia v1.3.0 is a local, stable, auditable memory platform with federation-beta support, production semantic retrieval, and governed LLM memory formation: embeddings improve recall and LLMs can draft candidates or summaries without turning Aletheia into a cloud service, global truth store, or unreviewed truth engine.
