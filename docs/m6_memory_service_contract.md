Aletheia M6 Contract

Milestone: Local Service, Agent Interoperability, and Secure Protocol Layer

⸻

1. Milestone Summary

M0 proved that Aletheia can remember.
M1 proved that Aletheia can recall across sessions and projects.
M2 proved that Aletheia can maintain trust through confidence, contradiction, decay, and curation.
M3 proved that Aletheia can ingest raw material and form candidate memories.
M4 proved that Aletheia can reason, infer, reflect, and preserve derivation lineage.
M5 proved that Aletheia can evaluate and improve itself safely.
M6 must prove that Aletheia can be used by any local AI agent through stable, secure, inspectable protocols.

M6 is where Aletheia becomes more than an importable Python library.

It becomes a local memory service.

M0 = Remember
M1 = Recall
M2 = Trust
M3 = Understand
M4 = Reason
M5 = Improve
M6 = Connect

The core M6 promise:

Aletheia can run as a secure local daemon, expose stable HTTP and MCP interfaces, support multiple local agents, enforce namespace and capability boundaries, preserve all memory governance rules, and provide thin adapters so any agent can use memory without embedding Aletheia internals.

M6 is not cloud hosting.
M6 is not enterprise multi-tenancy.
M6 is the local service layer that makes Aletheia practical for real agents.

⸻

2. M6 Name

M6 — Agent Interoperability

Fuller name:

M6 — Local Service, Agent Interoperability, and Secure Protocol Layer

Recommended short name:

M6 — Agent Interoperability

⸻

3. M6 Contract Status

milestone: M6
name: Agent Interoperability
depends_on: M5
version_target: 0.7.0
stability: service-beta
breaking_changes_allowed: limited
storage_migration_required: yes
daemon_required: yes
http_api_required: yes
mcp_required: yes
python_client_required: yes
typescript_client_supported: yes
llm_required: no
vector_backend_required: no
dashboard_required: no
cloud_required: no
enterprise_acl_required: no
primary_theme: local_service_and_agent_protocols

Important clarification:

M6 must expose Aletheia over stable protocols.
M6 must not weaken M0–M5 governance.
M6 must not require cloud infrastructure.
M6 must not require an LLM.
M6 must not require a vector database.

⸻

4. M5 Assumptions

M6 assumes M5 already provides:

- Evidence ledger
- Claim store
- Manual/schema-driven remember()
- Candidate memory system
- Confidence engine
- Conflict and contradiction handling
- Curation lifecycle
- Sessions and projects
- Ingestion
- Entity and category registry
- Semantic index interface
- Hybrid retrieval
- Inference system
- Reflection and abstraction system
- Derivation graph
- Invalidation and refresh queue
- Evaluation system
- Learning and policy proposals
- Local job queue
- Memory health reports
- Audit trail
- CLI support for M0–M5 commands

M6 wraps this kernel in stable service interfaces.

It should not reimplement the memory logic in the server layer.

⸻

5. M6 Primary Objective

M6 must make this flow work reliably:

aletheia serve \
  --db ./aletheia.db \
  --host 127.0.0.1 \
  --port 8765

Then an arbitrary local agent can call:

POST /v1/context-pack
Authorization: Bearer <token>
Content-Type: application/json
{
  "namespace": "user/default",
  "project_id": "aletheia",
  "query": "Write the next milestone contract.",
  "retrieval_mode": "hybrid",
  "record_usage": true
}

Expected response:

{
  "data": {
    "context_pack_id": "ctx_001",
    "markdown": "## Memory Context\n...",
    "items": [],
    "warnings": [],
    "provenance": []
  },
  "request_id": "req_001",
  "warnings": []
}

The same capability must also be available through MCP:

memory_context_pack
memory_search
memory_remember
memory_feedback
memory_audit

Expected behavior:

- The daemon starts locally.
- The API is versioned.
- Requests require authorization by default.
- Tokens have namespace and capability restrictions.
- Agents can read context without direct database access.
- Agent writes can be restricted to candidate memories.
- MCP tools are thin wrappers over the same service logic.
- Every state-changing call is auditable.
- Existing CLI/library behavior remains intact.

⸻

6. M6 Non-Negotiable Principles

6.1 The service layer must not bypass the kernel

The HTTP server, MCP server, SDKs, and adapters must call the same core Aletheia APIs.

They must not duplicate or bypass:

confidence gates
conflict gates
candidate review rules
privacy rules
audit logging
namespace isolation
policy versioning
invalidation logic

The service is a protocol wrapper, not a second memory engine.

⸻

6.2 Local-first by default

Default binding must be:

127.0.0.1

Not:

0.0.0.0

Remote exposure must require an explicit flag:

--allow-remote

and must require authentication.

⸻

6.3 Authentication is required by default

M6 must not expose write-capable memory APIs without authentication.

Default behavior:

auth_required = true

For local development, unauthenticated mode may exist, but it must require an explicit flag:

aletheia serve --no-auth

and print a clear warning.

⸻

6.4 Capabilities must be explicit

Agents should not get full memory power by default.

Tokens must be scoped by:

namespace
project
capability
privacy ceiling
expiration
read/write permissions

An agent that only needs context should not be able to promote core memories.

⸻

6.5 Service writes are safer than library writes by default

Inside Python, a trusted developer may call:

memory.remember(...)

But over HTTP/MCP, untrusted or semi-trusted agents should default to:

candidate write

not:

active claim write

Active writes must require a stronger capability.

⸻

6.6 MCP tools must be capability-aware

MCP tools must not become a backdoor.

For example:

memory_search

requires:

memory:read

while:

memory_promote_candidate

requires:

memory:review

and:

memory_apply_policy

requires:

memory:policy

⸻

6.7 All state-changing requests must be auditable

Any request that changes memory state must write an audit event.

Examples:

remember
ingest
extract
promote
reject
feedback
resolve conflict
apply policy
run learning
run job
delete/redact

⸻

6.8 Request logging must be privacy-aware

Request logs should default to metadata-only.

Do not store full request bodies by default.

Default service request log should store:

request_id
client_id
agent_id
endpoint
status
duration
namespace
target IDs
created_at

Sensitive text payloads should be redacted unless logging is explicitly configured.

⸻

6.9 API contracts must be versioned

M6 must introduce:

/v1/...

Breaking API changes must require a new major API version later.

⸻

6.10 Agent adapters must be thin

Adapters for LangGraph, LlamaIndex, custom agents, or other frameworks should be thin clients.

Correct:

Agent framework → adapter → Aletheia HTTP/MCP → Memory kernel

Incorrect:

Adapter reimplements retrieval, confidence, ranking, or curation logic

⸻

7. M6 Scope

In Scope

M6 includes:

1. Local daemon
2. HTTP JSON API
3. OpenAPI schema
4. MCP server
5. Python HTTP client SDK
6. Optional TypeScript client SDK
7. Agent registration
8. API token management
9. Capability model
10. Namespace access grants
11. Privacy ceiling enforcement
12. Request audit logging
13. Idempotency keys for state-changing calls
14. Pagination and filtering conventions
15. Standard error envelope
16. Service configuration file
17. Health/readiness/version endpoints
18. Job worker integration
19. Context-pack service endpoint
20. Retrieval/search service endpoint
21. Remember/write service endpoint
22. Feedback/outcome service endpoints
23. Audit/explain endpoints
24. Admin endpoints for jobs, health, policies, and evaluation
25. MCP tools for common agent memory operations
26. Example local agent integrations
27. Migration from M5 to M6
28. Service/API/adapter tests

⸻

Out of Scope

M6 explicitly excludes:

Cloud hosting
Cloud sync
Hosted authentication
Enterprise SSO
Multi-node clustering
Distributed consensus
Web dashboard
Remote multi-user collaboration
Full enterprise RBAC
Browser-based UI
Automatic public network exposure
External telemetry by default

M6 may prepare interfaces that future milestones can use, but the core target is a secure local service.

⸻

8. M6 Deliverables

8.1 Library and Service Deliverables

- AletheiaDaemon
- HTTP API server
- OpenAPI generator
- MCP server
- AuthService
- TokenService
- AgentRegistry
- CapabilityChecker
- NamespaceGrantService
- RequestAuditLogger
- IdempotencyService
- RateLimiter
- ServiceConfig model
- ServiceHealth model
- Python client SDK
- Async Python client SDK
- Optional TypeScript client SDK
- AgentAdapter interface
- Generic HTTP adapter
- MCP tool registry

⸻

8.2 Storage Deliverables

M6 adds:

- api_clients
- api_tokens
- agent_registrations
- namespace_access_grants
- capability_grants
- service_request_log
- mcp_tool_invocation_log
- idempotency_records
- rate_limit_records
- service_config_history
- service_instance_log

⸻

8.3 CLI Deliverables

M6 adds or improves:

aletheia serve
aletheia mcp
aletheia auth
aletheia clients
aletheia api
aletheia worker
aletheia service

Existing M0–M5 CLI commands must remain valid.

⸻

8.4 Protocol Deliverables

- HTTP API v1
- OpenAPI JSON
- Standard JSON response envelope
- Standard JSON error envelope
- MCP tool schemas
- Capability names
- Request ID propagation
- Idempotency key behavior
- Pagination behavior

⸻

8.5 Test Deliverables

- HTTP API tests
- MCP tool tests
- Auth tests
- Capability enforcement tests
- Namespace isolation tests
- Privacy ceiling tests
- Request audit tests
- Idempotency tests
- Rate limit tests
- Client SDK tests
- Adapter tests
- Worker tests
- Migration tests
- Golden service tests

⸻

9. Service Architecture

9.1 Recommended runtime architecture

Local Agent
   |
   | HTTP / MCP
   v
Aletheia Service Layer
   |
   +--> Auth / Capability Check
   +--> Request Validation
   +--> Namespace / Privacy Enforcement
   +--> Idempotency Guard
   +--> Memory Kernel Call
   +--> Audit Logging
   +--> Response Formatting
   |
   v
Aletheia Core Kernel
   |
   +--> Evidence Ledger
   +--> Claim Store
   +--> Retrieval
   +--> Context Pack
   +--> Confidence / Conflict / Curation
   +--> Ingestion / Inference / Reflection
   +--> Evaluation / Learning / Jobs
   |
   v
SQLite + Indexes + Optional Semantic Backends

⸻

9.2 Recommended service modes

M6 should support three service modes.

Embedded library mode

from aletheia import Memory
memory = Memory.open("./aletheia.db")

This remains unchanged.

⸻

Local daemon mode

aletheia serve --db ./aletheia.db

This exposes HTTP APIs.

⸻

MCP mode

aletheia mcp --db ./aletheia.db --namespace user/default

This exposes MCP tools for agent clients that support MCP.

⸻

9.3 Daemon and database concurrency

M6 should make the daemon the preferred multi-agent access pattern.

SQLite should be configured safely:

WAL mode enabled
busy timeout configured
transaction boundaries explicit
state-changing operations serialized where needed
idempotency records checked before mutation

Recommended default:

one daemon process per database file

If another daemon tries to open the same DB in write mode, it should warn or refuse unless explicitly configured.

⸻

10. Service Configuration Contract

10.1 Config file

M6 should support:

aletheia serve --config ./aletheia.toml

Example:

[server]
host = "127.0.0.1"
port = 8765
db = "./aletheia.db"
api_prefix = "/v1"
auto_migrate = false
[auth]
required = true
token_header = "Authorization"
[security]
allow_remote = false
default_privacy_ceiling = "personal"
request_log_mode = "metadata_only"
cors_allowed_origins = []
[mcp]
enabled = true
default_namespace = "user/default"
default_mode = "read_write_candidate"
[jobs]
worker_enabled = false
max_jobs_per_tick = 10
[limits]
max_request_bytes = 1048576
default_page_size = 50
max_page_size = 200
rate_limit_per_minute = 120

⸻

10.2 Environment variables

M6 should support:

ALETHEIA_DB
ALETHEIA_HOST
ALETHEIA_PORT
ALETHEIA_API_TOKEN
ALETHEIA_CONFIG
ALETHEIA_AUTH_REQUIRED

Environment variables may override config file values.

⸻

10.3 Startup behavior

When starting:

aletheia serve --db ./aletheia.db

The daemon must:

1. Load config.
2. Open database.
3. Check schema version.
4. Refuse outdated schema unless auto_migrate=true.
5. Initialize auth service.
6. Start HTTP server.
7. Optionally start job worker.
8. Write service instance log.

If auth is required and no token exists, the server should refuse write access and instruct the user to create a token:

aletheia auth create-token ...

It should not silently create an unrestricted admin token during migration.

⸻

11. Authentication and Authorization Contract

11.1 API clients

An API client represents an agent, app, or local process.

@dataclass
class ApiClient:
    id: str
    name: str
    client_type: str
    status: str
    created_at: datetime
    metadata: dict

Allowed client types:

agent
cli
mcp
sdk
admin
worker
test
unknown

⸻

11.2 API tokens

Tokens must be stored hashed.

Raw token values must never be stored.

@dataclass
class ApiToken:
    id: str
    client_id: str
    token_prefix: str
    token_hash: str
    status: str
    capabilities: list[str]
    namespace_grants: list[str]
    privacy_ceiling: str
    expires_at: datetime | None
    created_at: datetime
    revoked_at: datetime | None

Allowed token statuses:

active
revoked
expired
disabled

⸻

11.3 Capability names

M6 must define capability strings.

Minimum required capabilities:

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

Recommended default local-agent token:

memory:read
memory:context
memory:write_candidate
memory:feedback
memory:audit

Not included by default:

memory:write_active
memory:review
memory:policy
memory:delete
memory:admin

⸻

11.4 Namespace grants

Tokens must be restricted by namespace.

Example:

{
  "token_id": "tok_001",
  "namespace_grants": [
    "user/default",
    "user/default/projects/aletheia"
  ],
  "capabilities": [
    "memory:read",
    "memory:context",
    "memory:write_candidate"
  ],
  "privacy_ceiling": "personal"
}

A token for:

user/default/projects/aletheia

must not read:

user/default/projects/private_finances

unless explicitly granted.

⸻

11.5 Privacy ceiling

Every token should have a maximum privacy level it may access.

Allowed privacy levels:

public
personal
sensitive
secret

Default:

personal

A token with privacy ceiling personal must not retrieve memories marked:

sensitive
secret

⸻

11.6 Capability-gated write behavior

Over service interfaces:

Operation	Required capability
context pack	memory:context
search/retrieve	memory:read
remember candidate	memory:write_candidate
write active claim	memory:write_active
ingest	memory:ingest
extract candidates	memory:extract
promote/reject candidate	memory:review
feedback	memory:feedback
audit read	memory:audit
run evaluation	memory:evaluate
run learning	memory:learn
apply policy	memory:policy
delete/redact	memory:delete
service admin	memory:admin

⸻

12. HTTP API Contract

12.1 API prefix

All M6 HTTP endpoints must be under:

/v1

Example:

POST /v1/context-pack

⸻

12.2 Standard response envelope

All successful responses should use:

{
  "data": {},
  "request_id": "req_...",
  "warnings": [],
  "pagination": null
}

⸻

12.3 Standard error envelope

All errors should use:

{
  "error": {
    "code": "validation_error",
    "message": "The field 'namespace' is required.",
    "details": {}
  },
  "request_id": "req_..."
}

Required error codes:

unauthorized
forbidden
not_found
validation_error
conflict
integrity_gate_failed
stale_schema
rate_limited
idempotency_conflict
payload_too_large
unsupported_operation
internal_error

⸻

12.4 Request IDs

Every request must have a request ID.

If the client sends:

X-Request-ID

the server should preserve it.

Otherwise, the server generates one.

⸻

12.5 Idempotency keys

State-changing endpoints must support:

Idempotency-Key

Required for:

remember
ingest
extract
promote
reject
feedback
outcome
policy apply
procedure apply
delete/redact

If the same idempotency key is reused with the same payload, the same result should be returned.

If reused with a different payload, the server must return:

idempotency_conflict

⸻

12.6 Pagination

List endpoints should support:

limit
cursor

Response:

{
  "data": [],
  "pagination": {
    "next_cursor": "cursor_...",
    "limit": 50
  },
  "request_id": "req_...",
  "warnings": []
}

⸻

13. Required HTTP Endpoints

13.1 Health and version

GET /v1/health
GET /v1/ready
GET /v1/version
GET /v1/openapi.json

GET /v1/health

Response:

{
  "data": {
    "status": "ok",
    "schema_version": "0.7.0",
    "service_version": "0.7.0"
  },
  "request_id": "req_001",
  "warnings": []
}

GET /v1/ready

Must check:

database open
schema current
auth initialized
migrations not pending
optional worker health

⸻

13.2 Context pack

POST /v1/context-pack

Required capability:

memory:context

Request:

{
  "namespace": "user/default",
  "query": "Write the M6 contract.",
  "project_id": "aletheia",
  "session_id": null,
  "retrieval_mode": "hybrid",
  "token_budget": 2000,
  "include_reflections": true,
  "include_derivation_metadata": false,
  "record_usage": true,
  "policy_version_id": null
}

Response:

{
  "data": {
    "context_pack_id": "ctx_001",
    "markdown": "## Memory Context\n...",
    "sections": {
      "core_memory": [],
      "project_memory": [],
      "procedural_memory": [],
      "reflections": [],
      "warnings": []
    },
    "provenance": [],
    "policy": {
      "ranking_policy_version_id": "rpv_001",
      "context_policy_version_id": "cpv_001"
    }
  },
  "request_id": "req_001",
  "warnings": []
}

Required behavior:

- Enforce namespace grant.
- Enforce privacy ceiling.
- Preserve M2/M3/M4/M5 governance.
- Record usage if requested and authorized.
- Return structured and markdown context.

⸻

13.3 Retrieve/search

POST /v1/retrieve
POST /v1/search

Required capability:

memory:read

Request:

{
  "namespace": "user/default",
  "query": "architecture contract preference",
  "mode": "hybrid",
  "limit": 10,
  "project_id": "aletheia",
  "memory_types": ["preference", "procedure", "reflection"],
  "include_archived": false,
  "include_disputed": false
}

Required behavior:

- Exclude rejected/superseded memories.
- Respect conflict and scope rules.
- Respect privacy ceiling.
- Return provenance IDs.

⸻

13.4 Remember

POST /v1/remember

Required capability:

memory:write_candidate

or for active claims:

memory:write_active

Request:

{
  "namespace": "user/default",
  "write_mode": "candidate",
  "memory_type": "preference",
  "subject": "user",
  "predicate": "prefers_response_style",
  "object": "comprehensive architecture contracts",
  "source_type": "agent_observation",
  "confidence": 0.75,
  "project_id": "aletheia",
  "evidence_text": "The user asked for comprehensive milestone contracts."
}

Allowed write_mode:

candidate
active

Default:

candidate

Required behavior:

- Candidate writes require memory:write_candidate.
- Active writes require memory:write_active.
- Active writes must still pass M2 gates.
- All writes create evidence/provenance.
- All writes are audited.

⸻

13.5 Feedback and outcomes

POST /v1/feedback
POST /v1/outcomes
POST /v1/retrieval-judgments

Required capabilities:

memory:feedback

These endpoints expose M2/M5 feedback and outcome tracking.

Required behavior:

- Outcomes do not automatically confirm truth.
- Feedback must respect source rules.
- User correction signals must remain high priority.

⸻

13.6 Ingestion and extraction

POST /v1/ingest
POST /v1/extract
GET  /v1/candidates
GET  /v1/candidates/{candidate_id}
POST /v1/candidates/{candidate_id}/promote
POST /v1/candidates/{candidate_id}/reject

Required capabilities:

Endpoint	Capability
/v1/ingest	memory:ingest
/v1/extract	memory:extract
candidate review	memory:review

Required behavior:

- Ingestion treats content as data.
- Prompt injection flags remain active.
- Candidates are not facts until promoted.
- Promotion runs M2 integrity gates.

⸻

13.7 Claims and audit

GET  /v1/claims/{claim_id}
GET  /v1/claims/{claim_id}/explain
POST /v1/claims/{claim_id}/promote
POST /v1/claims/{claim_id}/demote
POST /v1/claims/{claim_id}/scope
POST /v1/claims/{old_claim_id}/supersede/{new_claim_id}
GET  /v1/audit/{target_type}/{target_id}

Required capabilities:

memory:read
memory:audit
memory:review

depending on endpoint.

⸻

13.8 Sessions and projects

POST /v1/sessions/start
POST /v1/sessions/{session_id}/end
GET  /v1/sessions
GET  /v1/sessions/{session_id}
POST /v1/projects
GET  /v1/projects
GET  /v1/projects/{project_id}

Required capabilities:

memory:read
memory:write_candidate
memory:context

depending on endpoint.

⸻

13.9 Conflicts, confidence, and curation

GET  /v1/conflicts
POST /v1/conflicts/detect
POST /v1/conflicts/{conflict_id}/resolve
GET  /v1/confidence/{claim_id}
POST /v1/confidence/recompute
POST /v1/curate/preview
POST /v1/curate/apply

Required capabilities:

memory:read
memory:review
memory:admin

depending on endpoint.

⸻

13.10 Inference, reflection, and derivation

POST /v1/infer/run
GET  /v1/inferences
POST /v1/inferences/{inference_id}/promote
POST /v1/inferences/{inference_id}/reject
POST /v1/reflections
GET  /v1/reflections
GET  /v1/reflections/{reflection_id}/expand
GET  /v1/derivation/{target_type}/{target_id}

Required behavior:

- Pending inferences are not facts.
- Reflections preserve source backlinks.
- Invalidated derived records do not appear as normal context.

⸻

13.11 Evaluation, learning, policies, and jobs

POST /v1/eval/sets
POST /v1/eval/sets/{eval_set_id}/cases
POST /v1/eval/sets/{eval_set_id}/run
POST /v1/optimize/retrieval
POST /v1/learning/run
GET  /v1/policies/proposals
POST /v1/policies/proposals/{proposal_id}/review
POST /v1/policies/proposals/{proposal_id}/apply
POST /v1/jobs
POST /v1/jobs/run
GET  /v1/jobs
GET  /v1/health-report

Required capabilities:

memory:evaluate
memory:learn
memory:policy
memory:jobs
memory:admin

⸻

14. MCP Contract

14.1 MCP server command

M6 must support:

aletheia mcp \
  --db ./aletheia.db \
  --namespace user/default \
  --mode read_write_candidate

Allowed modes:

read_only
read_write_candidate
read_write_active
admin

Default:

read_write_candidate

⸻

14.2 Required MCP tools

M6 must expose at least these tools.

memory_context_pack
memory_search
memory_remember
memory_feedback
memory_audit
memory_explain_claim
memory_health

Recommended additional tools:

memory_ingest
memory_extract_candidates
memory_list_candidates
memory_promote_candidate
memory_reject_candidate
memory_trace_derivation
memory_record_outcome

⸻

14.3 MCP tool: memory_context_pack

Input:

{
  "namespace": "user/default",
  "query": "Write the M6 contract.",
  "project_id": "aletheia",
  "retrieval_mode": "hybrid",
  "token_budget": 2000
}

Output:

{
  "context_pack_id": "ctx_001",
  "markdown": "## Memory Context\n...",
  "warnings": [],
  "provenance": []
}

Required capability:

memory:context

⸻

14.4 MCP tool: memory_search

Input:

{
  "namespace": "user/default",
  "query": "architecture contract preference",
  "mode": "hybrid",
  "limit": 10
}

Required capability:

memory:read

⸻

14.5 MCP tool: memory_remember

Input:

{
  "namespace": "user/default",
  "write_mode": "candidate",
  "memory_type": "preference",
  "subject": "user",
  "predicate": "prefers_response_style",
  "object": "comprehensive architecture contracts",
  "evidence_text": "Observed during interaction."
}

Default behavior:

write_mode = candidate

Required capability:

memory:write_candidate

Active claim writes require:

memory:write_active

⸻

14.6 MCP safety requirement

MCP tools must not expose unrestricted raw SQL, file access, arbitrary code execution, or direct database mutation.

All MCP operations must pass through the Aletheia service/kernel APIs.

⸻

15. Python Client SDK Contract

15.1 Client initialization

from aletheia_client import AletheiaClient
client = AletheiaClient(
    base_url="http://127.0.0.1:8765",
    token="...",
)

Async:

from aletheia_client import AsyncAletheiaClient
client = AsyncAletheiaClient(
    base_url="http://127.0.0.1:8765",
    token="...",
)

⸻

15.2 Required client methods

client.health()
client.context_pack(...)
client.retrieve(...)
client.remember(...)
client.feedback(...)
client.record_outcome(...)
client.audit(...)
client.explain_claim(...)
client.start_session(...)
client.end_session(...)
client.create_project(...)
client.list_jobs(...)
client.run_jobs(...)

⸻

15.3 Client behavior

The client must:

- Attach auth token.
- Attach request ID when provided.
- Support idempotency keys.
- Raise typed exceptions.
- Preserve server error details.
- Support timeout configuration.
- Not hide warnings.

Typed exceptions:

AletheiaUnauthorizedError
AletheiaForbiddenError
AletheiaValidationError
AletheiaIntegrityGateError
AletheiaRateLimitError
AletheiaServerError

⸻

16. Adapter Contract

16.1 AgentAdapter interface

class AgentMemoryAdapter:
    def before_agent_call(
        self,
        *,
        namespace: str,
        query: str,
        project_id: str | None = None,
        session_id: str | None = None,
    ) -> str:
        ...
    def after_agent_call(
        self,
        *,
        namespace: str,
        task_id: str,
        outcome: str | None = None,
        notes: str | None = None,
    ) -> None:
        ...
    def remember_candidate(
        self,
        *,
        namespace: str,
        subject: str,
        predicate: str,
        object: str,
        memory_type: str,
        evidence_text: str,
    ) -> str:
        ...

⸻

16.2 Required generic adapter

M6 must include a generic HTTP adapter that can be used by custom agents.

Optional adapters may include:

LangGraph adapter
LlamaIndex adapter
OpenAI-compatible tools adapter
Ollama/local-agent example
CrewAI example
AutoGen example

But M6 should not require these frameworks as core dependencies.

⸻

17. Storage Contract

17.1 Schema version

M6 updates schema version to:

0.7.0

⸻

17.2 Required new tables

api_clients

CREATE TABLE api_clients (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    client_type TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    metadata_json TEXT
);

⸻

api_tokens

CREATE TABLE api_tokens (
    id TEXT PRIMARY KEY,
    client_id TEXT NOT NULL,
    token_prefix TEXT NOT NULL,
    token_hash TEXT NOT NULL,
    status TEXT NOT NULL,
    privacy_ceiling TEXT NOT NULL DEFAULT 'personal',
    expires_at TEXT,
    created_at TEXT NOT NULL,
    revoked_at TEXT,
    metadata_json TEXT
);

⸻

capability_grants

CREATE TABLE capability_grants (
    id TEXT PRIMARY KEY,
    token_id TEXT NOT NULL,
    capability TEXT NOT NULL,
    created_at TEXT NOT NULL
);

⸻

namespace_access_grants

CREATE TABLE namespace_access_grants (
    id TEXT PRIMARY KEY,
    token_id TEXT NOT NULL,
    namespace TEXT NOT NULL,
    access_level TEXT NOT NULL,
    created_at TEXT NOT NULL
);

Allowed access levels:

read
context
write_candidate
write_active
review
admin

⸻

agent_registrations

CREATE TABLE agent_registrations (
    id TEXT PRIMARY KEY,
    namespace TEXT NOT NULL,
    name TEXT NOT NULL,
    agent_type TEXT,
    client_id TEXT,
    default_project_id TEXT,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    metadata_json TEXT
);

⸻

service_request_log

CREATE TABLE service_request_log (
    id TEXT PRIMARY KEY,
    request_id TEXT NOT NULL,
    client_id TEXT,
    agent_id TEXT,
    namespace TEXT,
    method TEXT NOT NULL,
    path TEXT NOT NULL,
    status_code INTEGER NOT NULL,
    duration_ms INTEGER,
    request_hash TEXT,
    response_hash TEXT,
    log_mode TEXT NOT NULL,
    created_at TEXT NOT NULL,
    metadata_json TEXT
);

⸻

mcp_tool_invocation_log

CREATE TABLE mcp_tool_invocation_log (
    id TEXT PRIMARY KEY,
    request_id TEXT NOT NULL,
    client_id TEXT,
    tool_name TEXT NOT NULL,
    namespace TEXT,
    status TEXT NOT NULL,
    duration_ms INTEGER,
    input_hash TEXT,
    output_hash TEXT,
    created_at TEXT NOT NULL,
    metadata_json TEXT
);

⸻

idempotency_records

CREATE TABLE idempotency_records (
    id TEXT PRIMARY KEY,
    namespace TEXT,
    client_id TEXT,
    idempotency_key TEXT NOT NULL,
    endpoint TEXT NOT NULL,
    request_hash TEXT NOT NULL,
    response_json TEXT,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    expires_at TEXT
);

⸻

rate_limit_records

CREATE TABLE rate_limit_records (
    id TEXT PRIMARY KEY,
    client_id TEXT NOT NULL,
    window_start TEXT NOT NULL,
    window_end TEXT NOT NULL,
    request_count INTEGER NOT NULL,
    created_at TEXT NOT NULL
);

⸻

service_config_history

CREATE TABLE service_config_history (
    id TEXT PRIMARY KEY,
    config_hash TEXT NOT NULL,
    config_redacted_json TEXT NOT NULL,
    source TEXT NOT NULL,
    created_at TEXT NOT NULL
);

⸻

service_instance_log

CREATE TABLE service_instance_log (
    id TEXT PRIMARY KEY,
    instance_id TEXT NOT NULL,
    host TEXT NOT NULL,
    port INTEGER,
    db_path TEXT NOT NULL,
    started_at TEXT NOT NULL,
    stopped_at TEXT,
    status TEXT NOT NULL,
    metadata_json TEXT
);

⸻

18. CLI Contract

18.1 aletheia serve

Purpose

Run the local HTTP daemon.

aletheia serve \
  --db ./aletheia.db \
  --host 127.0.0.1 \
  --port 8765

Options:

--config
--host
--port
--db
--auto-migrate
--no-auth
--allow-remote
--with-worker
--log-level

Required behavior:

- Bind to 127.0.0.1 by default.
- Require auth by default.
- Refuse stale schema unless auto-migrate enabled.
- Write service instance log.
- Print OpenAPI URL.

⸻

18.2 aletheia mcp

Purpose

Run MCP server.

aletheia mcp \
  --db ./aletheia.db \
  --namespace user/default \
  --mode read_write_candidate

Options:

--mode read_only|read_write_candidate|read_write_active|admin
--namespace
--project
--token
--config

⸻

18.3 aletheia auth

Purpose

Manage API tokens.

aletheia auth create-token \
  --db ./aletheia.db \
  --client local-agent \
  --namespace user/default \
  --capabilities memory:read,memory:context,memory:write_candidate,memory:feedback \
  --privacy-ceiling personal
aletheia auth list-tokens \
  --db ./aletheia.db
aletheia auth revoke-token tok_001 \
  --db ./aletheia.db \
  --reason "Rotating local agent token."

Important:

create-token is the only time the raw token is displayed.

⸻

18.4 aletheia clients

Purpose

Manage registered API clients and agents.

aletheia clients create \
  --db ./aletheia.db \
  --name local-research-agent \
  --type agent
aletheia clients list \
  --db ./aletheia.db
aletheia clients disable cli_001 \
  --db ./aletheia.db

⸻

18.5 aletheia api

Purpose

Inspect API schema and service behavior.

aletheia api openapi \
  --db ./aletheia.db \
  --output ./openapi.json
aletheia api routes
aletheia api ping \
  --url http://127.0.0.1:8765

⸻

18.6 aletheia worker

Purpose

Run local M5 jobs through the service layer.

aletheia worker run \
  --db ./aletheia.db \
  --max-jobs 10
aletheia worker watch \
  --db ./aletheia.db

watch may be optional, but run is required.

⸻

18.7 aletheia service

Purpose

Inspect service logs and status.

aletheia service status \
  --db ./aletheia.db
aletheia service requests \
  --db ./aletheia.db \
  --limit 50
aletheia service mcp-log \
  --db ./aletheia.db

⸻

19. Backward Compatibility Contract

M6 must preserve M5 behavior.

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

Allowed M6 changes:

- Add service APIs.
- Add auth tables.
- Add request logs.
- Add HTTP/MCP protocol layers.
- Add client SDKs.
- Add service configuration.

Not allowed:

- Breaking local library mode.
- Breaking existing CLI commands.
- Requiring service mode for library users.
- Requiring network access.
- Requiring cloud accounts.
- Exposing memory without explicit authorization by default.
- Letting service calls bypass memory integrity gates.

⸻

20. Migration Contract

20.1 Migration path

M6 must support:

0.6.x → 0.7.0

⸻

20.2 Migration command

aletheia migrate --db ./aletheia.db

or:

memory = Memory.open("./aletheia.db", auto_migrate=True)

⸻

20.3 Migration rules

- Existing evidence remains unchanged.
- Existing claims remain unchanged.
- Existing candidates remain unchanged.
- Existing inferences and reflections remain unchanged.
- Existing policy and learning data remain unchanged.
- New service/auth tables are added.
- No unrestricted token is created automatically.
- No daemon is started automatically.
- No MCP server is started automatically.
- Migration must be idempotent.

⸻

20.4 Initial migration behavior

During migration, Aletheia should:

1. Add M6 tables.
2. Insert no default tokens.
3. Insert no external clients.
4. Preserve all M5 behavior.
5. Mark schema version as 0.7.0.

After migration, users create tokens explicitly:

aletheia auth create-token ...

⸻

21. Security Contract

21.1 Default bind policy

Default:

127.0.0.1 only

Binding to public interfaces requires:

--allow-remote

and authentication must remain enabled.

⸻

21.2 Token storage

Tokens must be stored as hashes only.

The raw token appears only once during creation.

⸻

21.3 Authorization failure behavior

If a token lacks access, the server must return:

403 forbidden

not silently downgrade to another namespace.

⸻

21.4 Privacy ceiling failure

If a request would retrieve memory above the token privacy ceiling, the server should either:

omit those memories

or return:

403 forbidden

depending on endpoint.

Context pack and retrieval should usually omit inaccessible memories and include a generic warning:

Some memories were omitted due to access policy.

Do not reveal secret memory titles or content in the warning.

⸻

21.5 Dangerous operations

These require stronger capability and audit logging:

write_active
promote_core
apply_policy
run_learning_apply
delete
redact
resolve_conflict
admin_config_change

⸻

22. Request Audit Contract

22.1 Required request logging

M6 must log service requests.

Default log mode:

metadata_only

Metadata includes:

request_id
client_id
agent_id
namespace
method
path
status
duration
created_at

⸻

22.2 Body logging

Full body logging must be disabled by default.

Allowed modes:

metadata_only
hashes
redacted_body
full_body

Default:

metadata_only

full_body must require explicit configuration.

⸻

22.3 State-changing audit

Service request logs are not enough.

State-changing requests must also write ordinary Aletheia audit events.

Example:

HTTP POST /v1/remember
  -> service_request_log
  -> evidence event
  -> candidate claim
  -> audit event

⸻

23. Rate Limiting and Loop Protection

23.1 Purpose

Agents can loop. Memory services must defend against runaway writes.

M6 must support simple local rate limits.

Default suggested limits:

120 requests/minute per token
30 state-changing requests/minute per token
10 candidate writes/minute per token

These should be configurable.

⸻

23.2 Write loop protection

If one agent writes many near-duplicate memories rapidly, Aletheia should:

rate limit
deduplicate
force candidate mode
or require review

depending on policy.

M6 does not need advanced abuse detection, but it must have basic brakes.

⸻

24. OpenAPI Contract

M6 must expose:

GET /v1/openapi.json

The OpenAPI schema must include:

all required endpoints
request schemas
response schemas
error schemas
auth scheme
capability notes
version information

The schema should be usable by local code generators and agent tool generators.

⸻

25. MCP Tool Governance Contract

MCP tool descriptions must be explicit about what each tool can and cannot do.

Example for memory_remember:

Stores a candidate memory unless the configured token has active-write permission.
This tool does not promote memories to core.
All writes are auditable.

Bad tool description:

Store anything permanently in memory.

MCP tools should encourage candidate-first writes.

⸻

26. Service and Worker Integration

M6 should allow:

aletheia serve --with-worker

or separate worker:

aletheia worker run --db ./aletheia.db

Required behavior:

- Worker processes M5 local jobs.
- Worker uses same kernel APIs.
- Worker writes audit events.
- Worker respects namespace policies where relevant.
- Worker failures are stored in local_jobs.

⸻

27. Test Contract

27.1 HTTP API tests

Required tests:

test_health_endpoint
test_ready_endpoint_checks_schema
test_openapi_endpoint_returns_schema
test_context_pack_endpoint
test_retrieve_endpoint
test_remember_candidate_endpoint
test_feedback_endpoint
test_audit_endpoint
test_jobs_endpoint

⸻

27.2 Auth tests

Required tests:

test_request_without_token_rejected_when_auth_required
test_valid_token_allows_request
test_revoked_token_rejected
test_expired_token_rejected
test_token_hash_stored_not_raw_token
test_token_capability_required_for_write
test_admin_capability_required_for_admin_endpoint

⸻

27.3 Namespace and privacy tests

Required tests:

test_token_cannot_read_ungranted_namespace
test_token_can_read_granted_namespace
test_privacy_ceiling_omits_sensitive_memory
test_secret_memory_not_leaked_in_warning
test_project_scoped_token_cannot_read_other_project

⸻

27.4 MCP tests

Required tests:

test_mcp_context_pack_tool
test_mcp_search_tool
test_mcp_remember_defaults_to_candidate
test_mcp_remember_active_requires_capability
test_mcp_tool_invocation_logged
test_mcp_tools_respect_namespace_grants

⸻

27.5 Idempotency tests

Required tests:

test_idempotency_key_replays_same_response
test_idempotency_key_rejects_different_payload
test_state_changing_endpoint_supports_idempotency
test_idempotency_record_expires

⸻

27.6 Request audit tests

Required tests:

test_service_request_logged
test_state_changing_request_writes_audit_event
test_metadata_only_logging_does_not_store_body
test_request_id_propagated
test_mcp_invocation_logged

⸻

27.7 Rate limit tests

Required tests:

test_rate_limit_applies_per_token
test_rate_limit_returns_rate_limited_error
test_state_changing_rate_limit_applies
test_rate_limit_can_be_disabled_in_test_config

⸻

27.8 Client SDK tests

Required tests:

test_python_client_context_pack
test_python_client_remember_candidate
test_python_client_handles_validation_error
test_python_client_handles_forbidden_error
test_python_async_client_context_pack
test_client_sends_idempotency_key

⸻

27.9 Worker tests

Required tests:

test_worker_runs_pending_job
test_worker_records_failure
test_worker_respects_max_jobs
test_worker_writes_audit_for_state_change

⸻

27.10 Migration tests

Required tests:

test_migration_from_m5_to_m6_adds_service_tables
test_migration_preserves_existing_claims
test_migration_preserves_policies
test_migration_does_not_create_unrestricted_token
test_migration_does_not_start_service
test_migration_is_idempotent

⸻

28. Golden M6 Tests

Golden test 1 — Local agent gets context

Given:

Aletheia daemon is running.
A token has memory:context for namespace user/default.

When:

POST /v1/context-pack

Expected:

- HTTP 200.
- Context pack returned.
- Provenance preserved.
- Request logged.
- Usage recorded if requested.

⸻

Golden test 2 — Unauthorized agent cannot read memory

Given:

Token grants namespace user/default/projects/aletheia.

When agent requests:

namespace user/default/projects/private

Expected:

- HTTP 403.
- No memory content returned.
- Request logged.

⸻

Golden test 3 — MCP remember is candidate-first

Given:

MCP server runs in read_write_candidate mode.

When:

memory_remember

Expected:

- Candidate memory created.
- No active claim created.
- Audit record created.

⸻

Golden test 4 — Active write requires stronger capability

Given:

Token has memory:write_candidate but not memory:write_active.

When:

POST /v1/remember with write_mode=active

Expected:

- HTTP 403.
- No active claim created.
- Request logged.

⸻

Golden test 5 — Sensitive memory is not leaked

Given:

A secret memory exists.
Token privacy ceiling is personal.

When:

POST /v1/context-pack

Expected:

- Secret memory omitted.
- No secret title/content in warning.
- Response may say some memories were omitted by access policy.

⸻

Golden test 6 — Idempotent write

Given:

POST /v1/remember with Idempotency-Key abc123

When the same request is repeated:

same key, same payload

Expected:

- Same response returned.
- No duplicate memory created.

When repeated with different payload:

same key, different payload

Expected:

- idempotency_conflict error.

⸻

29. Acceptance Criteria

M6 is complete only when all of the following are true.

29.1 Daemon acceptance

[ ] aletheia serve starts local daemon.
[ ] Daemon binds to 127.0.0.1 by default.
[ ] Daemon refuses stale schema unless migration allowed.
[ ] Health/readiness/version endpoints work.
[ ] OpenAPI schema is exposed.

⸻

29.2 HTTP API acceptance

[ ] HTTP context-pack endpoint works.
[ ] HTTP retrieval endpoint works.
[ ] HTTP remember endpoint works.
[ ] HTTP feedback/outcome endpoints work.
[ ] HTTP audit/explain endpoints work.
[ ] Admin endpoints are capability-gated.
[ ] Standard response/error envelopes are used.

⸻

29.3 MCP acceptance

[ ] aletheia mcp starts MCP server.
[ ] memory_context_pack works.
[ ] memory_search works.
[ ] memory_remember works.
[ ] memory_feedback works.
[ ] memory_audit works.
[ ] MCP writes default to candidate mode.
[ ] MCP tools respect capabilities and namespaces.

⸻

29.4 Auth acceptance

[ ] API tokens can be created.
[ ] Raw tokens are shown only once.
[ ] Token hashes are stored, not raw tokens.
[ ] Revoked tokens fail.
[ ] Expired tokens fail.
[ ] Capabilities are enforced.
[ ] Namespace grants are enforced.
[ ] Privacy ceilings are enforced.

⸻

29.5 Audit acceptance

[ ] Service requests are logged.
[ ] MCP invocations are logged.
[ ] State-changing operations write Aletheia audit events.
[ ] Metadata-only logging avoids storing sensitive bodies by default.

⸻

29.6 Client and adapter acceptance

[ ] Python client can call context_pack.
[ ] Python client can call remember candidate.
[ ] Python client handles typed errors.
[ ] Async Python client works.
[ ] Generic HTTP adapter works for local agents.

⸻

29.7 Worker acceptance

[ ] Worker can run local jobs.
[ ] Worker failures are recorded.
[ ] Worker state changes are audited.

⸻

29.8 Migration acceptance

[ ] M5 database migrates to M6.
[ ] Migration is idempotent.
[ ] Existing memories remain retrievable.
[ ] Existing policies remain valid.
[ ] No unrestricted token is created during migration.
[ ] No daemon or MCP server starts during migration.

⸻

30. M6 Demo Script

This should be the official M6 demo.

⸻

Step 1 — Migrate

aletheia migrate --db ./aletheia.db

Expected:

Schema migrated to 0.7.0.
Service tables created.
No token created automatically.

⸻

Step 2 — Create client

aletheia clients create \
  --db ./aletheia.db \
  --name local-contract-agent \
  --type agent

Expected:

Client created:
id: cli_001

⸻

Step 3 — Create token

aletheia auth create-token \
  --db ./aletheia.db \
  --client cli_001 \
  --namespace user/default \
  --capabilities memory:read,memory:context,memory:write_candidate,memory:feedback,memory:audit \
  --privacy-ceiling personal

Expected:

Token created.
Raw token:
atl_...

The raw token is shown once.

⸻

Step 4 — Start daemon

aletheia serve \
  --db ./aletheia.db \
  --host 127.0.0.1 \
  --port 8765

Expected:

Aletheia service running.
HTTP API: http://127.0.0.1:8765/v1
OpenAPI: http://127.0.0.1:8765/v1/openapi.json

⸻

Step 5 — Call health endpoint

curl http://127.0.0.1:8765/v1/health

Expected:

{
  "data": {
    "status": "ok"
  }
}

⸻

Step 6 — Request context pack

curl -X POST http://127.0.0.1:8765/v1/context-pack \
  -H "Authorization: Bearer atl_..." \
  -H "Content-Type: application/json" \
  -d '{
    "namespace": "user/default",
    "project_id": "aletheia",
    "query": "Write the M6 contract.",
    "retrieval_mode": "hybrid",
    "record_usage": true
  }'

Expected:

Context pack returned.
Usage recorded.
Request logged.

⸻

Step 7 — Remember through service

curl -X POST http://127.0.0.1:8765/v1/remember \
  -H "Authorization: Bearer atl_..." \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: demo-m6-remember-001" \
  -d '{
    "namespace": "user/default",
    "write_mode": "candidate",
    "memory_type": "project",
    "subject": "project:aletheia",
    "predicate": "current_milestone",
    "object": "M6 Agent Interoperability",
    "evidence_text": "The user requested the M6 contract."
  }'

Expected:

Candidate memory created.
No active claim created unless promoted.
Audit record written.

⸻

Step 8 — Start MCP server

aletheia mcp \
  --db ./aletheia.db \
  --namespace user/default \
  --mode read_write_candidate

Expected:

MCP tools available:
- memory_context_pack
- memory_search
- memory_remember
- memory_feedback
- memory_audit

⸻

Step 9 — Inspect service logs

aletheia service requests \
  --db ./aletheia.db \
  --limit 20

Expected:

Recent requests shown with request_id, client_id, endpoint, status, duration.
No raw sensitive body stored by default.

⸻

Step 10 — Revoke token

aletheia auth revoke-token tok_001 \
  --db ./aletheia.db \
  --reason "Demo complete."

Expected:

Token revoked.
Subsequent API calls fail with unauthorized.

⸻

31. M6 Implementation Checklist

Daemon

[ ] Add AletheiaDaemon
[ ] Add HTTP server
[ ] Add config loader
[ ] Add service startup checks
[ ] Add health endpoint
[ ] Add readiness endpoint
[ ] Add OpenAPI endpoint
[ ] Add service instance log

⸻

HTTP API

[ ] Add standard response envelope
[ ] Add standard error envelope
[ ] Add request ID middleware
[ ] Add context-pack endpoint
[ ] Add retrieve/search endpoint
[ ] Add remember endpoint
[ ] Add feedback/outcome endpoints
[ ] Add ingest/extract/candidate endpoints
[ ] Add audit/explain endpoints
[ ] Add sessions/projects endpoints
[ ] Add jobs/health/eval endpoints

⸻

Auth and capabilities

[ ] Add ApiClient model
[ ] Add ApiToken model
[ ] Store token hashes only
[ ] Add token creation
[ ] Add token revocation
[ ] Add capability checks
[ ] Add namespace grant checks
[ ] Add privacy ceiling checks
[ ] Add auth CLI commands

⸻

MCP

[ ] Add MCP server
[ ] Add MCP tool registry
[ ] Add memory_context_pack tool
[ ] Add memory_search tool
[ ] Add memory_remember tool
[ ] Add memory_feedback tool
[ ] Add memory_audit tool
[ ] Add memory_explain_claim tool
[ ] Add MCP invocation logging
[ ] Enforce capabilities in MCP tools

⸻

Request logging and idempotency

[ ] Add service request logger
[ ] Add metadata-only default logging
[ ] Add idempotency records
[ ] Add idempotency middleware
[ ] Add rate limiter
[ ] Add request audit integration

⸻

Clients and adapters

[ ] Add Python sync client
[ ] Add Python async client
[ ] Add typed client errors
[ ] Add generic HTTP agent adapter
[ ] Add example local agent integration
[ ] Optionally add TypeScript client

⸻

Worker

[ ] Add worker command
[ ] Integrate with M5 local_jobs
[ ] Add worker audit behavior
[ ] Add worker failure recording

⸻

Migration

[ ] Add schema version 0.7.0
[ ] Add migration from 0.6.x
[ ] Add service/auth tables
[ ] Ensure no unrestricted token is created
[ ] Ensure no daemon starts during migration
[ ] Add migration tests

⸻

Tests

[ ] HTTP API tests
[ ] Auth tests
[ ] Namespace tests
[ ] Privacy ceiling tests
[ ] MCP tests
[ ] Idempotency tests
[ ] Request audit tests
[ ] Rate limit tests
[ ] Client SDK tests
[ ] Worker tests
[ ] Migration tests
[ ] Golden M6 tests

⸻

32. M6 Definition of Done

M6 is done when this statement is true:

Any local AI agent can use Aletheia through HTTP or MCP without direct database access, while Aletheia enforces namespace isolation, capability permissions, privacy ceilings, audit logging, and all memory integrity rules.

More practically, M6 is complete when Aletheia can do all of this:

- Run as a local daemon.
- Expose versioned HTTP APIs.
- Expose MCP tools.
- Authenticate local agents.
- Restrict tokens by namespace, capability, and privacy ceiling.
- Return context packs over the network.
- Accept candidate memories from agents.
- Record feedback and outcomes.
- Log service requests safely.
- Prevent unauthorized reads/writes.
- Preserve all M0–M5 memory governance.
- Provide a Python client and generic adapter.
- Run local jobs through the service layer.

M6 is where Aletheia becomes usable by the wider local-agent ecosystem.
It stops being only a library and becomes a memory service.