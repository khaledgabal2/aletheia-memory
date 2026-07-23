# CLI Reference

The `aletheia` console script is the main operator interface for local
databases, memory workflows, service setup, docs, plugins, and release gates.

Use `--help` at any level for exact arguments:

```bash
aletheia --help
aletheia candidates --help
aletheia backup create --help
```

Installed help is available without opening a database:

```bash
aletheia docs list
aletheia docs path
aletheia docs show index
```

## Setup And Schema

| Command | Purpose |
| --- | --- |
| `init` | Create or migrate a database and optionally enable protected mode. |
| `migrate` | Show current migration health. |
| `migrate plan` | Preview migration work. |
| `migrate apply` | Apply migrations, optionally with backup and verification. |
| `migrate verify` | Verify schema and optional namespace integrity. |

## Memory Read And Write

| Command | Purpose |
| --- | --- |
| `remember` | Store an explicit evidence-backed claim. |
| `search` | Search memory with lexical, semantic, or hybrid retrieval. |
| `context` | Build an M1 context pack with expanded options. |
| `context-pack` | Build an agent-ready context pack. |
| `audit` | Show provenance for a claim or evidence event. |
| `feedback` | Record confirmation, correction, usefulness, staleness, or other feedback. |

## Ingestion, Extraction, And Review

| Command | Purpose |
| --- | --- |
| `ingest text` | Store text as evidence in an ingestion batch. |
| `ingest file` | Store file content as evidence in an ingestion batch. |
| `extract run` | Create candidate memories from evidence. |
| `extract dry-run` | Preview extraction without writing candidates. |
| `extract show` | Inspect an extraction run. |
| `candidates list/show` | Inspect candidate memories. |
| `candidates promote/reject/edit` | Review and resolve candidate memories. |
| `events list/show` | Inspect raw evidence events. |
| `entities list/show/merge` | Inspect and manage extracted entities. |
| `categories list/label` | Inspect and assign category labels. |
| `index semantic/status/resume/verify/mark-stale/prune-stale` | Manage semantic indexes. |
| `llm ...` | Run governed LLM memory tasks as reviewable outputs. |

## Governed LLM Tasks

| Command | Purpose |
| --- | --- |
| `llm expand-query` | Produce a non-persistent query expansion. |
| `llm summarize-evidence` | Draft a summary from evidence. |
| `llm suggest-entities` | Suggest entity records from evidence. |
| `llm suggest-categories` | Suggest category labels from evidence. |
| `llm suggest-scope` | Suggest scope for a candidate. |
| `llm suggest-duplicate-merge` | Suggest duplicate merge handling. |
| `llm draft-reflection` | Draft a source-backed reflection. |
| `llm explain-conflict` | Draft a conflict explanation without resolving it. |
| `llm runs/show` | Inspect LLM run provenance. |

LLM outputs are review-only. Persistent `llm_outputs` store metadata and hashes
by default; set `ALETHEIA_LLM_OUTPUT_STORAGE=full` only for trusted local
debugging.

## Projects And Sessions

| Command | Purpose |
| --- | --- |
| `projects create/list/show` | Manage durable project records. |
| `sessions start/end/list/show` | Manage bounded interaction sessions. |

## Claims And Governance

| Command | Purpose |
| --- | --- |
| `claims list/show` | Inspect claims. |
| `claims promote/demote/supersede/scope/history` | Change claim status, lineage, and scope. |
| `confidence show/recompute` | Inspect or recompute effective confidence. |
| `confidence policy list/set` | Inspect or set half-life policies. |
| `decay preview/run` | Preview or persist decay effects. |
| `curate preview/apply` | Preview or apply deterministic curation. |
| `conflicts detect/list/show/resolve` | Detect and resolve conflicting claims. |

## Reasoned Memory

| Command | Purpose |
| --- | --- |
| `infer run/list/show/review/promote/reject/explain` | Run and review inference candidates. |
| `rules list/define/enable/disable/run` | Manage deterministic inference rules. |
| `reflect build/expand/list` | Build and inspect source-backed reflections. |
| `derivation trace/invalidated` | Inspect derivation lineage and invalidations. |
| `clusters build/relations` | Build semantic clusters and inspect relations. |
| `abstractions create/list/show` | Create and inspect lossless abstractions. |

## Evaluation, Learning, And Jobs

| Command | Purpose |
| --- | --- |
| `usage list/show` | Inspect usage events. |
| `outcome record/list` | Record and inspect task outcomes. |
| `eval create/add-case/run/report/list` | Build and run local evaluation sets. |
| `optimize retrieval` | Generate governed retrieval-policy proposals. |
| `learn run/list` | Run governed learning cycles. |
| `policies list/proposals/show/approve/reject/apply/versions` | Manage learned policy proposals and versions. |
| `procedures propose/approve/reject/apply/list/versions` | Review and version procedure updates. |
| `jobs enqueue/run/list/show` | Manage local jobs. |
| `health report` | Generate memory health reports. |
| `rollback policy/procedure` | Roll back learned behavior. |

## Service Access

| Command | Purpose |
| --- | --- |
| `serve` | Run the local HTTP daemon. |
| `mcp` | Run MCP-style memory tools over stdio. |
| `auth create-token/list-tokens/revoke-token` | Manage API tokens. |
| `clients create/list/disable` | Manage API clients and agents. |
| `api openapi/routes/ping` | Inspect service schema and connectivity. |
| `worker run/watch` | Run local jobs through the service layer. |
| `service status/requests/mcp-log` | Inspect service and MCP logs. |

## Console And Observability

| Command | Purpose |
| --- | --- |
| `console serve` | Run the HTTP daemon with `/console` enabled. |
| `console login-token/sessions/revoke-session` | Manage console access. |
| `reviews list/show/generate/resolve/dismiss/defer` | Inspect and resolve review tasks. |
| `metrics snapshot/latest/list` | Capture and inspect metric snapshots. |
| `traces retrieval/context/list/show/items` | Run and inspect retrieval/context traces. |
| `notifications list/create/dismiss` | Manage local notification events. |
| `reports export/list/show` | Export and inspect operational reports. |

## Production Hardening

| Command | Purpose |
| --- | --- |
| `backup create/verify/list/show` | Create, verify, and inspect backup archives. |
| `restore verify/dry-run/apply/namespace` | Verify and restore backup archives. |
| `encrypt status/enable` | Inspect or enable protected mode. |
| `keys list/create/rotate` | Manage local key records. |
| `redact evidence` | Preview or apply evidence redaction. |
| `forget preview/apply` | Preview or apply tombstone/delete requests. |
| `retention policy create/list` | Manage retention policies. |
| `retention run/apply` | Run retention processing. |
| `integrity check/repair` | Run and repair integrity checks. |
| `compact preview/run` | Preview or run database compaction. |
| `export namespace` | Export namespace archives. |
| `import dry-run/apply` | Import namespace archives. |
| `support bundle` | Create redacted support bundles. |
| `benchmark run/compare` | Run and compare benchmark profiles. |
| `release check/manifest` | Check and write release manifests. |
| `readiness check` | Run production readiness checks. |

## Stable Platform

| Command | Purpose |
| --- | --- |
| `doctor` | Run platform diagnostics. |
| `compatibility report/matrix/status/sdks/plugins` | Inspect v1 compatibility. |
| `plugins discover/install/enable/disable/list/show/logs/run` | Manage governed plugins. |
| `conformance list/run/report` | Run v1 conformance suites. |
| `adapters scaffold/test/certify/list` | Scaffold and certify agent adapters. |
| `docs build/status/test-examples/open/list/path/show` | Build, inspect, and read installed documentation. |
| `examples list/create/test` | Manage example projects. |
| `contracts list/show/register` | Inspect and register public contracts. |
| `deprecations list/check` | Inspect deprecation policy. |
| `v1-gate run/report` | Run and inspect the v1 release gate. |

## Federation

| Command | Purpose |
| --- | --- |
| `federation init/status/export-identity/rotate-key` | Manage local federation identity. |
| `peers add/list/show/trust/revoke/trust-domains` | Manage peer trust. |
| `shares create/list/show/recipients/export/import/revoke` | Manage scoped share grants and bundles. |
| `sync run/export/import/runs/collections/conflicts/resolve/cursors/remote-sources/trust-policies` | Run file-bundle sync and inspect sync state. |
| `workspaces create/list/show/members/add-member/remove-member/create-agent-group/agent-groups/add-agent/agent-members` | Manage workspaces and agent groups. |
| `grants list/show/consent` | Inspect share grants and consent records. |
| `revocations list/propagate` | Inspect and propagate revocations. |
| `federation-conformance run` | Run federation conformance checks. |

Federation is local-first and explicit. It is not automatic cloud sync.
