# Aletheia Integration Guide

This guide explains how to integrate the current Aletheia implementation into other systems.

Use the integration style that matches your boundary:

- Same Python process: use `Memory`.
- Different process or language: run `aletheia serve` and use HTTP.
- MCP-capable agent host: run `aletheia mcp`.
- Python agent loop over HTTP: use `AletheiaClient` or `HttpAgentMemoryAdapter`.
- Extension inside Aletheia governance: write a plugin.
- Operational automation: use the CLI.

## Integration Pattern 1: Embedded Python

Choose this when the integrating system is Python and can safely access the local database file.

```python
from aletheia import Memory

memory = Memory.open("./aletheia.db", namespace="user/default")
try:
    pack = memory.context_pack(
        namespace="user/default",
        query="What context matters for this task?",
        retrieval_mode="hybrid",
        record_usage=True,
    )
    context_for_agent = pack.to_markdown()

    memory.feedback(
        namespace="user/default",
        target_id="clm_...",
        signal="confirmed",
        note="User explicitly confirmed this memory.",
    )
finally:
    memory.close()
```

Use embedded Python for local scripts, notebooks, tests, and agents that do not need a service boundary.

Avoid opening the same SQLite file independently from many unrelated long-running processes unless you have tested the concurrency profile. The HTTP service gives a cleaner boundary for multi-agent local use.

## Integration Pattern 2: HTTP Sidecar

Choose this when another process, runtime, or language needs memory.

Start the sidecar:

```bash
uv run --extra dev aletheia serve \
  --db ./aletheia.db \
  --host 127.0.0.1 \
  --port 8765
```

Fetch context before an agent call:

```bash
curl -s http://127.0.0.1:8765/v1/context-pack \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer atl_..." \
  -d '{
    "namespace": "user/default",
    "query": "How should I answer?",
    "retrieval_mode": "hybrid",
    "token_budget": 1200,
    "record_usage": true
  }'
```

Store a candidate memory after an agent observation:

```bash
curl -s http://127.0.0.1:8765/v1/remember \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer atl_..." \
  -H "Idempotency-Key: task-001-memory-001" \
  -d '{
    "namespace": "user/default",
    "write_mode": "candidate",
    "memory_type": "preference",
    "subject": "user",
    "predicate": "prefers_response_style",
    "object": "practical and direct",
    "evidence_text": "The user asked for practical and direct answers."
  }'
```

Promote only after review:

```bash
curl -s http://127.0.0.1:8765/v1/candidates/cand_.../promote \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer atl_..." \
  -d '{"reason": "Reviewed against source evidence."}'
```

## Integration Pattern 3: Python SDK Over HTTP

Use the SDK when your integration is Python but should talk to the daemon.

```python
from aletheia import AletheiaClient

client = AletheiaClient("http://127.0.0.1:8765", token="atl_...")

compatibility = client.check_compatibility()
if not compatibility["compatible"]:
    raise RuntimeError(compatibility["warnings"])

pack = client.context_pack(
    namespace="user/default",
    query="What should the agent remember?",
    retrieval_mode="hybrid",
)

candidate = client.remember_candidate(
    namespace="user/default",
    memory_type="fact",
    subject="project:aletheia",
    predicate="has_doc_goal",
    object="grounded implementation help docs",
    evidence_text="The user asked for grounded implementation help docs.",
)
```

The client stores `last_request_id`, `last_warnings`, `last_pagination`, and `last_envelope` after requests.

## Integration Pattern 4: Generic Agent Adapter

Use `HttpAgentMemoryAdapter` when your agent loop has clear before/after hooks.

```python
from aletheia import AletheiaClient, HttpAgentMemoryAdapter

adapter = HttpAgentMemoryAdapter(
    AletheiaClient("http://127.0.0.1:8765", token="atl_...")
)

context = adapter.before_agent_call(
    namespace="user/default",
    query="Plan the next implementation step",
    project_id="aletheia",
)

# Pass `context` into your agent prompt.

adapter.after_agent_call(
    namespace="user/default",
    task_id="task_001",
    outcome="completed",
    notes="Used context pack in answer.",
)

candidate_id = adapter.remember_candidate(
    namespace="user/default",
    memory_type="preference",
    subject="user",
    predicate="prefers_docs",
    object="grounded in real implementation",
    evidence_text="The user requested no hallucination and no memory recalls.",
)
```

The adapter intentionally writes candidates, not active claims.

## Integration Pattern 5: MCP

Use MCP when the agent host can run stdio tools.

```bash
uv run --extra dev aletheia mcp \
  --db ./aletheia.db \
  --namespace user/default \
  --mode read_write_candidate
```

Recommended modes:

- `read_only` for context-only consumers.
- `read_write_candidate` for normal local agents.
- `read_write_active` only for trusted tools that are allowed to bypass candidate review.
- `admin` only for operational tooling.

The core agent loop is:

```text
memory_context_pack before reasoning
memory_search when more focused recall is needed
memory_remember with candidate writes after observing useful information
memory_record_outcome after task completion
memory_feedback when user or system feedback arrives
memory_audit / memory_explain_claim when provenance matters
```

## Integration Pattern 6: Plugins

Use plugins to extend Aletheia while staying inside its governance model.

Plugin types are protocol-defined in `aletheia/plugins.py`:

- `ExtractorPlugin`
- `EmbeddingProviderPlugin`
- `VectorIndexPlugin`
- `ImporterPlugin`
- `ExporterPlugin`
- `InferenceEnginePlugin`
- `KeyProviderPlugin`
- `ReportGeneratorPlugin`
- `AgentAdapterPlugin`

A plugin must declare `aletheia-plugin.toml`. The platform validates plugin type, compatibility, API contract version, capabilities, and permissions.

Plugins should assume:

- Reading evidence text is high-risk and requires permission.
- Writing active claims is high-risk and blocked by the stable operation runner.
- Candidate writes are the safe default.
- Plugin runs are logged.

## Integration Pattern 7: Operational Automation

Use the CLI for local automation:

```bash
uv run --extra dev aletheia doctor --db ./aletheia.db
uv run --extra dev aletheia compatibility report --db ./aletheia.db
uv run --extra dev aletheia backup create \
  --db ./aletheia.db \
  --output ./aletheia.alet \
  --encrypt \
  --passphrase "change-me"
uv run --extra dev aletheia readiness check --db ./aletheia.db --namespace user/default
```

Use `api routes` and `api openapi` to keep external clients aligned with the current service:

```bash
uv run --extra dev aletheia api routes --db ./aletheia.db
uv run --extra dev aletheia api openapi --db ./aletheia.db --output ./openapi.json
```

## Authentication And Authorization

HTTP service auth uses:

- API clients.
- Hashed API tokens.
- Capability grants.
- Namespace grants.
- Privacy ceilings.

Current capabilities are:

```text
memory:read
memory:context
memory:write_candidate
memory:write_active
memory:ingest
memory:extract
memory:review
memory:feedback
memory:audit
memory:admin
memory:jobs
memory:evaluate
memory:learn
memory:policy
memory:delete
```

For ordinary agents, grant only:

```text
memory:read,memory:context,memory:write_candidate,memory:feedback,memory:audit
```

Add `memory:ingest`, `memory:extract`, or `memory:review` only if the integration needs those workflows. Reserve `memory:admin`, `memory:write_active`, and `memory:delete` for trusted operational tools.

## Namespace And Privacy Design

Use namespaces as the main boundary between users, projects, tenants, or workspaces.

Examples:

```text
user/default
user/default/projects/aletheia
team/research
agent/local-coding
```

API tokens can be granted one or more namespaces. Privacy ceilings restrict which evidence-backed memories are visible to the caller. The current privacy order is `public`, `personal`, `private`/`sensitive`, `secret`.

## Safe Agent Memory Loop

A conservative integration loop looks like this:

```text
1. Start or identify project/session.
2. Build context pack before the agent reasons.
3. Give the agent context Markdown plus source IDs when useful.
4. Record task outcome after the agent acts.
5. Write new observations as candidate memories.
6. Review/promote candidates separately.
7. Record user feedback against claims or outcomes.
8. Audit or explain claims before relying on high-impact memories.
```

This loop matches the implemented `HttpAgentMemoryAdapter`.

## What Not To Do

Do not treat extracted candidates as facts.

Do not let an ordinary agent use `memory:write_active` unless you explicitly want it to bypass candidate review.

Do not rely on assistant repetition as confirmation. The kernel downweights assistant-originated confirmation without evidence.

Do not write directly into SQLite tables from external systems. Use the Python kernel, CLI, HTTP API, SDK, MCP, or plugin surface so audit, confidence, indexing, and governance code runs.

Do not expose the HTTP service on a remote host without authentication. The service validates that remote binding requires `--allow-remote` and authentication.

Do not assume federation exists yet. Use export/import or backup/restore for current movement of data between databases.
