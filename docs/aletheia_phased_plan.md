Aletheia Memory Library — Phased Design Plan

Project North Star

Aletheia should become a local, auditable, production-grade memory substrate that any AI agent can install and use.

It should not start as a full agent framework. It should start as a memory kernel with clean APIs.

The core promise:

Aletheia lets local AI agents remember across sessions, retrieve relevant context, resolve contradiction, decay stale confidence, curate important memories, and distinguish facts from inferences.

⸻

0. Guiding Architecture

Recommended final shape

Aletheia
├── Python package
├── Local SQLite-based memory kernel
├── CLI
├── Local daemon/server
├── HTTP API
├── MCP adapter
├── Agent framework adapters
├── Background curation workers
├── Optional dashboard
└── Pluggable storage/indexing backends

Recommended build order

Phase 0  — Product definition and constraints
Phase 1  — Package skeleton and local memory kernel
Phase 2  — Evidence ledger
Phase 3  — Claim store
Phase 4  — Manual memory write/read API
Phase 5  — Indexing and retrieval
Phase 6  — Context pack builder
Phase 7  — Confidence and half-life decay
Phase 8  — Contradiction detection and resolution
Phase 9  — Curation and promotion lifecycle
Phase 10 — Persistence across sessions and projects
Phase 11 — Inference engines
Phase 12 — Self-learning feedback loops
Phase 13 — Local daemon and HTTP API
Phase 14 — MCP and agent adapters
Phase 15 — CLI, dashboard, and observability
Phase 16 — Production hardening

For the concrete M0 / MVP release boundary, tooling choices, CLI scope,
extraction policy, and storage decision, treat docs/m0_MVP_contract.md as the
implementation contract.

For M1 / v0.2.0 Reliable Recall and Context Continuity, treat
docs/m1_reliable_recall_contract.md as the implementation contract.

For M2 / v0.3.0 Memory Integrity, Confidence, and Conflict Resolution, treat
docs/m2_memory_integrity_contract.md as the implementation contract.

For M3 / v0.4.0 Intelligent Ingestion and Semantic Recall, treat
docs/m3_Intelligent_Ingestion_Semantic_Recall_contract.md as the implementation
contract.

For M4 / v0.5.0 Reasoned Memory, Inference, and Lossless Abstraction, treat
docs/m4_reasoned_memory_contract.md as the implementation contract.

For M5 / v0.6.0 Adaptive Memory, Evaluation, and Self-Improvement, treat
docs/m5_adaptive_memory_contract.md as the implementation contract.

For M6 / v0.7.0 Agent Interoperability, Local Service, and Secure Protocol
Layer, treat docs/m6_memory_service_contract.md as the implementation contract.

For M7 / v0.8.0 Operational Console, Observability, and Human Governance,
treat docs/m7_observability_contract.md as the implementation contract.

For M8 / v0.9.0 Production Hardening, Backup/Restore, Encryption, and
Release Readiness, treat docs/m8_production_hardening_contract.md as the
implementation contract.

For M9 / v1.0.0 Stable Platform, Public Contracts, Plugin Ecosystem, and
v1 Gate, treat docs/m9_stable_platform_contract.md as the implementation
contract.

For M10 / v1.1.0 Federated Memory, Multi-Agent Governance, and Secure Sync,
treat docs/m10_federated_memory_contract.md as the implementation contract.

⸻

Phase 0 — Product Definition and Constraints

Goal

Define what Aletheia is, what it is not, and what guarantees it must provide.

Core decision

Aletheia should be:

A local-first memory library and service for AI agents.

It should not be:

A full agent framework.
A chatbot.
A vector database wrapper.
A cloud-only memory service.
A fine-tuning platform.

Key design constraints

Constraint	Design consequence
Local-first	Default storage should work on one machine
Agent-agnostic	Provide SDK, HTTP API, and adapters
Auditable	Every memory must link back to evidence
Safe	Distinguish evidence, claims, and inference
Correctable	User corrections must supersede weaker claims
Persistent	Memory must survive across sessions
Inspectable	CLI and later dashboard are essential
Extensible	Storage, vector DB, models, and adapters should be pluggable

Deliverables

docs/
├── vision.md
├── architecture.md
├── memory_model.md
├── api_principles.md
├── security_principles.md
└── roadmap.md

Exit criteria

This phase is complete when you can clearly answer:

What does Aletheia store?
What does it refuse to store?
How does it know where a memory came from?
How does it resolve stale or conflicting memories?
How can any local agent use it?

⸻

Phase 1 — Package Skeleton and Local Memory Kernel

Goal

Create the installable package and the basic internal structure.

Recommended package name

aletheia-memory

Recommended import name

import aletheia

Initial package structure

aletheia/
├── __init__.py
├── core/
│   ├── memory.py
│   ├── config.py
│   ├── ids.py
│   ├── time.py
│   └── errors.py
├── storage/
│   ├── sqlite.py
│   ├── migrations/
│   └── schema.sql
├── models/
│   ├── evidence.py
│   ├── claim.py
│   ├── context.py
│   ├── feedback.py
│   └── conflict.py
├── retrieval/
│   ├── lexical.py
│   ├── ranking.py
│   └── filters.py
├── curation/
│   ├── extraction.py
│   ├── promotion.py
│   ├── contradiction.py
│   └── decay.py
├── cli/
│   └── main.py
└── tests/

First public API

from aletheia import Memory
memory = Memory.open("./aletheia.db")

Minimal configuration

memory = Memory.open(
    path="./aletheia.db",
    namespace="user/default",
    config={
        "local_first": True,
        "audit_enabled": True,
        "default_confidence": 0.75,
    }
)

Deliverables

- Installable Python package
- SQLite database initialization
- Config loader
- Basic namespace support
- Basic error handling
- Unit test structure

Exit criteria

This phase is complete when this works:

from aletheia import Memory
memory = Memory.open("./aletheia.db")
memory.health()

Expected result:

{
    "status": "ok",
    "database": "connected",
    "schema_version": "0.1.0"
}

⸻

Phase 2 — Evidence Ledger

Goal

Build the immutable source-of-truth layer.

This is the foundation. Do not let memories exist without evidence.

Core concept

An evidence event is any raw input or observation from which memories may later be extracted.

Examples:

User message
Assistant message
Tool output
File contents
API response
User correction
Task result
System note
Imported document

Evidence event schema

class EvidenceEvent:
    id: str
    namespace: str
    session_id: str | None
    source_type: str
    source_uri: str | None
    content: str
    content_hash: str
    created_at: str
    observed_at: str
    trust_level: str
    privacy_level: str
    retention_policy: str

SQLite table

CREATE TABLE evidence_events (
    id TEXT PRIMARY KEY,
    namespace TEXT NOT NULL,
    session_id TEXT,
    source_type TEXT NOT NULL,
    source_uri TEXT,
    content TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    created_at TEXT NOT NULL,
    observed_at TEXT,
    trust_level TEXT DEFAULT 'unknown',
    privacy_level TEXT DEFAULT 'personal',
    retention_policy TEXT DEFAULT 'default'
);

API

event = memory.write_event(
    namespace="user/default",
    source_type="user_message",
    content="I prefer practical, direct answers.",
    trust_level="user_asserted",
)

Important rules

Evidence is append-only.
Evidence has a content hash.
Evidence can be redacted or tombstoned.
Derived claims must link back to evidence.
Deleting evidence must invalidate derived claims.

Deliverables

- Evidence event model
- Evidence table
- write_event()
- read_event()
- list_events()
- content hashing
- audit entry for every event write

Tests

- Can write evidence
- Can retrieve evidence
- Duplicate hashes are detected
- Evidence IDs are stable
- Evidence cannot be silently overwritten

Exit criteria

This phase is complete when this works:

event = memory.write_event(
    namespace="user/default",
    source_type="user_message",
    content="I prefer practical, direct answers."
)
loaded = memory.read_event(event.id)
assert loaded.content == "I prefer practical, direct answers."

⸻

Phase 3 — Claim Store

Goal

Create the structured memory layer.

Evidence says:

The user said something.

A claim says:

This is what the system thinks the evidence means.

Claim schema

class Claim:
    id: str
    namespace: str
    subject: str
    predicate: str
    object: str
    memory_type: str
    status: str
    confidence_base: float
    confidence_effective: float
    half_life_days: float
    importance: float
    volatility: str
    evidence_ids: list[str]
    created_at: str
    last_verified_at: str | None
    valid_from: str | None
    valid_to: str | None

Example claim

Claim(
    subject="user",
    predicate="prefers_response_style",
    object="practical and direct",
    memory_type="preference",
    status="active",
    confidence_base=0.88,
    half_life_days=180,
    evidence_ids=["evt_001"],
)

SQLite table

CREATE TABLE claims (
    id TEXT PRIMARY KEY,
    namespace TEXT NOT NULL,
    subject TEXT NOT NULL,
    predicate TEXT NOT NULL,
    object TEXT NOT NULL,
    memory_type TEXT NOT NULL,
    status TEXT NOT NULL,
    confidence_base REAL NOT NULL,
    confidence_effective REAL NOT NULL,
    half_life_days REAL NOT NULL,
    importance REAL DEFAULT 0.5,
    volatility TEXT DEFAULT 'medium',
    created_at TEXT NOT NULL,
    last_verified_at TEXT,
    valid_from TEXT,
    valid_to TEXT
);

Claim-evidence link table

CREATE TABLE claim_evidence_links (
    claim_id TEXT NOT NULL,
    evidence_id TEXT NOT NULL,
    PRIMARY KEY (claim_id, evidence_id)
);

API

claim = memory.write_claim(
    namespace="user/default",
    subject="user",
    predicate="prefers_response_style",
    object="practical and direct",
    memory_type="preference",
    evidence_ids=[event.id],
    confidence=0.88,
)

Claim statuses

candidate
active
core
disputed
superseded
rejected
archived

Deliverables

- Claim model
- Claim storage
- Claim-evidence linking
- Basic confidence field
- Claim status lifecycle
- Claim audit trail

Exit criteria

This phase is complete when a claim can be created, retrieved, audited, and traced back to its evidence.

⸻

Phase 4 — Manual Memory Write/Read API

Goal

Make the system useful before introducing automatic extraction.

At this point, the user or agent can manually write memories.

API design

memory.remember(
    text="The user prefers practical, direct answers.",
    namespace="user/default",
    memory_type="preference",
    source="user_message",
)

Internally, this should:

1. Write evidence event.
2. Create claim.
3. Link claim to evidence.
4. Assign initial confidence.
5. Mark status as active or candidate.
6. Write audit event.

Convenience API

memory.remember_fact(...)
memory.remember_preference(...)
memory.remember_procedure(...)
memory.remember_project_state(...)
memory.remember_correction(...)

Example

memory.remember_preference(
    namespace="user/default",
    subject="user",
    preference="prefers practical, direct answers",
    confidence=0.9,
)

Deliverables

- remember()
- remember_fact()
- remember_preference()
- remember_procedure()
- resolve_claim()
- audit_claim()

Tests

- Manual memory write creates evidence
- Manual memory write creates claim
- Claim links to evidence
- Audit trail is created
- Memory can be resolved by subject/predicate

Exit criteria

This phase is complete when this works:

memory.remember(
    namespace="user/default",
    text="The user prefers practical, direct answers.",
    memory_type="preference",
)
claim = memory.resolve_claim(
    namespace="user/default",
    subject="user",
    predicate="prefers_response_style",
)

⸻

Phase 5 — Indexing and Retrieval

Goal

Retrieve relevant memories using more than one signal.

Do not start with vector search alone. Start with lexical search and metadata filtering. Add embeddings after the retrieval interface is stable.

Indexing layers

1. Metadata index
2. Full-text index
3. Entity/predicate index
4. Temporal index
5. Optional vector index
6. Later graph index

Initial retrieval API

results = memory.retrieve(
    namespace="user/default",
    query="How should I respond to this user?",
    limit=10,
)

Retrieval result

class RetrievalResult:
    claim_id: str
    text: str
    memory_type: str
    status: str
    score: float
    confidence_effective: float
    evidence_ids: list[str]

Ranking formula, first version

score =
  lexical_score
  + confidence_effective
  + importance
  + recency_bonus
  - conflict_penalty

Later hybrid ranking

score =
  0.30 lexical_score
+ 0.25 semantic_similarity
+ 0.15 confidence_effective
+ 0.10 importance
+ 0.10 recency
+ 0.05 memory_type_priority
+ 0.05 user_confirmation
- 0.20 unresolved_conflict_penalty

Categories

Start with these base categories:

identity
preference
project
task
procedure
domain_knowledge
tool_usage
file_knowledge
decision
mistake
constraint
safety
privacy
schedule
location
communication_style
inference
correction

Deliverables

- Searchable claim text
- Metadata filters
- FTS search
- Ranking function
- retrieve()
- retrieve_by_entity()
- retrieve_by_type()
- retrieve_recent()

Tests

- Exact terms retrieve the right claim
- Preferences are retrievable by related query
- Archived claims are excluded by default
- Disputed claims are penalized
- Namespace filters work

Exit criteria

This phase is complete when Aletheia can retrieve useful memories from a different session than the one in which they were written.

⸻

Phase 6 — Context Pack Builder

Goal

Return agent-ready memory, not raw database rows.

This is one of the most important phases.

A normal retrieval result says:

Here are ten memories.

A context pack says:

Here is the usable context the agent should carry into reasoning.

Context pack structure

class ContextPack:
    core_memory: list[str]
    relevant_memory: list[str]
    project_memory: list[str]
    procedural_memory: list[str]
    warnings: list[str]
    disputed_memory: list[str]
    sources: list[str]

Example output

## Memory Context
### Core Memory
- User prefers practical, direct answers.
### Relevant Memory
- Current project: designing Aletheia, a local AI agent memory library.
### Procedural Memory
- For architecture/design requests, provide implementation-level structure and tradeoffs.
### Warnings
- Do not treat inferred memories as confirmed facts.

API

context = memory.context_pack(
    namespace="user/default",
    query="Write a design plan for each phase.",
    token_budget=1500,
)

Token budget behavior

The context packer should prioritize:

1. Core memory
2. Directly relevant project memory
3. Procedural memory
4. Recent session memory
5. High-confidence semantic memory
6. Inferences, only if useful and clearly labeled
7. Disputed memories, only as warnings

Deliverables

- ContextPack model
- context_pack()
- Token budget estimator
- Memory prioritization
- Grouped output
- Conflict warning section

Tests

- Core memory appears first
- Low-confidence memories can be omitted
- Disputed claims are labeled
- Token budget is respected
- Context pack is stable and readable

Exit criteria

This phase is complete when a local agent can call context_pack() at the beginning of a new session and receive useful context.

⸻

Phase 7 — Confidence and Half-Life Decay

Goal

Prevent stale memories from having permanent authority.

Core principle

Track two separate concepts:

Truth confidence:
How likely is this claim to be true?
Retrieval salience:
How useful is this claim right now?

Basic decay formula

effective_confidence = base_confidence * 2 ** (-age_days / half_life_days)

Claim fields

confidence_base: float
confidence_effective: float
half_life_days: float
volatility: str
last_verified_at: datetime | None
last_accessed_at: datetime | None

Default half-lives

Memory type	Suggested half-life
Current task state	3 days
Temporary preference	14 days
Project state	30 days
User preference	180 days
User identity/profile	1000 days
Domain knowledge	1000 days
Tool behavior	90 days
Inference-only memory	14 days
User correction	1000 days

API

memory.recompute_confidence(namespace="user/default")
memory.feedback(
    claim_id="clm_001",
    signal="confirmed",
)

Feedback effects

Signal	Effect
confirmed	Raise confidence, reset decay clock
contradicted	Lower confidence, create conflict
wrong	Mark disputed or rejected
useful	Raise salience, not necessarily truth
stale	Lower salience and maybe confidence
verified	Raise confidence strongly

Important rule

The agent repeating a memory does not count as confirmation.

Deliverables

- Decay calculator
- Effective confidence computation
- Feedback model
- Confidence audit history
- Default half-life policy

Tests

- Old volatile memory decays quickly
- Stable identity memory decays slowly
- Confirmation resets confidence clock
- Useful feedback affects salience more than truth
- Wrong feedback demotes claim

Exit criteria

This phase is complete when old project memories naturally lose priority while durable user preferences remain available.

⸻

Phase 8 — Contradiction Detection and Resolution

Goal

Detect and resolve contradictions instead of silently overwriting memories.

Core principle

Aletheia should not merely delete contradiction. It should classify it.

Possible outcomes:

superseded
time-scoped
context-scoped
disputed
rejected
merged

Conflict example

Claim A:
User prefers concise answers.
Claim B:
User prefers comprehensive design explanations.

Correct resolution:

No hard contradiction.
Context-scoped preference:
- Concise for progress updates.
- Comprehensive for design and architecture.

Conflict table

CREATE TABLE conflicts (
    id TEXT PRIMARY KEY,
    namespace TEXT NOT NULL,
    subject TEXT NOT NULL,
    predicate TEXT NOT NULL,
    status TEXT NOT NULL,
    active_claim_id TEXT,
    resolution_note TEXT,
    created_at TEXT NOT NULL,
    resolved_at TEXT
);

Conflict-claim link table

CREATE TABLE conflict_claim_links (
    conflict_id TEXT NOT NULL,
    claim_id TEXT NOT NULL,
    PRIMARY KEY (conflict_id, claim_id)
);

First contradiction detector

Start simple:

same namespace
same subject
same predicate
different object
both active
not time-scoped
not context-scoped

Later contradiction detectors

Semantic contradiction detector
Natural language inference model
Temporal conflict detector
Preference conflict detector
Entity conflict detector
Tool-verified fact checker

API

conflicts = memory.detect_conflicts(namespace="user/default")
memory.resolve_conflict(
    conflict_id="conf_001",
    strategy="context_scope",
    active_claims=["clm_001", "clm_002"],
    note="Concise for updates; detailed for technical design.",
)

Resolution policies

Conflict type	Policy
User correction vs model inference	User correction wins
User correction vs old user statement	Newer correction wins
Tool-verified vs model-generated	Tool-verified wins
Old project status vs new project status	New supersedes old
Preference conflict	Scope by context
Location/status conflict	Scope by time
Weak inference vs direct evidence	Direct evidence wins

Deliverables

- Conflict model
- Conflict detection
- Conflict resolution
- Claim supersession
- Context scoping
- Temporal scoping
- Conflict audit trail

Tests

- Direct contradiction creates conflict
- New correction supersedes old claim
- Time-scoped memories do not falsely conflict
- Context-scoped preferences can coexist
- Disputed claims are penalized in retrieval

Exit criteria

This phase is complete when Aletheia can handle contradictory user preferences without becoming confused or overwriting history.

⸻

Phase 9 — Curation and Promotion Lifecycle

Goal

Move memories through a controlled lifecycle.

Memory lifecycle

observed
  → candidate
  → active
  → core
  → reflected
  → archived
or
observed
  → candidate
  → rejected
or
active
  → disputed
  → superseded

Status definitions

Status	Meaning
candidate	Extracted but not trusted enough
active	Usable by retrieval
core	High-priority durable memory
reflected	Included in higher abstraction
disputed	In conflict
superseded	Replaced by newer/better claim
rejected	Not worth storing
archived	Kept but not normally retrieved

Promotion criteria

A claim may be promoted when it has:

Clear evidence
High confidence
High future usefulness
Low contradiction risk
Known scope
Known half-life
Appropriate privacy label
Repeated confirmation or explicit importance

API

memory.promote_claim(
    claim_id="clm_001",
    target_status="core",
    reason="Stable user communication preference.",
)
memory.demote_claim(
    claim_id="clm_001",
    target_status="archived",
    reason="Stale project state.",
)

Curator worker

Curator responsibilities:
- Promote high-value claims
- Demote stale claims
- Archive low-salience memories
- Surface unresolved conflicts
- Identify duplicate memories
- Identify candidates needing confirmation

Deliverables

- Promotion policy
- Demotion policy
- Candidate queue
- Core memory support
- Duplicate detection
- Curator job

Tests

- High-confidence preference can become core
- Stale project state is demoted
- Disputed memory cannot become core
- Duplicate memories are merged or linked
- Promotion is recorded in audit log

Exit criteria

This phase is complete when Aletheia can separate ordinary memories from durable, high-value core memories.

⸻

Phase 10 — Persistence Across Sessions and Projects

Goal

Make memory useful across conversations, projects, agents, and time.

Namespace structure

/user/{user_id}
/user/{user_id}/profile
/user/{user_id}/projects/{project_id}
/agent/{agent_id}/procedures
/org/{org_id}/shared
/sessions/{session_id}
/files/{file_id}

Session start behavior

At the beginning of a session:

1. Load user core memory.
2. Load agent procedural memory.
3. Detect active project.
4. Retrieve recent project state.
5. Retrieve relevant long-term memories.
6. Build context pack.

Session end behavior

At the end of a session:

1. Write session summary evidence.
2. Extract candidate memories.
3. Update project state.
4. Store decisions.
5. Store corrections.
6. Queue curation jobs.

Project memory

Project memory should include:

Project name
Project goal
Current phase
Open decisions
Resolved decisions
Constraints
Important files
Recent progress
Outstanding questions
Known mistakes

API

memory.start_session(
    user_id="default",
    agent_id="local_agent",
    project_id="aletheia",
)
memory.end_session(
    session_id="sess_001",
    summary="Designed phase plan for Aletheia Memory Library.",
)

Deliverables

- Session model
- Project model
- Namespace hierarchy
- Project state claims
- Session summary support
- Cross-session context loading

Tests

- New session retrieves old core memory
- Project state persists
- Separate projects do not contaminate each other
- Agent-specific procedures are isolated
- User-level memory is shared only when allowed

Exit criteria

This phase is complete when an agent can resume a project days later and accurately recover the relevant context.

⸻

Phase 11 — Inference Engines

Goal

Add controlled inference without confusing inference with fact.

Aletheia should support three inference types:

Logical inference
Semantic inference
Factual inference

⸻

11.1 Logical inference

Purpose

Use explicit rules over structured claims.

Example

If claim A supersedes claim B,
then claim B should not be treated as current.

Initial implementation

Start with simple rule functions:

def infer_current_claim(claims):
    ...

Later, use a small rule engine.

Use cases

Supersession
Temporal validity
Access control
Project dependency
Contradiction propagation
Procedure selection

⸻

11.2 Semantic inference

Purpose

Use meaning similarity to improve retrieval, clustering, categorization, and duplicate detection.

Example

"seismic inversion"
"rock physics"
"reservoir characterization"

These are semantically related, but semantic relation is not the same as factual truth.

Rule

Semantic inference should usually produce retrieval hints, not factual claims.

⸻

11.3 Factual inference

Purpose

Extract or derive factual claims from evidence.

Example

Evidence:

"I am flying to Oslo on Thursday for the workshop."

Possible factual claims:

User has travel destination: Oslo.
User has event: workshop.

Speculative claim:

User may be unavailable during travel.

That last one should be marked as inference-only unless confirmed.

Inference claim fields

derived_from_claims: list[str]
inference_type: str
inference_rule: str
inference_confidence: float
is_confirmed: bool

Deliverables

- Inference model
- Logical rule engine v1
- Semantic relationship index
- Factual extraction pipeline
- Inference labeling
- Inference confidence policy

Tests

- Inferred claims link to source claims
- Inferences are labeled clearly
- Weak inferences decay faster
- Contradicted inferences are rejected
- Semantic similarity does not create fake facts

Exit criteria

This phase is complete when Aletheia can infer useful context while clearly distinguishing known facts from inferred possibilities.

⸻

Phase 12 — Self-Learning Feedback Loops

Goal

Allow Aletheia to improve over time without corrupting memory.

Learning sources

User corrections
Explicit confirmations
Task outcomes
Tool verification
Repeated independent evidence
Retrieval usefulness feedback
Conflict resolutions
Evaluation results

What can self-improve

Allowed:

Retrieval ranking weights
Promotion thresholds
Half-life defaults
Categorization rules
Context pack formatting
Procedure memories
Duplicate detection thresholds

Restricted:

User-confirmed facts
Privacy policy
Audit logs
Evidence ledger
Safety constraints
Deletion behavior

Feedback API

memory.feedback(
    target_id="clm_001",
    signal="confirmed",
    note="User explicitly confirmed this preference.",
)

Possible signals:

confirmed
wrong
stale
useful
not_useful
contradicted
verified
irrelevant

Procedural memory learning

Example:

Observed:
The user asks for design plans and values practical structure.
Learned procedure:
For architecture requests, provide phased implementation plans with deliverables, tests, and exit criteria.

Evaluation gate

Before updating procedural memory:

1. Generate proposed procedure change.
2. Compare against old procedure.
3. Run local regression tests.
4. Check for privacy/safety regression.
5. Promote or reject.
6. Store diff in audit log.

Deliverables

- Feedback store
- Feedback-to-confidence updates
- Feedback-to-ranking updates
- Procedure memory model
- Procedure optimizer
- Evaluation harness

Tests

- Confirmed memories gain confidence
- Wrong memories are demoted
- Useful memories gain salience
- Procedural changes are auditable
- Self-repetition does not reinforce truth

Exit criteria

This phase is complete when Aletheia improves retrieval and procedures from real feedback while preserving auditability.

⸻

Phase 13 — Local Daemon and HTTP API

Goal

Make Aletheia usable by any local agent, regardless of programming language.

Command

aletheia serve --db ./aletheia.db --host 127.0.0.1 --port 8765

HTTP endpoints

GET  /health
POST /events
POST /claims
POST /remember
POST /retrieve
POST /context-pack
POST /feedback
GET  /claims/{claim_id}
GET  /events/{event_id}
GET  /audit/{id}
GET  /conflicts
POST /conflicts/{conflict_id}/resolve

Example request

POST /context-pack
Content-Type: application/json
{
  "namespace": "user/default",
  "query": "Write a design plan for each phase.",
  "token_budget": 2000
}

Example response

{
  "core_memory": [
    "User prefers practical, direct answers."
  ],
  "project_memory": [
    "Current project: Aletheia Memory Library."
  ],
  "procedural_memory": [
    "For architecture requests, provide phased plans with deliverables and exit criteria."
  ],
  "warnings": []
}

Deliverables

- Local server
- HTTP API
- Request validation
- API authentication token
- JSON schemas
- Error responses
- OpenAPI spec

Tests

- Server starts locally
- Agent can write memory over HTTP
- Agent can retrieve context over HTTP
- API rejects invalid payloads
- Namespace isolation works

Exit criteria

This phase is complete when a non-Python agent can use Aletheia through HTTP.

⸻

Phase 14 — MCP and Agent Adapters

Goal

Make Aletheia easy to connect to existing agent ecosystems.

MCP tools

Expose memory operations as tools:

memory_search
memory_remember
memory_resolve
memory_context_pack
memory_feedback
memory_audit

Tool: memory_search

{
  "name": "memory_search",
  "description": "Search Aletheia memory for relevant claims.",
  "input": {
    "namespace": "string",
    "query": "string",
    "limit": "integer"
  }
}

Tool: memory_context_pack

{
  "name": "memory_context_pack",
  "description": "Build an agent-ready memory context pack.",
  "input": {
    "namespace": "string",
    "query": "string",
    "token_budget": "integer"
  }
}

Agent adapters

Recommended adapters:

LangGraph adapter
LlamaIndex adapter
CrewAI adapter
AutoGen adapter
OpenAI-compatible tool adapter
Ollama/local model adapter
Generic HTTP adapter

Adapter principle

Adapters should be thin.

They should not duplicate memory logic.

Agent framework
  → adapter
  → Aletheia API
  → Memory kernel

Deliverables

- MCP server
- MCP tool schemas
- Python agent adapter
- Generic HTTP adapter
- Example integrations
- Documentation

Tests

- MCP client can search memory
- MCP client can write memory
- Agent can receive context pack
- Adapter does not bypass audit rules
- Adapter respects namespace permissions

Exit criteria

This phase is complete when multiple local agents can connect to Aletheia without custom internal integration.

⸻

Phase 15 — CLI, Dashboard, and Observability

Goal

Make the memory system inspectable and trustworthy.

A memory system that cannot be inspected will eventually become dangerous or useless.

CLI commands

aletheia init
aletheia serve
aletheia remember "User prefers practical answers"
aletheia search "communication preference"
aletheia claims list
aletheia claims show clm_001
aletheia audit clm_001
aletheia conflicts list
aletheia conflicts resolve conf_001
aletheia decay run
aletheia curate run
aletheia export
aletheia import

Dashboard views

Memory browser
Evidence browser
Claim detail view
Conflict view
Core memory view
Project memory view
Decay/confidence view
Audit log
Feedback history
Namespace permissions

Observability metrics

Number of claims
Number of evidence events
Number of active conflicts
Retrieval latency
Context pack latency
Average confidence
Number of stale memories
Number of core memories
Feedback count
Promotion/demotion count

Deliverables

- CLI
- Local dashboard
- Audit viewer
- Conflict viewer
- Memory search UI
- Export/import tools
- Metrics logging

Tests

- CLI commands work
- Dashboard shows correct claim state
- Audit trail is readable
- Export/import preserves links
- Deleted/tombstoned evidence is handled correctly

Exit criteria

This phase is complete when a user can inspect, correct, export, and understand Aletheia’s memory state without writing code.

⸻

Phase 16 — Production Hardening

Goal

Make Aletheia reliable enough for serious local use.

Security requirements

Encryption at rest
Access control by namespace
Local API token
Audit logs
Redaction
Tombstones
Backup and restore
No telemetry by default
Sensitive memory classification
Prompt-injection-aware import handling

Reliability requirements

Schema migrations
Database backups
Crash-safe writes
Idempotent event ingestion
Corruption checks
Retryable background jobs
Versioned APIs
Deterministic tests

Performance requirements

Fast context pack generation
Efficient indexing
Batch writes
Lazy embedding generation
Background curation queue
Configurable memory limits
Archival of low-value memories

Privacy requirements

User-controlled deletion
Derived-memory invalidation
Namespace isolation
Sensitive field redaction
Exportable memory archive
No external calls unless configured

Packaging

pip install aletheia-memory

Optional extras:

pip install "aletheia-memory[server]"
pip install "aletheia-memory[mcp]"
pip install "aletheia-memory[qdrant]"
pip install "aletheia-memory[dashboard]"

Deliverables

- Stable package release
- Semantic versioning
- Migration system
- Backup/restore
- Encryption support
- Permission model
- Performance benchmarks
- Documentation site
- Example local agents

Tests

- Database migration tests
- Crash recovery tests
- Conflict resolution tests
- Retrieval quality tests
- Privacy propagation tests
- Deletion invalidation tests
- API compatibility tests
- Load tests

Exit criteria

This phase is complete when Aletheia can be trusted as a durable local memory layer for real agents and real projects.

⸻

Version Roadmap

Version 0.1 — Memory Kernel

- SQLite database
- Evidence ledger
- Claim store
- Manual remember/search API
- Basic CLI
- Basic audit trail

Version 0.2 — Retrieval and Context

- Full-text retrieval
- Metadata filters
- Context pack builder
- Memory categories
- Namespace support

Version 0.3 — Confidence and Contradiction

- Confidence model
- Half-life decay
- Conflict detection
- Supersession
- Disputed memory handling

Version 0.4 — Curation

- Candidate memories
- Promotion/demotion
- Core memory
- Duplicate detection
- Background curator

Version 0.5 — Session Persistence

- Session model
- Project memory
- Cross-session recall
- Session summaries

Version 0.6 — Inference

- Logical inference v1
- Semantic inference hints
- Factual inference labels
- Inference confidence

Version 0.7 — Self-Learning

- Feedback loops
- Procedure memory
- Retrieval ranking adaptation
- Evaluation gate

Version 0.8 — Service Layer

- Local daemon
- HTTP API
- OpenAPI schema
- Auth token

Version 0.9 — Integrations

- MCP server
- LangGraph adapter
- LlamaIndex adapter
- Generic agent adapter
- Example agents

Version 1.0 — Production Local Release

- Encryption
- Backup/restore
- Migration stability
- Dashboard
- Strong audit tools
- Documentation
- Production test suite

⸻

Recommended MVP Scope

The first real build should be small and serious.

The detailed M0 MVP boundary is formalized in docs/m0_MVP_contract.md.

MVP should include

pyproject.toml with Hatchling
uv development workflow
pytest tests
SQLite database
SQLite FTS5
Evidence events
Claims
Manual/schema-driven remember()
retrieve()
Context pack
Basic confidence
Basic half-life decay
Basic contradiction detection
CLI

MVP should not include yet

LLM extraction
Autonomous self-learning
Complex graph reasoning
Vector database
Graph database
Full dashboard
Daemon
MCP server
Agent framework adapters
Cloud sync
Fine-tuning
Multi-user enterprise permissions
Advanced ontology
Complex LLM-based curation

MVP demo

The first demo should show this:

1. User tells an agent a stable preference.
2. Aletheia stores it as evidence.
3. Aletheia creates a claim.
4. A new session starts.
5. Agent retrieves the preference.
6. User corrects the memory.
7. Aletheia supersedes the old claim.
8. Audit trail shows what happened.

That demo proves the soul of the system.

⸻

First Concrete Build Checklist

Repository setup

[ ] Create repo: aletheia-memory
[ ] Add Python package structure
[ ] Add pyproject.toml with Hatchling build backend
[ ] Add uv development workflow and uv.lock
[ ] Add pytest test framework
[ ] Add CLI entrypoint
[ ] Add documentation folder

Database

[ ] Create schema version table
[ ] Create evidence_events table
[ ] Create claims table
[ ] Create claim_evidence_links table
[ ] Create audit_log table
[ ] Create conflicts table
[ ] Create conflict_claim_links table
[ ] Create feedback table
[ ] Create claims_fts table

Core API

[ ] Memory.open()
[ ] memory.write_event()
[ ] memory.write_claim()
[ ] memory.remember()
[ ] memory.retrieve()
[ ] memory.context_pack()
[ ] memory.audit()
[ ] memory.feedback()

Retrieval

[ ] Full-text index
[ ] Metadata filters
[ ] Ranking function
[ ] Exclude archived/rejected memories by default
[ ] Penalize disputed memories

Confidence

[ ] Base confidence
[ ] Effective confidence
[ ] Half-life policy
[ ] Decay computation
[ ] Feedback updates

Contradiction

[ ] Same subject/predicate conflict detection
[ ] Conflict object creation
[ ] Supersede old claim
[ ] Mark disputed claim
[ ] Conflict audit trail

CLI

[ ] aletheia init
[ ] aletheia remember
[ ] aletheia search
[ ] aletheia context-pack
[ ] aletheia feedback
[ ] aletheia events
[ ] aletheia claims
[ ] aletheia audit
[ ] aletheia conflicts

⸻

The Best Starting Point

Start with this single file as the conceptual center:

aletheia/core/memory.py

It should expose:

class Memory:
    @classmethod
    def open(cls, path: str) -> "Memory":
        ...
    def write_event(self, ...):
        ...
    def write_claim(self, ...):
        ...
    def remember(self, ...):
        ...
    def retrieve(self, ...):
        ...
    def context_pack(self, ...):
        ...
    def feedback(self, ...):
        ...
    def audit(self, ...):
        ...

Everything else should serve this class.

The cleanest first milestone is not “build an intelligent memory.” It is:

Build a local memory kernel that can remember, retrieve, audit, decay, and correct one fact reliably.

Once that works, the rest of Aletheia can grow without becoming fragile.
