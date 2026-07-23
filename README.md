# Aletheia

Local, auditable memory for AI agents.

Aletheia is a Python package, CLI, and local service for giving agents durable
memory without giving up provenance, review, privacy, or operator control. It
stores memory in SQLite and treats memory as an evidence-backed lifecycle:

```text
evidence -> candidate memory -> review/promotion -> claim -> retrieval/context -> feedback/audit
```

That lifecycle is the point. Raw notes, transcripts, tool observations, and LLM
outputs can be captured as evidence or candidate memories, but they do not need
to become trusted facts until a review or explicit active-write policy promotes
them.

Aletheia is useful for local agents, agent frameworks, developer tools,
research assistants, and any application that needs cross-session recall with a
clear audit trail.

## Status

- Package name: `aletheia-memory`
- CLI command: `aletheia`
- Current version: `1.3.0`
- Runtime: Python 3.11+
- Storage: local SQLite
- License: MIT

## What Aletheia Provides

- **Local-first memory kernel**: structured evidence, candidates, claims,
  confidence, conflicts, projects, sessions, audit trails, and context packs.
- **Reliable retrieval**: deterministic SQLite FTS search, optional governed
  semantic indexing, hybrid retrieval, retrieval traces, and agent-ready
  context budgets.
- **Review-first ingestion**: ingest notes, logs, and transcripts; extract
  candidate memories; then promote, reject, scope, or merge after review.
- **Governed LLM memory tasks**: optional LLM extraction, query expansion,
  entity/category suggestions, duplicate-merge suggestions, reflection drafts,
  and conflict explanations with provenance and review state.
- **Reasoned memory**: inference candidates, reflections, semantic relations,
  derivation traces, lossless abstractions, and invalidation when source
  material changes.
- **Memory integrity controls**: confidence recomputation, contradiction
  detection, decay policies, curation decisions, feedback, claim scoping, and
  audit/explanation commands.
- **Agent interfaces**: in-process Python API, CLI, local HTTP API, sync/async
  Python SDK clients, MCP tools, and generic agent adapters.
- **Operational hardening**: protected mode, scoped API tokens, namespace
  grants, privacy ceilings, encrypted backups, restore verification, redaction,
  forget tombstones, retention, integrity checks, support bundles, diagnostics,
  release gates, and compatibility reports.
- **Extension platform**: plugin manifests, permissions, compatibility checks,
  conformance suites, adapters, public contracts, and generated docs/examples.

## Installation

Install from a published package or release wheel:

```bash
python -m pip install aletheia-memory
```

Verify the CLI and bundled docs:

```bash
aletheia --help
aletheia docs list
aletheia docs show introduction
```

Install from source:

```bash
git clone https://github.com/<owner>/<repo>.git
cd <repo>
python -m pip install ".[dev]"
```

For local development with `uv`:

```bash
uv run --extra dev aletheia --help
uv run --extra dev pytest
```

## Quick Start

Create a local SQLite database:

```bash
aletheia init --db ./aletheia.db
```

Store a reviewed explicit memory:

```bash
aletheia remember \
  --db ./aletheia.db \
  --namespace user/default \
  --type preference \
  --subject user \
  --predicate prefers_response_style \
  --object "practical and direct"
```

Search memory:

```bash
aletheia search \
  --db ./aletheia.db \
  --namespace user/default \
  "response style"
```

Build an agent-ready context pack:

```bash
aletheia context-pack \
  --db ./aletheia.db \
  --namespace user/default \
  --mode lexical \
  --token-budget 1200 \
  "How should the assistant respond?"
```

During repository development, prefix the same commands with
`uv run --extra dev`:

```bash
uv run --extra dev aletheia init --db ./aletheia.db
```

## Candidate-First Ingestion

Use candidate-first ingestion when you want to capture source material without
trusting every extracted statement automatically.

Ingest a note:

```bash
aletheia ingest text \
  --db ./aletheia.db \
  --namespace user/default \
  --project demo \
  --title "Agent operating notes" \
  "For architecture questions, include concrete implementation details and cite the relevant files."
```

Extract candidate memories:

```bash
aletheia extract run \
  --db ./aletheia.db \
  --namespace user/default \
  --batch ing_... \
  --extractor rule_based
```

Review candidates:

```bash
aletheia candidates list \
  --db ./aletheia.db \
  --namespace user/default
```

Promote only what was reviewed:

```bash
aletheia candidates promote cand_... \
  --db ./aletheia.db \
  --reason "Reviewed against the original note."
```

## Semantic And Hybrid Retrieval

Aletheia works with deterministic lexical search out of the box. You can also
index promoted claims with a local semantic provider and run hybrid retrieval:

```bash
aletheia index semantic \
  --db ./aletheia.db \
  --namespace user/default \
  --target claims \
  --provider local_hash \
  --dimension 64

aletheia search \
  --db ./aletheia.db \
  --namespace user/default \
  --mode hybrid \
  --semantic-provider local_hash \
  "What response style does the user prefer?"
```

## Python API

Use the in-process kernel when your Python application can safely share the
local SQLite database.

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
        query="How should the assistant respond?",
        retrieval_mode="lexical",
        token_budget=1200,
    )

    print(claim.id)
    print([result.claim_id for result in results])
    print(pack.to_markdown())
finally:
    memory.close()
```

## Local HTTP Service

Use the HTTP service when another process, runtime, or language needs access to
memory.

Create an API client and scoped token:

```bash
aletheia clients create \
  --db ./aletheia.db \
  --name local-agent \
  --type agent

aletheia auth create-token \
  --db ./aletheia.db \
  --client local-agent \
  --namespace user/default \
  --capabilities memory:read,memory:context,memory:write_candidate,memory:feedback,memory:audit
```

Start the local daemon:

```bash
aletheia serve \
  --db ./aletheia.db \
  --host 127.0.0.1 \
  --port 8765
```

Health and API discovery:

```bash
curl -s http://127.0.0.1:8765/v1/health
curl -s http://127.0.0.1:8765/v1/openapi.json
```

Fetch a context pack:

```bash
curl -s http://127.0.0.1:8765/v1/context-pack \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer atl_..." \
  -d '{
    "namespace": "user/default",
    "query": "How should the assistant respond?",
    "retrieval_mode": "lexical",
    "token_budget": 1200,
    "record_usage": true
  }'
```

Store an agent observation as a reviewable candidate:

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

## MCP

Use MCP when an agent host can run local stdio tools.

```bash
aletheia mcp \
  --db ./aletheia.db \
  --namespace user/default \
  --mode read_write_candidate
```

Recommended modes:

- `read_only` for context-only consumers.
- `read_write_candidate` for normal local agents.
- `read_write_active` for trusted tools that may write active claims.
- `admin` for operational tooling.

## Common Workflows

Inspect claim provenance:

```bash
aletheia audit clm_... --db ./aletheia.db
```

Record feedback:

```bash
aletheia feedback clm_... \
  --db ./aletheia.db \
  --namespace user/default \
  --signal confirmed \
  --note "Confirmed during review."
```

Detect and resolve conflicts:

```bash
aletheia conflicts list \
  --db ./aletheia.db \
  --namespace user/default

aletheia conflicts resolve conf_... \
  --db ./aletheia.db \
  --strategy context_scope \
  --note "Both claims are valid in different contexts."
```

Run operational checks:

```bash
aletheia doctor --db ./aletheia.db
aletheia compatibility report --db ./aletheia.db
aletheia readiness check --db ./aletheia.db --namespace user/default
```

Create and verify an encrypted backup:

```bash
aletheia backup create \
  --db ./aletheia.db \
  --namespace user/default \
  --output ./aletheia.alet \
  --encrypt \
  --passphrase "change-me"

aletheia backup verify ./aletheia.alet \
  --db ./aletheia.db \
  --passphrase "change-me"
```

Generate local docs:

```bash
aletheia docs build --db ./aletheia.db --output ./site
aletheia examples list --db ./aletheia.db
```

## Documentation

Aletheia ships its docs with the installed package:

```bash
aletheia docs list
aletheia docs path
aletheia docs show index
```

Recommended starting points:

- [Installation](docs/installation.md)
- [Introduction](docs/introduction.md)
- [Core Concepts](docs/core_concepts.md)
- [Memory Lifecycle](docs/memory_lifecycle.md)
- [Architecture](docs/architecture.md)
- [Interfaces](docs/interfaces.md)
- [CLI Reference](docs/cli_reference.md)
- [Integration Guide](docs/integration_guide.md)
- [HTTP API Reference](docs/http_api_reference.md)
- [MCP Reference](docs/mcp_reference.md)
- [Security And Privacy Guide](docs/security_privacy_guide.md)
- [Operations Guide](docs/operations_guide.md)
- [Troubleshooting](docs/troubleshooting.md)
- [Near-Future Changes](docs/near_future_changes.md)

## Trust And Privacy Model

Aletheia is local-first by default. Evidence, claims, review state, service logs,
metrics, traces, and operational records live in the configured SQLite database
unless explicitly exported.

Important boundaries:

- Raw ingested content is evidence, not truth.
- Candidate writes are the default safer write path for agents.
- Active writes require explicit authority.
- API tokens can be scoped by capability, namespace grant, and privacy ceiling.
- Protected mode encrypts sensitive stored content when configured with local
  key material.
- External LLM providers are optional and governed by policy.
- Forget and redaction workflows preserve tombstones and auditability.

## Development

Run tests:

```bash
uv run --extra dev pytest
```

Run the release gate for the public baseline:

```bash
python scripts/release_gate.py --branch main
```

Build the package:

```bash
uv build
```

## Public Repository Checklist

Before publishing a new public repository, verify:

- The default branch is `main`.
- The repository does not include local databases, generated support bundles,
  credentials, tokens, private logs, or environment files.
- The Git remote URL does not contain embedded credentials.
- Historical design docs are acceptable to publish, or are moved to a private
  branch before the public import.
- `uv run --extra dev pytest` passes.
- `python scripts/release_gate.py --branch main` passes.
- The package metadata in `pyproject.toml` has the intended name, version,
  license, authorship, and project URLs.

## Contributing

Contributions should preserve Aletheia's core boundaries: local-first operation,
evidence-backed memory, candidate-first agent writes, explicit review for trust,
scoped access, and auditability. Open an issue or discussion before introducing
new persistent schema, new network behavior, or new active-write paths.
