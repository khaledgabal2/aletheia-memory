Aletheia M2 Contract

Milestone: Memory Integrity, Confidence, Contradiction, and Curation

⸻

1. Milestone Summary

M0 proved that Aletheia can remember.
M1 proved that Aletheia can recall useful context across sessions and projects.
M2 must prove that Aletheia can maintain memory integrity over time.

M2 is the milestone where Aletheia stops being merely a local memory store and becomes a truth-maintenance system.

The core M2 promise:

Aletheia can evaluate memory confidence, decay stale claims, detect contradiction, resolve conflicts, promote durable memories, demote weak memories, and preserve a complete audit trail of why each memory is trusted, disputed, superseded, or forgotten.

M2 is not about adding LLM intelligence yet. It is about discipline.

M0 = Remember
M1 = Recall
M2 = Trust

⸻

2. M2 Name

M2 — Memory Integrity

Fuller name:

M2 — Memory Integrity, Confidence, Contradiction, and Curation

I recommend using the fuller name in the contract and Memory Integrity as the short milestone name.

⸻

3. M2 Contract Status

milestone: M2
name: Memory Integrity
depends_on: M1
version_target: 0.3.0
stability: internal-beta-plus
breaking_changes_allowed: limited
storage_migration_required: yes
llm_required: no
vector_backend_required: no
daemon_required: no
dashboard_required: no
background_worker_required: optional
primary_theme: truth_maintenance

⸻

4. M1 Assumptions

M2 assumes M1 already provides:

- SQLite database
- Evidence ledger
- Claim store
- Claim-evidence links
- Manual/schema-driven remember()
- Basic confidence fields
- Basic half-life decay
- Basic contradiction detection
- Audit trail
- FTS5 retrieval
- RetrievalResult model
- ContextPack model
- Session model
- Project model
- Cross-session recall
- Conflict-aware retrieval
- CLI commands:
  - init
  - remember
  - search
  - context
  - claims
  - audit
  - conflicts
  - sessions
  - projects

M2 should not replace M1 retrieval. It should improve the quality and trustworthiness of the memories being retrieved.

⸻

5. M2 Primary Objective

M2 must make this flow work reliably:

claim_a = memory.remember(
    namespace="user/default",
    memory_type="preference",
    subject="user",
    predicate="prefers_response_style",
    object="concise progress updates",
    confidence=0.85,
)
claim_b = memory.remember(
    namespace="user/default",
    memory_type="preference",
    subject="user",
    predicate="prefers_response_style",
    object="comprehensive architecture explanations",
    confidence=0.88,
)
conflicts = memory.detect_conflicts(namespace="user/default")
resolution = memory.resolve_conflict(
    conflict_id=conflicts[0].id,
    strategy="context_scope",
    note="Concise for progress updates; comprehensive for architecture/design work.",
)
memory.promote_claim(
    claim_id=claim_b.id,
    target_status="core",
    reason="Stable preference for design work."
)
context = memory.context_pack(
    namespace="user/default",
    query="Write an architecture contract.",
    project_id="aletheia",
)

Expected behavior:

- Both claims are preserved.
- The apparent contradiction is not silently overwritten.
- A conflict family is created.
- The conflict is resolved through context scoping.
- Retrieval understands which preference applies.
- The context pack does not present disputed memory as fact.
- Promotion is auditable.

⸻

6. M2 Non-Negotiable Principles

6.1 Evidence remains immutable

M2 must not mutate raw evidence.

Claims can be superseded, rejected, promoted, demoted, archived, or scoped. Evidence remains intact unless explicitly redacted or deleted through a formal deletion policy.

⸻

6.2 Contradiction is not deletion

M2 must not “remove contradiction” by erasing inconvenient memories.

It must classify contradiction as one of:

unresolved
resolved
superseded
time_scoped
context_scoped
duplicate
merged
rejected

⸻

6.3 User correction is stronger than model memory

If a user explicitly corrects a memory, that correction must outrank:

model-generated memory
old inferred memory
old weak evidence
retrieval repetition
assistant repetition

⸻

6.4 Truth confidence and retrieval salience are separate

M2 must formally separate:

truth_confidence:
  How likely the claim is true.
retrieval_salience:
  How useful the claim is right now.

A memory can be true but not relevant.
A memory can be useful but uncertain.
These must not be collapsed into one score.

⸻

6.5 Decay must be explainable

If confidence changes, Aletheia must be able to explain why:

age
half-life
source reliability
contradiction pressure
feedback
verification
promotion
demotion

No invisible confidence magic.

⸻

6.6 Promotion must be conservative

A memory should not become core merely because it was retrieved often.

Promotion requires:

evidence
confidence
importance
stability
low contradiction risk
known scope
audit reason

⸻

7. M2 Scope

In Scope

M2 includes:

1. Confidence engine v1
2. Truth confidence vs retrieval salience separation
3. Half-life policy table
4. Confidence event history
5. Feedback-to-confidence updates
6. Improved contradiction detection
7. Conflict family model
8. Conflict resolution policies
9. Claim relationships:
   - supports
   - contradicts
   - supersedes
   - duplicate_of
   - refines
   - scopes
10. Promotion/demotion lifecycle
11. Core memory governance
12. Curation decision model
13. Manual and deterministic curation
14. Duplicate detection v1
15. Claim status history
16. CLI support for confidence, decay, curation, and conflict resolution
17. Context pack integration with resolved conflicts and scoped preferences
18. Migration from M1 to M2
19. Golden integrity tests

⸻

Out of Scope

M2 explicitly excludes:

LLM automatic extraction
LLM-based contradiction detection
Vector embeddings
Graph database
MCP server
HTTP daemon
Dashboard
Cloud sync
Autonomous self-learning
Advanced semantic inference
Background autonomous memory rewriting
Multi-user enterprise ACL

M2 can introduce interfaces for later automation, but the actual M2 implementation should stay deterministic and inspectable.

⸻

8. M2 Deliverables

8.1 Library Deliverables

- ConfidenceEngine
- HalfLifePolicy
- ConfidenceEvent model
- ConfidenceSnapshot model
- ClaimRelationship model
- ConflictFamily model
- ConflictResolution model
- CurationDecision model
- CurationPolicy model
- Promotion/demotion engine
- Duplicate detection v1
- Conflict detector v2
- Conflict resolver v1
- Claim status history
- Context-scope and time-scope support

⸻

8.2 Storage Deliverables

M2 adds or upgrades:

- confidence_events
- confidence_snapshots
- half_life_policies
- claim_relationships
- claim_status_history
- conflict_families
- conflict_resolutions
- curation_decisions
- curation_queue
- claim_scopes

⸻

8.3 CLI Deliverables

M2 adds or improves:

aletheia confidence
aletheia decay
aletheia curate
aletheia conflicts detect
aletheia conflicts resolve
aletheia claims promote
aletheia claims demote
aletheia claims supersede
aletheia claims history

Existing commands must remain valid:

aletheia init
aletheia remember
aletheia search
aletheia context
aletheia claims
aletheia audit
aletheia conflicts
aletheia sessions
aletheia projects

⸻

8.4 Test Deliverables

- Confidence formula tests
- Half-life decay tests
- Feedback update tests
- Conflict detection tests
- Conflict resolution tests
- Supersession tests
- Context scoping tests
- Temporal scoping tests
- Promotion/demotion tests
- Core memory governance tests
- Duplicate detection tests
- Migration tests
- Golden context-pack integrity tests

⸻

9. Public API Contract

⸻

9.1 memory.compute_confidence()

Purpose

Compute the effective confidence of a claim using the M2 confidence model.

Signature

def compute_confidence(
    self,
    claim_id: str,
    *,
    at_time: datetime | None = None,
    explain: bool = False,
) -> ConfidenceSnapshot:
    ...

Required behavior

compute_confidence() must:

- Load the claim.
- Apply half-life decay.
- Apply source reliability.
- Apply feedback effects.
- Apply contradiction penalties.
- Apply verification bonuses.
- Apply promotion/demotion effects.
- Return a structured confidence snapshot.
- Optionally include a human-readable explanation.

ConfidenceSnapshot model

@dataclass
class ConfidenceSnapshot:
    claim_id: str
    truth_confidence: float
    retrieval_salience: float
    base_confidence: float
    effective_confidence: float
    decay_factor: float
    source_reliability_factor: float
    feedback_factor: float
    contradiction_factor: float
    verification_factor: float
    half_life_days: float
    age_days: float
    computed_at: datetime
    explanation: str | None = None

Example

snapshot = memory.compute_confidence(
    claim_id="clm_001",
    explain=True,
)

Expected explanation:

Base confidence 0.90 decayed by 0.96 due to age, no contradiction penalty,
confirmed feedback increased confidence, final effective confidence 0.91.

⸻

9.2 memory.recompute_confidence()

Purpose

Recompute confidence for one claim, many claims, or an entire namespace.

Signature

def recompute_confidence(
    self,
    *,
    namespace: str | None = None,
    claim_id: str | None = None,
    memory_types: list[str] | None = None,
    persist: bool = True,
) -> list[ConfidenceSnapshot]:
    ...

Required behavior

- Recompute effective confidence.
- Persist snapshots when persist=True.
- Write confidence event records.
- Preserve audit trail.
- Support namespace-level recomputation.

Example

memory.recompute_confidence(
    namespace="user/default",
    memory_types=["preference", "project", "procedure"],
)

⸻

9.3 memory.feedback()

Purpose

Update confidence and salience based on user or system feedback.

M0/M1 may already have basic feedback. M2 formalizes it.

Signature

def feedback(
    self,
    target_id: str,
    *,
    target_type: str = "claim",
    signal: str,
    source: str = "user",
    note: str | None = None,
    evidence_id: str | None = None,
    strength: float = 1.0,
) -> FeedbackRecord:
    ...

Allowed signals

confirmed
wrong
stale
useful
not_useful
contradicted
verified
irrelevant
important
unimportant

Required behavior

Signal	Truth confidence effect	Retrieval salience effect	Status effect
confirmed	Increase	Increase	May promote candidate to active
wrong	Strong decrease	Strong decrease	May mark disputed/rejected
stale	Moderate decrease	Strong decrease	May archive if low value
useful	No direct truth change	Increase	None
not_useful	No direct truth change	Decrease	None
contradicted	Decrease	Decrease	Creates or updates conflict
verified	Strong increase	Increase	May promote
irrelevant	No truth change	Decrease	None
important	Slight increase	Strong increase	May promote
unimportant	No truth change	Decrease	May demote

Critical rule

Assistant repetition is not confirmation.

If source="assistant" and signal="confirmed", the feedback must either be rejected or downweighted to near zero unless backed by external evidence.

⸻

9.4 memory.set_half_life_policy()

Purpose

Create or update decay policy for a memory type, predicate, or namespace.

Signature

def set_half_life_policy(
    self,
    *,
    namespace: str | None = None,
    memory_type: str | None = None,
    predicate: str | None = None,
    half_life_days: float,
    reason: str,
) -> HalfLifePolicy:
    ...

HalfLifePolicy model

@dataclass
class HalfLifePolicy:
    id: str
    namespace: str | None
    memory_type: str | None
    predicate: str | None
    half_life_days: float
    reason: str
    created_at: datetime
    updated_at: datetime

Default M2 half-life policy

Memory Type	Half-life
current_task	3 days
temporary_preference	14 days
project	30 days
session_summary	45 days
preference	180 days
procedure	365 days
identity	1000 days
correction	1000 days
domain_knowledge	1000 days
inference	14 days

⸻

9.5 memory.detect_conflicts()

Purpose

Detect contradictions and create conflict families.

Signature

def detect_conflicts(
    self,
    *,
    namespace: str,
    subject: str | None = None,
    predicate: str | None = None,
    include_resolved: bool = False,
    create: bool = True,
) -> list[ConflictFamily]:
    ...

Required behavior

M2 conflict detection must detect at least:

- Same subject + same predicate + incompatible object
- Active claim contradicted by user correction
- Active claim contradicted by verified claim
- Active claim contradicted by newer current-state claim
- Duplicate or near-duplicate claims with same meaning

M2 does not need LLM/NLI contradiction detection yet.

ConflictFamily model

@dataclass
class ConflictFamily:
    id: str
    namespace: str
    subject: str
    predicate: str
    status: str
    conflict_type: str
    claim_ids: list[str]
    active_claim_id: str | None
    resolution_id: str | None
    created_at: datetime
    updated_at: datetime

Conflict types

direct_value_conflict
user_correction_conflict
verified_fact_conflict
temporal_state_conflict
contextual_preference_conflict
duplicate_claim
scope_ambiguity

⸻

9.6 memory.resolve_conflict()

Purpose

Resolve a conflict family through explicit policy.

Signature

def resolve_conflict(
    self,
    conflict_id: str,
    *,
    strategy: str,
    active_claim_id: str | None = None,
    superseded_claim_ids: list[str] | None = None,
    rejected_claim_ids: list[str] | None = None,
    scoped_claims: list[dict] | None = None,
    note: str,
) -> ConflictResolution:
    ...

Allowed strategies

latest_wins
highest_confidence_wins
user_correction_wins
verified_source_wins
context_scope
time_scope
merge_duplicates
mark_unresolved
reject_weak_claims
manual

Required behavior

resolve_conflict() must:

- Write a conflict resolution record.
- Update claim statuses if needed.
- Create claim relationships if needed.
- Preserve all evidence links.
- Write audit events.
- Update retrieval behavior immediately.

ConflictResolution model

@dataclass
class ConflictResolution:
    id: str
    conflict_id: str
    strategy: str
    active_claim_id: str | None
    superseded_claim_ids: list[str]
    rejected_claim_ids: list[str]
    scoped_claims: list[dict]
    note: str
    created_at: datetime

⸻

9.7 memory.supersede_claim()

Purpose

Mark one claim as replacing another.

Signature

def supersede_claim(
    self,
    old_claim_id: str,
    new_claim_id: str,
    *,
    reason: str,
) -> ClaimRelationship:
    ...

Required behavior

- Mark old claim as superseded.
- Keep old claim retrievable only when include_superseded=True.
- Create claim relationship: new_claim supersedes old_claim.
- Write audit event for both claims.
- Update conflict family if relevant.

⸻

9.8 memory.scope_claim()

Purpose

Apply temporal or contextual scope to a claim.

Signature

def scope_claim(
    self,
    claim_id: str,
    *,
    scope_type: str,
    applies_when: str | None = None,
    valid_from: datetime | None = None,
    valid_to: datetime | None = None,
    reason: str,
) -> ClaimScope:
    ...

Scope types

temporal
contextual
project
session
agent
conditional

Example

memory.scope_claim(
    claim_id="clm_002",
    scope_type="contextual",
    applies_when="architecture_or_design_request",
    reason="User prefers comprehensive detail for design work.",
)

⸻

9.9 memory.promote_claim()

Purpose

Promote a claim to a stronger lifecycle status.

Signature

def promote_claim(
    self,
    claim_id: str,
    *,
    target_status: str,
    reason: str,
    force: bool = False,
) -> CurationDecision:
    ...

Allowed target statuses

active
core

Required behavior

By default, promotion must fail if:

- Claim is rejected.
- Claim is superseded.
- Claim is unresolved disputed.
- Claim has low effective confidence.
- Claim has no evidence.
- Claim belongs to unresolved conflict.

force=True can override some checks, but must write a high-visibility audit event.

⸻

9.10 memory.demote_claim()

Purpose

Demote a claim to a weaker lifecycle status.

Signature

def demote_claim(
    self,
    claim_id: str,
    *,
    target_status: str,
    reason: str,
) -> CurationDecision:
    ...

Allowed target statuses

candidate
disputed
superseded
archived
rejected

Required behavior

- Update claim status.
- Write claim status history.
- Write curation decision.
- Write audit event.
- Update retrieval behavior.

⸻

9.11 memory.curate()

Purpose

Run deterministic curation over claims.

Signature

def curate(
    self,
    *,
    namespace: str,
    dry_run: bool = True,
    memory_types: list[str] | None = None,
    max_decisions: int | None = None,
) -> list[CurationDecision]:
    ...

Required behavior

In M2, curate() must be deterministic and rule-based.

It may suggest:

promote_to_core
promote_to_active
demote_to_candidate
archive_stale
mark_disputed
merge_duplicate
needs_review

But in dry_run=True, it must not mutate the database.

CurationDecision model

@dataclass
class CurationDecision:
    id: str
    claim_id: str
    namespace: str
    decision_type: str
    old_status: str
    proposed_status: str | None
    reason: str
    confidence_before: float
    confidence_after: float | None
    applied: bool
    created_at: datetime

⸻

9.12 memory.explain_claim()

Purpose

Return a human-readable explanation of why Aletheia trusts, distrusts, retrieves, or suppresses a claim.

Signature

def explain_claim(
    self,
    claim_id: str,
    *,
    include_evidence: bool = True,
    include_confidence: bool = True,
    include_conflicts: bool = True,
    include_history: bool = True,
) -> ClaimExplanation:
    ...

Required behavior

The explanation must answer:

What is the claim?
Where did it come from?
What evidence supports it?
What is its current status?
What is its confidence?
Has it decayed?
Has it been contradicted?
Has it been promoted or demoted?
Is it scoped?
Why would or would not it appear in context?

⸻

10. Storage Contract

10.1 Schema version

M2 updates schema version to:

0.3.0

⸻

10.2 Required new tables

confidence_events

CREATE TABLE confidence_events (
    id TEXT PRIMARY KEY,
    claim_id TEXT NOT NULL,
    namespace TEXT NOT NULL,
    event_type TEXT NOT NULL,
    old_truth_confidence REAL,
    new_truth_confidence REAL,
    old_retrieval_salience REAL,
    new_retrieval_salience REAL,
    reason TEXT NOT NULL,
    created_at TEXT NOT NULL,
    metadata_json TEXT
);

⸻

confidence_snapshots

CREATE TABLE confidence_snapshots (
    id TEXT PRIMARY KEY,
    claim_id TEXT NOT NULL,
    namespace TEXT NOT NULL,
    truth_confidence REAL NOT NULL,
    retrieval_salience REAL NOT NULL,
    base_confidence REAL NOT NULL,
    effective_confidence REAL NOT NULL,
    decay_factor REAL NOT NULL,
    source_reliability_factor REAL NOT NULL,
    feedback_factor REAL NOT NULL,
    contradiction_factor REAL NOT NULL,
    verification_factor REAL NOT NULL,
    half_life_days REAL NOT NULL,
    age_days REAL NOT NULL,
    computed_at TEXT NOT NULL,
    explanation TEXT
);

⸻

half_life_policies

CREATE TABLE half_life_policies (
    id TEXT PRIMARY KEY,
    namespace TEXT,
    memory_type TEXT,
    predicate TEXT,
    half_life_days REAL NOT NULL,
    reason TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

⸻

claim_relationships

CREATE TABLE claim_relationships (
    id TEXT PRIMARY KEY,
    namespace TEXT NOT NULL,
    source_claim_id TEXT NOT NULL,
    target_claim_id TEXT NOT NULL,
    relationship_type TEXT NOT NULL,
    confidence REAL DEFAULT 1.0,
    reason TEXT,
    created_at TEXT NOT NULL
);

Allowed relationship types:

supports
contradicts
supersedes
duplicate_of
refines
scopes
derived_from

⸻

claim_status_history

CREATE TABLE claim_status_history (
    id TEXT PRIMARY KEY,
    claim_id TEXT NOT NULL,
    namespace TEXT NOT NULL,
    old_status TEXT,
    new_status TEXT NOT NULL,
    reason TEXT NOT NULL,
    changed_by TEXT,
    created_at TEXT NOT NULL
);

⸻

conflict_families

If M1 already has a simple conflicts table, M2 may either migrate it or add a richer table.

CREATE TABLE conflict_families (
    id TEXT PRIMARY KEY,
    namespace TEXT NOT NULL,
    subject TEXT NOT NULL,
    predicate TEXT NOT NULL,
    conflict_type TEXT NOT NULL,
    status TEXT NOT NULL,
    active_claim_id TEXT,
    resolution_id TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

⸻

conflict_family_claims

CREATE TABLE conflict_family_claims (
    conflict_id TEXT NOT NULL,
    claim_id TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'member',
    created_at TEXT NOT NULL,
    PRIMARY KEY (conflict_id, claim_id)
);

Allowed roles:

member
active
superseded
rejected
supporting
contradicting

⸻

conflict_resolutions

CREATE TABLE conflict_resolutions (
    id TEXT PRIMARY KEY,
    conflict_id TEXT NOT NULL,
    namespace TEXT NOT NULL,
    strategy TEXT NOT NULL,
    active_claim_id TEXT,
    note TEXT NOT NULL,
    created_at TEXT NOT NULL,
    metadata_json TEXT
);

⸻

claim_scopes

CREATE TABLE claim_scopes (
    id TEXT PRIMARY KEY,
    claim_id TEXT NOT NULL,
    namespace TEXT NOT NULL,
    scope_type TEXT NOT NULL,
    applies_when TEXT,
    valid_from TEXT,
    valid_to TEXT,
    project_id TEXT,
    session_id TEXT,
    agent_id TEXT,
    reason TEXT NOT NULL,
    created_at TEXT NOT NULL
);

⸻

curation_decisions

CREATE TABLE curation_decisions (
    id TEXT PRIMARY KEY,
    namespace TEXT NOT NULL,
    claim_id TEXT NOT NULL,
    decision_type TEXT NOT NULL,
    old_status TEXT,
    proposed_status TEXT,
    reason TEXT NOT NULL,
    confidence_before REAL,
    confidence_after REAL,
    applied INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    metadata_json TEXT
);

⸻

curation_queue

CREATE TABLE curation_queue (
    id TEXT PRIMARY KEY,
    namespace TEXT NOT NULL,
    claim_id TEXT NOT NULL,
    task_type TEXT NOT NULL,
    priority REAL NOT NULL DEFAULT 0.5,
    status TEXT NOT NULL DEFAULT 'pending',
    reason TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

⸻

11. Confidence Contract

11.1 M2 confidence formula

M2 should move from simple decay to explainable factor-based confidence.

Suggested formula:

effective_confidence =
  clamp(
    base_confidence
    × decay_factor
    × source_reliability_factor
    × feedback_factor
    × contradiction_factor
    × verification_factor,
    0,
    1
  )

Where:

decay_factor = 2 ^ (-age_days / half_life_days)

⸻

11.2 Retrieval salience formula

Suggested formula:

retrieval_salience =
  clamp(
    importance
    × recency_salience
    × usefulness_factor
    × project_relevance_factor
    × status_factor
    × scope_factor,
    0,
    1
  )

⸻

11.3 Factor definitions

Factor	Meaning
base_confidence	Initial confidence at claim creation
decay_factor	Age-based confidence decay
source_reliability_factor	Trustworthiness of source
feedback_factor	User/system feedback impact
contradiction_factor	Penalty from unresolved contradictions
verification_factor	Bonus from verification or confirmation
importance	Long-term value
recency_salience	Task usefulness due to recency
usefulness_factor	Retrieval usefulness history
project_relevance_factor	Relevance to active project
status_factor	Candidate/active/core/disputed/etc.
scope_factor	Whether scope applies to current query

⸻

11.4 Default contradiction penalties

Conflict state	Contradiction factor
No conflict	1.00
Resolved conflict, active claim	1.00
Resolved conflict, superseded claim	0.10
Context-scoped claim, scope matches	1.00
Context-scoped claim, scope unclear	0.65
Context-scoped claim, scope mismatch	0.20
Unresolved conflict	0.40
User-corrected as wrong	0.05

⸻

12. Conflict Resolution Contract

12.1 Conflict lifecycle

detected
  → unresolved
  → resolved
unresolved
  → context_scoped
  → resolved
unresolved
  → time_scoped
  → resolved
unresolved
  → superseded
  → resolved
unresolved
  → rejected
  → resolved

⸻

12.2 Resolution policy priority

When multiple policies could apply, M2 should use this priority order:

1. Explicit user correction
2. Verified external/tool evidence
3. Newer time-scoped current-state claim
4. Higher-confidence direct evidence
5. Context scoping
6. Temporal scoping
7. Manual resolution
8. Leave unresolved

⸻

12.3 Required conflict behavior in retrieval

Claim state	Normal retrieval	Context pack
Active, no conflict	Include if relevant	Include if relevant
Core, no conflict	High priority	High priority
Active in resolved conflict	Include if scope matches	Include if scope matches
Superseded	Exclude by default	Exclude
Rejected	Always exclude	Always exclude
Unresolved disputed	Exclude by default	Warning only
Context-scoped mismatch	Exclude or heavily penalize	Usually omit
Context-scoped match	Include	Include

⸻

13. Curation Contract

13.1 Claim lifecycle

M2 formalizes the lifecycle:

candidate
  → active
  → core
  → archived
candidate
  → rejected
active
  → disputed
  → superseded
active
  → archived
core
  → active
  → archived

⸻

13.2 Promotion criteria

A claim may be promoted from candidate to active if:

- It has at least one evidence link.
- It is not rejected.
- It is not superseded.
- Effective confidence is above threshold.
- It has no unresolved contradiction.
- It has a known memory type.

A claim may be promoted from active to core if:

- It has high effective confidence.
- It has high importance.
- It is durable, not temporary.
- It has known scope.
- It is useful across sessions.
- It has no unresolved contradiction.
- The promotion includes a reason.

⸻

13.3 Suggested thresholds

Promotion	Minimum effective confidence	Minimum importance
candidate → active	0.65	0.30
active → core	0.85	0.70

These should be configurable later.

⸻

13.4 Demotion criteria

A claim should be considered for demotion if:

- Effective confidence falls below threshold.
- It becomes stale.
- It is contradicted.
- It is superseded by a stronger claim.
- It has low retrieval salience.
- It is no longer relevant to any active project.
- User marks it wrong, stale, or unimportant.

⸻

13.5 Core memory governance

Core memory is privileged. M2 must protect it.

Core memories should:

- Be few.
- Be high-confidence.
- Be durable.
- Be auditable.
- Be explicitly promoted.
- Be demotable if contradicted.

M2 must prevent accidental core promotion.

⸻

14. Context Pack Integration Contract

M2 must update context_pack() to respect:

- Confidence snapshots
- Retrieval salience
- Resolved conflicts
- Context scopes
- Temporal scopes
- Core memory governance
- Disputed memory warnings

Required behavior

When building a context pack:

1. Recompute or load current confidence.
2. Apply scope matching.
3. Exclude rejected/superseded claims.
4. Exclude unresolved disputed claims from normal memory sections.
5. Include unresolved conflicts in warnings if relevant.
6. Prefer core memories only when they are still valid.
7. Include explanation metadata in structured output.

Example warning

### Warnings
- There are two unresolved memories about preferred response length.
  Do not assume either as globally true until scoped or resolved.

Example scoped memory

### Procedural Memory
- For architecture and design requests, provide comprehensive phased plans.
  scope: architecture_or_design_request | confidence: 0.91 | claim: clm_022

⸻

15. CLI Contract

⸻

15.1 aletheia confidence

Commands

aletheia confidence show clm_001 \
  --db ./aletheia.db
aletheia confidence show clm_001 \
  --db ./aletheia.db \
  --explain
aletheia confidence recompute \
  --db ./aletheia.db \
  --namespace user/default
aletheia confidence policy list \
  --db ./aletheia.db
aletheia confidence policy set \
  --db ./aletheia.db \
  --memory-type preference \
  --half-life-days 180 \
  --reason "User preferences are moderately stable."

⸻

15.2 aletheia decay

Commands

aletheia decay run \
  --db ./aletheia.db \
  --namespace user/default
aletheia decay preview \
  --db ./aletheia.db \
  --namespace user/default

preview must not mutate the database.

⸻

15.3 aletheia curate

Commands

aletheia curate preview \
  --db ./aletheia.db \
  --namespace user/default
aletheia curate apply \
  --db ./aletheia.db \
  --namespace user/default \
  --max-decisions 10

preview should show proposed curation decisions:

claim: clm_014
decision: archive_stale
reason: Project-state claim has low salience and decayed confidence.
applied: false

⸻

15.4 aletheia conflicts

M2 expands conflict commands.

aletheia conflicts detect \
  --db ./aletheia.db \
  --namespace user/default
aletheia conflicts list \
  --db ./aletheia.db \
  --namespace user/default
aletheia conflicts show conf_001 \
  --db ./aletheia.db
aletheia conflicts resolve conf_001 \
  --db ./aletheia.db \
  --strategy context_scope \
  --note "Concise for updates; detailed for architecture."

⸻

15.5 aletheia claims

M2 expands claim lifecycle commands.

aletheia claims promote clm_001 \
  --db ./aletheia.db \
  --to core \
  --reason "Stable durable user preference."
aletheia claims demote clm_001 \
  --db ./aletheia.db \
  --to archived \
  --reason "Stale project state."
aletheia claims supersede clm_old clm_new \
  --db ./aletheia.db \
  --reason "User corrected the earlier memory."
aletheia claims scope clm_002 \
  --db ./aletheia.db \
  --type contextual \
  --applies-when architecture_or_design_request \
  --reason "Preference applies to design work."
aletheia claims history clm_001 \
  --db ./aletheia.db

⸻

16. Backward Compatibility Contract

M2 must preserve M1 behavior.

The following must still work:

Memory.open()
memory.write_event()
memory.write_claim()
memory.remember()
memory.retrieve()
memory.context_pack()
memory.start_session()
memory.end_session()
memory.create_project()
memory.audit()
memory.feedback()

Existing CLI commands must still work:

aletheia init
aletheia remember
aletheia search
aletheia context
aletheia claims
aletheia audit
aletheia conflicts
aletheia sessions
aletheia projects

Allowed M2 changes:

- Additional optional API parameters
- More structured return objects
- Better confidence computation
- More explicit conflict handling
- New storage tables
- New CLI subcommands

Not allowed:

- Requiring LLMs
- Requiring vector search
- Breaking M1 databases without migration
- Silently changing claim statuses without audit entries
- Presenting disputed memories as normal facts

⸻

17. Migration Contract

17.1 Migration path

M2 must support:

0.2.x → 0.3.0

17.2 Migration command

aletheia migrate --db ./aletheia.db

Or:

memory = Memory.open("./aletheia.db", auto_migrate=True)

17.3 Migration rules

- Existing evidence remains unchanged.
- Existing claims remain unchanged except for added fields/defaults.
- Existing conflict records migrate into conflict families if needed.
- Existing confidence fields are preserved.
- New confidence snapshots may be created.
- New half-life defaults may be inserted.
- Existing audit records remain valid.
- Migration must be idempotent.

17.4 Initial migration behavior

During migration, Aletheia should:

1. Add M2 tables.
2. Insert default half-life policies.
3. Create initial confidence snapshots for active claims.
4. Create claim status history entries for existing claims.
5. Migrate simple conflicts into conflict_families.
6. Preserve all M1 retrieval behavior.

⸻

18. Test Contract

18.1 Confidence tests

Required tests:

test_compute_confidence_applies_half_life_decay
test_compute_confidence_uses_memory_type_policy
test_confirmed_feedback_increases_truth_confidence
test_useful_feedback_increases_salience_not_truth
test_wrong_feedback_demotes_claim
test_assistant_repetition_does_not_confirm_claim
test_confidence_snapshot_is_persisted
test_confidence_explanation_mentions_decay_and_feedback

⸻

18.2 Conflict tests

Required tests:

test_same_subject_predicate_different_object_creates_conflict
test_user_correction_supersedes_old_claim
test_verified_claim_wins_over_model_claim
test_context_scope_resolves_preference_conflict
test_time_scope_resolves_state_conflict
test_unresolved_conflict_excluded_from_retrieval
test_unresolved_conflict_appears_as_context_warning
test_resolved_active_claim_appears_in_retrieval

⸻

18.3 Curation tests

Required tests:

test_candidate_can_promote_to_active_when_confident
test_active_can_promote_to_core_when_durable
test_disputed_claim_cannot_promote_to_core
test_stale_project_claim_can_archive
test_superseded_claim_excluded_from_context
test_curation_preview_does_not_mutate_database
test_curation_apply_writes_decision_and_audit
test_claim_status_history_records_changes

⸻

18.4 Scope tests

Required tests:

test_context_scoped_claim_matches_relevant_query
test_context_scoped_claim_penalized_when_scope_unclear
test_context_scoped_claim_excluded_when_scope_mismatch
test_temporal_scope_uses_current_claim
test_past_temporal_claim_retrievable_when_requested

⸻

18.5 CLI tests

Required tests:

test_cli_confidence_show
test_cli_confidence_recompute
test_cli_decay_preview
test_cli_decay_run
test_cli_curate_preview
test_cli_conflicts_detect
test_cli_conflicts_resolve
test_cli_claims_promote
test_cli_claims_demote
test_cli_claims_supersede
test_cli_claims_scope
test_cli_claims_history

⸻

18.6 Migration tests

Required tests:

test_migration_from_m1_to_m2_adds_tables
test_migration_preserves_claims
test_migration_preserves_evidence_links
test_migration_creates_default_half_life_policies
test_migration_creates_initial_confidence_snapshots
test_migration_is_idempotent

⸻

19. Golden Integrity Tests

M2 should introduce golden integrity fixtures.

Golden test 1 — Context-scoped preference

Given:

Claim A:
User prefers concise updates.
Claim B:
User prefers comprehensive architecture explanations.

When:

Query = "Write a detailed architecture contract."

Expected:

- Claim B appears in procedural/relevant memory.
- Claim A does not override Claim B.
- No false global contradiction is presented.
- Context pack may include scoped note if useful.

⸻

Golden test 2 — User correction supersedes old memory

Given:

Old claim:
User prefers short answers.
Correction:
Actually, for technical design, user wants comprehensive answers.

Expected:

- Old claim is superseded or scoped.
- Correction is active.
- Context pack uses correction.
- Audit shows correction caused status change.

⸻

Golden test 3 — Stale project state decays

Given:

Project state from 90 days ago.
Newer project state from today.

Expected:

- New project state ranks higher.
- Old project state is omitted or marked stale.
- Confidence explanation mentions decay.

⸻

Golden test 4 — Disputed memory warning

Given:

Two active incompatible claims with no resolution.

Expected:

- Neither disputed claim appears as normal fact.
- Context pack contains warning.
- Retrieval excludes disputed claims by default.

⸻

20. Acceptance Criteria

M2 is complete only when all of the following are true.

20.1 Confidence acceptance

[ ] Claims have truth confidence and retrieval salience.
[ ] Confidence can be recomputed deterministically.
[ ] Half-life policies are configurable.
[ ] Confidence snapshots are persisted.
[ ] Confidence changes are auditable.
[ ] Feedback updates confidence/salience correctly.
[ ] Assistant repetition does not count as confirmation.

⸻

20.2 Conflict acceptance

[ ] Conflict families exist.
[ ] Claim relationships exist.
[ ] Direct contradictions are detected.
[ ] User corrections can supersede old claims.
[ ] Context-scoped conflicts can be resolved.
[ ] Time-scoped conflicts can be resolved.
[ ] Unresolved disputed claims are excluded from normal context.
[ ] Conflict resolutions are auditable.

⸻

20.3 Curation acceptance

[ ] Claims can be promoted and demoted.
[ ] Core memory promotion is guarded.
[ ] Disputed claims cannot become core by default.
[ ] Claim status history is recorded.
[ ] Curation preview is available.
[ ] Curation apply is available.
[ ] Curation decisions are auditable.

⸻

20.4 Context acceptance

[ ] context_pack() respects resolved conflicts.
[ ] context_pack() respects claim scopes.
[ ] context_pack() includes warnings for relevant unresolved conflicts.
[ ] context_pack() excludes rejected and superseded memories.
[ ] context_pack() does not present disputed memories as facts.
[ ] context_pack() uses updated confidence and salience.

⸻

20.5 CLI acceptance

[ ] aletheia confidence works.
[ ] aletheia decay works.
[ ] aletheia curate works.
[ ] aletheia conflicts detect/resolve works.
[ ] aletheia claims promote/demote/supersede/scope/history works.
[ ] Existing M1 CLI commands still work.

⸻

20.6 Migration acceptance

[ ] M1 database migrates to M2.
[ ] Migration is idempotent.
[ ] Existing claims remain retrievable.
[ ] Existing context packs still work.
[ ] Existing audit trails remain valid.

⸻

21. M2 Demo Script

This should be the official M2 demo.

⸻

Step 1 — Start with an M1 database

aletheia init --db ./aletheia.db

⸻

Step 2 — Create project

aletheia projects create \
  --db ./aletheia.db \
  --namespace user/default \
  --id aletheia \
  --title "Aletheia Memory Library"

⸻

Step 3 — Remember two apparently conflicting preferences

aletheia remember \
  --db ./aletheia.db \
  --namespace user/default \
  --type preference \
  --subject user \
  --predicate prefers_response_style \
  --object "concise progress updates"
aletheia remember \
  --db ./aletheia.db \
  --namespace user/default \
  --type preference \
  --subject user \
  --predicate prefers_response_style \
  --object "comprehensive architecture explanations"

⸻

Step 4 — Detect conflict

aletheia conflicts detect \
  --db ./aletheia.db \
  --namespace user/default

Expected:

Conflict detected:
subject: user
predicate: prefers_response_style
type: contextual_preference_conflict
claims:
  clm_001 concise progress updates
  clm_002 comprehensive architecture explanations

⸻

Step 5 — Resolve by context scoping

aletheia claims scope clm_001 \
  --db ./aletheia.db \
  --type contextual \
  --applies-when progress_update \
  --reason "Concise preference applies to progress updates."
aletheia claims scope clm_002 \
  --db ./aletheia.db \
  --type contextual \
  --applies-when architecture_or_design_request \
  --reason "Comprehensive preference applies to architecture/design requests."
aletheia conflicts resolve conf_001 \
  --db ./aletheia.db \
  --strategy context_scope \
  --note "Concise for progress updates; comprehensive for architecture/design work."

⸻

Step 6 — Promote durable design preference

aletheia claims promote clm_002 \
  --db ./aletheia.db \
  --to core \
  --reason "Stable high-value preference for architecture/design work."

⸻

Step 7 — Show confidence explanation

aletheia confidence show clm_002 \
  --db ./aletheia.db \
  --explain

Expected:

Claim: user prefers comprehensive architecture explanations.
Status: core
Truth confidence: high
Retrieval salience: high
Scope: architecture_or_design_request
No unresolved contradiction.

⸻

Step 8 — Generate context for architecture request

aletheia context \
  --db ./aletheia.db \
  --namespace user/default \
  --project aletheia \
  --query "Write the M2 contract for Aletheia."

Expected context includes:

- For architecture/design requests, user prefers comprehensive explanations.

Expected context does not incorrectly include:

- User always wants concise responses.

⸻

Step 9 — Generate context for progress update

aletheia context \
  --db ./aletheia.db \
  --namespace user/default \
  --project aletheia \
  --query "Give a quick progress update."

Expected context includes:

- For progress updates, user prefers concise responses.

⸻

22. M2 Implementation Checklist

Confidence

[ ] Add ConfidenceSnapshot model
[ ] Add ConfidenceEvent model
[ ] Add HalfLifePolicy model
[ ] Implement ConfidenceEngine
[ ] Implement factor-based confidence formula
[ ] Implement truth confidence vs retrieval salience
[ ] Persist confidence snapshots
[ ] Add confidence explanations
[ ] Add default half-life policies

⸻

Feedback

[ ] Formalize feedback signals
[ ] Implement feedback effects on confidence
[ ] Implement feedback effects on salience
[ ] Reject/downweight assistant self-confirmation
[ ] Write feedback audit records

⸻

Conflicts

[ ] Add ConflictFamily model
[ ] Add ConflictResolution model
[ ] Add ClaimRelationship model
[ ] Upgrade conflict detection
[ ] Implement direct contradiction detection
[ ] Implement user correction conflict detection
[ ] Implement duplicate detection v1
[ ] Implement conflict resolution policies
[ ] Implement claim supersession

⸻

Scoping

[ ] Add ClaimScope model
[ ] Implement temporal scoping
[ ] Implement contextual scoping
[ ] Integrate scope matching into retrieval
[ ] Integrate scope matching into context_pack()

⸻

Curation

[ ] Add CurationDecision model
[ ] Implement promote_claim()
[ ] Implement demote_claim()
[ ] Implement curate(dry_run=True)
[ ] Implement curate(dry_run=False)
[ ] Enforce core memory promotion guards
[ ] Record claim status history

⸻

CLI

[ ] Add confidence command group
[ ] Add decay command group
[ ] Add curate command group
[ ] Expand conflicts command group
[ ] Expand claims command group
[ ] Add JSON output support where useful

⸻

Migration

[ ] Add schema version 0.3.0
[ ] Add migration from 0.2.x
[ ] Insert default half-life policies
[ ] Create initial confidence snapshots
[ ] Migrate simple conflicts into conflict families
[ ] Add migration tests

⸻

Tests

[ ] Confidence tests
[ ] Feedback tests
[ ] Conflict tests
[ ] Scope tests
[ ] Curation tests
[ ] CLI tests
[ ] Migration tests
[ ] Golden integrity tests

⸻

23. M2 Definition of Done

M2 is done when this statement is true:

Aletheia can explain why a memory is trusted, stale, disputed, superseded, scoped, promoted, demoted, or excluded from context.

More practically, M2 is complete when Aletheia can do all of this:

- Detect a contradiction.
- Preserve both claims.
- Resolve the contradiction by correction, time, context, or supersession.
- Decay stale confidence.
- Promote durable memories to core.
- Demote weak or stale memories.
- Keep complete audit history.
- Build context packs that respect all of the above.

The soul of M2 is not more memory.
It is better memory judgment.
