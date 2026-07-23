Aletheia M4 Contract

Milestone: Reasoned Memory, Inference, and Lossless Abstraction

⸻

1. Milestone Summary

M0 proved that Aletheia can remember.
M1 proved that Aletheia can recall across sessions and projects.
M2 proved that Aletheia can maintain trust through confidence, contradiction, decay, and curation.
M3 proved that Aletheia can ingest raw material, extract candidate memories, and support semantic recall.
M4 must prove that Aletheia can reason over memory without confusing inference with fact.

M4 is where Aletheia becomes capable of controlled inference and lossless abstraction.

M0 = Remember
M1 = Recall
M2 = Trust
M3 = Understand
M4 = Reason

The core M4 promise:

Aletheia can derive logical, semantic, and factual inferences from existing evidence and claims; build higher-level reflections and abstractions; preserve complete derivation lineage; invalidate derived memories when sources change; and clearly label what is known, inferred, probable, speculative, or abstracted.

M4 is not yet autonomous self-improvement.
It is governed reasoning over memory.

⸻

2. M4 Name

M4 — Reasoned Memory

Fuller name:

M4 — Reasoned Memory, Inference, and Lossless Abstraction

Recommended short name:

M4 — Reasoned Memory

⸻

3. M4 Contract Status

milestone: M4
name: Reasoned Memory
depends_on: M3
version_target: 0.5.0
stability: advanced-beta
breaking_changes_allowed: limited
storage_migration_required: yes
llm_required: no
llm_supported: yes
vector_backend_required: no
vector_backend_supported: yes
daemon_required: no
dashboard_required: no
background_worker_required: optional
primary_theme: governed_inference_and_abstraction

Important clarification:

M4 may support LLM-assisted reflection.
M4 may support semantic clustering.
M4 may support optional vector-backed similarity.
M4 must not require LLMs.
M4 must not require vector search.
M4 must not silently promote inferences into facts.

⸻

4. M3 Assumptions

M4 assumes M3 already provides:

- Evidence ledger
- Claim store
- Manual/schema-driven remember()
- Candidate extraction
- Candidate review and promotion
- Evidence span tracking
- Entity registry
- Category labels
- Semantic index interface
- Hybrid retrieval
- Confidence engine
- Conflict families
- Claim relationships
- Claim scopes
- Curation lifecycle
- Context pack builder
- Audit trail
- CLI support for:
  - init
  - remember
  - search
  - context
  - claims
  - audit
  - conflicts
  - sessions
  - projects
  - confidence
  - decay
  - curate
  - ingest
  - extract
  - candidates
  - entities
  - categories
  - index

M4 builds on this by adding derivation, reasoning, abstraction, reflection, and invalidation propagation.

⸻

5. M4 Primary Objective

M4 must make this flow work reliably:

memory = Memory.open("./aletheia.db")
run = memory.run_inference(
    namespace="user/default",
    project_id="aletheia",
    engines=["logical", "factual", "semantic", "reflection"],
    dry_run=False,
)
inferences = memory.list_inferences(
    namespace="user/default",
    status="pending_review",
)
memory.review_inference(
    inference_id=inferences[0].id,
    decision="validate",
    reason="Inference is directly supported by active scoped claims.",
)
reflection = memory.build_reflection(
    namespace="user/default",
    source_claim_ids=["clm_001", "clm_002"],
    title="User response-style preference",
    abstraction_level=2,
    reason="Combines scoped preferences into a higher-level operating principle.",
)
context = memory.context_pack(
    namespace="user/default",
    project_id="aletheia",
    query="Write the next milestone contract.",
    retrieval_mode="hybrid",
)

Expected behavior:

- Inferences are created as governed derived records.
- Each inference records its source claims, source evidence, rule, engine, confidence, and derivation path.
- Reflections preserve backlinks to source claims and evidence.
- Context packs label inferred and reflected memories clearly.
- If a source claim is superseded, contradicted, rejected, or deleted, derived memories are marked stale, invalid, or needing refresh.

⸻

6. M4 Non-Negotiable Principles

6.1 Inference is not fact

An inference must never be silently treated as a direct fact.

Aletheia must distinguish:

direct_claim
logical_inference
semantic_relation
factual_inference
reflection
abstraction
speculation

A context pack may use inferences, but it must label them when that distinction matters.

⸻

6.2 Every inference must have lineage

Every derived memory must answer:

What source claims produced this?
What evidence supports those claims?
What rule or engine produced the inference?
When was it produced?
What confidence did it inherit?
What assumptions were used?
What would invalidate it?

No lineage means no inference.

⸻

6.3 Semantic inference is not truth

Semantic relationships may indicate:

related_to
similar_to
clustered_with
possibly_duplicate
category_suggestion
retrieval_hint

They do not prove factual correctness.

M4 must prevent semantic similarity from becoming factual support.

⸻

6.4 Logical inference must be deterministic

Logical inference in M4 should be deterministic and inspectable.

Examples:

If claim A supersedes claim B, then B is not current.
If a claim has valid_to in the past, it is not current.
If a scoped claim matches the query context, it can be retrieved.
If evidence is deleted, derived claims from that evidence require invalidation.

No hidden chain of magical reasoning.

⸻

6.5 Factual inference must be conservative

Factual inference may produce:

entailed_candidate
probable_candidate
speculative_candidate

Only strongly entailed candidates should be eligible for promotion, and even then they must pass M2 integrity gates.

⸻

6.6 Abstraction must be lossless by backlink

Aletheia cannot compress information without loss if it discards the source.

Therefore:

Every abstraction must point back to source claims and evidence.
Every reflection must be expandable.
Every summary must declare its abstraction level.
Every derived abstraction must be invalidated or refreshed when its sources change.

⸻

6.7 Derived memory must be invalidatable

If source material changes, Aletheia must know what depends on it.

Example:

Source claim clm_001 is superseded.
Derived reflection ref_001 depends on clm_001.
Therefore ref_001 becomes stale or requires refresh.

This is essential. Without invalidation, reasoning becomes rot.

⸻

7. M4 Scope

In Scope

M4 includes:

1. Inference run model
2. Inference candidate model
3. Derived claim lineage
4. Derivation graph
5. Logical inference engine v1
6. Semantic inference engine v1
7. Factual inference engine v1
8. Reflection model
9. Abstraction model
10. Source-backed reflection builder
11. Inference review lifecycle
12. Inference promotion/rejection
13. Rule registry v1
14. Rule execution audit
15. Dependency invalidation
16. Derived-memory refresh
17. Semantic clustering v1
18. Semantic relation records
19. Context-pack integration for inferences/reflections
20. Explanation API for inferences and reflections
21. CLI support for inference, rules, reflection, and derivation tracing
22. Migration from M3 to M4
23. Golden reasoning tests

⸻

Out of Scope

M4 explicitly excludes:

Autonomous self-improvement
Automatic rewriting of procedures based on outcomes
Automatic core promotion of inferred memories
Advanced theorem proving
Full knowledge graph database requirement
Mandatory LLM reflection
Mandatory vector backend
HTTP daemon
MCP server
Dashboard
Cloud sync
Enterprise ACL
Multi-agent shared memory governance
Long-horizon self-optimization

M4 may create interfaces that later milestones use, but it should not depend on those future systems.

⸻

8. M4 Deliverables

8.1 Library Deliverables

- InferenceRun model
- InferenceCandidate model
- InferenceDecision model
- InferenceRule model
- InferenceEngine interface
- LogicalInferenceEngine
- SemanticInferenceEngine
- FactualInferenceEngine
- Reflection model
- AbstractionRecord model
- DerivationEdge model
- DerivationGraph service
- DependencyInvalidator
- ReflectionBuilder
- SemanticCluster model
- SemanticRelation model
- InferenceExplanation model
- RuleRegistry
- RuleExecutionResult

⸻

8.2 Storage Deliverables

M4 adds:

- inference_runs
- inference_candidates
- inference_decisions
- inference_rules
- rule_execution_log
- derivation_edges
- derived_claim_links
- reflections
- reflection_sources
- abstraction_records
- abstraction_sources
- semantic_clusters
- semantic_cluster_members
- semantic_relations
- invalidation_events
- refresh_queue
- inference_explanations

⸻

8.3 CLI Deliverables

M4 adds or improves:

aletheia infer
aletheia rules
aletheia reflect
aletheia derivation
aletheia clusters
aletheia abstractions

Existing M0–M3 commands must remain valid.

⸻

8.4 Test Deliverables

- Logical inference tests
- Semantic inference tests
- Factual inference tests
- Reflection builder tests
- Abstraction expansion tests
- Derivation graph tests
- Invalidation tests
- Inference review tests
- Inference promotion tests
- Context-pack integration tests
- CLI tests
- Migration tests
- Golden reasoning tests

⸻

9. Public API Contract

⸻

9.1 memory.run_inference()

Purpose

Run one or more inference engines over claims, candidates, evidence, entities, categories, or projects.

Signature

def run_inference(
    self,
    namespace: str,
    *,
    engines: list[str] | None = None,
    project_id: str | None = None,
    session_id: str | None = None,
    target_claim_ids: list[str] | None = None,
    target_evidence_ids: list[str] | None = None,
    target_entity_ids: list[str] | None = None,
    rule_ids: list[str] | None = None,
    dry_run: bool = True,
    max_inferences: int | None = None,
    policy: dict | None = None,
) -> InferenceRun:
    ...

Allowed engines

logical
semantic
factual
reflection
all

Required behavior

run_inference() must:

- Load eligible source material.
- Respect namespace, project, session, status, scope, privacy, and confidence filters.
- Run selected inference engines.
- Produce inference candidates or semantic relations.
- Validate every inference candidate.
- Persist inference candidates only when dry_run=False.
- Preserve complete lineage.
- Write rule execution logs.
- Write audit events.
- Never create canonical active claims directly by default.

InferenceRun model

@dataclass
class InferenceRun:
    id: str
    namespace: str
    engines: list[str]
    project_id: str | None
    session_id: str | None
    target_claim_ids: list[str]
    target_evidence_ids: list[str]
    rule_ids: list[str]
    dry_run: bool
    inference_count: int
    persisted_count: int
    created_at: datetime
    warnings: list[str]
    metadata: dict

⸻

9.2 InferenceCandidate

Purpose

Represent a derived memory that has not yet become canonical.

Model

@dataclass
class InferenceCandidate:
    id: str
    namespace: str
    inference_run_id: str
    inference_type: str
    subject: str | None
    predicate: str | None
    object: str | None
    text: str
    status: str
    source_claim_ids: list[str]
    source_evidence_ids: list[str]
    source_candidate_ids: list[str]
    rule_id: str | None
    engine: str
    derivation_confidence: float
    suggested_truth_confidence: float
    suggested_retrieval_salience: float
    inference_strength: str
    abstraction_level: int
    invalidation_policy: str
    created_at: datetime
    metadata: dict

Allowed inference_type

logical
semantic
factual
reflection
abstraction
scope_match
temporal_currentness
duplicate_relation
category_relation
project_relation

Allowed inference_strength

entailed
strong
probable
weak
speculative
retrieval_hint

Allowed statuses

pending_review
validated
promoted
rejected
superseded
stale
invalidated
needs_source_review
needs_conflict_resolution

⸻

9.3 memory.list_inferences()

Purpose

List inference candidates for review or inspection.

Signature

def list_inferences(
    self,
    namespace: str,
    *,
    status: str | None = None,
    inference_type: str | None = None,
    engine: str | None = None,
    project_id: str | None = None,
    source_claim_id: str | None = None,
    limit: int = 50,
) -> list[InferenceCandidate]:
    ...

⸻

9.4 memory.review_inference()

Purpose

Review an inference candidate without necessarily promoting it.

Signature

def review_inference(
    self,
    inference_id: str,
    *,
    decision: str,
    reason: str,
    reviewer: str = "user",
    edits: dict | None = None,
) -> InferenceDecision:
    ...

Allowed decisions

validate
reject
edit
defer
mark_speculative
needs_conflict_resolution
needs_source_review

InferenceDecision model

@dataclass
class InferenceDecision:
    id: str
    namespace: str
    inference_id: str
    decision: str
    reason: str
    reviewer: str
    edits: dict | None
    created_at: datetime

⸻

9.5 memory.promote_inference()

Purpose

Convert a reviewed inference candidate into a canonical claim or reflection.

Signature

def promote_inference(
    self,
    inference_id: str,
    *,
    target_type: str = "claim",
    target_status: str = "active",
    reason: str,
    reviewer: str = "user",
    force: bool = False,
) -> Claim | Reflection:
    ...

Required behavior

promote_inference() must:

- Load inference candidate.
- Validate source lineage.
- Validate inference strength.
- Validate source claims are active/current unless policy allows otherwise.
- Apply M2 confidence and conflict gates.
- Preserve derivation edges.
- Create claim or reflection.
- Link promoted object back to inference candidate.
- Write audit event.
- Write status history.

Promotion must fail by default if:

- Inference has no source lineage.
- Inference is speculative.
- Inference depends on rejected or superseded claims.
- Inference conflicts with active claims.
- Inference target_status is core without explicit promotion gates.

⸻

9.6 memory.reject_inference()

Purpose

Reject an inference candidate while preserving the reasoning trace.

Signature

def reject_inference(
    self,
    inference_id: str,
    *,
    reason: str,
    reviewer: str = "user",
) -> InferenceDecision:
    ...

Required behavior

- Mark inference as rejected.
- Preserve inference record.
- Preserve derivation lineage.
- Write audit event.
- Prevent it from appearing in context.

⸻

9.7 memory.define_rule()

Purpose

Create a deterministic inference rule.

Signature

def define_rule(
    self,
    namespace: str | None,
    *,
    name: str,
    rule_type: str,
    description: str,
    condition: dict,
    conclusion: dict,
    confidence_policy: dict | None = None,
    enabled: bool = True,
) -> InferenceRule:
    ...

InferenceRule model

@dataclass
class InferenceRule:
    id: str
    namespace: str | None
    name: str
    rule_type: str
    description: str
    condition: dict
    conclusion: dict
    confidence_policy: dict
    enabled: bool
    created_at: datetime
    updated_at: datetime

Allowed rule types

logical
temporal
scope
conflict
dependency
factual
classification

Required behavior

Rules must be:

- Versioned or update-tracked
- Auditable
- Enableable/disableable
- Deterministic in M4
- Safe to run repeatedly

⸻

9.8 memory.run_rule()

Purpose

Run a specific rule.

Signature

def run_rule(
    self,
    rule_id: str,
    *,
    namespace: str,
    target_claim_ids: list[str] | None = None,
    dry_run: bool = True,
) -> RuleExecutionResult:
    ...

RuleExecutionResult model

@dataclass
class RuleExecutionResult:
    id: str
    rule_id: str
    namespace: str
    matched_count: int
    inference_count: int
    dry_run: bool
    created_at: datetime
    warnings: list[str]

⸻

9.9 memory.build_reflection()

Purpose

Create a higher-level abstraction from multiple source claims, evidence events, candidates, or prior reflections.

Signature

def build_reflection(
    self,
    namespace: str,
    *,
    source_claim_ids: list[str] | None = None,
    source_evidence_ids: list[str] | None = None,
    source_reflection_ids: list[str] | None = None,
    title: str,
    text: str | None = None,
    abstraction_level: int = 2,
    project_id: str | None = None,
    reason: str,
    builder: str = "manual",
    require_review: bool = True,
) -> Reflection:
    ...

Required behavior

build_reflection() must:

- Require at least one source.
- Preserve source backlinks.
- Store abstraction level.
- Store builder identity.
- Compute derived confidence from sources.
- Mark reflection as candidate/pending if require_review=True.
- Write audit event.
- Support expansion back to sources.

Reflection model

@dataclass
class Reflection:
    id: str
    namespace: str
    title: str
    text: str
    abstraction_level: int
    source_claim_ids: list[str]
    source_evidence_ids: list[str]
    source_reflection_ids: list[str]
    project_id: str | None
    status: str
    confidence_effective: float
    retrieval_salience: float
    builder: str
    created_at: datetime
    updated_at: datetime
    metadata: dict

Reflection statuses

candidate
active
core
stale
invalidated
archived
rejected

⸻

9.10 memory.expand_reflection()

Purpose

Expand a reflection back into its source material.

Signature

def expand_reflection(
    self,
    reflection_id: str,
    *,
    include_claims: bool = True,
    include_evidence: bool = True,
    include_derivation: bool = True,
) -> ReflectionExpansion:
    ...

ReflectionExpansion model

@dataclass
class ReflectionExpansion:
    reflection_id: str
    reflection_text: str
    source_claims: list[Claim]
    source_evidence: list[EvidenceEvent]
    derivation_edges: list[DerivationEdge]
    warnings: list[str]

Required behavior

A reflection must always be expandable unless its source evidence has been deleted. If evidence was deleted, expansion must show tombstones and invalidation state.

⸻

9.11 memory.create_abstraction()

Purpose

Create an explicit abstraction record over one or more lower-level memories.

Signature

def create_abstraction(
    self,
    namespace: str,
    *,
    source_ids: list[str],
    source_type: str,
    abstraction_text: str,
    abstraction_level: int,
    information_loss_policy: str = "lossless_via_backlinks",
    reason: str,
) -> AbstractionRecord:
    ...

AbstractionRecord model

@dataclass
class AbstractionRecord:
    id: str
    namespace: str
    abstraction_text: str
    abstraction_level: int
    source_ids: list[str]
    source_type: str
    information_loss_policy: str
    status: str
    created_at: datetime
    metadata: dict

Allowed information loss policies

lossless_via_backlinks
lossy_summary
index_only
compressed_view

M4 default:

lossless_via_backlinks

⸻

9.12 memory.trace_derivation()

Purpose

Return the full dependency tree for a claim, inference, reflection, or abstraction.

Signature

def trace_derivation(
    self,
    target_id: str,
    *,
    target_type: str,
    max_depth: int = 10,
) -> DerivationTrace:
    ...

DerivationTrace model

@dataclass
class DerivationTrace:
    target_id: str
    target_type: str
    nodes: list[dict]
    edges: list[DerivationEdge]
    invalidation_risks: list[str]
    root_evidence_ids: list[str]

⸻

9.13 memory.explain_inference()

Purpose

Explain why an inference exists and whether it should be trusted.

Signature

def explain_inference(
    self,
    inference_id: str,
    *,
    include_sources: bool = True,
    include_rule: bool = True,
    include_confidence: bool = True,
    include_invalidation: bool = True,
) -> InferenceExplanation:
    ...

Explanation must answer

What was inferred?
Was it logical, semantic, factual, or reflective?
What produced it?
What sources support it?
What confidence does it have?
Is it entailed, probable, weak, or speculative?
What could invalidate it?
Can it be promoted?
Why or why not?

⸻

9.14 memory.invalidate_derived()

Purpose

Invalidate or mark stale derived records affected by source changes.

Signature

def invalidate_derived(
    self,
    *,
    namespace: str,
    source_id: str,
    source_type: str,
    reason: str,
    mode: str = "mark_stale",
) -> list[InvalidationEvent]:
    ...

Allowed modes

mark_stale
invalidate
queue_refresh
recompute

Required behavior

- Find all derived records depending on source.
- Mark affected records stale/invalidated or queue refresh.
- Write invalidation events.
- Preserve audit trail.
- Prevent invalidated records from appearing as active context.

⸻

10. Storage Contract

10.1 Schema version

M4 updates schema version to:

0.5.0

⸻

10.2 Required new tables

inference_runs

CREATE TABLE inference_runs (
    id TEXT PRIMARY KEY,
    namespace TEXT NOT NULL,
    engines_json TEXT NOT NULL,
    project_id TEXT,
    session_id TEXT,
    target_claim_ids_json TEXT,
    target_evidence_ids_json TEXT,
    rule_ids_json TEXT,
    dry_run INTEGER NOT NULL DEFAULT 1,
    inference_count INTEGER NOT NULL,
    persisted_count INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    warnings_json TEXT,
    metadata_json TEXT
);

⸻

inference_candidates

CREATE TABLE inference_candidates (
    id TEXT PRIMARY KEY,
    namespace TEXT NOT NULL,
    inference_run_id TEXT NOT NULL,
    inference_type TEXT NOT NULL,
    subject TEXT,
    predicate TEXT,
    object TEXT,
    text TEXT NOT NULL,
    status TEXT NOT NULL,
    engine TEXT NOT NULL,
    rule_id TEXT,
    derivation_confidence REAL NOT NULL,
    suggested_truth_confidence REAL NOT NULL,
    suggested_retrieval_salience REAL NOT NULL,
    inference_strength TEXT NOT NULL,
    abstraction_level INTEGER NOT NULL DEFAULT 1,
    invalidation_policy TEXT NOT NULL DEFAULT 'mark_stale',
    created_at TEXT NOT NULL,
    metadata_json TEXT
);

⸻

inference_decisions

CREATE TABLE inference_decisions (
    id TEXT PRIMARY KEY,
    namespace TEXT NOT NULL,
    inference_id TEXT NOT NULL,
    decision TEXT NOT NULL,
    reason TEXT NOT NULL,
    reviewer TEXT NOT NULL,
    edits_json TEXT,
    created_at TEXT NOT NULL
);

⸻

inference_rules

CREATE TABLE inference_rules (
    id TEXT PRIMARY KEY,
    namespace TEXT,
    name TEXT NOT NULL,
    rule_type TEXT NOT NULL,
    description TEXT NOT NULL,
    condition_json TEXT NOT NULL,
    conclusion_json TEXT NOT NULL,
    confidence_policy_json TEXT,
    enabled INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

⸻

rule_execution_log

CREATE TABLE rule_execution_log (
    id TEXT PRIMARY KEY,
    namespace TEXT NOT NULL,
    rule_id TEXT NOT NULL,
    inference_run_id TEXT,
    matched_count INTEGER NOT NULL,
    inference_count INTEGER NOT NULL,
    dry_run INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    warnings_json TEXT
);

⸻

derivation_edges

CREATE TABLE derivation_edges (
    id TEXT PRIMARY KEY,
    namespace TEXT NOT NULL,
    source_id TEXT NOT NULL,
    source_type TEXT NOT NULL,
    target_id TEXT NOT NULL,
    target_type TEXT NOT NULL,
    relationship TEXT NOT NULL,
    rule_id TEXT,
    confidence REAL DEFAULT 1.0,
    created_at TEXT NOT NULL,
    metadata_json TEXT
);

Allowed relationships:

derived_from
entailed_by
supported_by
summarizes
abstracts
clusters_with
semantically_related_to
depends_on
invalidated_by
refreshes

⸻

derived_claim_links

CREATE TABLE derived_claim_links (
    inference_id TEXT NOT NULL,
    claim_id TEXT NOT NULL,
    relation TEXT NOT NULL DEFAULT 'promoted_to_claim',
    created_at TEXT NOT NULL,
    PRIMARY KEY (inference_id, claim_id)
);

⸻

reflections

CREATE TABLE reflections (
    id TEXT PRIMARY KEY,
    namespace TEXT NOT NULL,
    title TEXT NOT NULL,
    text TEXT NOT NULL,
    abstraction_level INTEGER NOT NULL,
    project_id TEXT,
    status TEXT NOT NULL,
    confidence_effective REAL NOT NULL,
    retrieval_salience REAL NOT NULL,
    builder TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    metadata_json TEXT
);

⸻

reflection_sources

CREATE TABLE reflection_sources (
    reflection_id TEXT NOT NULL,
    source_id TEXT NOT NULL,
    source_type TEXT NOT NULL,
    relation TEXT NOT NULL DEFAULT 'source',
    created_at TEXT NOT NULL,
    PRIMARY KEY (reflection_id, source_id, source_type)
);

⸻

abstraction_records

CREATE TABLE abstraction_records (
    id TEXT PRIMARY KEY,
    namespace TEXT NOT NULL,
    abstraction_text TEXT NOT NULL,
    abstraction_level INTEGER NOT NULL,
    source_type TEXT NOT NULL,
    information_loss_policy TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    metadata_json TEXT
);

⸻

abstraction_sources

CREATE TABLE abstraction_sources (
    abstraction_id TEXT NOT NULL,
    source_id TEXT NOT NULL,
    source_type TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (abstraction_id, source_id, source_type)
);

⸻

semantic_clusters

CREATE TABLE semantic_clusters (
    id TEXT PRIMARY KEY,
    namespace TEXT NOT NULL,
    label TEXT,
    cluster_type TEXT NOT NULL,
    created_by TEXT NOT NULL,
    confidence REAL NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    metadata_json TEXT
);

⸻

semantic_cluster_members

CREATE TABLE semantic_cluster_members (
    cluster_id TEXT NOT NULL,
    member_id TEXT NOT NULL,
    member_type TEXT NOT NULL,
    membership_confidence REAL NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (cluster_id, member_id, member_type)
);

⸻

semantic_relations

CREATE TABLE semantic_relations (
    id TEXT PRIMARY KEY,
    namespace TEXT NOT NULL,
    source_id TEXT NOT NULL,
    source_type TEXT NOT NULL,
    target_id TEXT NOT NULL,
    target_type TEXT NOT NULL,
    relation_type TEXT NOT NULL,
    confidence REAL NOT NULL,
    created_at TEXT NOT NULL,
    metadata_json TEXT
);

Allowed relation types:

related_to
similar_to
possibly_duplicate
category_related
conceptually_near
retrieval_hint

⸻

invalidation_events

CREATE TABLE invalidation_events (
    id TEXT PRIMARY KEY,
    namespace TEXT NOT NULL,
    source_id TEXT NOT NULL,
    source_type TEXT NOT NULL,
    affected_id TEXT NOT NULL,
    affected_type TEXT NOT NULL,
    action TEXT NOT NULL,
    reason TEXT NOT NULL,
    created_at TEXT NOT NULL,
    metadata_json TEXT
);

⸻

refresh_queue

CREATE TABLE refresh_queue (
    id TEXT PRIMARY KEY,
    namespace TEXT NOT NULL,
    target_id TEXT NOT NULL,
    target_type TEXT NOT NULL,
    reason TEXT NOT NULL,
    priority REAL NOT NULL DEFAULT 0.5,
    status TEXT NOT NULL DEFAULT 'pending',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    metadata_json TEXT
);

⸻

inference_explanations

CREATE TABLE inference_explanations (
    id TEXT PRIMARY KEY,
    namespace TEXT NOT NULL,
    inference_id TEXT NOT NULL,
    explanation_text TEXT NOT NULL,
    generated_at TEXT NOT NULL,
    metadata_json TEXT
);

⸻

11. Logical Inference Contract

11.1 Purpose

Logical inference performs deterministic reasoning over structured claims, scopes, statuses, conflicts, and relationships.

Required logical inference types

M4 must support at least:

currentness inference
supersession inference
temporal validity inference
scope match inference
resolved conflict active-claim inference
dependency invalidation inference
project relevance inference

⸻

11.2 Examples

Currentness

If claim.status = active
and claim.valid_to is null or future
and claim is not superseded
then claim is current.

Supersession

If claim A supersedes claim B,
then claim B is not current.

Scope match

If claim has contextual scope architecture_or_design_request
and query intent matches architecture/design,
then claim applies to current context.

Invalidation

If source claim is rejected, superseded, or invalidated,
then derived memories depending on it require refresh or invalidation.

⸻

11.3 Logical inference output

Logical inference may produce:

InferenceCandidate
ClaimRelationship
DerivationEdge
InvalidationEvent
Context warning
Retrieval hint

It should not produce unreviewed active factual claims by default.

⸻

12. Semantic Inference Contract

12.1 Purpose

Semantic inference discovers conceptual relationships between memories.

Examples:

Aletheia Memory Library
memory kernel
local agent memory
context persistence
retrieval system

These may cluster together.

Semantic inference may produce

semantic_clusters
semantic_relations
category suggestions
duplicate candidates
retrieval hints
reflection source suggestions

Semantic inference must not produce

trusted factual claims
user-confirmed preferences
core memories

Semantic similarity is useful for recall, not truth.

⸻

13. Factual Inference Contract

13.1 Purpose

Factual inference derives candidate facts from existing evidence and claims.

Factual inference strengths

entailed
strong
probable
weak
speculative

Rules

Entailed:
  May become active after review and M2 validation.
Strong:
  May become candidate requiring review.
Probable:
  Candidate only, lower confidence.
Weak:
  Usually retrieval hint or candidate with warning.
Speculative:
  Must not be promoted by default.

⸻

13.2 Example

Source claims:

Project Aletheia current milestone is M4.
M4 name is Reasoned Memory.

Possible inferred claim:

Project Aletheia is currently focused on reasoned memory and inference.

This is a factual inference candidate, not a direct fact.

⸻

14. Reflection and Abstraction Contract

14.1 Purpose

Reflections compress multiple memories into a useful higher-level pattern while preserving source access.

Example

Source claims:

User prefers concise progress updates.
User prefers comprehensive architecture contracts.
User values practical, direct technical design.

Reflection:

The user prefers response depth to match context: concise for status updates, comprehensive for architecture and design work.

This is useful, but it must remain expandable.

⸻

14.2 Abstraction levels

M4 formalizes abstraction levels:

Level	Meaning	Example
0	Raw evidence	Original message, file, transcript
1	Atomic claim	User prefers concise progress updates
2	Local reflection	User wants response depth matched to context
3	Project/domain pattern	Aletheia design work benefits from phased contracts
4	Procedure-like principle	For architecture contracts, include scope, APIs, storage, tests, acceptance
5	Core operating principle	Preserve truth/inference distinction at all times

M4 may create levels 2–3.
Level 4–5 promotion should remain conservative and pass M2 curation gates.

⸻

14.3 Reflection confidence

Reflection confidence should be derived from source confidence:

reflection_confidence =
  min(source_effective_confidences)
  × source_consistency_factor
  × abstraction_quality_factor
  × contradiction_factor

A reflection cannot be more trustworthy than its weakest essential source unless explicitly justified.

⸻

14.4 Reflection invalidation

If any essential source becomes:

rejected
superseded
invalidated
deleted
strongly contradicted

then the reflection must become:

stale
needs_refresh
invalidated

depending on policy.

⸻

15. Derivation Graph Contract

15.1 Purpose

The derivation graph tracks how memories depend on each other.

Without this, Aletheia cannot explain or invalidate its reasoning.

Derivation graph must support

claim → inference
evidence → inference
claim → reflection
reflection → abstraction
candidate → claim
inference → claim
claim → invalidation event

Required behavior

- Every derived record must have at least one derivation edge.
- Derivation traces must be inspectable.
- Source deletion or rejection must propagate.
- Cycles must be detected and rejected or clearly marked.

⸻

16. Invalidation and Refresh Contract

16.1 Purpose

Derived memories must not remain trusted after their source changes.

Invalidation triggers

source claim rejected
source claim superseded
source claim marked wrong
source evidence deleted
source evidence redacted
conflict created involving source
source confidence drops below threshold
scope changed
half-life decay crosses threshold

Invalidation actions

mark_stale
invalidate
queue_refresh
recompute_confidence
demote
remove_from_context

Required behavior

- Invalidated records must not appear as normal context.
- Stale records may appear only with warning.
- Refresh queue must preserve reason.
- All invalidation events must be auditable.

⸻

17. Context Pack Integration Contract

M4 must update context_pack() to support inferences, reflections, and abstractions.

Required behavior

- Include active reflections when useful.
- Label inferred memories clearly.
- Exclude unreviewed inference candidates by default.
- Exclude invalidated reflections.
- Warn when a reflection depends on stale sources.
- Allow expansion/debug metadata in structured output.
- Respect all M2 confidence/conflict/scope rules.
- Respect all M3 candidate/semantic governance rules.

Suggested context_pack() extension

context = memory.context_pack(
    namespace="user/default",
    query="Write the M4 contract.",
    project_id="aletheia",
    retrieval_mode="hybrid",
    include_reflections=True,
    include_inferences=False,
    include_derivation_metadata=True,
)

Default:

include_reflections = true
include_inferences = false unless promoted/validated
include_derivation_metadata = false for clean agent output, true for debug

⸻

Context item labeling

A context item should be able to carry:

source_kind: direct_claim | reflection | inference | abstraction
confidence
salience
claim_ids
evidence_ids
reflection_id
inference_id
abstraction_level
is_inferred
is_reflected
is_stale

⸻

18. CLI Contract

⸻

18.1 aletheia infer

Purpose

Run and inspect inference.

Commands

aletheia infer run \
  --db ./aletheia.db \
  --namespace user/default \
  --project aletheia \
  --engines logical,factual,semantic \
  --dry-run
aletheia infer run \
  --db ./aletheia.db \
  --namespace user/default \
  --project aletheia \
  --engines logical,factual,semantic \
  --apply
aletheia infer list \
  --db ./aletheia.db \
  --namespace user/default \
  --status pending_review
aletheia infer show inf_001 \
  --db ./aletheia.db
aletheia infer validate inf_001 \
  --db ./aletheia.db \
  --reason "Inference is directly entailed by active project claims."
aletheia infer promote inf_001 \
  --db ./aletheia.db \
  --reason "Reviewed and supported by active source claims."
aletheia infer reject inf_002 \
  --db ./aletheia.db \
  --reason "Speculative inference not sufficiently supported."
aletheia infer explain inf_001 \
  --db ./aletheia.db

⸻

18.2 aletheia rules

Purpose

Manage deterministic inference rules.

Commands

aletheia rules list \
  --db ./aletheia.db
aletheia rules show rule_001 \
  --db ./aletheia.db
aletheia rules enable rule_001 \
  --db ./aletheia.db
aletheia rules disable rule_001 \
  --db ./aletheia.db
aletheia rules run rule_001 \
  --db ./aletheia.db \
  --namespace user/default \
  --dry-run

M4 may support file-based rule import later, but it is not required for the core contract.

⸻

18.3 aletheia reflect

Purpose

Create, inspect, expand, and refresh reflections.

Commands

aletheia reflect build \
  --db ./aletheia.db \
  --namespace user/default \
  --title "User response-style preference" \
  --claims clm_001,clm_002 \
  --text "User prefers concise progress updates and comprehensive architecture explanations." \
  --reason "Combines scoped response preferences."
aletheia reflect list \
  --db ./aletheia.db \
  --namespace user/default
aletheia reflect show ref_001 \
  --db ./aletheia.db
aletheia reflect expand ref_001 \
  --db ./aletheia.db
aletheia reflect refresh ref_001 \
  --db ./aletheia.db
aletheia reflect archive ref_001 \
  --db ./aletheia.db \
  --reason "Reflection superseded by newer source claims."

⸻

18.4 aletheia derivation

Purpose

Trace lineage.

Commands

aletheia derivation trace clm_101 \
  --db ./aletheia.db \
  --type claim
aletheia derivation trace ref_001 \
  --db ./aletheia.db \
  --type reflection
aletheia derivation invalidated \
  --db ./aletheia.db \
  --namespace user/default

⸻

18.5 aletheia clusters

Purpose

Inspect semantic clusters.

Commands

aletheia clusters build \
  --db ./aletheia.db \
  --namespace user/default \
  --target claims
aletheia clusters list \
  --db ./aletheia.db \
  --namespace user/default
aletheia clusters show cluster_001 \
  --db ./aletheia.db

⸻

18.6 aletheia abstractions

Purpose

Inspect and expand abstraction records.

Commands

aletheia abstractions list \
  --db ./aletheia.db \
  --namespace user/default
aletheia abstractions show abs_001 \
  --db ./aletheia.db
aletheia abstractions expand abs_001 \
  --db ./aletheia.db

⸻

19. Backward Compatibility Contract

M4 must preserve M3 behavior.

The following Python methods must still work:

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
memory.compute_confidence()
memory.detect_conflicts()
memory.resolve_conflict()
memory.promote_claim()
memory.demote_claim()
memory.curate()
memory.ingest()
memory.extract_candidates()
memory.list_candidates()
memory.promote_candidate()
memory.reject_candidate()
memory.resolve_entity()
memory.label_memory()
memory.index_semantic()

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
aletheia confidence
aletheia decay
aletheia curate
aletheia ingest
aletheia extract
aletheia candidates
aletheia entities
aletheia categories
aletheia index

Allowed M4 changes:

- Add inference-related optional parameters.
- Add reflection and abstraction sections to context packs.
- Add derivation metadata in structured output.
- Add reasoning tables.
- Add invalidation events and refresh queue.

Not allowed:

- Requiring LLMs.
- Requiring vector search.
- Auto-promoting speculative inferences.
- Treating semantic similarity as truth.
- Breaking M3 candidate review behavior.
- Dropping provenance or evidence backlinks.
- Allowing invalidated derived memories to appear as normal context.

⸻

20. Migration Contract

20.1 Migration path

M4 must support:

0.4.x → 0.5.0

20.2 Migration command

aletheia migrate --db ./aletheia.db

Or:

memory = Memory.open("./aletheia.db", auto_migrate=True)

20.3 Migration rules

- Existing evidence remains unchanged.
- Existing claims remain unchanged.
- Existing candidates remain unchanged.
- Existing entity/category data remains valid.
- Existing semantic indexes remain valid.
- Existing confidence/conflict/curation data remains valid.
- New reasoning tables are added safely.
- Default inference rules may be inserted.
- No inference run happens automatically during migration.
- No reflections are built automatically during migration unless explicitly requested.
- Migration must be idempotent.

20.4 Initial migration behavior

During migration, Aletheia should:

1. Add M4 tables.
2. Insert default deterministic rules.
3. Create no inference candidates by default.
4. Create no reflections by default.
5. Preserve all M3 retrieval and context behavior.
6. Mark schema version as 0.5.0.

⸻

21. Default M4 Rules

M4 should ship with a small deterministic rule set.

Rule 1 — Superseded claims are not current

IF claim_relationship(source_claim_id=A, target_claim_id=B, type=supersedes)
THEN B is not current.

Rule 2 — Expired temporal claims are not current

IF claim.valid_to < now
THEN claim is not current.

Rule 3 — Active resolved-conflict claim applies

IF conflict_family.status = resolved
AND conflict_family.active_claim_id = claim.id
THEN claim is active_for_conflict.

Rule 4 — Unresolved disputed claims produce warning

IF claim.status = disputed
AND conflict_family.status = unresolved
THEN create context warning.

Rule 5 — Source invalidation propagates

IF source claim is rejected/superseded/invalidated
AND derived object depends_on source claim
THEN derived object requires refresh.

Rule 6 — Scoped claim applies when scope matches

IF claim.scope = contextual
AND query_context matches scope.applies_when
THEN claim applies_to_context.

These are enough to make the reasoning layer useful without pretending to be a theorem prover.

⸻

22. Test Contract

22.1 Logical inference tests

Required tests:

test_logical_inference_detects_superseded_not_current
test_logical_inference_detects_expired_claim_not_current
test_logical_inference_respects_resolved_conflict_active_claim
test_logical_inference_generates_warning_for_unresolved_conflict
test_logical_inference_scope_match_applies_claim
test_logical_inference_scope_mismatch_excludes_claim

⸻

22.2 Factual inference tests

Required tests:

test_factual_inference_creates_candidate_not_claim
test_factual_inference_requires_source_claims_or_evidence
test_entailed_inference_can_be_reviewed
test_speculative_inference_cannot_promote_by_default
test_factual_inference_confidence_bounded_by_sources
test_factual_inference_records_rule_or_engine

⸻

22.3 Semantic inference tests

Required tests:

test_semantic_inference_creates_relation_not_fact
test_semantic_cluster_membership_records_confidence
test_semantic_relation_does_not_support_truth_confidence
test_semantic_duplicate_suggestion_requires_review
test_semantic_inference_respects_namespace

⸻

22.4 Reflection tests

Required tests:

test_build_reflection_requires_source
test_build_reflection_preserves_source_claims
test_build_reflection_preserves_source_evidence
test_expand_reflection_returns_sources
test_reflection_confidence_bounded_by_sources
test_reflection_marked_stale_when_source_superseded
test_reflection_excluded_from_context_when_invalidated

⸻

22.5 Derivation graph tests

Required tests:

test_derivation_edge_created_for_inference
test_derivation_trace_returns_root_evidence
test_derivation_trace_detects_missing_source
test_derivation_cycle_rejected
test_source_invalidation_propagates_to_derived_records
test_refresh_queue_created_for_stale_reflection

⸻

22.6 Context pack tests

Required tests:

test_context_pack_includes_active_reflection
test_context_pack_labels_reflection_as_reflection
test_context_pack_excludes_pending_inference_by_default
test_context_pack_includes_validated_inference_when_enabled
test_context_pack_warns_about_stale_reflection
test_context_pack_derivation_metadata_optional

⸻

22.7 CLI tests

Required tests:

test_cli_infer_run_dry_run
test_cli_infer_run_apply
test_cli_infer_list
test_cli_infer_explain
test_cli_rules_list
test_cli_rules_disable_enable
test_cli_reflect_build
test_cli_reflect_expand
test_cli_derivation_trace
test_cli_clusters_build
test_cli_abstractions_expand

⸻

22.8 Migration tests

Required tests:

test_migration_from_m3_to_m4_adds_tables
test_migration_preserves_claims
test_migration_preserves_candidates
test_migration_preserves_semantic_indexes
test_migration_inserts_default_rules
test_migration_does_not_run_inference
test_migration_does_not_build_reflections
test_migration_is_idempotent

⸻

23. Golden M4 Tests

Golden test 1 — Scoped preference reflection

Given active scoped claims:

Claim A:
User prefers concise progress updates.
Claim B:
User prefers comprehensive architecture explanations.

When a reflection is built:

The user prefers response depth to match context: concise for progress updates, comprehensive for architecture/design work.

Expected:

- Reflection has source links to Claim A and Claim B.
- Reflection is expandable.
- Reflection appears in context for architecture/design queries.
- Reflection does not erase the original scoped claims.

⸻

Golden test 2 — Source invalidation

Given:

Reflection ref_001 depends on clm_001 and clm_002.
clm_002 is later superseded.

Expected:

- ref_001 is marked stale or needs_refresh.
- ref_001 is not presented as fresh context.
- derivation trace shows clm_002 caused invalidation.

⸻

Golden test 3 — Semantic relation is not fact

Given two claims:

Aletheia uses context packs.
Aletheia uses memory retrieval.

Semantic inference creates:

These claims are related to local agent memory architecture.

Expected:

- Semantic relation is stored.
- No new factual claim is automatically created.
- Context retrieval may benefit from the relation.
- Truth confidence of either source claim is unchanged.

⸻

Golden test 4 — Factual inference candidate

Given:

Project Aletheia current milestone is M4.
M4 short name is Reasoned Memory.

Factual inference suggests:

Project Aletheia is currently focused on reasoned memory.

Expected:

- Inference candidate is created.
- It is not active by default.
- It has source claim links.
- It can be reviewed and promoted if accepted.

⸻

Golden test 5 — Derivation trace

Given a promoted inference:

clm_100 was promoted from inf_010.
inf_010 was derived from clm_001 and clm_002.
clm_001 and clm_002 link to evt_001.

Expected trace:

clm_100
  ← inf_010
    ← clm_001
      ← evt_001
    ← clm_002
      ← evt_001

⸻

24. Acceptance Criteria

M4 is complete only when all of the following are true.

24.1 Inference acceptance

[ ] Inference runs can be executed.
[ ] Logical inference works deterministically.
[ ] Semantic inference creates relations, not facts.
[ ] Factual inference creates candidates, not active claims.
[ ] Inference candidates have source lineage.
[ ] Inference candidates can be reviewed.
[ ] Inference candidates can be promoted through integrity gates.
[ ] Speculative inferences cannot promote by default.

⸻

24.2 Rule acceptance

[ ] Inference rules can be registered.
[ ] Rules can be enabled and disabled.
[ ] Rule execution is logged.
[ ] Default deterministic rules exist.
[ ] Rules are safe to run repeatedly.

⸻

24.3 Reflection and abstraction acceptance

[ ] Reflections can be built from source claims/evidence.
[ ] Reflections preserve backlinks.
[ ] Reflections are expandable.
[ ] Reflections carry abstraction level.
[ ] Reflection confidence is derived from sources.
[ ] Abstraction records preserve source links.
[ ] Lossless-via-backlinks is the default abstraction policy.

⸻

24.4 Derivation and invalidation acceptance

[ ] Derived records have derivation edges.
[ ] Derivation traces can be inspected.
[ ] Source changes propagate invalidation.
[ ] Stale reflections are marked.
[ ] Invalidated derived memories are excluded from normal context.
[ ] Refresh queue exists for stale derived records.

⸻

24.5 Context acceptance

[ ] Context packs can include active reflections.
[ ] Context packs label inferences/reflections.
[ ] Pending inference candidates are excluded by default.
[ ] Stale or invalidated reflections are not presented as fresh facts.
[ ] Derivation metadata is available in structured output.

⸻

24.6 CLI acceptance

[ ] aletheia infer works.
[ ] aletheia rules works.
[ ] aletheia reflect works.
[ ] aletheia derivation works.
[ ] aletheia clusters works.
[ ] aletheia abstractions works.
[ ] Existing M3 CLI commands still work.

⸻

24.7 Migration acceptance

[ ] M3 database migrates to M4.
[ ] Migration is idempotent.
[ ] Existing memories remain retrievable.
[ ] Existing context packs still work.
[ ] Default rules are inserted.
[ ] No inference or reflection is created automatically during migration.

⸻

25. M4 Demo Script

This should be the official M4 demo.

⸻

Step 1 — Initialize or migrate

aletheia migrate --db ./aletheia.db

⸻

Step 2 — Ensure project exists

aletheia projects create \
  --db ./aletheia.db \
  --namespace user/default \
  --id aletheia \
  --title "Aletheia Memory Library"

⸻

Step 3 — Store scoped claims

aletheia remember \
  --db ./aletheia.db \
  --namespace user/default \
  --type preference \
  --subject user \
  --predicate prefers_response_style \
  --object "concise progress updates"
aletheia claims scope clm_001 \
  --db ./aletheia.db \
  --type contextual \
  --applies-when progress_update \
  --reason "Concise preference applies to progress updates."
aletheia remember \
  --db ./aletheia.db \
  --namespace user/default \
  --type preference \
  --subject user \
  --predicate prefers_response_style \
  --object "comprehensive architecture explanations"
aletheia claims scope clm_002 \
  --db ./aletheia.db \
  --type contextual \
  --applies-when architecture_or_design_request \
  --reason "Comprehensive preference applies to architecture/design requests."

⸻

Step 4 — Build a reflection

aletheia reflect build \
  --db ./aletheia.db \
  --namespace user/default \
  --title "Context-sensitive response depth" \
  --claims clm_001,clm_002 \
  --text "User prefers concise progress updates and comprehensive architecture/design explanations." \
  --reason "Combines two scoped response-style preferences."

Expected:

Reflection created:
id: ref_001
sources:
  clm_001
  clm_002

⸻

Step 5 — Expand reflection

aletheia reflect expand ref_001 \
  --db ./aletheia.db

Expected:

Reflection:
User prefers concise progress updates and comprehensive architecture/design explanations.
Source claims:
- clm_001: concise progress updates
- clm_002: comprehensive architecture explanations
Evidence:
- evt_...

⸻

Step 6 — Run inference

aletheia infer run \
  --db ./aletheia.db \
  --namespace user/default \
  --project aletheia \
  --engines logical,semantic,factual \
  --apply

Expected:

Inference run created.
Logical inferences: scope/currentness
Semantic relations: related preference cluster
Factual candidates: any conservative project-level derived candidates

⸻

Step 7 — Trace derivation

aletheia derivation trace ref_001 \
  --db ./aletheia.db \
  --type reflection

Expected:

ref_001
  derives from clm_001
  derives from clm_002
  both trace back to source evidence

⸻

Step 8 — Generate context

aletheia context \
  --db ./aletheia.db \
  --namespace user/default \
  --project aletheia \
  --query "Write the M4 contract." \
  --mode hybrid

Expected context includes:

- User prefers comprehensive architecture/design explanations.
- Reflection: user prefers response depth to match context.

Expected context does not include:

- Pending unreviewed inferences as facts.

⸻

Step 9 — Supersede source claim

aletheia remember \
  --db ./aletheia.db \
  --namespace user/default \
  --type preference \
  --subject user \
  --predicate prefers_response_style \
  --object "concise progress updates but detailed milestone contracts"
aletheia claims supersede clm_001 clm_003 \
  --db ./aletheia.db \
  --reason "Newer preference refines prior progress-update memory."

⸻

Step 10 — Invalidate derived records

aletheia derivation invalidated \
  --db ./aletheia.db \
  --namespace user/default

Expected:

ref_001 marked stale or queued for refresh because source clm_001 was superseded.

⸻

26. M4 Implementation Checklist

Inference core

[ ] Add InferenceRun model
[ ] Add InferenceCandidate model
[ ] Add InferenceDecision model
[ ] Define InferenceEngine interface
[ ] Implement run_inference()
[ ] Implement list_inferences()
[ ] Implement review_inference()
[ ] Implement promote_inference()
[ ] Implement reject_inference()
[ ] Implement explain_inference()

⸻

Rules

[ ] Add InferenceRule model
[ ] Add RuleRegistry
[ ] Add define_rule()
[ ] Add run_rule()
[ ] Insert default deterministic rules
[ ] Log rule execution
[ ] Add rule enable/disable

⸻

Logical inference

[ ] Currentness inference
[ ] Supersession inference
[ ] Temporal validity inference
[ ] Scope match inference
[ ] Conflict status inference
[ ] Dependency invalidation inference

⸻

Semantic inference

[ ] Add SemanticRelation model
[ ] Add SemanticCluster model
[ ] Implement semantic relation creation
[ ] Implement cluster creation
[ ] Ensure semantic relations do not affect truth confidence
[ ] Integrate semantic hints with retrieval only

⸻

Factual inference

[ ] Add conservative factual inference engine
[ ] Create inference candidates only
[ ] Assign inference strength
[ ] Bound confidence by source confidence
[ ] Prevent speculative promotion by default

⸻

Reflection and abstraction

[ ] Add Reflection model
[ ] Add AbstractionRecord model
[ ] Implement build_reflection()
[ ] Implement expand_reflection()
[ ] Implement create_abstraction()
[ ] Store abstraction levels
[ ] Preserve source backlinks

⸻

Derivation and invalidation

[ ] Add DerivationEdge model
[ ] Implement trace_derivation()
[ ] Add invalidation events
[ ] Add refresh queue
[ ] Implement invalidate_derived()
[ ] Integrate invalidation with claim supersession/rejection/deletion

⸻

Context pack integration

[ ] Add reflection support to context pack
[ ] Add inference labeling
[ ] Exclude pending inferences by default
[ ] Exclude invalidated derived records
[ ] Add optional derivation metadata
[ ] Add stale reflection warnings

⸻

CLI

[ ] Add infer command group
[ ] Add rules command group
[ ] Add reflect command group
[ ] Add derivation command group
[ ] Add clusters command group
[ ] Add abstractions command group

⸻

Migration

[ ] Add schema version 0.5.0
[ ] Add migration from 0.4.x
[ ] Add M4 tables
[ ] Insert default rules
[ ] Ensure no inference runs during migration
[ ] Ensure no reflections created during migration
[ ] Add migration tests

⸻

Tests

[ ] Logical inference tests
[ ] Semantic inference tests
[ ] Factual inference tests
[ ] Reflection tests
[ ] Abstraction tests
[ ] Derivation graph tests
[ ] Invalidation tests
[ ] Context pack tests
[ ] CLI tests
[ ] Golden M4 tests

⸻

27. M4 Definition of Done

M4 is done when this statement is true:

Aletheia can reason over memory while preserving the boundary between fact, inference, semantic relation, and abstraction.

More practically, M4 is complete when Aletheia can do all of this:

- Run deterministic logical inference.
- Create factual inference candidates without auto-trusting them.
- Create semantic relations without treating them as facts.
- Build source-backed reflections.
- Expand reflections back to evidence.
- Trace derivation lineage.
- Invalidate derived memories when sources change.
- Include valid reflections in context.
- Exclude pending or invalidated inferences from normal context.
- Explain why an inference or reflection exists.

M4 is where Aletheia begins to reason.
But it must reason like a disciplined archivist, not like a dreamer.