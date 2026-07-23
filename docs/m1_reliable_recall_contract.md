# Aletheia M1 Contract: Reliable Recall and Context Continuity

This document is the implementation contract for M1.

M0 proved that Aletheia can remember, inspect, retrieve, audit, and correct
basic memories. M1 must prove that Aletheia can recall correctly across
sessions and package useful context for an agent.

## Status

- milestone: `M1`
- name: `Reliable Recall and Context Continuity`
- depends on: `M0`
- version target: `0.2.0`
- stability: `internal-beta`
- storage migration required: yes
- LLM required: no
- vector backend required: no
- daemon required: no
- dashboard required: no

## Core Promise

Given a namespace, query, and optional session or project context, Aletheia
returns the most relevant, highest-confidence, non-contradictory memories in an
agent-ready context pack, with provenance preserved.

## In Scope

- Stable retrieval API
- Improved SQLite FTS5 search
- Metadata filtering
- Ranking v1
- Context pack v1
- Session model
- Project model
- Cross-session recall
- Claim lifecycle hardening
- Effective confidence recomputation during retrieval
- Conflict-aware retrieval
- CLI improvements for context, sessions, and projects
- Golden retrieval/context tests
- Storage migration from M0 to M1

## Out of Scope

- LLM automatic extraction
- Vector embeddings
- Qdrant, LanceDB, pgvector
- Graph database
- MCP server
- HTTP daemon
- Dashboard
- Autonomous self-learning
- Advanced inference engine
- Background curator
- Cloud sync
- Multi-user enterprise permission model

M1 must remain local, deterministic, and inspectable.

## Public API Contract

### `memory.retrieve()`

Purpose: retrieve ranked memories for a query.

```python
def retrieve(
    self,
    namespace: str,
    query: str,
    *,
    limit: int = 10,
    memory_types: list[str] | None = None,
    statuses: list[str] | None = None,
    subject: str | None = None,
    predicate: str | None = None,
    project_id: str | None = None,
    session_id: str | None = None,
    min_confidence: float | None = None,
    include_disputed: bool = False,
    include_archived: bool = False,
    recompute_confidence: bool = True,
) -> list[RetrievalResult]:
    ...
```

Required behavior:

- Search only within the requested namespace unless explicitly configured
  otherwise.
- Exclude rejected memories always.
- Exclude archived memories by default.
- Exclude disputed memories by default.
- Recompute effective confidence before ranking by default.
- Penalize stale memories.
- Penalize conflict-linked memories.
- Prefer active and core memories.
- Return deterministic ranking for identical inputs.
- Preserve provenance in each result.

`RetrievalResult` must include:

- `claim_id`
- `namespace`
- `text`
- `subject`
- `predicate`
- `object`
- `memory_type`
- `status`
- `score`
- `lexical_score`
- `confidence_base`
- `confidence_effective`
- `importance`
- `created_at`
- `last_verified_at`
- `evidence_ids`
- `conflict_ids`
- `project_ids`

### `memory.context_pack()`

Purpose: build an agent-ready memory context from retrieved claims.

```python
def context_pack(
    self,
    namespace: str,
    query: str,
    *,
    session_id: str | None = None,
    project_id: str | None = None,
    token_budget: int = 1500,
    include_sources: bool = True,
    include_confidence: bool = True,
    include_warnings: bool = True,
) -> ContextPack:
    ...
```

Required behavior:

- Retrieve relevant memories.
- Group memories by use.
- Respect token budget.
- Prioritize core memory.
- Include project memory when `project_id` is provided.
- Include session continuity when `session_id` is provided.
- Include procedural memory when relevant.
- Label inferred, disputed, or stale memories.
- Exclude rejected memories.
- Exclude archived memories unless explicitly requested.
- Preserve provenance in structured output.

`ContextPack` must include:

- `namespace`
- `query`
- `session_id`
- `project_id`
- `token_budget`
- `generated_at`
- `core_memory`
- `project_memory`
- `session_memory`
- `procedural_memory`
- `relevant_memory`
- `warnings`
- `omitted`
- `to_markdown()`
- `to_dict()`

`ContextItem` must include:

- `text`
- `claim_id`
- `memory_type`
- `confidence_effective`
- `status`
- `evidence_ids`
- `reason`

`ContextWarning` must include:

- `text`
- `warning_type`
- `claim_ids`
- `conflict_ids`

`OmittedMemory` must include:

- `claim_id`
- `reason`
- `score`

## Sessions API

### `memory.start_session()`

```python
def start_session(
    self,
    namespace: str,
    *,
    agent_id: str | None = None,
    project_id: str | None = None,
    title: str | None = None,
    metadata: dict | None = None,
) -> Session:
    ...
```

Required behavior:

- Create a durable session row.
- Associate the session with a project when `project_id` is provided.
- Write an audit event.
- Return the session ID for later context packing.

### `memory.end_session()`

```python
def end_session(
    self,
    session_id: str,
    *,
    summary: str | None = None,
    remember_summary: bool = True,
) -> Session:
    ...
```

If `summary` is provided and `remember_summary=True`, Aletheia must:

- Write summary as evidence.
- Create a `session_summary` claim.
- Link claim to session.
- Link claim to project if the session has `project_id`.
- Index the summary.

## Projects API

### `memory.create_project()`

```python
def create_project(
    self,
    namespace: str,
    project_id: str,
    *,
    title: str,
    description: str | None = None,
    status: str = "active",
    metadata: dict | None = None,
) -> Project:
    ...
```

The project model must include:

- `id`
- `namespace`
- `title`
- `description`
- `status`
- `created_at`
- `updated_at`
- `metadata`

## Storage Contract

M1 updates the schema version to `0.2.0`.

Required new tables:

- `sessions`
- `projects`
- `project_claim_links`
- `session_claim_links`
- `retrieval_log`
- `context_pack_log`

Migration requirements:

- Automatic migration path from `0.1.x` to `0.2.0`.
- `aletheia migrate --db ./aletheia.db` should be supported.
- `Memory.open("./aletheia.db", auto_migrate=True)` should be supported.
- Existing evidence remains unchanged.
- Existing claims remain unchanged.
- Existing claim-evidence links remain valid.
- Existing audit records remain valid.
- Migration is idempotent.

## Ranking Contract

M1 introduces deterministic ranking v1.

Suggested formula:

```text
score =
  0.35 lexical_score
+ 0.20 confidence_effective
+ 0.15 memory_type_priority
+ 0.10 status_priority
+ 0.10 project_relevance
+ 0.05 recency_score
+ 0.05 importance
- 0.20 conflict_penalty
- 0.10 staleness_penalty
```

Memory type priority defaults:

| Memory Type | Priority |
|---|---:|
| procedure | 0.95 |
| preference | 0.90 |
| project | 0.85 |
| identity | 0.85 |
| decision | 0.80 |
| correction | 0.80 |
| fact | 0.70 |
| session_summary | 0.65 |
| episodic | 0.55 |
| inference | 0.40 |

Status priority defaults:

| Status | Priority |
|---|---:|
| core | 1.00 |
| active | 0.80 |
| candidate | 0.30 |
| disputed | 0.10 |
| archived | 0.05 |
| superseded | 0.00 |
| rejected | excluded |

Conflict behavior:

- Rejected claims are always excluded.
- Superseded claims are excluded by default.
- Archived claims are excluded by default.
- Disputed claims are excluded from normal results by default.
- Disputed claims may appear only in warnings, disputed/debug output, or
  explicit disputed retrieval.
- Active claims in a resolved conflict family are allowed.
- Unresolved conflict claims are penalized or moved to warnings.

## Context Pack Contract

Required sections:

- `core_memory`
- `project_memory`
- `session_memory`
- `procedural_memory`
- `relevant_memory`
- `warnings`
- `omitted`

Token budget priority:

1. Warnings that materially affect response correctness.
2. Core memory.
3. Project memory.
4. Procedural memory.
5. Session continuity memory.
6. Directly relevant retrieved memory.
7. Lower-confidence supporting memory.

Warnings may render last, but they must not be dropped when they materially
affect correctness.

Omission reasons may include:

- `token_budget_exceeded`
- `low_confidence`
- `low_relevance`
- `archived`
- `disputed`
- `superseded`
- `duplicate`

## CLI Contract

M1 preserves all M0 commands:

- `aletheia init`
- `aletheia remember`
- `aletheia search`
- `aletheia context-pack`
- `aletheia feedback`
- `aletheia events`
- `aletheia claims`
- `aletheia audit`
- `aletheia conflicts`

M1 adds or improves:

- `aletheia context`
- `aletheia sessions`
- `aletheia projects`
- `aletheia migrate`

### `aletheia context`

```bash
aletheia context \
  --db ./aletheia.db \
  --namespace user/default \
  --project aletheia \
  --query "Continue designing the memory system" \
  --budget 1800
```

Default output is markdown. `--json` returns structured output.

### `aletheia sessions`

```bash
aletheia sessions start \
  --db ./aletheia.db \
  --namespace user/default \
  --project aletheia \
  --title "M1 contract design"

aletheia sessions end \
  --db ./aletheia.db \
  --session sess_001 \
  --summary "Completed M1 contract draft."

aletheia sessions list \
  --db ./aletheia.db \
  --namespace user/default

aletheia sessions show \
  --db ./aletheia.db \
  --session sess_001
```

### `aletheia projects`

```bash
aletheia projects create \
  --db ./aletheia.db \
  --namespace user/default \
  --id aletheia \
  --title "Aletheia Memory Library"

aletheia projects list \
  --db ./aletheia.db \
  --namespace user/default

aletheia projects show \
  --db ./aletheia.db \
  --namespace user/default \
  --id aletheia
```

## Test Contract

Required unit tests:

- `test_retrieve_filters_by_namespace`
- `test_retrieve_excludes_rejected`
- `test_retrieve_excludes_archived_by_default`
- `test_retrieve_excludes_disputed_by_default`
- `test_retrieve_recomputes_effective_confidence`
- `test_retrieve_ranking_is_deterministic`
- `test_context_pack_groups_memory_correctly`
- `test_context_pack_respects_token_budget`
- `test_context_pack_preserves_sources`
- `test_session_start_creates_session`
- `test_session_end_stores_summary_claim`
- `test_project_create_and_lookup`
- `test_project_claim_linking`

Required integration tests:

- `test_cross_session_context_recall`
- `test_project_context_recall`
- `test_conflict_warning_in_context_pack`
- `test_cli_context_outputs_markdown`
- `test_cli_context_outputs_json`
- `test_migration_from_m0_database`

Golden tests:

- Add golden context-pack tests.
- Section membership must be stable.
- Whitespace need not match exactly.

Live tests:

- Keep baseline M0 live scorecards passing.
- Add an M1 live scorecard for sessions, projects, context continuity,
  migration, conflict-aware context, and project/session recall.

## Acceptance Criteria

M1 is complete only when all of the following are true.

### Retrieval

- [ ] Retrieval supports namespace filtering.
- [ ] Retrieval supports memory type filtering.
- [ ] Retrieval supports status filtering.
- [ ] Retrieval supports project filtering.
- [ ] Retrieval recomputes effective confidence.
- [ ] Retrieval ranks core memories above ordinary active memories when
      relevant.
- [ ] Retrieval excludes rejected claims.
- [ ] Retrieval excludes archived claims by default.
- [ ] Retrieval excludes disputed claims by default.
- [ ] Retrieval returns provenance.

### Context Pack

- [ ] `context_pack()` returns structured `ContextPack` object.
- [ ] `ContextPack` can render to markdown.
- [ ] `ContextPack` can render to dict/JSON.
- [ ] `ContextPack` has core/project/session/procedural/relevant/warnings
      sections.
- [ ] `ContextPack` respects token budget.
- [ ] `ContextPack` includes claim IDs and evidence IDs.
- [ ] `ContextPack` labels disputed or stale memory appropriately.
- [ ] `ContextPack` is useful to an agent without extra formatting.

### Sessions

- [ ] `start_session()` creates a durable session.
- [ ] `end_session()` closes a session.
- [ ] Session summaries can be remembered as claims.
- [ ] New sessions can retrieve summaries from previous sessions.

### Projects

- [ ] `create_project()` creates durable project record.
- [ ] Claims can be linked to projects.
- [ ] `context_pack(project_id=...)` prioritizes project memories.
- [ ] Separate projects do not contaminate each other.

### CLI

- [ ] `aletheia context` works.
- [ ] `aletheia sessions start/end/list/show` works.
- [ ] `aletheia projects create/list/show` works.
- [ ] Existing M0 CLI commands still work.

### Migration

- [ ] M0 database migrates to M1.
- [ ] Migration is idempotent.
- [ ] Existing claims remain retrievable.
- [ ] Existing audit trails remain valid.

## Official M1 Demo

```bash
aletheia init --db ./aletheia.db

aletheia projects create \
  --db ./aletheia.db \
  --namespace user/default \
  --id aletheia \
  --title "Aletheia Memory Library"

aletheia remember \
  --db ./aletheia.db \
  --namespace user/default \
  --type preference \
  --subject user \
  --predicate prefers_response_style \
  --object "practical and direct"

aletheia sessions start \
  --db ./aletheia.db \
  --namespace user/default \
  --project aletheia \
  --title "M1 contract design"

aletheia remember \
  --db ./aletheia.db \
  --namespace user/default \
  --type project \
  --subject project:aletheia \
  --predicate current_milestone \
  --object "M1 Reliable Recall and Context Continuity"

aletheia context \
  --db ./aletheia.db \
  --namespace user/default \
  --project aletheia \
  --query "Continue designing Aletheia" \
  --budget 1200

aletheia sessions end \
  --db ./aletheia.db \
  --session sess_001 \
  --summary "Completed the M1 contract for reliable recall and context continuity."

aletheia context \
  --db ./aletheia.db \
  --namespace user/default \
  --project aletheia \
  --query "Where did we leave off?"
```

Expected output includes:

- User prefers practical and direct responses.
- Current project: Aletheia Memory Library.
- Current milestone: M1 Reliable Recall and Context Continuity.
- Previous session summary after a new session starts.

## Definition of Done

M1 is done when Aletheia can resume a project in a new session, retrieve the
right memories, package them into a clean context pack, preserve provenance,
respect confidence and conflict status, and expose the whole flow through both
Python and CLI.
