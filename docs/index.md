# Aletheia Documentation Index

This is the public help map for Aletheia v1.3.0 on `main`.
Aletheia is a local, auditable memory system for AI agents. The production
baseline is intentionally generic: product-specific integration layers belong
on their own branches or forks.

All files in this directory are packaged with Aletheia. After installation,
use:

```bash
aletheia docs list
aletheia docs path
aletheia docs show introduction
```

To copy the installed help set into a local site directory, use:

```bash
aletheia init --db ./aletheia.db
aletheia docs build --db ./aletheia.db --output ./site
```

## Recommended Reading Paths

New users should read:

1. `installation.md`
2. `introduction.md`
3. `core_concepts.md`
4. `memory_lifecycle.md`
5. `interfaces.md`
6. `cli_reference.md`

Agent and tool integrators should read:

1. `integration_guide.md`
2. `http_api_reference.md`
3. `mcp_reference.md`
4. `security_privacy_guide.md`
5. `adapter_developer_guide.md`

Operators should read:

1. `operations_guide.md`
2. `encryption_layer.md`
3. `backup_restore_guide.md`
4. `migration_guide.md`
5. `security_privacy_guide.md`
6. `troubleshooting.md`

Plugin authors should read:

1. `plugin_developer_guide.md`
2. `v1_public_contracts.md`
3. `m9_stable_platform_contract.md`
4. `examples.md`

## Public Help Documents

| Document | Purpose |
| --- | --- |
| `installation.md` | Install Aletheia, verify the CLI, initialize a database, and locate installed docs. |
| `introduction.md` | Explain what Aletheia is, what it is not, and the trust boundaries. |
| `architecture.md` | Describe the implemented layers, core modules, storage schema, and data flow. |
| `core_concepts.md` | Define namespaces, evidence, candidates, claims, confidence, conflicts, context packs, and audit. |
| `memory_lifecycle.md` | Walk through ingestion, extraction, review, retrieval, feedback, hardening, and maintenance. |
| `interfaces.md` | Show how to use the Python kernel, CLI, HTTP API, SDK, MCP, console, plugins, and adapters. |
| `cli_reference.md` | Map each command group to the functionality it controls. |
| `http_api_reference.md` | Explain HTTP service discovery, auth shape, envelopes, and major route families. |
| `mcp_reference.md` | Explain MCP modes, tool behavior, and local-agent expectations. |
| `integration_guide.md` | Show integration patterns for embedded Python, HTTP sidecars, SDKs, MCP, adapters, and plugins. |
| `security_privacy_guide.md` | Explain local-first security, protected mode, tokens, privacy ceilings, and plugin controls. |
| `encryption_layer.md` | Explain protected content encryption, key records, encrypted archives, indexing effects, and limits. |
| `backup_restore_guide.md` | Explain encrypted backup, restore dry-runs, verification, and production readiness. |
| `migration_guide.md` | Explain schema migration planning, application, verification, and compatibility. |
| `operations_guide.md` | Explain day-to-day operation, monitoring, release checks, and service hardening. |
| `troubleshooting.md` | Provide practical fixes for install, database, auth, service, retrieval, docs, and package issues. |
| `plugin_developer_guide.md` | Explain governed plugin manifests, permissions, compatibility, and conformance. |
| `adapter_developer_guide.md` | Explain how to build and certify agent adapters. |
| `examples.md` | Show example scaffolding and docs validation commands. |
| `near_future_changes.md` | Summarize current v1.3.0 status and likely next changes. |
| `v1_public_contracts.md` | Document stable public contracts and compatibility expectations. |

## Layer Map

Aletheia is easiest to understand as layers:

| Layer | Main files | Primary docs |
| --- | --- | --- |
| Storage | `aletheia/storage/sqlite.py`, `aletheia/storage/migrations/schema.sql` | `architecture.md`, `migration_guide.md` |
| Memory kernel | `aletheia/core/memory.py` | `core_concepts.md`, `memory_lifecycle.md`, `interfaces.md` |
| Retrieval | `aletheia/retrieval/lexical.py`, `aletheia/semantic.py` | `architecture.md`, `memory_lifecycle.md` |
| Ingestion and extraction | `aletheia/extraction.py`, `aletheia/llm.py` | `memory_lifecycle.md`, `interfaces.md` |
| Governance | `aletheia/core/memory.py`, `aletheia/review.py` | `core_concepts.md`, `security_privacy_guide.md` |
| Service | `aletheia/service/http.py`, `aletheia/service/auth.py` | `http_api_reference.md`, `integration_guide.md` |
| MCP | `aletheia/service/mcp.py` | `mcp_reference.md`, `integration_guide.md` |
| SDK and adapters | `aletheia/client.py`, `aletheia/adapters.py` | `interfaces.md`, `adapter_developer_guide.md` |
| Hardening | `aletheia/core/hardening.py` | `operations_guide.md`, `backup_restore_guide.md`, `security_privacy_guide.md` |
| Encryption | `aletheia/core/crypto.py`, `aletheia/core/hardening.py` | `encryption_layer.md`, `security_privacy_guide.md`, `backup_restore_guide.md` |
| Stable platform | `aletheia/core/platform.py`, `aletheia/plugins.py` | `plugin_developer_guide.md`, `v1_public_contracts.md` |
| Federation | `aletheia/core/federation.py` | `m10_federated_memory_contract.md`, `near_future_changes.md` |

## Contracts And Historical Design Docs

The milestone contracts are included for maintainers and advanced users who
need to understand why the implemented surfaces exist. They are not the fastest
starting point for normal usage.

- `m0_MVP_contract.md`
- `m1_reliable_recall_contract.md`
- `m2_memory_integrity_contract.md`
- `m3_Intelligent_Ingestion_Semantic_Recall_contract.md`
- `m4_reasoned_memory_contract.md`
- `m5_adaptive_memory_contract.md`
- `m6_memory_service_contract.md`
- `m7_observability_contract.md`
- `m8_production_hardening_contract.md`
- `m9_stable_platform_contract.md`
- `m10_federated_memory_contract.md`
- `M11_Embedding_Integration_contract.md`
- `M11_M12_preface.md`
- `M12_LLM_Integration_contract.md`

Release-remediation and postmortem files are retained as maintenance evidence.
They are useful when preparing another production gate, but they are not core
user help.
