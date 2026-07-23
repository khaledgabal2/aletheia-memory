# Aletheia Interfaces

This guide explains how to use each current Aletheia interface: Python kernel, CLI, local HTTP API, Python SDK, MCP tools, console, plugins, adapters, and generated docs/examples.

All commands assume the repository root and a local database at `./aletheia.db`.

## 1. Python Kernel

Use the in-process kernel when your application is Python and can share a local SQLite database directly.

```python
from aletheia import Memory

memory = Memory.open("./aletheia.db", namespace="user/default")
try:
    claim = memory.remember(
        namespace="user/default",
        memory_type="preference",
        subject="user",
        predicate="prefers_response_style",
        object="practical and direct",
    )

    results = memory.retrieve(
        namespace="user/default",
        query="response style",
        mode="lexical",
        limit=5,
    )

    pack = memory.context_pack(
        namespace="user/default",
        query="How should I answer?",
        retrieval_mode="hybrid",
        token_budget=1200,
    )
    print(pack.to_markdown())
finally:
    memory.close()
```

Use `ingest()` and `extract_candidates()` when content should not be trusted automatically:

```python
batch = memory.ingest(
    "user/default",
    source_type="note",
    content="For architecture docs, prefer concrete implementation detail.",
)
run = memory.extract_candidates("user/default", batch_id=batch.id)
candidates = memory.list_candidates("user/default")
claim = memory.promote_candidate(candidates[0].id, reason="Reviewed against source note.")
```

Useful kernel method groups:

- Setup: `open`, `migrate`, `health`, `close`.
- Evidence and claims: `write_event`, `ingest`, `write_claim`, `remember`, `read_claim`, `list_claims`, `audit`.
- Retrieval and context: `retrieve`, `context_pack`, `trace_retrieval`, `trace_context_pack`.
- Review: `list_candidates`, `review_candidate`, `promote_candidate`, `reject_candidate`, `create_review_task`, `generate_review_tasks`.
- Governance: `feedback`, `compute_confidence`, `recompute_confidence`, `detect_conflicts`, `resolve_conflict`, `promote_claim`, `demote_claim`, `scope_claim`, `curate`, `explain_claim`.
- Project/session memory: `create_project`, `list_projects`, `start_session`, `end_session`, `list_sessions`.
- Reasoning: `run_inference`, `list_inferences`, `promote_inference`, `define_rule`, `run_rule`, `build_reflection`, `trace_derivation`, `invalidate_derived`.
- Governed LLM tasks: `extract_candidates(..., extractor="llm")`, `list_llm_runs`, `read_llm_run`, `expand_query`, `summarize_evidence`, `suggest_entities`, `suggest_categories`, `suggest_scope_with_llm`, `suggest_duplicate_merge_with_llm`, `draft_reflection_with_llm`, `explain_conflict_with_llm`.
- Learning and operations: `record_usage`, `record_outcome`, `create_eval_set`, `run_evaluation`, `optimize_retrieval`, `run_learning`, `enqueue_job`, `run_jobs`, `health_report`.
- Hardening: `create_backup`, `verify_backup`, `restore_backup`, `enable_protected_mode`, `redact`, `forget`, `integrity_check`, `export_archive`, `import_archive`, `support_bundle`, `readiness_check`.
- Platform: `list_public_contracts`, `compatibility_report`, `discover_plugins`, `install_plugin`, `run_conformance`, `doctor_run`, `v1_gate_run`.

## 2. CLI

Initialize a database:

```bash
uv run --extra dev aletheia init --db ./aletheia.db
```

Store and search an explicit memory:

```bash
uv run --extra dev aletheia remember \
  --db ./aletheia.db \
  --namespace user/default \
  --type preference \
  --subject user \
  --predicate prefers_response_style \
  --object "practical and direct"

uv run --extra dev aletheia search \
  --db ./aletheia.db \
  --namespace user/default \
  "response style"
```

Build an agent context pack:

```bash
uv run --extra dev aletheia context-pack \
  --db ./aletheia.db \
  --namespace user/default \
  --mode hybrid \
  --token-budget 1200 \
  "How should I answer this user?"
```

Candidate-first ingestion and review:

```bash
uv run --extra dev aletheia ingest text \
  --db ./aletheia.db \
  --namespace user/default \
  --title "Project note" \
  "For architecture docs, prefer concrete implementation detail."

uv run --extra dev aletheia extract run \
  --db ./aletheia.db \
  --namespace user/default \
  --batch ing_...

uv run --extra dev aletheia candidates list \
  --db ./aletheia.db \
  --namespace user/default

uv run --extra dev aletheia candidates promote cand_... \
  --db ./aletheia.db \
  --reason "Reviewed against source note."
```

Governed LLM tasks:

```bash
uv run --extra dev aletheia extract run \
  --db ./aletheia.db \
  --namespace user/default \
  --batch ing_... \
  --extractor llm

uv run --extra dev aletheia llm summarize-evidence \
  --db ./aletheia.db \
  --namespace user/default \
  --evidence evt_...

uv run --extra dev aletheia llm expand-query \
  --db ./aletheia.db \
  --namespace user/default \
  --privacy-level personal \
  "what should I know before the next milestone?"

uv run --extra dev aletheia llm suggest-entities \
  --db ./aletheia.db \
  --namespace user/default \
  --evidence evt_...

uv run --extra dev aletheia llm suggest-categories \
  --db ./aletheia.db \
  --namespace user/default \
  --evidence evt_...

uv run --extra dev aletheia llm suggest-scope \
  --db ./aletheia.db \
  --namespace user/default \
  cand_...

uv run --extra dev aletheia llm suggest-duplicate-merge \
  --db ./aletheia.db \
  --namespace user/default \
  cand_...

uv run --extra dev aletheia llm runs \
  --db ./aletheia.db \
  --namespace user/default
```

The top-level CLI command groups currently are:

| Area | Commands |
| --- | --- |
| Setup and schema | `init`, `migrate` |
| Memory read/write | `remember`, `search`, `context`, `context-pack`, `audit`, `feedback` |
| Ingestion and review | `ingest`, `extract`, `candidates`, `events`, `entities`, `categories`, `index`, `llm` |
| Projects and sessions | `projects`, `sessions` |
| Claims and governance | `claims`, `confidence`, `decay`, `curate`, `conflicts` |
| Reasoned memory | `infer`, `rules`, `reflect`, `derivation`, `clusters`, `abstractions` |
| Evaluation and learning | `usage`, `outcome`, `eval`, `optimize`, `learn`, `policies`, `procedures`, `jobs`, `health`, `rollback` |
| Service access | `serve`, `mcp`, `auth`, `clients`, `api`, `worker`, `service` |
| Console and observability | `console`, `reviews`, `metrics`, `traces`, `notifications`, `reports` |
| Production hardening | `backup`, `restore`, `encrypt`, `keys`, `redact`, `forget`, `retention`, `integrity`, `compact`, `export`, `import`, `support`, `benchmark`, `release`, `readiness` |
| Stable platform | `doctor`, `compatibility`, `plugins`, `conformance`, `adapters`, `docs`, `examples`, `contracts`, `deprecations`, `v1-gate` |

Use `--help` on any group for exact arguments:

```bash
uv run --extra dev aletheia candidates --help
uv run --extra dev aletheia backup create --help
```

## 3. Local HTTP API

Start the local daemon:

```bash
uv run --extra dev aletheia serve \
  --db ./aletheia.db \
  --host 127.0.0.1 \
  --port 8765
```

Create an API client and token before using authenticated access:

```bash
uv run --extra dev aletheia clients create \
  --db ./aletheia.db \
  --name local-agent \
  --type agent

uv run --extra dev aletheia auth create-token \
  --db ./aletheia.db \
  --client local-agent \
  --namespace user/default \
  --capabilities memory:read,memory:context,memory:write_candidate,memory:feedback,memory:audit
```

Common routes:

- `GET /v1/health`, `/v1/ready`, `/v1/version`, `/v1/openapi.json`.
- `POST /v1/context-pack` and alias `/v1/context`.
- `POST /v1/retrieve` and alias `/v1/search`.
- `POST /v1/remember`.
- `POST /v1/feedback`, `/v1/outcomes`, `/v1/retrieval-judgments`.
- `POST /v1/ingest`, `/v1/extract`.
- `GET /v1/candidates`, `GET /v1/candidates/{candidate_id}`, candidate promote/reject routes.
- Claim read/explain/promote/demote/scope/supersede routes.
- Project/session routes.
- Conflict, confidence, curation, inference, reflection, derivation, eval, learning, jobs, and health-report routes.
- Console, dashboard, review, trace, metric, notification, and report routes.
- Backup, restore, encryption, keys, redaction, forget, tombstone, retention, integrity, migration, compact, export/import, support, benchmark, release, and readiness routes.
- Contracts, deprecations, compatibility, plugins, conformance, adapters, docs, examples, doctor, and v1-gate routes.

Inspect the exact route list from the implementation:

```bash
uv run --extra dev aletheia api routes --db ./aletheia.db
uv run --extra dev aletheia api openapi --db ./aletheia.db --output ./openapi.json
```

HTTP responses are JSON envelopes:

```json
{
  "data": {},
  "request_id": "req_...",
  "warnings": [],
  "pagination": null
}
```

Errors use:

```json
{
  "error": {
    "code": "validation_error",
    "message": "The field 'namespace' is required.",
    "details": {}
  },
  "request_id": "req_..."
}
```

Use `Authorization: Bearer <token>` when auth is required. For state-changing retries, pass `Idempotency-Key`.

## 4. Python HTTP SDK

Use the SDK when your Python app should talk to the local daemon rather than opening SQLite directly.

```python
from aletheia import AletheiaClient

client = AletheiaClient("http://127.0.0.1:8765", token="atl_...")

pack = client.context_pack(
    namespace="user/default",
    query="How should I answer?",
    retrieval_mode="hybrid",
    record_usage=True,
)

candidate = client.remember_candidate(
    namespace="user/default",
    memory_type="preference",
    subject="user",
    predicate="prefers_response_style",
    object="practical and direct",
    evidence_text="The user said they prefer practical and direct answers.",
)
```

The SDK exposes sync and async clients:

- `AletheiaClient`
- `AsyncAletheiaClient`

It also exposes typed exceptions such as `AletheiaUnauthorizedError`, `AletheiaForbiddenError`, `AletheiaValidationError`, `AletheiaRateLimitError`, and `AletheiaServerError`.

## 5. MCP Tools

List available MCP tools:

```bash
uv run --extra dev aletheia mcp \
  --db ./aletheia.db \
  --mode read_write_candidate \
  --list-tools
```

Run the stdio tool registry:

```bash
uv run --extra dev aletheia mcp \
  --db ./aletheia.db \
  --namespace user/default \
  --mode read_write_candidate
```

Current MCP tools:

| Tool | Purpose |
| --- | --- |
| `memory_context_pack` | Build governed context for an agent. |
| `memory_search` | Search retrievable memory. |
| `memory_remember` | Store candidate memory by default. |
| `memory_feedback` | Record governed feedback. |
| `memory_audit` | Read provenance and audit information. |
| `memory_explain_claim` | Explain a claim with evidence, confidence, scope, history, and audit trail. |
| `memory_health` | Generate a memory health report. |
| `memory_ingest` | Store raw content as evidence. |
| `memory_extract_candidates` | Extract candidate memories from evidence. |
| `memory_list_candidates` | List candidates for review. |
| `memory_promote_candidate` | Promote a reviewed candidate through integrity gates. |
| `memory_reject_candidate` | Reject a candidate with audit trail. |
| `memory_trace_derivation` | Trace derivation lineage to source evidence. |
| `memory_record_outcome` | Record a task outcome as usefulness/policy signal. |

Modes are `read_only`, `read_write_candidate`, `read_write_active`, and `admin`.

## 6. Console

The local console is served by the HTTP service at `/console` when console mode is enabled.

Start it:

```bash
uv run --extra dev aletheia console serve \
  --db ./aletheia.db \
  --host 127.0.0.1 \
  --port 8765
```

Create a console login token:

```bash
uv run --extra dev aletheia console login-token \
  --db ./aletheia.db \
  --namespace user/default
```

The console uses:

- `/v1/console/login`, `/v1/console/logout`, and `/v1/console/session`.
- Dashboard overview and saved views.
- Review queue generation and resolution.
- Retrieval/context traces.
- Metrics snapshots.
- Notifications.
- Report exports.
- Production hardening checks.
- Stable-platform diagnostics.

State-changing console actions require a console session and CSRF token.

## 7. Plugins

Plugins are local extensions described by `aletheia-plugin.toml`.

Install and enable:

```bash
uv run --extra dev aletheia plugins install ./example-plugin --db ./aletheia.db
uv run --extra dev aletheia plugins enable example-extractor \
  --db ./aletheia.db \
  --permission write_candidate \
  --reason "Local test plugin"
```

Supported plugin protocol types are defined in `aletheia/plugins.py`: extractor, embedding provider, vector index, importer, exporter, inference engine, key provider, report generator, and agent adapter.

Plugin execution is governed by manifest validation, explicit permission approval, compatibility checks, and execution logs.

## 8. Agent Adapters

Use adapters when wrapping Aletheia into another agent loop.

```python
from aletheia import AletheiaClient, HttpAgentMemoryAdapter

client = AletheiaClient("http://127.0.0.1:8765", token="atl_...")
adapter = HttpAgentMemoryAdapter(client)

context_markdown = adapter.before_agent_call(
    namespace="user/default",
    query="Continue the architecture docs",
    project_id="aletheia",
)

adapter.after_agent_call(
    namespace="user/default",
    task_id="task_001",
    outcome="completed",
    notes="Generated grounded docs.",
)
```

Scaffold an adapter:

```bash
uv run --extra dev aletheia adapters scaffold \
  --db ./aletheia.db \
  --type generic-http \
  --name demo-adapter \
  --output ./examples/demo-adapter
```

Test or certify it:

```bash
uv run --extra dev aletheia adapters test ./examples/demo-adapter --db ./aletheia.db
uv run --extra dev aletheia adapters certify ./examples/demo-adapter --db ./aletheia.db
```

## 9. Docs And Examples Interface

Aletheia installs its canonical docs with the package. These commands do not
require a database:

```bash
uv run --extra dev aletheia docs list
uv run --extra dev aletheia docs path
uv run --extra dev aletheia docs show index
```

Aletheia can also copy the installed docs into a local site directory and
validate docs/example records through the stable-platform commands:

```bash
uv run --extra dev aletheia docs build --db ./aletheia.db --output ./site
uv run --extra dev aletheia docs status --db ./aletheia.db
uv run --extra dev aletheia docs test-examples --db ./aletheia.db
uv run --extra dev aletheia examples list --db ./aletheia.db
uv run --extra dev aletheia examples create \
  --db ./aletheia.db \
  --type python-sdk \
  --name python-sdk-agent \
  --output ./examples/python-sdk-agent
```

These commands are part of the M9 stable-platform surface.
