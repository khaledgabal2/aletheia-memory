Aletheia M7 Contract

Milestone: Operational Console, Observability, and Human Governance

⸻

1. Milestone Summary

M0 proved that Aletheia can remember.
M1 proved that Aletheia can recall across sessions and projects.
M2 proved that Aletheia can maintain trust through confidence, contradiction, decay, and curation.
M3 proved that Aletheia can ingest raw material and form candidate memories.
M4 proved that Aletheia can reason, infer, reflect, and preserve derivation lineage.
M5 proved that Aletheia can evaluate and improve itself safely.
M6 proved that Aletheia can serve local agents through HTTP and MCP.
M7 must prove that Aletheia can be operated, inspected, governed, and trusted by a human.

M7 is where Aletheia becomes visible.

A memory system that cannot be inspected will eventually become untrusted. M7 solves that by adding a local operational console, review workflows, observability, traceability, and human governance over memory state.

M0 = Remember
M1 = Recall
M2 = Trust
M3 = Understand
M4 = Reason
M5 = Improve
M6 = Connect
M7 = Operate

The core M7 promise:

Aletheia can expose a local human-facing console where users can inspect memories, trace provenance, review candidates, resolve conflicts, approve policies, monitor health, understand retrieval decisions, and govern the memory system without directly touching the database.

M7 is not cloud hosting.
M7 is not enterprise administration.
M7 is not a flashy dashboard for vanity metrics.

M7 is the local cockpit for a serious memory system.

⸻

2. M7 Name

M7 — Memory Operations Console

Fuller name:

M7 — Operational Console, Observability, and Human Governance

Recommended short name:

M7 — Memory Operations

⸻

3. M7 Contract Status

milestone: M7
name: Memory Operations
depends_on: M6
version_target: 0.8.0
stability: operations-beta
breaking_changes_allowed: limited
storage_migration_required: yes
daemon_required: yes
http_api_required: yes
console_required: yes
mcp_required: no_new_requirements
dashboard_required: yes
cloud_required: no
external_telemetry_required: no
enterprise_acl_required: no
primary_theme: local_observability_and_human_governance

Important clarification:

M7 must add a local console.
M7 must not require cloud hosting.
M7 must not require external telemetry.
M7 must not bypass M0–M6 memory integrity rules.
M7 must not allow UI actions to mutate memory without audit records.

⸻

4. M6 Assumptions

M7 assumes M6 already provides:

- Local daemon
- HTTP API v1
- MCP server
- API token management
- Capability enforcement
- Namespace grants
- Privacy ceilings
- Request audit logging
- Idempotency support
- Service logs
- Python client SDK
- Local worker/job support
- All M0–M5 memory features:
  - evidence
  - claims
  - retrieval
  - context packs
  - confidence
  - conflicts
  - curation
  - sessions/projects
  - ingestion
  - candidates
  - entities/categories
  - semantic search
  - inference
  - reflections
  - derivation
  - learning
  - evaluation
  - policies
  - jobs
  - health reports

M7 should sit on top of this existing service layer.

The console must call the same HTTP/kernel APIs that agents use. It must not become a privileged backdoor.

⸻

5. M7 Primary Objective

M7 must make this flow work reliably:

aletheia serve \
  --db ./aletheia.db \
  --host 127.0.0.1 \
  --port 8765 \
  --with-console

Then the user opens:

http://127.0.0.1:8765/console

The console should allow the user to:

- inspect memory health
- browse claims and evidence
- see where memories came from
- review candidate memories
- resolve conflicts
- inspect confidence decay
- inspect context-pack construction
- approve or reject learned policies
- inspect inference and derivation
- monitor jobs
- inspect service/API/MCP activity
- manage API clients and tokens

Expected behavior:

- The console requires authentication.
- The console respects namespace grants and privacy ceilings.
- The console never shows inaccessible memory.
- Dangerous actions require explicit confirmation.
- Every state-changing action writes an audit event.
- The user can understand why a memory was included, omitted, promoted, demoted, stale, disputed, or invalidated.

⸻

6. M7 Non-Negotiable Principles

6.1 The console is a governance layer, not a second memory engine

The console must not implement its own memory logic.

Correct:

Console → HTTP API → Aletheia kernel

Incorrect:

Console directly edits database tables.
Console reimplements retrieval scoring.
Console bypasses confidence or conflict checks.

⸻

6.2 No mutation without audit

Any UI action that changes state must create an audit event.

Examples:

promote candidate
reject candidate
resolve conflict
demote claim
scope claim
approve policy
apply policy
rollback policy
approve procedure
run curation
run learning
revoke token
dismiss critical warning

⸻

6.3 Inspection must preserve provenance

Every displayed memory must be traceable to:

claim_id
evidence_id
candidate_id if applicable
inference_id if applicable
reflection_id if applicable
source spans
audit trail
confidence history
derivation graph

A memory card without provenance is not acceptable.

⸻

6.4 The UI must distinguish memory states clearly

The console must visibly distinguish:

active
core
candidate
pending_review
disputed
superseded
rejected
archived
stale
invalidated
inferred
reflected
abstracted

Do not hide these states behind color alone. Text labels are required.

⸻

6.5 The console must not leak secrets

The console must respect:

namespace grants
privacy ceilings
token capabilities
redaction rules
service logging configuration

A user or agent without secret access must not see secret memory content, evidence text, titles, or revealing snippets.

⸻

6.6 Destructive or high-risk actions require confirmation

High-risk actions include:

delete/redact evidence
reject user-confirmed memory
promote to core
apply policy
apply procedure
run learning apply
resolve major conflict
revoke token
change privacy label downward

The console must require explicit confirmation and record the reason.

⸻

6.7 Observability is local by default

M7 must not send telemetry outside the machine.

All metrics, traces, logs, and health snapshots stay local unless a future explicit integration is configured.

⸻

6.8 Traceability must be understandable

Aletheia must not only show scores. It must explain them.

For retrieval and context packs, the console should answer:

Why was this memory included?
Why was this memory omitted?
What score did it receive?
What filters applied?
Was it excluded due to conflict, privacy, scope, status, or token budget?
What policy version was used?

⸻

6.9 Review queues must be action-oriented

The console should not merely list problems. It should organize human review.

Examples:

5 candidates need review
2 unresolved conflicts need resolution
1 policy proposal awaits approval
3 stale core memories need verification
4 invalidated reflections need refresh

Each item should have a recommended next action.

⸻

6.10 The console must be optional

Library and service users should still be able to run Aletheia without the console.

aletheia serve --db ./aletheia.db

should work without UI assets.

Console mode:

aletheia serve --with-console

or:

aletheia console

⸻

7. M7 Scope

In Scope

M7 includes:

1. Local web console
2. Console authentication/session layer
3. Dashboard overview
4. Memory browser
5. Evidence browser
6. Claim detail view
7. Context-pack inspector
8. Retrieval trace inspector
9. Candidate review workflow
10. Conflict resolution workflow
11. Confidence and decay visualization
12. Inference/reflection/derivation views
13. Policy and procedure review workflow
14. Learning/evaluation view
15. Health report view
16. Job queue view
17. Service/API/MCP log view
18. API client/token management view
19. Review task system
20. Notification/warning system
21. Local metric snapshots
22. Local trace events
23. Saved filters/views
24. Report export for local files
25. Console-specific HTTP endpoints
26. CLI commands for console/reviews/metrics/traces
27. Migration from M6 to M7
28. Golden operational tests

⸻

Out of Scope

M7 explicitly excludes:

Cloud-hosted dashboard
Multi-user collaborative UI
Enterprise SSO
Remote team administration
Distributed deployment monitoring
Full backup/restore system
Full encryption/key management
Cloud sync
External telemetry
Mobile app
Full graph visualization engine
Data labeling workforce tools

Backup, restore, encryption hardening, and release engineering belong naturally in M8.

⸻

8. M7 Deliverables

8.1 Console Deliverables

- Local console web app
- Console route mounted at /console
- Console login/session handling
- Dashboard overview
- Memory browser
- Evidence viewer
- Claim detail page
- Context-pack inspector
- Retrieval trace inspector
- Candidate review page
- Conflict resolution page
- Confidence/decay page
- Inference and derivation page
- Reflection/abstraction page
- Policy/procedure review page
- Evaluation/learning page
- Jobs page
- Health page
- Service logs page
- API clients/tokens page
- Settings page

⸻

8.2 Backend Deliverables

- ReviewTask model
- ReviewTaskEvent model
- NotificationEvent model
- DashboardSavedView model
- MetricSnapshot model
- TraceRun model
- TraceEvent model
- RetrievalTrace model
- ContextPackTrace model
- ConsoleSession model
- ConsoleActionConfirmation model
- ReportExport model
- Console API endpoints
- Trace capture service
- Review queue service
- Notification service
- Metrics snapshot service

⸻

8.3 CLI Deliverables

M7 adds:

aletheia console
aletheia reviews
aletheia metrics
aletheia traces
aletheia notifications
aletheia reports

Existing M0–M6 CLI commands must remain valid.

⸻

8.4 Storage Deliverables

M7 adds:

- console_sessions
- console_action_confirmations
- review_tasks
- review_task_events
- notification_events
- dashboard_saved_views
- dashboard_preferences
- metric_snapshots
- trace_runs
- trace_events
- retrieval_trace_items
- context_trace_items
- report_exports

⸻

8.5 Test Deliverables

- Console route tests
- Console authentication tests
- Console authorization tests
- Review workflow tests
- Candidate review UI/API tests
- Conflict resolution UI/API tests
- Trace capture tests
- Metrics snapshot tests
- Privacy redaction tests
- Dangerous action confirmation tests
- Service log tests
- CLI tests
- Migration tests
- Golden M7 operational tests

⸻

9. Console Architecture

9.1 Recommended architecture

Browser
  |
  v
Aletheia Console UI
  |
  v
Aletheia HTTP API v1
  |
  +--> Auth / Capability Checks
  +--> Namespace / Privacy Enforcement
  +--> Review Task Service
  +--> Trace Service
  +--> Metrics Service
  +--> Existing M0–M6 APIs
  |
  v
Aletheia Kernel
  |
  v
SQLite + Indexes

The UI should not access SQLite directly.

⸻

9.2 Console serving modes

M7 should support:

Console through daemon

aletheia serve --with-console

Console available at:

http://127.0.0.1:8765/console

⸻

Console-only launcher

aletheia console --db ./aletheia.db

This may internally start the local service if needed.

⸻

Headless mode

aletheia serve --no-console

or simply:

aletheia serve

The console should not be mandatory.

⸻

10. Console Security Contract

10.1 Console access

The console must require authentication by default.

Allowed authentication modes:

local_api_token
console_session
one_time_login_token

Recommended local login flow:

aletheia console login-token --db ./aletheia.db

Output:

One-time console login token:
alc_...
Expires in 10 minutes.

The browser exchanges that one-time token for a console session.

⸻

10.2 Console session model

@dataclass
class ConsoleSession:
    id: str
    client_id: str | None
    token_id: str | None
    namespace_grants: list[str]
    capabilities: list[str]
    privacy_ceiling: str
    created_at: datetime
    expires_at: datetime
    revoked_at: datetime | None

Console sessions must expire.

⸻

10.3 Browser token handling

The console should not store raw API tokens in browser local storage.

Recommended:

HttpOnly session cookie
SameSite=Strict
short-lived session
CSRF protection for state-changing requests

⸻

10.4 CSRF protection

Any browser-based state-changing request must include CSRF protection.

Required for:

candidate promotion/rejection
conflict resolution
policy approval/application
procedure approval/application
token revocation
settings changes
delete/redact actions

⸻

10.5 Dangerous action confirmation

Dangerous actions must require:

explicit reason
confirmation phrase or checkbox
capability check
audit event

Example:

Type "promote to core" to confirm.

⸻

11. Review Task System

11.1 Purpose

M7 introduces a unified review queue.

Before M7, Aletheia has many separate pending things:

candidate memories
unresolved conflicts
policy proposals
procedure proposals
inference candidates
stale reflections
health warnings
pending jobs
risky content flags

M7 should unify these into review tasks.

⸻

11.2 ReviewTask model

@dataclass
class ReviewTask:
    id: str
    namespace: str
    task_type: str
    title: str
    description: str
    target_id: str
    target_type: str
    priority: float
    severity: str
    status: str
    recommended_action: str | None
    created_at: datetime
    updated_at: datetime
    due_at: datetime | None
    metadata: dict

Allowed task types:

candidate_review
conflict_resolution
inference_review
reflection_refresh
policy_review
procedure_review
stale_core_memory
health_warning
privacy_warning
risk_flag_review
job_failure
access_review
service_warning

Allowed statuses:

open
in_progress
resolved
dismissed
deferred
blocked

Allowed severities:

info
low
medium
high
critical

⸻

11.3 ReviewTaskEvent model

@dataclass
class ReviewTaskEvent:
    id: str
    review_task_id: str
    event_type: str
    actor: str
    note: str | None
    created_at: datetime
    metadata: dict

Allowed event types:

created
assigned
commented
action_taken
resolved
dismissed
deferred
reopened

⸻

11.4 Required review task creation

M7 should create review tasks for:

new candidate claims
high-risk content flags
unresolved conflicts
pending policy proposals
pending procedure proposals
stale core memories
invalidated reflections
failed jobs
evaluation failures
disputed memory leakage
unreviewed inference candidates

Review tasks may be generated during:

health_report()
curate()
detect_conflicts()
extract_candidates()
run_inference()
run_learning()
run_jobs()

⸻

12. Dashboard Overview Contract

12.1 Purpose

The dashboard must show the state of the memory system at a glance.

Required sections:

Memory Health
Review Queue
Recent Activity
Conflicts
Candidates
Core Memory
Stale Memory
Jobs
Service Activity
Evaluation Status
Policy Proposals

⸻

12.2 Required dashboard metrics

active_claim_count
core_memory_count
candidate_count
pending_review_count
unresolved_conflict_count
stale_claim_count
invalidated_reflection_count
open_review_task_count
critical_review_task_count
failed_job_count
last_health_report_status
last_eval_run_status
recent_context_pack_count
recent_service_request_count

⸻

12.3 Dashboard principle

The dashboard must prioritize actionable risk over vanity.

Good dashboard item:

3 unresolved conflicts may affect context packs.

Bad dashboard item:

You have 14,381 memories.

Memory count alone is not wisdom.

⸻

13. Memory Browser Contract

13.1 Purpose

The memory browser lets the user inspect all memory objects.

It must support:

claims
candidate claims
evidence events
inferences
reflections
abstractions
entities
categories
conflicts
policies
procedures

⸻

13.2 Required filters

namespace
project_id
memory_type
status
confidence range
salience range
privacy level
source type
created date
last verified date
conflict state
scope type
entity
category
has evidence
is derived
is stale
is core

⸻

13.3 Claim card requirements

Each claim card must show:

claim text
status
memory type
confidence
salience
privacy level
source count
conflict state
scope
created_at
last_verified_at
actions

Actions may include:

view
audit
explain
promote
demote
scope
supersede
archive
open evidence
trace derivation

Actions must be capability-gated.

⸻

14. Evidence Viewer Contract

14.1 Purpose

The evidence viewer lets the user inspect raw source material without losing provenance.

Required features:

show evidence metadata
show source type
show source URI
show content hash
show privacy level
show trust level
show derived claims
show candidate spans
show risk flags
show redactions/tombstones

⸻

14.2 Evidence span highlighting

When viewing a candidate, claim, inference, or reflection, the evidence viewer should highlight supporting spans.

Example:

“For architecture contracts, provide comprehensive detail.”

Highlighted as supporting evidence for:

claim: user prefers comprehensive architecture explanations

⸻

15. Claim Detail and Explanation Contract

15.1 Claim detail page

A claim detail page must answer:

What is the claim?
What is its status?
What is its memory type?
What evidence supports it?
What confidence does it have?
Why does it have that confidence?
Is it scoped?
Is it contradicted?
Has it been promoted/demoted?
Was it derived?
Does it appear in context packs?
What would invalidate it?

⸻

15.2 Required tabs

Overview
Evidence
Confidence
Conflicts
Scope
Audit
Derivation
Usage
Context History

⸻

16. Context-Pack Inspector Contract

16.1 Purpose

The context-pack inspector explains how a context pack was built.

Required views:

final markdown
structured sections
included items
omitted items
warnings
token budget
ranking policy
context policy
retrieval mode
provenance
trace

⸻

16.2 Context trace requirements

A context trace must show:

query
namespace
project/session filters
retrieval mode
candidate result set
ranking scores
governance filters
scope filters
privacy filters
token-budget decisions
included items
omitted items
warnings
policy versions

⸻

16.3 Omission explanations

For each omitted memory, the console should show a reason:

token_budget_exceeded
low_relevance
low_confidence
scope_mismatch
privacy_denied
status_excluded
superseded
rejected
unresolved_conflict
duplicate
stale

⸻

17. Retrieval Trace Contract

17.1 Purpose

The retrieval trace lets users debug memory recall.

A retrieval trace should answer:

Why did Aletheia retrieve this?
Why did it miss that?
What filters applied?
What scoring policy was active?
What semantic/lexical scores contributed?
Was memory excluded because of governance?

⸻

17.2 RetrievalTrace model

@dataclass
class RetrievalTrace:
    id: str
    namespace: str
    query: str
    retrieval_mode: str
    policy_version_id: str | None
    created_at: datetime
    result_count: int
    omitted_count: int
    duration_ms: int
    metadata: dict

⸻

17.3 RetrievalTraceItem model

@dataclass
class RetrievalTraceItem:
    id: str
    trace_id: str
    target_id: str
    target_type: str
    final_score: float | None
    lexical_score: float | None
    semantic_score: float | None
    confidence_score: float | None
    salience_score: float | None
    status: str
    included: bool
    omission_reason: str | None
    rank: int | None
    metadata: dict

⸻

18. Candidate Review Contract

18.1 Candidate review page

The candidate review page must show:

candidate claim
source evidence span
extractor
extraction run
suggested confidence
suggested type/category/entities
contradiction risk
duplicate risk
privacy level
risk flags
recommended action

⸻

18.2 Required actions

promote
edit and promote
reject
mark duplicate
needs scope
needs conflict resolution
defer
open evidence
open extraction run

Promotion must call M3/M2 gates.

The UI must not create active claims directly unless the user has the required capability and the gates pass.

⸻

19. Conflict Resolution Contract

19.1 Conflict resolution page

The conflict page must show:

conflict family
conflict type
affected subject/predicate
claims involved
evidence for each claim
confidence for each claim
source reliability
timestamps
scope
recommended strategies
audit history

⸻

19.2 Supported strategies in UI

latest_wins
highest_confidence_wins
user_correction_wins
verified_source_wins
context_scope
time_scope
merge_duplicates
reject_weak_claims
manual
mark_unresolved

The UI should explain the consequences before applying a strategy.

Example:

This action will mark clm_001 as superseded and keep clm_002 active.

⸻

20. Confidence and Decay View Contract

20.1 Purpose

The confidence view helps users understand memory trust.

Required visual/explanatory items:

base confidence
effective confidence
truth confidence
retrieval salience
half-life policy
age
decay factor
feedback factor
contradiction factor
verification factor
confidence history

⸻

20.2 Required explanation

The view should generate a readable explanation:

This claim started with confidence 0.88.
It decayed due to age.
It was confirmed once by user feedback.
It has no unresolved conflict.
Its current effective confidence is 0.84.

⸻

21. Inference, Reflection, and Derivation View Contract

21.1 Inference page

Must show:

inference type
inference strength
source claims
source evidence
rule or engine
derivation confidence
promotion eligibility
review status

⸻

21.2 Reflection page

Must show:

reflection text
abstraction level
source claims
source evidence
confidence
status
staleness
expand button
refresh button
archive button

⸻

21.3 Derivation graph view

M7 should provide a basic derivation graph/tree.

It does not need to be a complex graph visualization engine.

Minimum acceptable view:

target
  ← inference/reflection
    ← source claim
      ← evidence

The tree must show invalidated or stale nodes clearly.

⸻

22. Policy, Procedure, and Learning Governance Contract

22.1 Policy proposal review

The console must show:

policy type
proposed config
reason
source learning run
evaluation summary
gate results
baseline metrics
new metrics
risk warnings
approval actions
rollback target

⸻

22.2 Required actions

approve
reject
request changes
apply
rollback
open evaluation run
open learning run

Applying a policy requires:

memory:policy capability
evaluation gate pass unless override
explicit reason
audit event

⸻

22.3 Procedure proposal review

The console must show:

old procedure
proposed procedure
diff
source signals
evaluation results
risk level
approval history
version history

⸻

23. Jobs and Health View Contract

23.1 Job view

The jobs page must show:

pending jobs
running jobs
failed jobs
completed jobs
job type
namespace
priority
attempts
last error
created_at
updated_at

Required actions:

run now
retry
cancel
inspect payload
inspect result

Capability-gated by:

memory:jobs

⸻

23.2 Health page

The health page must show the latest memory health report.

Required sections:

conflicts
stale memories
pending candidates
invalidated derived records
low-confidence active memories
high-salience low-confidence memories
failed jobs
unindexed claims
policy/evaluation status
recommendations

⸻

24. Service and MCP Log View Contract

24.1 Service log page

Must show metadata-only request logs by default:

request_id
client_id
agent_id
namespace
method
path
status
duration
created_at

It must not show raw request bodies unless logging mode explicitly allowed it.

⸻

24.2 MCP log page

Must show:

tool_name
client_id
namespace
status
duration
created_at
input hash
output hash

No raw sensitive payloads by default.

⸻

25. API Client and Token Management View

25.1 Client view

Must show:

client name
client type
status
created_at
tokens
namespace grants
capabilities
recent activity

⸻

25.2 Token actions

Required actions:

create token
revoke token
view capabilities
view namespace grants
view privacy ceiling

Important:

Raw tokens are shown once at creation only.

The console must not display stored raw tokens because they must not exist.

⸻

26. Local Metrics Contract

26.1 MetricSnapshot model

@dataclass
class MetricSnapshot:
    id: str
    namespace: str | None
    project_id: str | None
    metrics: dict
    generated_at: datetime
    source: str

⸻

26.2 Required local metrics

claim counts by status
candidate counts by status
conflict counts by status
average retrieval latency
average context-pack latency
context packs generated
service requests by endpoint
failed jobs
pending jobs
evaluation pass rate
policy proposals pending
memory health warning count
open review task count

⸻

26.3 Metrics rule

Metrics are operational signals. They must not alter memory truth.

⸻

27. Report Export Contract

27.1 Purpose

M7 may export human-readable local reports.

Supported report types:

memory_health
review_queue
conflict_summary
candidate_summary
policy_review
audit_summary
service_activity

Supported formats:

markdown
json

PDF is not required for M7.

⸻

27.2 ReportExport model

@dataclass
class ReportExport:
    id: str
    namespace: str | None
    report_type: str
    format: str
    file_path: str
    created_at: datetime
    metadata: dict

Reports must respect privacy ceilings and namespace grants.

⸻

28. Public API Contract

M7 extends the M6 HTTP API.

All endpoints remain under:

/v1

⸻

28.1 Console endpoints

GET  /console
GET  /console/assets/*
POST /v1/console/login
POST /v1/console/logout
GET  /v1/console/session

⸻

28.2 Dashboard endpoints

GET /v1/dashboard/overview
GET /v1/dashboard/preferences
POST /v1/dashboard/preferences
GET /v1/dashboard/saved-views
POST /v1/dashboard/saved-views
DELETE /v1/dashboard/saved-views/{view_id}

Required capabilities:

memory:read
memory:admin for settings changes

⸻

28.3 Review endpoints

GET  /v1/reviews
GET  /v1/reviews/{review_task_id}
POST /v1/reviews/{review_task_id}/resolve
POST /v1/reviews/{review_task_id}/dismiss
POST /v1/reviews/{review_task_id}/defer
POST /v1/reviews/generate

Required capabilities depend on target action.

Example:

candidate_review resolution requires memory:review
policy_review resolution requires memory:policy
job_failure retry requires memory:jobs

⸻

28.4 Trace endpoints

POST /v1/traces/retrieval
POST /v1/traces/context-pack
GET  /v1/traces
GET  /v1/traces/{trace_id}
GET  /v1/traces/{trace_id}/items

Required capability:

memory:read

Trace endpoints must respect privacy ceilings.

⸻

28.5 Metrics endpoints

POST /v1/metrics/snapshot
GET  /v1/metrics/snapshots
GET  /v1/metrics/latest

Required capability:

memory:admin

or:

memory:read

for read-only metrics, depending on configuration.

⸻

28.6 Notification endpoints

GET  /v1/notifications
POST /v1/notifications/{notification_id}/dismiss
POST /v1/notifications/{notification_id}/snooze

⸻

28.7 Report endpoints

POST /v1/reports/export
GET  /v1/reports
GET  /v1/reports/{report_id}

Reports must be generated locally.

⸻

29. Python API Contract

M7 adds these Python methods.

⸻

29.1 memory.create_review_task()

def create_review_task(
    self,
    namespace: str,
    *,
    task_type: str,
    title: str,
    description: str,
    target_id: str,
    target_type: str,
    priority: float = 0.5,
    severity: str = "medium",
    recommended_action: str | None = None,
    metadata: dict | None = None,
) -> ReviewTask:
    ...

⸻

29.2 memory.list_review_tasks()

def list_review_tasks(
    self,
    namespace: str,
    *,
    status: str | None = None,
    task_type: str | None = None,
    severity: str | None = None,
    limit: int = 50,
) -> list[ReviewTask]:
    ...

⸻

29.3 memory.resolve_review_task()

def resolve_review_task(
    self,
    review_task_id: str,
    *,
    resolution: str,
    reason: str,
    actor: str = "user",
) -> ReviewTask:
    ...

⸻

29.4 memory.trace_retrieval()

def trace_retrieval(
    self,
    namespace: str,
    *,
    query: str,
    retrieval_mode: str = "hybrid",
    project_id: str | None = None,
    limit: int = 10,
) -> RetrievalTrace:
    ...

⸻

29.5 memory.trace_context_pack()

def trace_context_pack(
    self,
    namespace: str,
    *,
    query: str,
    project_id: str | None = None,
    session_id: str | None = None,
    retrieval_mode: str = "hybrid",
    token_budget: int = 2000,
) -> ContextPackTrace:
    ...

⸻

29.6 memory.metrics_snapshot()

def metrics_snapshot(
    self,
    *,
    namespace: str | None = None,
    project_id: str | None = None,
    source: str = "manual",
) -> MetricSnapshot:
    ...

⸻

29.7 memory.create_notification()

def create_notification(
    self,
    namespace: str,
    *,
    notification_type: str,
    title: str,
    message: str,
    severity: str = "info",
    target_id: str | None = None,
    target_type: str | None = None,
) -> NotificationEvent:
    ...

⸻

29.8 memory.export_report()

def export_report(
    self,
    *,
    namespace: str | None,
    report_type: str,
    format: str = "markdown",
    output_path: str | None = None,
    filters: dict | None = None,
) -> ReportExport:
    ...

⸻

30. Storage Contract

30.1 Schema version

M7 updates schema version to:

0.8.0

⸻

30.2 Required new tables

console_sessions

CREATE TABLE console_sessions (
    id TEXT PRIMARY KEY,
    client_id TEXT,
    token_id TEXT,
    namespace_grants_json TEXT NOT NULL,
    capabilities_json TEXT NOT NULL,
    privacy_ceiling TEXT NOT NULL,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    revoked_at TEXT,
    metadata_json TEXT
);

⸻

console_action_confirmations

CREATE TABLE console_action_confirmations (
    id TEXT PRIMARY KEY,
    namespace TEXT,
    action_type TEXT NOT NULL,
    target_id TEXT,
    target_type TEXT,
    confirmation_text TEXT,
    reason TEXT NOT NULL,
    actor TEXT NOT NULL,
    created_at TEXT NOT NULL,
    metadata_json TEXT
);

⸻

review_tasks

CREATE TABLE review_tasks (
    id TEXT PRIMARY KEY,
    namespace TEXT NOT NULL,
    task_type TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    target_id TEXT NOT NULL,
    target_type TEXT NOT NULL,
    priority REAL NOT NULL DEFAULT 0.5,
    severity TEXT NOT NULL DEFAULT 'medium',
    status TEXT NOT NULL DEFAULT 'open',
    recommended_action TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    due_at TEXT,
    metadata_json TEXT
);

⸻

review_task_events

CREATE TABLE review_task_events (
    id TEXT PRIMARY KEY,
    review_task_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    actor TEXT NOT NULL,
    note TEXT,
    created_at TEXT NOT NULL,
    metadata_json TEXT
);

⸻

notification_events

CREATE TABLE notification_events (
    id TEXT PRIMARY KEY,
    namespace TEXT,
    notification_type TEXT NOT NULL,
    title TEXT NOT NULL,
    message TEXT NOT NULL,
    severity TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'unread',
    target_id TEXT,
    target_type TEXT,
    created_at TEXT NOT NULL,
    dismissed_at TEXT,
    snoozed_until TEXT,
    metadata_json TEXT
);

Allowed statuses:

unread
read
dismissed
snoozed
resolved

⸻

dashboard_saved_views

CREATE TABLE dashboard_saved_views (
    id TEXT PRIMARY KEY,
    namespace TEXT,
    name TEXT NOT NULL,
    view_type TEXT NOT NULL,
    filters_json TEXT NOT NULL,
    sort_json TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    metadata_json TEXT
);

⸻

dashboard_preferences

CREATE TABLE dashboard_preferences (
    id TEXT PRIMARY KEY,
    namespace TEXT,
    preference_key TEXT NOT NULL,
    preference_value_json TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

⸻

metric_snapshots

CREATE TABLE metric_snapshots (
    id TEXT PRIMARY KEY,
    namespace TEXT,
    project_id TEXT,
    metrics_json TEXT NOT NULL,
    source TEXT NOT NULL,
    generated_at TEXT NOT NULL,
    metadata_json TEXT
);

⸻

trace_runs

CREATE TABLE trace_runs (
    id TEXT PRIMARY KEY,
    namespace TEXT NOT NULL,
    trace_type TEXT NOT NULL,
    query TEXT,
    project_id TEXT,
    session_id TEXT,
    retrieval_mode TEXT,
    policy_version_id TEXT,
    duration_ms INTEGER,
    created_at TEXT NOT NULL,
    metadata_json TEXT
);

Allowed trace types:

retrieval
context_pack
curation
inference
policy_evaluation

⸻

trace_events

CREATE TABLE trace_events (
    id TEXT PRIMARY KEY,
    trace_run_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    message TEXT NOT NULL,
    created_at TEXT NOT NULL,
    metadata_json TEXT
);

⸻

retrieval_trace_items

CREATE TABLE retrieval_trace_items (
    id TEXT PRIMARY KEY,
    trace_run_id TEXT NOT NULL,
    target_id TEXT NOT NULL,
    target_type TEXT NOT NULL,
    final_score REAL,
    lexical_score REAL,
    semantic_score REAL,
    confidence_score REAL,
    salience_score REAL,
    included INTEGER NOT NULL,
    omission_reason TEXT,
    rank INTEGER,
    metadata_json TEXT
);

⸻

context_trace_items

CREATE TABLE context_trace_items (
    id TEXT PRIMARY KEY,
    trace_run_id TEXT NOT NULL,
    target_id TEXT NOT NULL,
    target_type TEXT NOT NULL,
    section TEXT,
    included INTEGER NOT NULL,
    omission_reason TEXT,
    token_estimate INTEGER,
    rank INTEGER,
    metadata_json TEXT
);

⸻

report_exports

CREATE TABLE report_exports (
    id TEXT PRIMARY KEY,
    namespace TEXT,
    report_type TEXT NOT NULL,
    format TEXT NOT NULL,
    file_path TEXT NOT NULL,
    created_at TEXT NOT NULL,
    metadata_json TEXT
);

⸻

31. CLI Contract

31.1 aletheia console

Purpose

Start or open the local console.

aletheia console \
  --db ./aletheia.db

Options:

--host
--port
--open-browser
--no-open-browser
--auth-token
--with-worker

Expected behavior:

- Starts service with console enabled if not already running.
- Prints console URL.
- Does not bind publicly by default.

⸻

31.2 aletheia reviews

Purpose

Manage review tasks from CLI.

aletheia reviews list \
  --db ./aletheia.db \
  --namespace user/default
aletheia reviews show rev_001 \
  --db ./aletheia.db
aletheia reviews resolve rev_001 \
  --db ./aletheia.db \
  --reason "Candidate reviewed and promoted."
aletheia reviews generate \
  --db ./aletheia.db \
  --namespace user/default

⸻

31.3 aletheia metrics

Purpose

Generate and inspect local metric snapshots.

aletheia metrics snapshot \
  --db ./aletheia.db \
  --namespace user/default
aletheia metrics latest \
  --db ./aletheia.db \
  --namespace user/default

⸻

31.4 aletheia traces

Purpose

Trace retrieval and context-pack construction.

aletheia traces retrieval \
  --db ./aletheia.db \
  --namespace user/default \
  --query "architecture contract preference"
aletheia traces context \
  --db ./aletheia.db \
  --namespace user/default \
  --project aletheia \
  --query "Write the M7 contract."
aletheia traces show trace_001 \
  --db ./aletheia.db

⸻

31.5 aletheia notifications

Purpose

Inspect notifications.

aletheia notifications list \
  --db ./aletheia.db \
  --namespace user/default
aletheia notifications dismiss note_001 \
  --db ./aletheia.db

⸻

31.6 aletheia reports

Purpose

Export local operational reports.

aletheia reports export \
  --db ./aletheia.db \
  --namespace user/default \
  --type memory_health \
  --format markdown \
  --output ./memory_health.md

⸻

32. Backward Compatibility Contract

M7 must preserve M6 behavior.

The following Python APIs must still work:

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
memory.record_usage()
memory.record_outcome()
memory.run_evaluation()
memory.optimize_retrieval()
memory.run_learning()
memory.health_report()

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
aletheia serve
aletheia mcp
aletheia auth
aletheia clients
aletheia api
aletheia worker
aletheia service

Allowed M7 changes:

- Add console web app.
- Add review task system.
- Add local trace records.
- Add metric snapshots.
- Add notification system.
- Add report export.
- Add console-specific endpoints.

Not allowed:

- Breaking service mode.
- Breaking library mode.
- Requiring cloud services.
- Sending telemetry externally by default.
- Letting UI bypass auth/capability checks.
- Letting UI mutate state without audit.
- Showing memory above privacy ceiling.

⸻

33. Migration Contract

33.1 Migration path

M7 must support:

0.7.x → 0.8.0

⸻

33.2 Migration command

aletheia migrate --db ./aletheia.db

or:

memory = Memory.open("./aletheia.db", auto_migrate=True)

⸻

33.3 Migration rules

- Existing evidence remains unchanged.
- Existing claims remain unchanged.
- Existing candidates remain unchanged.
- Existing inferences/reflections remain unchanged.
- Existing service/auth data remains unchanged.
- New console/review/trace tables are added.
- No console session is created automatically.
- No report is exported automatically.
- No review task is generated automatically unless explicitly requested.
- Migration must be idempotent.

⸻

33.4 Initial migration behavior

During migration, Aletheia should:

1. Add M7 tables.
2. Preserve all M6 behavior.
3. Insert default dashboard preferences if safe.
4. Create no active console session.
5. Create no external telemetry configuration.
6. Mark schema version as 0.8.0.

Review tasks can be generated after migration with:

aletheia reviews generate --db ./aletheia.db --namespace user/default

⸻

34. Test Contract

34.1 Console route tests

Required tests:

test_console_route_available_when_enabled
test_console_route_unavailable_when_disabled
test_console_requires_auth
test_console_session_expires
test_console_logout_revokes_session

⸻

34.2 Authorization and privacy tests

Required tests:

test_console_respects_namespace_grant
test_console_respects_privacy_ceiling
test_console_does_not_show_secret_memory_to_personal_token
test_console_actions_require_capability
test_dangerous_action_requires_confirmation
test_csrf_required_for_state_changing_action

⸻

34.3 Review task tests

Required tests:

test_create_review_task
test_list_review_tasks
test_resolve_review_task
test_review_task_event_recorded
test_generate_review_tasks_for_candidates
test_generate_review_tasks_for_unresolved_conflicts
test_generate_review_tasks_for_failed_jobs

⸻

34.4 Candidate review tests

Required tests:

test_console_candidate_review_loads_evidence_span
test_console_promote_candidate_calls_kernel_gate
test_console_reject_candidate_writes_audit
test_console_candidate_review_resolves_review_task

⸻

34.5 Conflict workflow tests

Required tests:

test_console_conflict_page_lists_claims
test_console_conflict_resolution_requires_reason
test_console_conflict_resolution_writes_audit
test_console_conflict_resolution_updates_context_behavior

⸻

34.6 Trace tests

Required tests:

test_trace_retrieval_creates_trace_run
test_trace_retrieval_records_included_items
test_trace_retrieval_records_omitted_items
test_trace_context_pack_records_token_budget_omissions
test_trace_respects_privacy_ceiling

⸻

34.7 Metrics tests

Required tests:

test_metrics_snapshot_created
test_metrics_snapshot_counts_review_tasks
test_metrics_snapshot_counts_conflicts
test_metrics_snapshot_counts_failed_jobs
test_metrics_latest_returns_recent_snapshot

⸻

34.8 Report tests

Required tests:

test_export_memory_health_markdown
test_export_review_queue_json
test_report_respects_namespace_filter
test_report_respects_privacy_ceiling
test_report_export_record_persisted

⸻

34.9 Service log tests

Required tests:

test_console_service_log_metadata_only
test_console_service_log_does_not_show_raw_body_by_default
test_console_mcp_log_view_filters_by_namespace

⸻

34.10 CLI tests

Required tests:

test_cli_console_starts
test_cli_reviews_list
test_cli_reviews_generate
test_cli_metrics_snapshot
test_cli_traces_retrieval
test_cli_traces_context
test_cli_notifications_list
test_cli_reports_export

⸻

34.11 Migration tests

Required tests:

test_migration_from_m6_to_m7_adds_console_tables
test_migration_preserves_auth_tables
test_migration_preserves_claims
test_migration_does_not_create_console_session
test_migration_does_not_generate_review_tasks
test_migration_is_idempotent

⸻

35. Golden M7 Tests

Golden test 1 — Console shows actionable review queue

Given:

2 candidate claims
1 unresolved conflict
1 failed job
1 stale core memory

When the user opens the dashboard:

Expected:

- Review queue shows 5 open tasks.
- Each task has severity, target, and recommended action.
- No task mutates memory until user acts.

⸻

Golden test 2 — Candidate review preserves evidence

Given:

Candidate claim extracted from evidence span:
"For architecture contracts, provide comprehensive detail."

When viewed in the console:

Expected:

- Candidate text is shown.
- Source evidence span is highlighted.
- Extraction run is linked.
- Promotion action calls M2/M3 gates.
- Audit record is written after promotion.

⸻

Golden test 3 — Context-pack trace explains omission

Given:

A relevant memory exists but is scoped to progress_update.
Query is architecture_contract.

When tracing context-pack generation:

Expected:

- Memory appears in omitted items.
- Omission reason is scope_mismatch.
- Final context does not include it as applicable memory.

⸻

Golden test 4 — Secret memory is not leaked

Given:

Secret evidence exists.
Console session has privacy ceiling personal.

Expected:

- Secret memory content is not visible.
- Secret title/snippet is not visible.
- Dashboard counts may omit or generically indicate restricted items.
- No warning reveals sensitive content.

⸻

Golden test 5 — Policy proposal review

Given:

A retrieval optimization proposal exists.
It improves recall but increases disputed-memory leakage.

When opened in the console:

Expected:

- Evaluation metrics are shown.
- Gate failure is visible.
- Apply button is disabled by default.
- User can reject with reason.
- Rejection writes audit event.

⸻

Golden test 6 — Retrieval trace explains ranking

Given:

Hybrid retrieval returns a preference claim above a project claim.

Expected trace:

- lexical_score visible
- semantic_score visible
- confidence contribution visible
- salience contribution visible
- status priority visible
- final score visible
- policy version visible

⸻

36. Acceptance Criteria

M7 is complete only when all of the following are true.

36.1 Console acceptance

[ ] Console can be enabled with --with-console.
[ ] Console is available locally.
[ ] Console requires authentication.
[ ] Console sessions expire.
[ ] Console respects namespace grants.
[ ] Console respects privacy ceilings.
[ ] Console does not bypass service/kernel APIs.

⸻

36.2 Dashboard acceptance

[ ] Dashboard overview works.
[ ] Dashboard shows memory health.
[ ] Dashboard shows review queue.
[ ] Dashboard shows conflicts/candidates/jobs/policies.
[ ] Dashboard prioritizes actionable issues.

⸻

36.3 Review acceptance

[ ] Review tasks can be created.
[ ] Review tasks can be listed.
[ ] Review tasks can be resolved/dismissed/deferred.
[ ] Candidate review workflow works.
[ ] Conflict resolution workflow works.
[ ] Policy/procedure review workflow works.
[ ] State-changing review actions write audit events.

⸻

36.4 Observability acceptance

[ ] Retrieval traces work.
[ ] Context-pack traces work.
[ ] Omitted memories include reasons.
[ ] Policy versions are visible in traces.
[ ] Metrics snapshots work.
[ ] Health reports are visible.
[ ] Service/API/MCP logs are inspectable.

⸻

36.5 Provenance acceptance

[ ] Claim detail page shows evidence.
[ ] Evidence viewer shows derived memories.
[ ] Candidate view shows evidence span.
[ ] Reflection view can expand sources.
[ ] Derivation trace is visible.

⸻

36.6 Security acceptance

[ ] Dangerous actions require confirmation.
[ ] CSRF protection exists for browser state changes.
[ ] Raw tokens are not stored in browser local storage.
[ ] Secret memory is not leaked through UI or reports.
[ ] Console actions are capability-gated.

⸻

36.7 CLI acceptance

[ ] aletheia console works.
[ ] aletheia reviews works.
[ ] aletheia metrics works.
[ ] aletheia traces works.
[ ] aletheia notifications works.
[ ] aletheia reports works.
[ ] Existing M6 CLI commands still work.

⸻

36.8 Migration acceptance

[ ] M6 database migrates to M7.
[ ] Migration is idempotent.
[ ] Existing memories remain retrievable.
[ ] Existing service/auth data remains valid.
[ ] No console session is created automatically.
[ ] No review tasks are generated automatically unless requested.

⸻

37. M7 Demo Script

This should be the official M7 demo.

⸻

Step 1 — Migrate

aletheia migrate --db ./aletheia.db

Expected:

Schema migrated to 0.8.0.
Console tables created.
No console session created.

⸻

Step 2 — Generate review tasks

aletheia reviews generate \
  --db ./aletheia.db \
  --namespace user/default

Expected:

Review tasks generated for candidates, conflicts, stale memories, failed jobs, and policy proposals.

⸻

Step 3 — Start console

aletheia serve \
  --db ./aletheia.db \
  --host 127.0.0.1 \
  --port 8765 \
  --with-console

Expected:

Aletheia service running.
Console: http://127.0.0.1:8765/console

⸻

Step 4 — Create console login token

aletheia console login-token \
  --db ./aletheia.db

Expected:

One-time console login token created.
Expires in 10 minutes.

⸻

Step 5 — Open dashboard

http://127.0.0.1:8765/console

Expected dashboard shows:

- memory health
- review queue
- open candidates
- unresolved conflicts
- jobs
- policy proposals
- recent service activity

⸻

Step 6 — Review a candidate

In console:

Review Queue → Candidate Review → cand_001

Expected:

- Candidate shown.
- Evidence span highlighted.
- Suggested confidence shown.
- Promote/reject/edit actions available.

User promotes candidate.

Expected:

- Candidate promoted through integrity gates.
- Claim created.
- Review task resolved.
- Audit event written.

⸻

Step 7 — Resolve conflict

In console:

Conflicts → conf_001

User selects:

strategy: context_scope
reason: Concise for updates; comprehensive for architecture contracts.

Expected:

- Conflict resolved.
- Claims scoped.
- Audit event written.
- Context behavior updated.

⸻

Step 8 — Trace context pack

aletheia traces context \
  --db ./aletheia.db \
  --namespace user/default \
  --project aletheia \
  --query "Write the M7 contract."

Expected:

Trace created.
Included memories and omitted memories are shown with reasons.

In console:

Traces → trace_001

Expected:

- Ranking scores visible.
- Omission reasons visible.
- Policy version visible.
- Token budget decisions visible.

⸻

Step 9 — View policy proposal

In console:

Policies → prop_001

Expected:

- Proposal config shown.
- Evaluation metrics shown.
- Gate pass/fail visible.
- Approve/reject/apply actions capability-gated.

⸻

Step 10 — Export health report

aletheia reports export \
  --db ./aletheia.db \
  --namespace user/default \
  --type memory_health \
  --format markdown \
  --output ./memory_health.md

Expected:

Local markdown report exported.
Report respects namespace and privacy filters.

⸻

38. M7 Implementation Checklist

Console foundation

[ ] Add console serving mode
[ ] Add /console route
[ ] Add console session auth
[ ] Add CSRF protection
[ ] Add capability checks to console actions
[ ] Add privacy ceiling enforcement

⸻

Dashboard

[ ] Add dashboard overview endpoint
[ ] Add dashboard UI
[ ] Add dashboard preferences
[ ] Add saved views
[ ] Add actionable health widgets

⸻

Review system

[ ] Add ReviewTask model
[ ] Add ReviewTaskEvent model
[ ] Implement create_review_task()
[ ] Implement list_review_tasks()
[ ] Implement resolve_review_task()
[ ] Generate review tasks for candidates/conflicts/policies/jobs/health
[ ] Add review queue UI

⸻

Memory browser

[ ] Add memory browser UI
[ ] Add claim detail view
[ ] Add evidence viewer
[ ] Add evidence span highlighting
[ ] Add filters by status/type/confidence/privacy/category/entity

⸻

Candidate/conflict workflows

[ ] Add candidate review UI
[ ] Add candidate promote/reject/edit actions
[ ] Add conflict resolution UI
[ ] Add conflict strategy explanation
[ ] Add dangerous action confirmation

⸻

Observability

[ ] Add TraceRun model
[ ] Add TraceEvent model
[ ] Add RetrievalTraceItem model
[ ] Add ContextTraceItem model
[ ] Implement trace_retrieval()
[ ] Implement trace_context_pack()
[ ] Add trace UI
[ ] Add metric snapshots
[ ] Add metrics UI

⸻

Governance views

[ ] Add confidence/decay view
[ ] Add inference/reflection/derivation views
[ ] Add policy/procedure review views
[ ] Add learning/evaluation views
[ ] Add jobs view
[ ] Add service/API/MCP log views
[ ] Add API client/token views

⸻

Notifications and reports

[ ] Add NotificationEvent model
[ ] Add notification UI
[ ] Add report export API
[ ] Add reports CLI
[ ] Add local markdown/json report generation

⸻

CLI

[ ] Add console command
[ ] Add reviews command group
[ ] Add metrics command group
[ ] Add traces command group
[ ] Add notifications command group
[ ] Add reports command group

⸻

Migration

[ ] Add schema version 0.8.0
[ ] Add migration from 0.7.x
[ ] Add console/review/trace/metric tables
[ ] Ensure no console session created during migration
[ ] Ensure no review tasks generated during migration
[ ] Add migration tests

⸻

Tests

[ ] Console route tests
[ ] Auth/session tests
[ ] Privacy tests
[ ] Review workflow tests
[ ] Candidate workflow tests
[ ] Conflict workflow tests
[ ] Trace tests
[ ] Metrics tests
[ ] Report tests
[ ] CLI tests
[ ] Golden M7 tests

⸻

39. M7 Definition of Done

M7 is done when this statement is true:

Aletheia can be operated through a secure local console where a human can inspect, understand, review, correct, approve, trace, and govern the memory system without bypassing its integrity rules.

More practically, M7 is complete when Aletheia can do all of this:

- Start a local web console.
- Authenticate console sessions.
- Show memory health.
- Show review tasks.
- Browse claims, evidence, candidates, conflicts, inferences, reflections, and policies.
- Highlight evidence spans.
- Explain confidence and decay.
- Trace retrieval and context-pack construction.
- Review and promote/reject candidates.
- Resolve conflicts.
- Approve/reject policy and procedure proposals.
- Monitor jobs and service logs.
- Manage API clients and tokens.
- Export local operational reports.
- Preserve namespace, privacy, capability, and audit guarantees.

M7 is where Aletheia becomes inspectable enough to trust.
It gives the human back the steering wheel.