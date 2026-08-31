# Aletheia Documentation Index

This help map covers the public v1.3.1 APIs and the explicitly marked, unpublished
1.4.0rc1 additions. The primary Python quickstart works on both.
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
2. [`quickstart.md`](quickstart.md): create, inspect, approve and recall the sample
3. [`examples.md`](examples.md): connect a scoped HTTP agent with a separate operator
4. `core_concepts.md` and `memory_lifecycle.md`
5. `integration_guide.md`: optional semantic/LLM paths and other interfaces
6. `security_privacy_guide.md` and `operations_guide.md` when operating a service

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
| `quickstart.md` | Complete the model-free, explicitly reviewed Python lifecycle and verify persistence. |
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

## Repository Community Files

The repository root also includes:

| File | Purpose |
| --- | --- |
| `LICENSE` | MIT license terms. |
| `CONTRIBUTING.md` | Contribution workflow, local verification, and public-boundary expectations. |
| `SECURITY.md` | Responsible disclosure and local deployment security guidance. |
| `CHANGELOG.md` | Release notes for public versions. |

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

The unpublished 1.4.0rc1 release candidate is tracked separately from public v1.3.1:

- [Release plan](v1_4_0_contract_hardening_and_developer_experience_plan.md)
- [Phase 0 scope and decisions](v1_4_0_phase0_decisions.md)
- [Phase 0 verification evidence](v1_4_0_phase0_evidence.md)
- [Discovery foundation](v1_4_0_discovery_contract.md)
- [Phase 1 verification evidence](v1_4_0_phase1_evidence.md)
- [Read contract](v1_4_0_read_contract.md)
- [Phase 2 verification evidence](v1_4_0_phase2_evidence.md)
- [Phase 3 implementation decisions](v1_4_0_phase3_decisions.md)
- [Phase 3 verification evidence](v1_4_0_phase3_evidence.md)
- [Governed review contract](v1_4_0_review_contract.md)
- [Review migration design](v1_4_0_review_migration_design.md)
- [Upgrade and recovery guide](v1_4_0_migration_guide.md)
- [Phase 4 verification evidence](v1_4_0_phase4_evidence.md)
- [Candidate-first agent contract](v1_4_0_agent_onboarding_contract.md)
- [Optional tested local model recipes](v1_4_0_local_model_recipes.md)
- [Phase 5 verification evidence](v1_4_0_phase5_evidence.md)
- [Release-candidate verification](v1_4_0_phase6_evidence.md)
- [Release approval and handoff](v1_4_0_release_handoff.md)
- [Model-free tutorial draft](v1_4_0_quickstart_draft.md)

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
