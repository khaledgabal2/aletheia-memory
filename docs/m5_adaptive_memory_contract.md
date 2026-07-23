Aletheia M5 Contract

Milestone: Adaptive Memory, Evaluation, and Self-Improvement

⸻

1. Milestone Summary

M0 proved that Aletheia can remember.
M1 proved that Aletheia can recall across sessions and projects.
M2 proved that Aletheia can maintain trust through confidence, contradiction, decay, and curation.
M3 proved that Aletheia can ingest raw material and form candidate memories.
M4 proved that Aletheia can reason, infer, reflect, and preserve derivation lineage.
M5 must prove that Aletheia can improve itself safely over time.

M5 is where Aletheia becomes adaptive.

But the core law remains:

Aletheia may improve retrieval, curation, ranking, procedural memory, and policies from feedback and evaluations. It must not silently rewrite truth.

M0 = Remember
M1 = Recall
M2 = Trust
M3 = Understand
M4 = Reason
M5 = Improve

The core M5 promise:

Aletheia can learn from user feedback, task outcomes, retrieval usage, evaluation tests, and curation history; propose safer and better memory policies; improve retrieval and context packing; update procedural memory through reviewable changes; and roll back any learned behavior without corrupting evidence or canonical facts.

M5 is not autonomous free-form self-modification.
It is governed self-improvement.

⸻

2. M5 Name

M5 — Adaptive Memory

Fuller name:

M5 — Adaptive Memory, Evaluation, and Self-Improvement

Recommended short name:

M5 — Adaptive Memory

⸻

3. M5 Contract Status

milestone: M5
name: Adaptive Memory
depends_on: M4
version_target: 0.6.0
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
job_queue_required: yes
primary_theme: governed_self_improvement

Important clarification:

M5 may support LLM-assisted procedure refinement.
M5 may support learned retrieval weighting.
M5 may support automated curation proposals.
M5 may support scheduled local jobs.
M5 must not require LLMs.
M5 must not require cloud telemetry.
M5 must not silently modify user-confirmed facts.
M5 must not treat the agent’s own repetition as evidence.

⸻

4. M4 Assumptions

M5 assumes M4 already provides:

- Evidence ledger
- Claim store
- Candidate memory system
- Confidence engine
- Half-life decay
- Feedback system
- Conflict families
- Claim scoping
- Curation lifecycle
- Session and project memory
- Semantic indexing interface
- Hybrid retrieval
- Entity and category labels
- Inference candidates
- Logical, semantic, and factual inference
- Reflections and abstractions
- Derivation graph
- Invalidation and refresh queue
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
  - infer
  - rules
  - reflect
  - derivation
  - clusters
  - abstractions

M5 builds on this by adding:

- outcome tracking
- evaluation harness
- retrieval policy optimization
- procedural memory updates
- governed learning proposals
- local job queue
- memory health reports
- rollback support

⸻

5. M5 Primary Objective

M5 must make this flow work reliably:

memory = Memory.open("./aletheia.db")
context = memory.context_pack(
    namespace="user/default",
    project_id="aletheia",
    query="Write the next milestone contract.",
    retrieval_mode="hybrid",
    record_usage=True,
)
memory.record_outcome(
    namespace="user/default",
    task_id="task_001",
    outcome="success",
    used_context_pack_id=context.id,
    note="Context pack included the correct project state and style preferences.",
)
eval_run = memory.run_evaluation(
    namespace="user/default",
    eval_set_id="eval_aletheia_contracts",
)
proposal = memory.optimize_retrieval(
    namespace="user/default",
    eval_set_id="eval_aletheia_contracts",
    dry_run=False,
)
memory.review_policy_proposal(
    proposal_id=proposal.id,
    decision="approve",
    reason="Improves project-memory recall without increasing disputed-memory leakage.",
)
memory.apply_policy_proposal(
    proposal_id=proposal.id,
    reason="Accepted after evaluation gate.",
)

Expected behavior:

- Aletheia records which memories were used.
- Task outcome is stored separately from truth confidence.
- Evaluation run measures retrieval/context-pack quality.
- Optimizer proposes a new ranking policy.
- Proposal is reviewable and auditable.
- Policy update is versioned.
- Previous policy can be rolled back.
- No canonical facts are rewritten.

⸻

6. M5 Non-Negotiable Principles

6.1 Self-improvement is proposal-first

Aletheia may suggest changes to:

retrieval weights
context-pack policy
curation thresholds
half-life defaults
procedure memories
category rules
reflection refresh policies

But by default, these changes must be created as:

policy proposals
procedure proposals
curation proposals

Not silently applied behavior.

⸻

6.2 Outcomes are not facts

If a task succeeds, that does not mean every memory used in the task was true.

Task outcome may affect:

retrieval salience
ranking usefulness
procedure usefulness
context-pack policy

Task outcome must not directly confirm truth unless explicit evidence supports that confirmation.

⸻

6.3 User correction beats learned behavior

If user correction conflicts with learned ranking, learned procedure, inferred preference, or optimization result:

user correction wins

No learned system should override explicit user correction.

⸻

6.4 No self-reinforcing truth loops

Aletheia must not increase truth confidence simply because:

the assistant repeated a memory
the memory was retrieved often
the memory appeared in a context pack
the model generated the same claim again

Repetition is not evidence.

⸻

6.5 Evaluation gates are mandatory for learned policies

Before a learned retrieval, curation, or context policy becomes active, it must pass an evaluation gate.

The gate should check at minimum:

retrieval quality
conflict leakage
stale-memory leakage
provenance preservation
token efficiency
regression against golden tests

⸻

6.6 Every learned behavior must be versioned

Any learned policy must have:

policy_id
version
created_at
source signals
evaluation results
approval decision
rollback target
audit trail

No anonymous behavioral drift.

⸻

6.7 Local-first learning

By default, all learning data stays local.

M5 must not introduce:

external telemetry
cloud analytics
remote training
automatic upload of memory data

unless explicitly configured by the developer/user.

⸻

6.8 Rollback is required

If a learned policy makes Aletheia worse, it must be possible to roll back.

Rollback must apply to:

retrieval policies
context-pack policies
procedure versions
curation policies
half-life policy updates

Rollback must not delete the audit trail.

⸻

7. M5 Scope

In Scope

M5 includes:

1. Memory usage logging
2. Context-pack usage tracking
3. Task outcome model
4. Retrieval judgment model
5. Evaluation set model
6. Evaluation case model
7. Evaluation runner
8. Retrieval metrics
9. Context-pack metrics
10. Conflict/staleness leakage metrics
11. Ranking policy versioning
12. Retrieval optimization proposals
13. Context-pack policy proposals
14. Curation policy proposals
15. Half-life policy proposals
16. Procedure memory versioning
17. Procedure update proposals
18. Procedure evaluation gates
19. Local job queue
20. Memory health reports
21. Learning run records
22. Rollback records
23. Policy application history
24. CLI support for evaluation, optimization, learning, jobs, health, and rollback
25. Migration from M4 to M5
26. Golden adaptive-memory tests

⸻

Out of Scope

M5 explicitly excludes:

External telemetry by default
Cloud sync
Multi-agent shared governance
Enterprise permission model
HTTP daemon
MCP server
Dashboard
Automatic fine-tuning
Autonomous deletion of evidence
Autonomous rewriting of canonical facts
Automatic promotion of speculative inferences
Unreviewed changes to safety or privacy policies

M5 can create the local substrate that later service/API layers use, but it should not require those layers.

⸻

8. M5 Deliverables

8.1 Library Deliverables

- MemoryUsageEvent model
- ContextUsageEvent model
- TaskOutcome model
- RetrievalJudgment model
- EvaluationSet model
- EvaluationCase model
- EvaluationRun model
- EvaluationMetric model
- RankingPolicy model
- RankingPolicyVersion model
- PolicyProposal model
- ProcedureVersion model
- ProcedureUpdateProposal model
- LearningRun model
- OptimizationRun model
- MemoryHealthReport model
- LocalJob model
- RollbackRecord model
- EvaluationRunner
- RetrievalOptimizer
- ContextPolicyOptimizer
- ProcedureOptimizer
- CurationPolicyOptimizer
- LearningGate
- JobQueue
- MemoryHealthAnalyzer

⸻

8.2 Storage Deliverables

M5 adds:

- memory_usage_events
- context_usage_events
- task_outcomes
- retrieval_judgments
- evaluation_sets
- evaluation_cases
- evaluation_runs
- evaluation_results
- evaluation_metrics
- ranking_policies
- ranking_policy_versions
- context_pack_policies
- policy_proposals
- policy_application_history
- procedure_versions
- procedure_update_proposals
- learning_runs
- optimization_runs
- learning_gate_results
- local_jobs
- memory_health_snapshots
- rollback_records

⸻

8.3 CLI Deliverables

M5 adds or improves:

aletheia usage
aletheia outcome
aletheia eval
aletheia optimize
aletheia learn
aletheia policies
aletheia procedures
aletheia jobs
aletheia health
aletheia rollback

Existing M0–M4 commands must remain valid.

⸻

8.4 Test Deliverables

- Usage logging tests
- Outcome tracking tests
- Evaluation set tests
- Evaluation runner tests
- Retrieval metric tests
- Context-pack metric tests
- Policy proposal tests
- Policy application tests
- Procedure update tests
- Learning gate tests
- Rollback tests
- Job queue tests
- Memory health tests
- CLI tests
- Migration tests
- Golden adaptive-memory tests

⸻

9. Public API Contract

⸻

9.1 memory.record_usage()

Purpose

Record that a memory, claim, reflection, inference, or context pack was used.

Signature

def record_usage(
    self,
    namespace: str,
    *,
    target_id: str,
    target_type: str,
    usage_type: str,
    query: str | None = None,
    session_id: str | None = None,
    project_id: str | None = None,
    context_pack_id: str | None = None,
    rank: int | None = None,
    score: float | None = None,
    metadata: dict | None = None,
) -> MemoryUsageEvent:
    ...

Allowed target_type

claim
candidate_claim
inference
reflection
abstraction
context_pack
procedure
policy

Allowed usage_type

retrieved
included_in_context
used_by_agent
ignored
expanded
audited
corrected
confirmed
rejected

Required behavior

record_usage() must:

- Persist usage event.
- Preserve query/session/project context.
- Not change truth confidence directly.
- Optionally affect retrieval salience through later learning jobs.
- Write audit event if usage_type materially affects memory state.

⸻

9.2 memory.record_outcome()

Purpose

Record the outcome of a task, response, workflow, or agent action.

Signature

def record_outcome(
    self,
    namespace: str,
    *,
    task_id: str,
    outcome: str,
    used_context_pack_id: str | None = None,
    session_id: str | None = None,
    project_id: str | None = None,
    user_feedback: str | None = None,
    score: float | None = None,
    note: str | None = None,
    metadata: dict | None = None,
) -> TaskOutcome:
    ...

Allowed outcomes

success
partial_success
failure
user_corrected
user_rejected
user_confirmed
irrelevant_context
missing_context
stale_context
conflicting_context
unsafe_context
unknown

Required behavior

record_outcome() must:

- Store task outcome.
- Link to context pack when provided.
- Link to session/project when provided.
- Not directly confirm every memory in the context pack.
- Create learning signals for retrieval/procedure/context policy.
- Write audit event.

Important rule

success increases usefulness evidence, not truth evidence.

⸻

9.3 memory.judge_retrieval()

Purpose

Record explicit judgment about retrieval quality.

Signature

def judge_retrieval(
    self,
    namespace: str,
    *,
    query: str,
    result_id: str,
    result_type: str,
    judgment: str,
    judge: str = "user",
    reason: str | None = None,
    expected_rank: int | None = None,
    session_id: str | None = None,
    project_id: str | None = None,
) -> RetrievalJudgment:
    ...

Allowed judgments

relevant
irrelevant
missing
too_stale
conflicting
wrong
useful
not_useful
should_rank_higher
should_rank_lower

Required behavior

- Store judgment.
- Link judgment to query and result.
- Affect retrieval salience/ranking only through governed learning.
- If judgment is wrong/conflicting, optionally create M2 feedback or conflict workflow.

⸻

9.4 memory.create_eval_set()

Purpose

Create a named local evaluation set.

Signature

def create_eval_set(
    self,
    namespace: str,
    *,
    name: str,
    description: str | None = None,
    project_id: str | None = None,
    metadata: dict | None = None,
) -> EvaluationSet:
    ...

EvaluationSet model

@dataclass
class EvaluationSet:
    id: str
    namespace: str
    name: str
    description: str | None
    project_id: str | None
    created_at: datetime
    updated_at: datetime
    metadata: dict

⸻

9.5 memory.add_eval_case()

Purpose

Add a retrieval/context-pack test case.

Signature

def add_eval_case(
    self,
    eval_set_id: str,
    *,
    query: str,
    expected_claim_ids: list[str] | None = None,
    expected_reflection_ids: list[str] | None = None,
    forbidden_claim_ids: list[str] | None = None,
    expected_sections: dict | None = None,
    project_id: str | None = None,
    session_id: str | None = None,
    tags: list[str] | None = None,
    note: str | None = None,
) -> EvaluationCase:
    ...

EvaluationCase model

@dataclass
class EvaluationCase:
    id: str
    eval_set_id: str
    namespace: str
    query: str
    expected_claim_ids: list[str]
    expected_reflection_ids: list[str]
    forbidden_claim_ids: list[str]
    expected_sections: dict
    project_id: str | None
    session_id: str | None
    tags: list[str]
    note: str | None
    created_at: datetime

Example

memory.add_eval_case(
    eval_set_id="eval_aletheia_contracts",
    query="Write an architecture contract.",
    expected_claim_ids=["clm_design_detail_preference"],
    forbidden_claim_ids=["clm_concise_progress_only"],
    expected_sections={
        "procedural_memory": ["architecture contract detail preference"]
    },
)

⸻

9.6 memory.run_evaluation()

Purpose

Run an evaluation set against current retrieval and context-pack behavior.

Signature

def run_evaluation(
    self,
    namespace: str,
    *,
    eval_set_id: str,
    policy_version_id: str | None = None,
    retrieval_mode: str = "hybrid",
    context_pack: bool = True,
    limit: int = 10,
    dry_run: bool = False,
) -> EvaluationRun:
    ...

Required behavior

run_evaluation() must compute:

recall_at_k
precision_at_k
mrr
forbidden_memory_leak_rate
disputed_memory_leak_rate
stale_memory_leak_rate
provenance_preservation_rate
context_section_accuracy
token_efficiency
average_latency_ms

EvaluationRun model

@dataclass
class EvaluationRun:
    id: str
    namespace: str
    eval_set_id: str
    policy_version_id: str | None
    retrieval_mode: str
    case_count: int
    metrics: dict
    passed: bool
    created_at: datetime
    metadata: dict

⸻

9.7 memory.optimize_retrieval()

Purpose

Propose an improved retrieval ranking policy based on evaluation results and usage history.

Signature

def optimize_retrieval(
    self,
    namespace: str,
    *,
    eval_set_id: str | None = None,
    baseline_policy_version_id: str | None = None,
    objective: str = "balanced",
    dry_run: bool = True,
    max_trials: int = 50,
    constraints: dict | None = None,
) -> OptimizationRun:
    ...

Allowed objectives

balanced
maximize_recall
maximize_precision
minimize_conflict_leakage
minimize_stale_leakage
maximize_token_efficiency
project_recall
procedure_recall

Required behavior

optimize_retrieval() must:

- Use local data only.
- Compare against baseline policy.
- Produce candidate ranking policy versions.
- Evaluate proposed policy.
- Reject proposals that leak disputed/rejected/superseded memories.
- Store optimization run.
- Create policy proposal when dry_run=False.
- Not automatically activate the new policy.

⸻

9.8 RankingPolicy

Purpose

Represent retrieval scoring weights and filtering behavior.

Model

@dataclass
class RankingPolicy:
    id: str
    namespace: str | None
    name: str
    active_version_id: str | None
    created_at: datetime
    updated_at: datetime

Version model

@dataclass
class RankingPolicyVersion:
    id: str
    policy_id: str
    version: int
    weights: dict
    filters: dict
    thresholds: dict
    created_by: str
    created_at: datetime
    evaluation_summary: dict | None
    status: str

Version statuses

draft
proposed
active
superseded
rejected
rolled_back

⸻

9.9 memory.propose_policy_update()

Purpose

Create a reviewable policy update.

Signature

def propose_policy_update(
    self,
    namespace: str,
    *,
    policy_type: str,
    target_policy_id: str | None,
    proposed_config: dict,
    reason: str,
    source_run_id: str | None = None,
    evaluation_run_id: str | None = None,
) -> PolicyProposal:
    ...

Allowed policy_type

ranking
context_pack
curation
half_life
reflection_refresh
candidate_promotion
inference_promotion

PolicyProposal model

@dataclass
class PolicyProposal:
    id: str
    namespace: str
    policy_type: str
    target_policy_id: str | None
    proposed_config: dict
    reason: str
    source_run_id: str | None
    evaluation_run_id: str | None
    status: str
    created_at: datetime
    reviewed_at: datetime | None
    reviewer: str | None
    review_note: str | None

Proposal statuses

draft
pending_review
approved
rejected
applied
superseded
rolled_back

⸻

9.10 memory.review_policy_proposal()

Purpose

Approve or reject a policy proposal.

Signature

def review_policy_proposal(
    self,
    proposal_id: str,
    *,
    decision: str,
    reason: str,
    reviewer: str = "user",
) -> PolicyProposal:
    ...

Allowed decisions

approve
reject
defer
request_changes

Required behavior

- Store review decision.
- Write audit event.
- Do not apply policy automatically unless explicitly requested elsewhere.

⸻

9.11 memory.apply_policy_proposal()

Purpose

Activate an approved policy proposal.

Signature

def apply_policy_proposal(
    self,
    proposal_id: str,
    *,
    reason: str,
    applied_by: str = "user",
    require_evaluation_pass: bool = True,
) -> PolicyApplicationRecord:
    ...

Required behavior

apply_policy_proposal() must:

- Require proposal status approved.
- Verify evaluation gate if require_evaluation_pass=True.
- Create new policy version if needed.
- Mark previous version superseded.
- Activate new policy version.
- Write policy application history.
- Create rollback record target.
- Write audit event.

Application must fail if:

- Proposal is rejected.
- Proposal has no evaluation result and evaluation is required.
- Evaluation shows increased conflict leakage above threshold.
- Evaluation shows forbidden-memory leakage above threshold.

⸻

9.12 memory.rollback_policy()

Purpose

Rollback active policy to an earlier version.

Signature

def rollback_policy(
    self,
    namespace: str,
    *,
    policy_id: str,
    target_version_id: str,
    reason: str,
    rolled_back_by: str = "user",
) -> RollbackRecord:
    ...

Required behavior

- Set target version as active.
- Mark rolled-back version accordingly.
- Preserve all policy history.
- Write rollback record.
- Write audit event.

⸻

9.13 memory.propose_procedure_update()

Purpose

Propose an update to procedural memory based on feedback, outcomes, evaluations, or reflections.

Signature

def propose_procedure_update(
    self,
    namespace: str,
    *,
    procedure_claim_id: str | None = None,
    title: str,
    proposed_text: str,
    reason: str,
    source_ids: list[str] | None = None,
    source_type: str | None = None,
    evaluation_run_id: str | None = None,
    require_review: bool = True,
) -> ProcedureUpdateProposal:
    ...

ProcedureUpdateProposal model

@dataclass
class ProcedureUpdateProposal:
    id: str
    namespace: str
    procedure_claim_id: str | None
    title: str
    proposed_text: str
    reason: str
    source_ids: list[str]
    source_type: str | None
    evaluation_run_id: str | None
    status: str
    created_at: datetime
    reviewed_at: datetime | None
    reviewer: str | None
    review_note: str | None

Required behavior

Procedure proposals must:

- Preserve sources.
- Be reviewable.
- Be versioned when applied.
- Not override higher-priority user/system instructions.
- Not modify safety/privacy behavior without explicit approval.

⸻

9.14 memory.apply_procedure_update()

Purpose

Apply an approved procedure update.

Signature

def apply_procedure_update(
    self,
    proposal_id: str,
    *,
    reason: str,
    applied_by: str = "user",
) -> ProcedureVersion:
    ...

Required behavior

- Require approved proposal.
- Create new procedure version.
- Link to source proposal.
- Supersede previous procedure version if applicable.
- Update associated claim/reflection/procedure memory.
- Write audit event.
- Support rollback.

⸻

9.15 memory.run_learning()

Purpose

Run a governed learning cycle.

Signature

def run_learning(
    self,
    namespace: str,
    *,
    project_id: str | None = None,
    learning_targets: list[str] | None = None,
    eval_set_id: str | None = None,
    dry_run: bool = True,
    max_proposals: int = 10,
) -> LearningRun:
    ...

Allowed learning targets

retrieval_policy
context_pack_policy
curation_policy
half_life_policy
procedure_memory
reflection_refresh
candidate_promotion_policy

Required behavior

run_learning() must:

- Gather usage, feedback, outcomes, evaluation results, and curation history.
- Produce proposals, not silent changes.
- Run evaluation gates where possible.
- Store learning run.
- Write audit event.

LearningRun model

@dataclass
class LearningRun:
    id: str
    namespace: str
    project_id: str | None
    learning_targets: list[str]
    eval_set_id: str | None
    dry_run: bool
    proposals_created: list[str]
    warnings: list[str]
    created_at: datetime
    metadata: dict

⸻

9.16 memory.enqueue_job()

Purpose

Schedule a local job for curation, decay, evaluation, indexing, inference, or learning.

Signature

def enqueue_job(
    self,
    namespace: str,
    *,
    job_type: str,
    payload: dict,
    priority: float = 0.5,
    run_after: datetime | None = None,
) -> LocalJob:
    ...

Allowed job types

recompute_confidence
run_decay
detect_conflicts
curate
refresh_reflections
run_inference
index_semantic
run_evaluation
optimize_retrieval
run_learning
memory_health_check

⸻

9.17 memory.run_jobs()

Purpose

Run pending local jobs synchronously.

Signature

def run_jobs(
    self,
    *,
    namespace: str | None = None,
    job_type: str | None = None,
    max_jobs: int = 10,
) -> list[LocalJob]:
    ...

Required behavior

- Run due jobs.
- Mark completed/failed.
- Store error messages.
- Retry only according to job policy.
- Write audit events for state-changing jobs.

⸻

9.18 memory.health_report()

Purpose

Generate a local memory health report.

Signature

def health_report(
    self,
    namespace: str,
    *,
    project_id: str | None = None,
    include_recommendations: bool = True,
) -> MemoryHealthReport:
    ...

Required metrics

active_claim_count
core_memory_count
candidate_count
pending_review_count
unresolved_conflict_count
stale_memory_count
invalidated_derived_count
orphaned_evidence_count
unindexed_claim_count
low_confidence_active_count
high_salience_low_confidence_count
retrieval_judgment_count
recent_failure_count
last_evaluation_score

HealthReport model

@dataclass
class MemoryHealthReport:
    id: str
    namespace: str
    project_id: str | None
    generated_at: datetime
    metrics: dict
    warnings: list[str]
    recommendations: list[str]

⸻

10. Storage Contract

10.1 Schema version

M5 updates schema version to:

0.6.0

⸻

10.2 Required new tables

memory_usage_events

CREATE TABLE memory_usage_events (
    id TEXT PRIMARY KEY,
    namespace TEXT NOT NULL,
    target_id TEXT NOT NULL,
    target_type TEXT NOT NULL,
    usage_type TEXT NOT NULL,
    query TEXT,
    session_id TEXT,
    project_id TEXT,
    context_pack_id TEXT,
    rank INTEGER,
    score REAL,
    created_at TEXT NOT NULL,
    metadata_json TEXT
);

⸻

context_usage_events

CREATE TABLE context_usage_events (
    id TEXT PRIMARY KEY,
    namespace TEXT NOT NULL,
    context_pack_id TEXT NOT NULL,
    query TEXT NOT NULL,
    session_id TEXT,
    project_id TEXT,
    item_count INTEGER,
    token_estimate INTEGER,
    created_at TEXT NOT NULL,
    metadata_json TEXT
);

⸻

task_outcomes

CREATE TABLE task_outcomes (
    id TEXT PRIMARY KEY,
    namespace TEXT NOT NULL,
    task_id TEXT NOT NULL,
    outcome TEXT NOT NULL,
    used_context_pack_id TEXT,
    session_id TEXT,
    project_id TEXT,
    user_feedback TEXT,
    score REAL,
    note TEXT,
    created_at TEXT NOT NULL,
    metadata_json TEXT
);

⸻

retrieval_judgments

CREATE TABLE retrieval_judgments (
    id TEXT PRIMARY KEY,
    namespace TEXT NOT NULL,
    query TEXT NOT NULL,
    result_id TEXT NOT NULL,
    result_type TEXT NOT NULL,
    judgment TEXT NOT NULL,
    judge TEXT NOT NULL,
    reason TEXT,
    expected_rank INTEGER,
    session_id TEXT,
    project_id TEXT,
    created_at TEXT NOT NULL,
    metadata_json TEXT
);

⸻

evaluation_sets

CREATE TABLE evaluation_sets (
    id TEXT PRIMARY KEY,
    namespace TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    project_id TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    metadata_json TEXT
);

⸻

evaluation_cases

CREATE TABLE evaluation_cases (
    id TEXT PRIMARY KEY,
    eval_set_id TEXT NOT NULL,
    namespace TEXT NOT NULL,
    query TEXT NOT NULL,
    expected_claim_ids_json TEXT,
    expected_reflection_ids_json TEXT,
    forbidden_claim_ids_json TEXT,
    expected_sections_json TEXT,
    project_id TEXT,
    session_id TEXT,
    tags_json TEXT,
    note TEXT,
    created_at TEXT NOT NULL
);

⸻

evaluation_runs

CREATE TABLE evaluation_runs (
    id TEXT PRIMARY KEY,
    namespace TEXT NOT NULL,
    eval_set_id TEXT NOT NULL,
    policy_version_id TEXT,
    retrieval_mode TEXT NOT NULL,
    case_count INTEGER NOT NULL,
    passed INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    metrics_json TEXT NOT NULL,
    metadata_json TEXT
);

⸻

evaluation_results

CREATE TABLE evaluation_results (
    id TEXT PRIMARY KEY,
    evaluation_run_id TEXT NOT NULL,
    evaluation_case_id TEXT NOT NULL,
    passed INTEGER NOT NULL,
    retrieved_ids_json TEXT,
    context_pack_id TEXT,
    metrics_json TEXT NOT NULL,
    failure_reasons_json TEXT,
    created_at TEXT NOT NULL
);

⸻

evaluation_metrics

CREATE TABLE evaluation_metrics (
    id TEXT PRIMARY KEY,
    evaluation_run_id TEXT NOT NULL,
    metric_name TEXT NOT NULL,
    metric_value REAL NOT NULL,
    threshold REAL,
    passed INTEGER,
    created_at TEXT NOT NULL
);

⸻

ranking_policies

CREATE TABLE ranking_policies (
    id TEXT PRIMARY KEY,
    namespace TEXT,
    name TEXT NOT NULL,
    active_version_id TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

⸻

ranking_policy_versions

CREATE TABLE ranking_policy_versions (
    id TEXT PRIMARY KEY,
    policy_id TEXT NOT NULL,
    version INTEGER NOT NULL,
    weights_json TEXT NOT NULL,
    filters_json TEXT,
    thresholds_json TEXT,
    created_by TEXT NOT NULL,
    status TEXT NOT NULL,
    evaluation_summary_json TEXT,
    created_at TEXT NOT NULL
);

⸻

context_pack_policies

CREATE TABLE context_pack_policies (
    id TEXT PRIMARY KEY,
    namespace TEXT,
    name TEXT NOT NULL,
    active_version_id TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

⸻

policy_proposals

CREATE TABLE policy_proposals (
    id TEXT PRIMARY KEY,
    namespace TEXT NOT NULL,
    policy_type TEXT NOT NULL,
    target_policy_id TEXT,
    proposed_config_json TEXT NOT NULL,
    reason TEXT NOT NULL,
    source_run_id TEXT,
    evaluation_run_id TEXT,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    reviewed_at TEXT,
    reviewer TEXT,
    review_note TEXT
);

⸻

policy_application_history

CREATE TABLE policy_application_history (
    id TEXT PRIMARY KEY,
    namespace TEXT NOT NULL,
    proposal_id TEXT NOT NULL,
    policy_type TEXT NOT NULL,
    old_version_id TEXT,
    new_version_id TEXT NOT NULL,
    reason TEXT NOT NULL,
    applied_by TEXT NOT NULL,
    created_at TEXT NOT NULL
);

⸻

procedure_versions

CREATE TABLE procedure_versions (
    id TEXT PRIMARY KEY,
    namespace TEXT NOT NULL,
    procedure_claim_id TEXT,
    version INTEGER NOT NULL,
    title TEXT NOT NULL,
    text TEXT NOT NULL,
    status TEXT NOT NULL,
    source_proposal_id TEXT,
    created_at TEXT NOT NULL,
    metadata_json TEXT
);

⸻

procedure_update_proposals

CREATE TABLE procedure_update_proposals (
    id TEXT PRIMARY KEY,
    namespace TEXT NOT NULL,
    procedure_claim_id TEXT,
    title TEXT NOT NULL,
    proposed_text TEXT NOT NULL,
    reason TEXT NOT NULL,
    source_ids_json TEXT,
    source_type TEXT,
    evaluation_run_id TEXT,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    reviewed_at TEXT,
    reviewer TEXT,
    review_note TEXT
);

⸻

learning_runs

CREATE TABLE learning_runs (
    id TEXT PRIMARY KEY,
    namespace TEXT NOT NULL,
    project_id TEXT,
    learning_targets_json TEXT NOT NULL,
    eval_set_id TEXT,
    dry_run INTEGER NOT NULL,
    proposals_created_json TEXT,
    warnings_json TEXT,
    created_at TEXT NOT NULL,
    metadata_json TEXT
);

⸻

optimization_runs

CREATE TABLE optimization_runs (
    id TEXT PRIMARY KEY,
    namespace TEXT NOT NULL,
    optimization_type TEXT NOT NULL,
    objective TEXT NOT NULL,
    baseline_policy_version_id TEXT,
    eval_set_id TEXT,
    trial_count INTEGER NOT NULL,
    best_metrics_json TEXT,
    proposal_id TEXT,
    dry_run INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    metadata_json TEXT
);

⸻

learning_gate_results

CREATE TABLE learning_gate_results (
    id TEXT PRIMARY KEY,
    namespace TEXT NOT NULL,
    proposal_id TEXT NOT NULL,
    gate_type TEXT NOT NULL,
    passed INTEGER NOT NULL,
    metrics_json TEXT,
    failure_reasons_json TEXT,
    created_at TEXT NOT NULL
);

⸻

local_jobs

CREATE TABLE local_jobs (
    id TEXT PRIMARY KEY,
    namespace TEXT,
    job_type TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    priority REAL NOT NULL DEFAULT 0.5,
    status TEXT NOT NULL DEFAULT 'pending',
    run_after TEXT,
    attempts INTEGER NOT NULL DEFAULT 0,
    max_attempts INTEGER NOT NULL DEFAULT 3,
    last_error TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

Allowed job statuses:

pending
running
completed
failed
cancelled
deferred

⸻

memory_health_snapshots

CREATE TABLE memory_health_snapshots (
    id TEXT PRIMARY KEY,
    namespace TEXT NOT NULL,
    project_id TEXT,
    metrics_json TEXT NOT NULL,
    warnings_json TEXT,
    recommendations_json TEXT,
    generated_at TEXT NOT NULL
);

⸻

rollback_records

CREATE TABLE rollback_records (
    id TEXT PRIMARY KEY,
    namespace TEXT NOT NULL,
    target_type TEXT NOT NULL,
    target_id TEXT NOT NULL,
    from_version_id TEXT,
    to_version_id TEXT,
    reason TEXT NOT NULL,
    rolled_back_by TEXT NOT NULL,
    created_at TEXT NOT NULL,
    metadata_json TEXT
);

⸻

11. Learning Signal Contract

11.1 Signal classes

M5 formalizes learning signals into three classes:

truth signals
usefulness signals
policy signals

⸻

11.2 Truth signals

Truth signals may affect truth confidence.

Allowed truth signals:

explicit user confirmation
explicit user correction
verified tool result
trusted imported source
manual curator decision

Not allowed as truth signals:

retrieval frequency
assistant repetition
context-pack inclusion
task success alone
semantic similarity

⸻

11.3 Usefulness signals

Usefulness signals may affect salience, ranking, and context-pack policy.

Examples:

memory was useful
memory was irrelevant
memory should rank higher
memory should rank lower
context was missing key memory
context included stale memory
context included too much noise

⸻

11.4 Policy signals

Policy signals may drive proposed changes to:

retrieval weights
context sections
token budgets
curation thresholds
half-life defaults
procedure memories
reflection refresh rules

Policy signals require evaluation before activation.

⸻

12. Evaluation Contract

12.1 Required metrics

M5 must support at least:

recall_at_1
recall_at_3
recall_at_5
precision_at_5
mean_reciprocal_rank
forbidden_memory_leak_rate
disputed_memory_leak_rate
superseded_memory_leak_rate
stale_memory_leak_rate
provenance_preservation_rate
context_section_accuracy
token_efficiency
average_latency_ms

⸻

12.2 Evaluation gate defaults

A policy proposal should pass only if:

forbidden_memory_leak_rate = 0
rejected_memory_leak_rate = 0
superseded_memory_leak_rate = 0
disputed_memory_leak_rate <= configured threshold
stale_memory_leak_rate does not increase
provenance_preservation_rate >= baseline
recall_at_5 improves or does not regress materially

Suggested default thresholds:

forbidden_memory_leak_rate: 0.00
rejected_memory_leak_rate: 0.00
superseded_memory_leak_rate: 0.00
disputed_memory_leak_rate: <= 0.02
stale_memory_leak_rate: no worse than baseline + 0.02
provenance_preservation_rate: >= 0.99
recall_at_5: >= baseline - 0.01

⸻

12.3 Golden tests are privileged

Golden evaluation cases must not be ignored by optimization.

If a policy improves average metrics but fails golden integrity tests, it must not be activated by default.

⸻

13. Retrieval Optimization Contract

13.1 What optimization may change

M5 retrieval optimization may change:

ranking weights
memory type priority
status priority
recency weights
confidence weights
salience weights
project relevance weights
semantic/lexical balance
context section quotas
duplicate suppression thresholds

⸻

13.2 What optimization must not change

Optimization must not change:

claim text
evidence
claim status
truth confidence
conflict resolution
privacy labels
safety constraints
namespace rules

⸻

13.3 Ranking policy example

{
  "weights": {
    "lexical_score": 0.20,
    "semantic_score": 0.25,
    "effective_confidence": 0.15,
    "retrieval_salience": 0.15,
    "project_relevance": 0.10,
    "status_priority": 0.07,
    "recency_score": 0.05,
    "memory_type_priority": 0.03
  },
  "penalties": {
    "unresolved_conflict": 0.25,
    "scope_mismatch": 0.20,
    "stale_memory": 0.15,
    "duplicate": 0.10
  },
  "filters": {
    "exclude_rejected": true,
    "exclude_superseded": true,
    "exclude_disputed_by_default": true,
    "require_provenance": true
  }
}

⸻

14. Procedure Learning Contract

14.1 Purpose

Procedural memory is where Aletheia can learn how to behave better.

Examples:

For architecture contracts, include APIs, storage, CLI, tests, acceptance criteria, migration, and demo script.
For progress updates, be concise.
When using inferred memories, label them clearly.

⸻

14.2 Procedure update lifecycle

usage/outcome/feedback
  → procedure proposal
  → evaluation/review
  → approved
  → applied as new version
  → active
  → superseded or rolled back

⸻

14.3 Procedure updates must preserve source lineage

Every proposed procedure update must link to at least one of:

user feedback
task outcome
evaluation run
reflection
claim
manual reason

⸻

14.4 Procedure update risk levels

Procedure updates should be classified:

low
medium
high
critical

High or critical updates include anything touching:

privacy
safety
deletion
external communication
tool execution
autonomous promotion

High or critical procedure updates must require explicit approval.

⸻

15. Curation Policy Learning Contract

15.1 What M5 may learn

M5 may propose updates to:

promotion thresholds
demotion thresholds
archive thresholds
candidate review priority
conflict review priority
reflection refresh timing
half-life defaults

⸻

15.2 What M5 must not auto-curate by default

By default, M5 must not automatically:

delete evidence
delete claims
promote to core
reject user-confirmed memories
resolve major conflicts
change privacy labels downward

⸻

15.3 Safe automatic actions

If configured, M5 may automatically run low-risk maintenance:

recompute confidence
detect conflicts
queue stale reflections for refresh
generate health reports
create curation proposals
index unindexed active claims

Even these actions must be logged.

⸻

16. Job Queue Contract

16.1 Purpose

M5 introduces a local job queue so Aletheia can perform maintenance and learning tasks consistently.

This is not a cloud service.
It is local, inspectable, and synchronous unless the developer runs a worker.

⸻

16.2 Required jobs

M5 must support jobs for:

recompute_confidence
run_decay
detect_conflicts
curate
refresh_reflections
run_evaluation
optimize_retrieval
run_learning
memory_health_check

Optional:

index_semantic
run_inference

⸻

16.3 CLI worker

M5 should support:

aletheia jobs run --db ./aletheia.db --max 10

And optionally:

aletheia jobs watch --db ./aletheia.db

watch is optional. The core contract is satisfied by run.

⸻

17. Memory Health Contract

17.1 Purpose

Memory systems rot if nobody inspects them.

M5 must provide a health report that tells the user/developer:

what is stale
what is conflicted
what is unreviewed
what lacks provenance
what is overused
what is under-verified
what needs curation
what needs indexing
what should be refreshed

⸻

17.2 Health warnings

A health report should warn about:

unresolved conflicts
high-salience low-confidence memories
core memories with stale confidence
active memories with no evidence
reflections depending on stale sources
pending candidates older than threshold
unreviewed inference candidates
too many core memories
retrieval failures
stale project state
missing evaluation coverage

⸻

18. Context Pack Integration Contract

M5 must update context_pack() to support usage tracking and policy versions.

Signature extension

context = memory.context_pack(
    namespace="user/default",
    query="Write the M5 contract.",
    project_id="aletheia",
    retrieval_mode="hybrid",
    policy_version_id=None,
    record_usage=True,
    explain_policy=False,
)

Required behavior

- Use active ranking/context policy by default.
- Allow explicit policy version for evaluation.
- Record context usage when record_usage=True.
- Preserve provenance.
- Preserve M2/M3/M4 governance.
- Exclude invalid/rejected/superseded memories as before.
- Track which memories were included and why.

Context metadata should include

context_pack_id
ranking_policy_version_id
context_policy_version_id
retrieval_mode
query
session_id
project_id
included_item_ids
omitted_item_ids
token_estimate
generated_at

⸻

19. CLI Contract

⸻

19.1 aletheia usage

Purpose

Inspect memory usage.

aletheia usage list \
  --db ./aletheia.db \
  --namespace user/default
aletheia usage show use_001 \
  --db ./aletheia.db

⸻

19.2 aletheia outcome

Purpose

Record task outcomes.

aletheia outcome record \
  --db ./aletheia.db \
  --namespace user/default \
  --task task_001 \
  --outcome success \
  --context ctx_001 \
  --note "Context contained the correct project state."
aletheia outcome list \
  --db ./aletheia.db \
  --namespace user/default

⸻

19.3 aletheia eval

Purpose

Manage and run evaluation sets.

aletheia eval create \
  --db ./aletheia.db \
  --namespace user/default \
  --name aletheia_contracts \
  --description "Golden tests for Aletheia milestone contracts."
aletheia eval add-case \
  --db ./aletheia.db \
  --set eval_001 \
  --query "Write an architecture contract" \
  --expected clm_design_detail_preference \
  --forbidden clm_progress_update_concise_only
aletheia eval run \
  --db ./aletheia.db \
  --namespace user/default \
  --set eval_001 \
  --mode hybrid
aletheia eval report \
  --db ./aletheia.db \
  --run evalrun_001

⸻

19.4 aletheia optimize

Purpose

Propose optimized policies.

aletheia optimize retrieval \
  --db ./aletheia.db \
  --namespace user/default \
  --eval-set eval_001 \
  --objective balanced \
  --dry-run
aletheia optimize retrieval \
  --db ./aletheia.db \
  --namespace user/default \
  --eval-set eval_001 \
  --objective balanced \
  --apply-proposal

⸻

19.5 aletheia learn

Purpose

Run governed learning.

aletheia learn run \
  --db ./aletheia.db \
  --namespace user/default \
  --project aletheia \
  --targets retrieval_policy,procedure_memory \
  --eval-set eval_001 \
  --dry-run
aletheia learn run \
  --db ./aletheia.db \
  --namespace user/default \
  --project aletheia \
  --targets retrieval_policy,procedure_memory \
  --eval-set eval_001 \
  --create-proposals

⸻

19.6 aletheia policies

Purpose

Review and apply policy proposals.

aletheia policies list \
  --db ./aletheia.db \
  --namespace user/default
aletheia policies show prop_001 \
  --db ./aletheia.db
aletheia policies approve prop_001 \
  --db ./aletheia.db \
  --reason "Passed evaluation gate."
aletheia policies reject prop_002 \
  --db ./aletheia.db \
  --reason "Increased stale-memory leakage."
aletheia policies apply prop_001 \
  --db ./aletheia.db \
  --reason "Approved ranking improvement."
aletheia policies versions \
  --db ./aletheia.db \
  --policy ranking_default

⸻

19.7 aletheia procedures

Purpose

Manage learned procedure versions.

aletheia procedures propose \
  --db ./aletheia.db \
  --namespace user/default \
  --title "Architecture contract response procedure" \
  --text "For architecture contracts, include scope, APIs, storage, tests, acceptance criteria, migration, and demo script." \
  --reason "Repeated successful Aletheia contract responses use this structure."
aletheia procedures approve procprop_001 \
  --db ./aletheia.db \
  --reason "Matches user preference and evaluation cases."
aletheia procedures apply procprop_001 \
  --db ./aletheia.db \
  --reason "Approved procedure update."
aletheia procedures versions \
  --db ./aletheia.db \
  --namespace user/default

⸻

19.8 aletheia jobs

Purpose

Manage local jobs.

aletheia jobs list \
  --db ./aletheia.db
aletheia jobs enqueue \
  --db ./aletheia.db \
  --namespace user/default \
  --type memory_health_check
aletheia jobs run \
  --db ./aletheia.db \
  --max 10
aletheia jobs show job_001 \
  --db ./aletheia.db

⸻

19.9 aletheia health

Purpose

Generate memory health report.

aletheia health report \
  --db ./aletheia.db \
  --namespace user/default

Expected output:

Memory Health Report
- unresolved conflicts: 0
- stale active memories: 2
- pending candidates: 5
- invalidated reflections: 1
- core memories: 7
- warnings:
  - One active project memory has not been verified in 90 days.
  - One reflection depends on a superseded claim.

⸻

19.10 aletheia rollback

Purpose

Rollback learned policies or procedures.

aletheia rollback policy \
  --db ./aletheia.db \
  --namespace user/default \
  --policy ranking_default \
  --to-version rpv_003 \
  --reason "New policy reduced project recall."
aletheia rollback procedure \
  --db ./aletheia.db \
  --namespace user/default \
  --procedure proc_001 \
  --to-version pv_002 \
  --reason "New procedure was too verbose."

⸻

20. Backward Compatibility Contract

M5 must preserve M4 behavior.

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
memory.run_inference()
memory.list_inferences()
memory.promote_inference()
memory.build_reflection()
memory.expand_reflection()
memory.trace_derivation()
memory.invalidate_derived()

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
aletheia infer
aletheia rules
aletheia reflect
aletheia derivation
aletheia clusters
aletheia abstractions

Allowed M5 changes:

- Add usage logging.
- Add policy versioning.
- Add evaluation and optimization APIs.
- Add procedure versioning.
- Add local job queue.
- Extend context_pack() with policy/version/usage parameters.

Not allowed:

- Requiring cloud services.
- Requiring LLMs.
- Requiring vector database.
- Changing canonical facts based on task success alone.
- Applying learned policies without audit trail.
- Removing rollback ability.
- Weakening M2/M3/M4 governance filters.

⸻

21. Migration Contract

21.1 Migration path

M5 must support:

0.5.x → 0.6.0

21.2 Migration command

aletheia migrate --db ./aletheia.db

Or:

memory = Memory.open("./aletheia.db", auto_migrate=True)

21.3 Migration rules

- Existing evidence remains unchanged.
- Existing claims remain unchanged.
- Existing candidates remain unchanged.
- Existing inferences remain unchanged.
- Existing reflections remain unchanged.
- Existing derivation graph remains valid.
- Existing retrieval behavior remains valid.
- New learning/evaluation tables are added safely.
- A default ranking policy is created from current ranking config.
- No optimization is run automatically.
- No learned policy is activated automatically.
- Migration must be idempotent.

21.4 Initial migration behavior

During migration, Aletheia should:

1. Add M5 tables.
2. Create default ranking policy from existing retrieval weights.
3. Create default context-pack policy from existing context behavior.
4. Add no evaluation cases automatically unless deterministic fixtures exist.
5. Run no learning.
6. Run no optimization.
7. Preserve all M4 behavior.
8. Mark schema version as 0.6.0.

⸻

22. Default M5 Policies

22.1 Default learning mode

proposal_only

Meaning:

learning creates proposals
learning does not apply changes

⸻

22.2 Default auto-job behavior

Allowed by default:

memory_health_check
recompute_confidence
detect_conflicts

Not allowed by default:

auto_promote_core
auto_delete_evidence
auto_resolve_conflicts
auto_apply_policy
auto_apply_procedure

⸻

22.3 Default policy gate

A policy proposal must pass:

golden eval cases
forbidden leakage check
disputed leakage check
stale leakage check
provenance preservation check

before application.

⸻

23. Test Contract

23.1 Usage and outcome tests

Required tests:

test_record_usage_does_not_change_truth_confidence
test_record_usage_updates_usage_log
test_record_outcome_links_context_pack
test_task_success_does_not_confirm_all_context_memories
test_user_corrected_outcome_creates_learning_signal
test_retrieval_judgment_records_query_and_result

⸻

23.2 Evaluation tests

Required tests:

test_create_eval_set
test_add_eval_case
test_run_evaluation_computes_recall_at_k
test_run_evaluation_detects_forbidden_memory_leak
test_run_evaluation_detects_disputed_memory_leak
test_run_evaluation_preserves_provenance_metric
test_evaluation_run_is_persisted
test_golden_case_failure_blocks_policy_gate

⸻

23.3 Optimization tests

Required tests:

test_optimize_retrieval_dry_run_creates_no_policy
test_optimize_retrieval_creates_policy_proposal
test_optimization_does_not_modify_claims
test_optimization_rejects_policy_with_conflict_leakage
test_policy_proposal_requires_review
test_apply_policy_requires_approval
test_apply_policy_writes_application_history

⸻

23.4 Procedure learning tests

Required tests:

test_propose_procedure_update_preserves_sources
test_apply_procedure_update_creates_new_version
test_procedure_update_does_not_override_safety_policy
test_procedure_versions_are_ordered
test_procedure_rollback_restores_prior_version
test_high_risk_procedure_requires_explicit_approval

⸻

23.5 Learning run tests

Required tests:

test_run_learning_dry_run_creates_no_proposals
test_run_learning_creates_retrieval_policy_proposal
test_run_learning_creates_procedure_proposal
test_learning_run_records_warnings
test_learning_does_not_apply_policy_by_default

⸻

23.6 Job queue tests

Required tests:

test_enqueue_job
test_run_jobs_executes_pending_job
test_failed_job_records_error
test_job_retry_respects_max_attempts
test_job_run_writes_audit_for_state_change
test_jobs_can_filter_by_namespace_and_type

⸻

23.7 Health report tests

Required tests:

test_health_report_counts_unresolved_conflicts
test_health_report_flags_stale_core_memory
test_health_report_flags_pending_candidates
test_health_report_flags_invalidated_reflections
test_health_report_recommends_curation
test_health_report_snapshot_persisted

⸻

23.8 Rollback tests

Required tests:

test_rollback_policy_restores_prior_version
test_rollback_policy_preserves_history
test_rollback_procedure_restores_prior_version
test_rollback_writes_audit_event
test_rollback_does_not_delete_proposal_history

⸻

23.9 CLI tests

Required tests:

test_cli_usage_list
test_cli_outcome_record
test_cli_eval_create_add_run_report
test_cli_optimize_retrieval_dry_run
test_cli_learn_run_dry_run
test_cli_policies_approve_apply
test_cli_procedures_propose_apply
test_cli_jobs_enqueue_run
test_cli_health_report
test_cli_rollback_policy

⸻

23.10 Migration tests

Required tests:

test_migration_from_m4_to_m5_adds_tables
test_migration_preserves_existing_claims
test_migration_preserves_existing_reflections
test_migration_creates_default_ranking_policy
test_migration_creates_default_context_policy
test_migration_does_not_run_learning
test_migration_does_not_run_optimization
test_migration_is_idempotent

⸻

24. Golden M5 Tests

Golden test 1 — Task success does not confirm truth

Given:

Context pack includes claims A, B, and C.
Task outcome is success.

Expected:

- Usage events are recorded.
- Retrieval salience may later be affected.
- Truth confidence of A, B, and C does not automatically increase.

⸻

Golden test 2 — Retrieval optimization proposal

Given evaluation cases:

Query:
Write architecture contract.
Expected memory:
User prefers comprehensive architecture/design explanations.
Forbidden memory:
User prefers concise progress updates only.

When retrieval optimization runs:

objective = balanced

Expected:

- Proposed ranking policy improves expected-memory ranking.
- Forbidden memory does not leak into context.
- Proposal remains pending review.
- Active policy does not change until approved and applied.

⸻

Golden test 3 — Procedure learning

Given repeated successful outcomes for architecture contracts:

Successful responses included:
- APIs
- storage
- CLI
- tests
- migration
- acceptance criteria
- demo script

Expected procedure proposal:

For architecture milestone contracts, include scope, APIs, storage, CLI, tests, migration, acceptance criteria, and demo script.

Expected behavior:

- Proposal links to task outcomes/evaluation runs.
- Proposal is not active by default.
- Applying proposal creates a new procedure version.

⸻

Golden test 4 — Bad policy blocked

Given a proposed policy that improves recall but includes disputed memories as facts:

Expected:

- Evaluation detects disputed-memory leakage.
- Learning gate fails.
- Policy cannot be applied by default.

⸻

Golden test 5 — Rollback

Given:

Policy version 4 is active.
User reports worse retrieval.
Rollback to version 3.

Expected:

- Version 3 becomes active.
- Version 4 is marked rolled_back or superseded.
- Rollback record is stored.
- Audit trail remains intact.

⸻

25. Acceptance Criteria

M5 is complete only when all of the following are true.

25.1 Usage and outcome acceptance

[ ] Aletheia records memory usage.
[ ] Aletheia records context-pack usage.
[ ] Aletheia records task outcomes.
[ ] Task outcomes do not automatically confirm truth.
[ ] Retrieval judgments can be stored and inspected.

⸻

25.2 Evaluation acceptance

[ ] Evaluation sets can be created.
[ ] Evaluation cases can be added.
[ ] Evaluation runs compute required metrics.
[ ] Golden cases can block bad policies.
[ ] Evaluation results are stored and auditable.

⸻

25.3 Optimization acceptance

[ ] Retrieval optimization can run.
[ ] Optimization creates proposals, not silent changes.
[ ] Proposals include evaluation summaries.
[ ] Bad proposals are blocked by gates.
[ ] Approved proposals can be applied.
[ ] Applied policies are versioned.

⸻

25.4 Procedure learning acceptance

[ ] Procedure update proposals can be created.
[ ] Procedure updates preserve source lineage.
[ ] Procedure updates require review by default.
[ ] Procedure versions are stored.
[ ] Procedure rollback works.

⸻

25.5 Learning acceptance

[ ] run_learning() can create proposals.
[ ] run_learning(dry_run=True) mutates nothing.
[ ] Learning targets are configurable.
[ ] Learning runs are auditable.
[ ] No learned behavior overrides explicit user correction.

⸻

25.6 Job queue acceptance

[ ] Jobs can be enqueued.
[ ] Jobs can be run locally.
[ ] Jobs record success/failure.
[ ] State-changing jobs write audit events.
[ ] Jobs are inspectable through CLI.

⸻

25.7 Memory health acceptance

[ ] health_report() works.
[ ] Health report identifies stale/conflicted/unreviewed memory.
[ ] Health report produces recommendations.
[ ] Health snapshots are persisted.

⸻

25.8 Rollback acceptance

[ ] Policy rollback works.
[ ] Procedure rollback works.
[ ] Rollback preserves history.
[ ] Rollback writes audit records.

⸻

25.9 CLI acceptance

[ ] aletheia usage works.
[ ] aletheia outcome works.
[ ] aletheia eval works.
[ ] aletheia optimize works.
[ ] aletheia learn works.
[ ] aletheia policies works.
[ ] aletheia procedures works.
[ ] aletheia jobs works.
[ ] aletheia health works.
[ ] aletheia rollback works.
[ ] Existing M4 CLI commands still work.

⸻

25.10 Migration acceptance

[ ] M4 database migrates to M5.
[ ] Migration is idempotent.
[ ] Existing memories remain retrievable.
[ ] Existing context packs still work.
[ ] Default policies are created.
[ ] No learning or optimization runs during migration.

⸻

26. M5 Demo Script

This should be the official M5 demo.

⸻

Step 1 — Migrate

aletheia migrate --db ./aletheia.db

Expected:

Schema migrated to 0.6.0.
Default ranking policy created.
Default context-pack policy created.
No learning run executed.

⸻

Step 2 — Create evaluation set

aletheia eval create \
  --db ./aletheia.db \
  --namespace user/default \
  --name aletheia_contracts \
  --description "Golden retrieval tests for Aletheia milestone contracts."

⸻

Step 3 — Add evaluation case

aletheia eval add-case \
  --db ./aletheia.db \
  --set eval_001 \
  --query "Write an architecture milestone contract." \
  --expected clm_architecture_detail_preference \
  --forbidden clm_progress_update_concise_only

⸻

Step 4 — Run baseline evaluation

aletheia eval run \
  --db ./aletheia.db \
  --namespace user/default \
  --set eval_001 \
  --mode hybrid

Expected:

Evaluation run complete.
Metrics:
- recall_at_5
- forbidden_memory_leak_rate
- provenance_preservation_rate

⸻

Step 5 — Generate a context pack with usage tracking

aletheia context \
  --db ./aletheia.db \
  --namespace user/default \
  --project aletheia \
  --query "Write the M5 contract." \
  --mode hybrid \
  --record-usage

Expected:

Context pack generated.
Usage events recorded.

⸻

Step 6 — Record task outcome

aletheia outcome record \
  --db ./aletheia.db \
  --namespace user/default \
  --task task_m5_contract \
  --outcome success \
  --context ctx_001 \
  --note "The context pack included the correct milestone and response-style memories."

Expected:

Outcome recorded.
Truth confidence of included memories unchanged.

⸻

Step 7 — Optimize retrieval

aletheia optimize retrieval \
  --db ./aletheia.db \
  --namespace user/default \
  --eval-set eval_001 \
  --objective balanced \
  --apply-proposal

Expected:

Optimization run complete.
Policy proposal created:
prop_001
Status:
pending_review

⸻

Step 8 — Review and apply policy

aletheia policies approve prop_001 \
  --db ./aletheia.db \
  --reason "Improves recall without forbidden-memory leakage."
aletheia policies apply prop_001 \
  --db ./aletheia.db \
  --reason "Passed evaluation gate."

Expected:

New ranking policy version active.
Previous policy version preserved.
Rollback target available.

⸻

Step 9 — Propose procedure update

aletheia procedures propose \
  --db ./aletheia.db \
  --namespace user/default \
  --title "Milestone contract writing procedure" \
  --text "For Aletheia milestone contracts, include scope, APIs, storage, CLI, tests, migration, acceptance criteria, and demo script." \
  --reason "Repeated successful milestone contracts follow this structure."
aletheia procedures approve procprop_001 \
  --db ./aletheia.db \
  --reason "Consistent with user preferences and evaluation results."
aletheia procedures apply procprop_001 \
  --db ./aletheia.db \
  --reason "Approved procedure improvement."

Expected:

New procedure version created.
Source proposal preserved.
Audit trail updated.

⸻

Step 10 — Run health report

aletheia health report \
  --db ./aletheia.db \
  --namespace user/default

Expected:

Memory health report generated.
Warnings and recommendations shown.

⸻

Step 11 — Rollback policy

aletheia rollback policy \
  --db ./aletheia.db \
  --namespace user/default \
  --policy ranking_default \
  --to-version rpv_previous \
  --reason "Testing rollback."

Expected:

Previous ranking policy restored.
Rollback record stored.
Audit trail preserved.

⸻

27. M5 Implementation Checklist

Usage and outcomes

[ ] Add MemoryUsageEvent model
[ ] Add ContextUsageEvent model
[ ] Add TaskOutcome model
[ ] Add RetrievalJudgment model
[ ] Implement record_usage()
[ ] Implement record_outcome()
[ ] Implement judge_retrieval()
[ ] Integrate context_pack(record_usage=True)

⸻

Evaluation

[ ] Add EvaluationSet model
[ ] Add EvaluationCase model
[ ] Add EvaluationRun model
[ ] Add EvaluationMetric model
[ ] Implement create_eval_set()
[ ] Implement add_eval_case()
[ ] Implement run_evaluation()
[ ] Implement recall/precision/MRR metrics
[ ] Implement leakage metrics
[ ] Implement provenance metric

⸻

Optimization and policies

[ ] Add RankingPolicy model
[ ] Add RankingPolicyVersion model
[ ] Add PolicyProposal model
[ ] Implement optimize_retrieval()
[ ] Implement propose_policy_update()
[ ] Implement review_policy_proposal()
[ ] Implement apply_policy_proposal()
[ ] Implement rollback_policy()
[ ] Add learning gate checks

⸻

Procedure learning

[ ] Add ProcedureVersion model
[ ] Add ProcedureUpdateProposal model
[ ] Implement propose_procedure_update()
[ ] Implement apply_procedure_update()
[ ] Implement procedure rollback
[ ] Add procedure risk classification

⸻

Learning runs

[ ] Add LearningRun model
[ ] Implement run_learning()
[ ] Support learning targets
[ ] Ensure dry_run mutates nothing
[ ] Ensure proposal_only default

⸻

Job queue

[ ] Add LocalJob model
[ ] Implement enqueue_job()
[ ] Implement run_jobs()
[ ] Add job status transitions
[ ] Add failure/retry behavior
[ ] Add CLI commands

⸻

Memory health

[ ] Add MemoryHealthReport model
[ ] Implement health_report()
[ ] Add stale/conflict/pending/invalidated metrics
[ ] Add recommendations
[ ] Persist health snapshots

⸻

CLI

[ ] Add usage command group
[ ] Add outcome command group
[ ] Add eval command group
[ ] Add optimize command group
[ ] Add learn command group
[ ] Add policies command group
[ ] Add procedures command group
[ ] Add jobs command group
[ ] Add health command group
[ ] Add rollback command group

⸻

Migration

[ ] Add schema version 0.6.0
[ ] Add migration from 0.5.x
[ ] Create default ranking policy
[ ] Create default context-pack policy
[ ] Ensure no learning runs during migration
[ ] Ensure no optimization runs during migration
[ ] Add migration tests

⸻

Tests

[ ] Usage tests
[ ] Outcome tests
[ ] Evaluation tests
[ ] Optimization tests
[ ] Procedure learning tests
[ ] Learning run tests
[ ] Job queue tests
[ ] Health report tests
[ ] Rollback tests
[ ] CLI tests
[ ] Golden M5 tests

⸻

28. M5 Definition of Done

M5 is done when this statement is true:

Aletheia can improve its retrieval, context packing, curation policies, and procedural memory from feedback and evaluation without corrupting factual memory or losing auditability.

More practically, M5 is complete when Aletheia can do all of this:

- Track which memories were used.
- Record task outcomes.
- Evaluate retrieval and context packs.
- Detect regressions.
- Propose improved ranking policies.
- Propose improved procedures.
- Require review and evaluation gates.
- Apply approved policy/procedure versions.
- Roll back learned behavior.
- Generate memory health reports.
- Run local maintenance jobs.
- Preserve the distinction between truth, usefulness, and learned behavior.

M5 is where Aletheia starts to improve itself.
But it improves like a disciplined engineer, not like an unchecked organism.