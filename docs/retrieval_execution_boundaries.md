# Retrieval and provider execution boundaries

## Eligibility before ranking and limits

Default lexical, semantic, and hybrid retrieval includes only `active` and
`core` claims. Embedded callers can explicitly opt into legacy
`claims.status = 'candidate'` with `include_candidates=True` or
`statuses=['candidate']`. This does not retrieve the separate review queue
in `candidate_claims`. Rejected and unknown statuses are always excluded;
archived, superseded, and disputed claims retain their explicit opt-ins.

Claim validity and matching claim scopes are checked before candidate selection
and the requested result limit. A validity window includes `valid_from` and
excludes `valid_to`; a null bound is open. Timestamps with offsets are compared
as instants. Malformed stored bounds are ineligible. Ordinary reads use the
current time. Embedded retrieval also supports an explicit historical instant:

```python
results = memory.retrieve(
    namespace="example",
    query="deployment preference",
    filters={"as_of": "2026-09-01T00:00:00Z"},
)
```

This evaluates validity windows against the currently stored records; it does
not reconstruct past content, status, authorization, or deleted data. The HTTP
read contract does not expose `as_of` as a supported input.

All eligible lexical matches and indexed semantic vectors can compete,
including old memories. Relevance selects a bounded set for the more expensive
provenance/conflict reranking. The local SQLite/vector implementation still
scans matching rows and eligible vectors; this is not an approximate-nearest-
neighbor index or a production-scale throughput guarantee. Returned results
remain ranked top-N, without an exhaustive enumeration or cursor guarantee.

HTTP reads apply the caller's current source privacy and scope before selecting
results and allocating context tokens. Hidden claims cannot crowd out visible
ones by consuming the result limit. Hidden reflections, inferences, and warnings
do not consume the context budget. Final response filtering also removes hidden
related IDs. The same rules apply to retrieval/context aliases and traces.

## Provider waits and current access

The HTTP service serializes database work on its shared SQLite connection.
Governed routes that call LLM or embedding providers release the service lock
and roll back their preliminary database snapshot before provider construction
or inference. Other requests, including health checks and independent writes,
can proceed while a provider is waiting. Embedded calls keep their direct
execution behavior.

After provider work, the route runs again in a fresh transaction. It rechecks
credentials, object scope, source privacy, and provider permissions before
using a request-local cached result. Results are reused only for the same
provider and inputs. Changed inputs return `409 provider_input_changed`;
revoked credentials or newly denied sources return their normal access errors.
No stale provider output is saved or returned in those cases. Callers may submit
a new request after inspecting the changed state. Access changes cannot recall
source bytes already sent to a provider before that change.

Provider failures roll back that operation without rolling back another
request's committed work. Existing idempotency reservations remain active while
a provider is running, so concurrent requests with the same key cannot duplicate
the call. The request cache is discarded when the request finishes. This does
not promise concurrent execution of database phases or slow administrative
filesystem work.

HTTP job execution commits the existing `running` claim and attempt count before
provider work starts. That ownership survives the temporary snapshot rollback,
so another service or worker cannot pick up the same pending job. Completion
commits the results once. A failed request returns unfinished owned jobs to
`pending`, or marks them `failed` when their attempt limit is reached. Snapshot
retries do not consume another job attempt or repeat successful provider calls.

## Python SDK redirects

The synchronous and asynchronous Python SDK reject service redirects, including
same-origin redirects. A 3xx response raises `AletheiaClientError` with
`code='redirect_blocked'` and the original HTTP status. The SDK neither follows
nor automatically retries it, so bearer credentials and mutation bodies cannot
be forwarded to a redirect destination. Configure the final service URL
explicitly. Normal direct requests and existing transport-error retry behavior
are unchanged.
