# Aletheia v0.1 Architectural Decisions

This document formalizes the MVP discipline for Aletheia v0.1.

The broader roadmap may include daemons, MCP, adapters, vector search,
automatic extraction, background curation, dashboards, and inference engines.
Version 0.1 does not. Version 0.1 must prove the memory kernel can remember,
retrieve, audit, decay, and correct explicit memories reliably.

## Decision 1: Package Tooling

Use:

- `pyproject.toml` for package metadata and tool configuration.
- Hatchling as the build backend.
- `uv` for the development workflow.
- `pytest` for tests.
- Standard Python installers for users.

`uv` is a development choice, not a user requirement. Users must still be able
to install Aletheia with normal Python tooling:

```bash
pip install aletheia-memory
```

The initial package should keep core dependencies nearly empty. SQLite is
available through Python's standard `sqlite3` module, so v0.1 should not add a
database dependency just to use SQLite.

Recommended initial `pyproject.toml` shape:

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "aletheia-memory"
version = "0.1.0"
description = "Local, auditable memory for AI agents."
readme = "README.md"
requires-python = ">=3.11"
license = "MIT"
authors = [
  { name = "Aletheia Contributors" }
]
keywords = [
  "ai",
  "agents",
  "memory",
  "local-first",
  "retrieval",
  "context"
]
dependencies = []

[project.optional-dependencies]
cli = []
server = []
mcp = []
dev = [
  "pytest"
]

[project.scripts]
aletheia = "aletheia.cli.main:main"

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["."]
addopts = "-q"
```

Later optional extras may include:

```toml
[project.optional-dependencies]
server = ["fastapi", "uvicorn"]
mcp = ["mcp"]
vector = ["qdrant-client"]
dev = ["pytest", "ruff", "mypy"]
```

Do not load the MVP with ecosystem dependencies before the memory kernel is
stable.

## Decision 2: MVP CLI Scope

The CLI belongs in the MVP because Aletheia must be inspectable from the start.
The v0.1 CLI is for inspection and control, not dashboards or observability.

Include these commands in v0.1:

- `aletheia init`
- `aletheia remember`
- `aletheia search`
- `aletheia context-pack`
- `aletheia feedback`
- `aletheia events`
- `aletheia claims`
- `aletheia audit`
- `aletheia conflicts`

Defer these until later:

- dashboard
- metrics server
- observability traces
- memory graph visualization
- embedding inspection
- background worker monitor
- advanced analytics

### `aletheia init`

Creates the local database and runs migrations:

```bash
aletheia init --db ./aletheia.db
```

Responsibilities:

- Create the database file.
- Create `schema_version`.
- Create `evidence_events`.
- Create `claims`.
- Create `claim_evidence_links`.
- Create `audit_log`.
- Create `conflicts`.
- Create `conflict_claim_links`.
- Create `feedback`.
- Create FTS tables.

### `aletheia remember`

Stores one explicit, schema-driven memory:

```bash
aletheia remember \
  --db ./aletheia.db \
  --namespace user/default \
  --type preference \
  --subject user \
  --predicate prefers_response_style \
  --object "practical and direct"
```

This command must create:

1. An evidence event.
2. A claim.
3. A claim-evidence link.
4. An audit entry.
5. A search index update.

In v0.1, `remember` must not call an LLM or infer hidden memories. It writes
exactly what was provided.

### `aletheia search`

Searches active memory:

```bash
aletheia search \
  --db ./aletheia.db \
  --namespace user/default \
  "response style"
```

Output should show:

- claim ID
- memory text
- memory type
- status
- confidence
- evidence count
- created time

Search should also support basic filters:

```bash
aletheia search \
  --db ./aletheia.db \
  --namespace user/default \
  --type preference \
  "response style"

aletheia search \
  --db ./aletheia.db \
  --namespace user/default \
  --status rejected \
  "response style"
```

Normal search should exclude archived, rejected, and superseded memories by
default. An explicit `--status` filter may intentionally inspect those states.

### `aletheia context-pack`

Builds grouped, agent-ready memory context:

```bash
aletheia context-pack \
  --db ./aletheia.db \
  --namespace user/default \
  "response style"
```

The output should group core, relevant, project, procedural, warning,
disputed, and source sections when present.

### `aletheia feedback`

Records explicit feedback on a memory:

```bash
aletheia feedback clm_001 \
  --db ./aletheia.db \
  --namespace user/default \
  --signal confirmed \
  --note "User explicitly confirmed this."
```

Supported v0.1 signals:

- `confirmed`
- `wrong`
- `stale`
- `useful`
- `not_useful`
- `contradicted`
- `verified`
- `irrelevant`

Feedback must be auditable. It may update confidence, verification time, or
claim status depending on signal.

### `aletheia events`

Inspects raw evidence:

```bash
aletheia events list \
  --db ./aletheia.db \
  --namespace user/default

aletheia events show evt_001 \
  --db ./aletheia.db
```

Evidence inspection is part of the MVP because Aletheia's central guarantee is
that memories can be traced back to their source.

### `aletheia claims`

Inspects and manages structured claims:

```bash
aletheia claims list --namespace user/default
aletheia claims show clm_001
aletheia claims promote clm_001 --to core
aletheia claims demote clm_001 --to archived
```

For v0.1, include:

- `claims list`
- `claims show`
- `claims promote`
- `claims demote`

### `aletheia audit`

Shows provenance:

```bash
aletheia audit clm_001 --db ./aletheia.db
```

The output must answer:

- Where did this memory come from?
- When was it created?
- What evidence supports it?
- Was it promoted, demoted, corrected, or superseded?

Auditability is not optional for Aletheia.

### `aletheia conflicts`

Lists and manually resolves simple contradictions:

```bash
aletheia conflicts list --namespace user/default
aletheia conflicts show conf_001
aletheia conflicts resolve conf_001 --active clm_002
```

For v0.1, conflict resolution can be manual. The system detects simple
conflicts; the user or developer resolves them.

## Decision 3: Automatic Extraction

Defer automatic LLM extraction.

The v0.1 write path must be:

```text
User or agent calls remember()
  -> Aletheia writes raw evidence
  -> Aletheia writes explicit structured claim
  -> Aletheia links claim to evidence
  -> Aletheia indexes claim
  -> Aletheia writes audit event
```

No hidden inference. No autonomous canonization.

Recommended v0.1 Python API:

```python
memory.remember(
    namespace="user/default",
    memory_type="preference",
    subject="user",
    predicate="prefers_response_style",
    object="practical and direct",
    source_type="manual",
    confidence=0.90,
)
```

Avoid this in v0.1:

```python
memory.remember("Example User likes clear answers and is probably technical.")
```

That sentence mixes a possible preference with a possible inference. The MVP
must not blur those categories.

Later automatic extraction may generate candidate claims, not active memories:

```text
Event
  -> extractor
  -> candidate claims
  -> validation
  -> contradiction check
  -> promotion policy
  -> active memory
```

The future extractor should sit behind an interface:

```python
class Extractor:
    def extract(self, event: EvidenceEvent) -> list[CandidateClaim]:
        ...
```

The v0.1 implementation can be explicit and inert:

```python
class ManualExtractor:
    def extract(self, event):
        return []
```

LLM extraction may suggest memories later. It must not silently canonize them.

## Decision 4: Storage

Use SQLite plus SQLite FTS5 first.

Do not add vector search until:

- the retrieval API is stable
- the claim schema is stable
- the context pack format is stable
- contradiction handling exists
- the audit trail exists

The v0.1 storage stack is:

- SQLite
- SQLite FTS5
- Python `sqlite3`
- local file path
- no external service
- no vector database
- no graph database

Initial tables:

- `schema_version`
- `evidence_events`
- `claims`
- `claim_evidence_links`
- `audit_log`
- `conflicts`
- `conflict_claim_links`
- `feedback`
- `claims_fts`

Suggested FTS table:

```sql
CREATE VIRTUAL TABLE claims_fts USING fts5(
    claim_id UNINDEXED,
    namespace UNINDEXED,
    subject,
    predicate,
    object,
    memory_type UNINDEXED,
    content
);
```

`content` should be a generated text representation of the claim, for example:

```text
User prefers response style practical and direct.
```

Keep the retrieval interface future-proof:

```python
class Retriever:
    def retrieve(
        self,
        namespace: str,
        query: str,
        filters: dict | None = None,
        limit: int = 10,
    ) -> list[RetrievalResult]:
        ...
```

The MVP implementation is:

```python
class SQLiteFTSRetriever(Retriever):
    ...
```

Later implementations may include `HybridRetriever` or `VectorRetriever`, but
they must not change the public API.

## v0.1 Release Boundary

Aletheia v0.1 includes:

- `pyproject.toml`
- `uv.lock`
- `pytest` tests
- SQLite database
- FTS5 lexical search
- evidence ledger
- claim store
- manual/schema-driven `remember()`
- `retrieve()`
- `context_pack()`
- confidence fields
- basic half-life decay
- simple contradiction detection
- audit trail
- MVP CLI

Aletheia v0.1 does not include:

- LLM extraction
- automatic curation
- vector database
- graph database
- dashboard
- daemon
- MCP server
- agent framework adapters
- cloud sync
- advanced inference

## v0.1 Proof

Version 0.1 should prove:

- Can the system remember one explicit claim?
- Can it link that claim to raw evidence?
- Can it retrieve the claim later?
- Can it show where the claim came from?
- Can it decay stale confidence?
- Can it detect a simple contradiction?
- Can it let the user inspect and correct memory?

The demo should be:

```bash
aletheia init --db ./aletheia.db
aletheia remember \
  --db ./aletheia.db \
  --namespace user/default \
  --type preference \
  --subject user \
  --predicate prefers_response_style \
  --object "practical and direct"
aletheia search \
  --db ./aletheia.db \
  --namespace user/default \
  "response style"
aletheia audit clm_001 --db ./aletheia.db
```

Then create a contradiction:

```bash
aletheia remember \
  --db ./aletheia.db \
  --namespace user/default \
  --type preference \
  --subject user \
  --predicate prefers_response_style \
  --object "long and highly detailed"
aletheia conflicts list --db ./aletheia.db
```

That demo is intentionally humble. It proves the heart of Aletheia.
