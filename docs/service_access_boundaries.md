# HTTP access boundaries

Service authorization combines capabilities, stored namespace/project scope,
and current source privacy. Supplying an authorized namespace or project in a
request does not authorize an object stored elsewhere. Denied operations do
not change the referenced memory; request accounting can still record the
denial.

## Object operations and session summaries

The service resolves referenced objects before session end, feedback, candidate
and claim review, conflict resolution, explicit reasoning-source operations,
evaluation-set operations, and policy review/application. Replacement claims,
feedback evidence, and other explicit source IDs are checked individually.
Target authorization and the corresponding database changes share a transaction.
Provider work releases that snapshot and the service lock, then the route
rechecks current authorization and source inputs before saving or returning
the result. See [retrieval and provider execution](retrieval_execution_boundaries.md)
for changed-input errors and concurrency limits.

`POST /v1/sessions/{session_id}/end` requires `memory:write_candidate` and
access to the stored session's scope. With a nonempty `summary`, the default
`write_mode` is `candidate`: the summary becomes a pending review candidate
with source evidence linked to the session. It is not marked `tool_verified`.
An explicit `write_mode: "active"` also requires `memory:write_active` and
uses the normal active-write path. `privacy_level` is checked against the
caller ceiling. Session completion and summary creation succeed or roll back
together.

Omitting the summary or setting `remember_summary: false` ends the session
without saving a summary. The response remains the session object. This HTTP
default does not change the trusted embedded `Memory.end_session` API.

## Approved LLM providers and source authorization

HTTP LLM routes accept the built-in IDs `mock`, `mock_llm`, `llm`, `local_http`,
`ollama_style`, and `openai_compatible`. Network providers use operator-managed
endpoint configuration. A native provider must be installed and enabled with
`plugin_type = "llm_provider"`; requests use `plugin:<installation ID>` or
`plugin:<registered name>`. Raw `plugin:module:factory` values and the bare
`plugin` environment fallback are rejected before any Python import.

Example manifest for a local source-task provider:

```toml
[plugin]
name = "review-provider"
version = "1.0.0"
plugin_type = "llm_provider"
entrypoint = "review_provider:Provider"
description = "Local provider for reviewed source tasks."

[compatibility]
aletheia_min_version = "1.0.0"
api_contract_version = "1.3.0"

[permissions]
permissions_required = ["read_claim_text", "read_evidence_text"]
external_network_access = false
reads_memory_content = true
writes_memory = false
stores_data = false
```

Install and enable through the existing operator plugin workflow, explicitly
approving the declared permissions. Source tasks require both `read_claim_text`
and `read_evidence_text`. External providers additionally require `use_network`.
The service checks installation status, current grants, declared caller
capabilities, and the manifest's network policy on every request.

All evidence is authorized before constructing a provider. Candidate tasks
check candidate provenance; duplicate suggestions also check each proposed
merge target; conflict explanations check all participating claims. Provider
disclosure rules apply in addition to caller authorization: secret evidence is
blocked, and private/sensitive evidence cannot go to external providers. An
authorized local provider can process private evidence for a caller whose
privacy ceiling permits it. LLM run lists recheck their recorded source IDs
against current access.

The embedded and CLI provider APIs remain trusted local interfaces; their raw
entrypoint support is unchanged.

## Traces

HTTP retrieval and context traces filter included and omitted objects before
writing trace items. Reads of both new and existing traces recheck each
object's current namespace, project provenance, privacy, and tombstones. Trace
responses omit arbitrary historical warning/derivation metadata and event
payloads that lack independent source authorization.

New HTTP traces label query text with the creator's privacy ceiling. A reader
below that ceiling receives `query: null`. Older traces without a query privacy
label also return `query: null`; their unclassified text remains available to
the trusted embedded API. This read behavior does not rewrite stored historical
traces.

Embedded `trace_retrieval` accepts optional `result_filter`, `claim_filter`, and
`query_privacy` arguments. `trace_context_pack` similarly accepts `context_filter`,
`claim_filter`, `query_privacy`, and `read_access`. The service supplies its current access
policy through these hooks. Embedded callers are responsible for any policy
they need when creating traces directly.

## Explicit scope for operational lists

Supply an authorized `namespace` query parameter for:

- `/v1/traces`, `/v1/llm/runs`, and `/v1/jobs`;
- `/v1/metrics/snapshots`, `/v1/metrics/latest`, `/v1/notifications`, and `/v1/reports`;
- `/v1/shares`, `/v1/grants`, and `/v1/grants/consent`;
- `/v1/sync/collections`, `/v1/sync/runs`, `/v1/sync/conflicts`,
  `/v1/sync/cursors`, and `/v1/sync/remote-sources`;
- `/v1/workspaces`, `/v1/workspaces/agent-groups`, and `/v1/revocations`.

Omission requires the literal `*` namespace grant as well as the route's
capability. A scoped admin token does not gain global access. Global job runs,
metric snapshots, and global report reads/exports follow the same scope rule.
Namespace-filtered revocations include that namespace's share-grant records;
peer and identity revocations belong to the global view.

Federation history filters run in SQL before ordering/limits. The Python SDK
accepts `namespace` on `sync_collections`, `sync_runs`, `remote_sources`, and
`list_revocations`, including asynchronous calls:

```python
runs = client.sync_runs(namespace="tenant/a", limit=20)
sources = await async_client.remote_sources(namespace="tenant/a")
```

Federation imports authorize the namespace/project from the verified signed
grant, including dry runs. Every imported content item must use the grant's
namespace. A caller-supplied namespace cannot override it. Embedded
`import_share_bundle` and `sync` accept an optional `authorize_scope(namespace,
project_id)` callback; the HTTP service supplies its scope checker. Import
authorization runs before database changes in the same import transaction.
