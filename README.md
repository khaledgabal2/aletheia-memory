# Aletheia

[![Release Gates](https://github.com/khaledgabal2/aletheia-memory/actions/workflows/release-gates.yml/badge.svg)](https://github.com/khaledgabal2/aletheia-memory/actions/workflows/release-gates.yml)

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
- Version: `1.4.1`
- Runtime: Python 3.11+
- Storage: local SQLite
- License: [MIT](https://github.com/khaledgabal2/aletheia-memory/blob/main/LICENSE)
- Distribution: published on PyPI; source installs and release wheels are also supported.

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

Use Python 3.11+ and install the published package:

```bash
python -m pip install aletheia-memory
```

Memory is independent of Desktop and Relay. Its core needs no model, account,
embedding index or running external service.

For the next steps, use the packaged [Python and TypeScript agent starters](https://github.com/khaledgabal2/aletheia-memory/blob/main/docs/examples.md),
then optionally [tested local model recipes](https://github.com/khaledgabal2/aletheia-memory/blob/main/docs/v1_4_0_local_model_recipes.md).
These additions require Memory 1.4.0 or later. Before upgrading an existing
database, follow the [backup and migration guide](https://github.com/khaledgabal2/aletheia-memory/blob/main/docs/v1_4_0_migration_guide.md).

## Your First Reviewed Memory

In a fresh demo directory, save this as `memory_demo.py` and run
`python memory_demo.py`. The example works with published 1.3.1 and with Memory
1.4.0 or later. Read the candidate and source before typing `approve`.

```python
"""A deterministic evidence → review → memory example; no model required."""
import os
from pathlib import Path
from aletheia import Memory

path = Path("aletheia-demo.db")
for suffix in ("-wal", "-shm", "-journal"):
    companion = Path(str(path) + suffix)
    if companion.exists() or companion.is_symlink():
        raise SystemExit("Database companion file already exists. Preserve it and choose a new directory.")
try:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    os.close(descriptor)
except FileExistsError:
    raise SystemExit("Demo database already exists. Choose a new directory; nothing was overwritten.")

namespace = "user/demo"
memory = Memory.open(str(path), namespace=namespace)
claim_id = None
try:
    batch = memory.ingest(namespace, source_type="manual",
                          content="User prefers careful architecture notes.", trust_level="user_asserted")
    run = memory.extract_candidates(namespace, batch_id=batch.id, extractor="rule_based")
    candidates = memory.list_candidates(namespace, extraction_run_id=run.id)
    if len(candidates) != 1:
        raise SystemExit("Expected one candidate from this bounded example; inspect the extraction result.")
    candidate = candidates[0]
    print("Pending candidate:", candidate.subject, candidate.predicate, candidate.object)
    print("Source:", memory.read_event(batch.evidence_ids[0]).content)
    print("Trusted results before approval:", len(memory.retrieve(namespace, "architecture", mode="lexical")))
    try:
        approve = input("Inspect the candidate and source. Type approve to promote it: ").strip() == "approve"
    except EOFError:
        approve = False
    if approve:
        claim = memory.promote_candidate(candidate.id, reason="I inspected and approved the demo candidate.")
        claim_id = claim.id
        print(memory.context_pack(namespace, "architecture", retrieval_mode="lexical", record_usage=False).to_markdown())
        print("Provenance:", memory.explain_claim(claim.id).evidence[0]["content"])
    else:
        print("Nothing promoted. The candidate remains pending review.")
finally:
    memory.close()

if claim_id:
    reopened = Memory.open(str(path), namespace=namespace, auto_migrate=False)
    try:
        hits = reopened.retrieve(namespace, "architecture", mode="lexical")
        assert hits and hits[0].claim_id == claim_id
        print("Reopened successfully: the reviewed claim and its evidence persist.")
    finally:
        reopened.close()
```

Before approval there are zero trusted matches. Approval produces context,
source provenance and a successful reopen check. Any other answer leaves the
candidate pending. The query matches the literal word `architecture`; arbitrary
paraphrase recall is not promised. Reruns refuse to overwrite the database.

See the [complete quickstart](https://github.com/khaledgabal2/aletheia-memory/blob/main/docs/quickstart.md), then the
[scoped HTTP agent starter](https://github.com/khaledgabal2/aletheia-memory/blob/main/docs/examples.md). The starter generator and read-only
diagnostic options require Aletheia Memory 1.4.0 or later:

```bash
aletheia examples create --type embedded --output ./memory-demo
cd memory-demo
python memory_demo.py
aletheia doctor --read-only --db ./aletheia-demo.db --namespace user/demo
```

On 1.3.1, use the copyable Python example above instead.
The five-minute human target is not yet measured.

The remaining sections are integration/reference workflows. Trusted embedded
`remember()` retains its active-write behavior; agents should submit candidates
and leave promotion to a separate operator.

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

- [Installation](https://github.com/khaledgabal2/aletheia-memory/blob/main/docs/installation.md)
- [Introduction](https://github.com/khaledgabal2/aletheia-memory/blob/main/docs/introduction.md)
- [Core Concepts](https://github.com/khaledgabal2/aletheia-memory/blob/main/docs/core_concepts.md)
- [Memory Lifecycle](https://github.com/khaledgabal2/aletheia-memory/blob/main/docs/memory_lifecycle.md)
- [Architecture](https://github.com/khaledgabal2/aletheia-memory/blob/main/docs/architecture.md)
- [Interfaces](https://github.com/khaledgabal2/aletheia-memory/blob/main/docs/interfaces.md)
- [CLI Reference](https://github.com/khaledgabal2/aletheia-memory/blob/main/docs/cli_reference.md)
- [Integration Guide](https://github.com/khaledgabal2/aletheia-memory/blob/main/docs/integration_guide.md)
- [HTTP API Reference](https://github.com/khaledgabal2/aletheia-memory/blob/main/docs/http_api_reference.md)
- [MCP Reference](https://github.com/khaledgabal2/aletheia-memory/blob/main/docs/mcp_reference.md)
- [Security And Privacy Guide](https://github.com/khaledgabal2/aletheia-memory/blob/main/docs/security_privacy_guide.md)
- [Operations Guide](https://github.com/khaledgabal2/aletheia-memory/blob/main/docs/operations_guide.md)
- [Troubleshooting](https://github.com/khaledgabal2/aletheia-memory/blob/main/docs/troubleshooting.md)
- [Near-Future Changes](https://github.com/khaledgabal2/aletheia-memory/blob/main/docs/near_future_changes.md)

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

## Release Verification

Before cutting a release, run:

```bash
uv run --extra dev pytest
python scripts/release_gate.py --branch main
uv build
```

## Community And Security

- Contributions: [CONTRIBUTING.md](https://github.com/khaledgabal2/aletheia-memory/blob/main/CONTRIBUTING.md)
- Security reports: [SECURITY.md](https://github.com/khaledgabal2/aletheia-memory/blob/main/SECURITY.md)
- Release notes: [CHANGELOG.md](https://github.com/khaledgabal2/aletheia-memory/blob/main/CHANGELOG.md)

## Contributing

Contributions should preserve Aletheia's core boundaries: local-first
operation, evidence-backed memory, candidate-first agent writes, explicit
review for trust, scoped access, and auditability. Open an issue or discussion
before introducing new persistent schema, new network behavior, or new
active-write paths.

## Development Installation

For repository development after the public quickstart:

```bash
git clone https://github.com/khaledgabal2/aletheia-memory.git
cd aletheia-memory
python -m pip install -e ".[dev]"
python -m pytest
```

A reviewed wheel can instead be installed by its local path. Development
checkouts may contain unreleased changes; use a pinned published version for
production. Never commit credentials or private databases.
