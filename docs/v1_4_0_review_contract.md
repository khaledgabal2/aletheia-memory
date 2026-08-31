# Governed review contract: memory-review-v1

This development contract is client-neutral and independent of Desktop. Check
`GET /v1/auth/me` for `memory-review-v1` before using it. The published 1.3.1
service does not implement this profile. Ordinary agents should retain only
candidate-write/read/context access; an explicit reviewer needs `memory:review`
and grants covering the candidate and its provenance. Admin does not widen
namespace, project or privacy scope.

## Inspect, decide, recover

Send `X-Aletheia-Contract: memory-review-v1` on these operations:

| Operation | Result |
| --- | --- |
| `GET /v1/candidates?namespace=…` | Authorized candidates, each with an opaque revision, and keyset pagination. |
| `GET /v1/candidates/{candidate_id}` | Current authorized candidate, provenance and revision. |
| `POST /v1/candidates/{candidate_id}/promote` | Atomic promotion receipt. |
| `POST /v1/candidates/{candidate_id}/reject` | Atomic rejection receipt. |

Writes accept only `reason` and `expected_revision` in JSON. Send an explicit
`Idempotency-Key`: 1–200 ASCII letters, digits, dots, underscores, colons or hyphens.
No force, implicit edit, automatic approval or automatic stale retry is offered.
Reasons must contain non-whitespace text and be at most 4096 characters.

1. Inspect the candidate, its evidence and proposed scope.
2. Obtain the reviewer's decision about that exact state.
3. Submit its revision, the reason and a new operation key.
4. If the response is lost, retain the **same key, action and complete payload**.
   Retry that operation; do not create another key to resolve uncertainty.
5. A 412 means memory changed. Refresh, show the new state and ask for a new
   decision. Do not silently transfer the previous approval to the new state.

| Status/code | Meaning |
| --- | --- |
| 428 `precondition_required` | Negotiated write has no revision. |
| 412 `stale_revision` | State, access, service instance or restore generation changed. |
| 400 `validation_error` | Invalid body or missing/invalid operation key. |
| 409 `idempotency_conflict` | This credential already used the key for different input or another operation. |
| 409 `review_conflict` | Candidate is promoted, rejected, duplicate or invalid. |
| 401/403 | Credential or current resource access does not permit the operation or replay. |
| 503 `database_busy` | A consistent transaction could not be acquired; retain the same key/payload. |

Normal governance validation can still reject promotion. The response is an
envelope with `data`, `request_id`, `warnings` and `pagination: null`. `data`
contains operation/audit/decision/candidate identifiers, optional promoted claim
ID, action, reviewed/result revisions and application time. It contains no copy
of evidence, claim text or review reason. Read the current claim or audit through
the read profile with the corresponding capability when needed.

A successful replay returns the original receipt and operation ID with the
current transport request ID. Authorization is rechecked before replay; changing
credential, revoking access or narrowing scope cannot recover another caller's
receipt. Keys remain replayable for 24 hours. Expired keys do not bypass revision
or terminal-state checks. Service restart retains successful receipts but
invalidates old revisions and cursors. Restore clears receipts and changes the
service cache identity. All responses use `Cache-Control: no-store`; do not store
credentials or sensitive candidate data in persistent browser storage.

## Python SDK

The new SDK has synchronous and asynchronous versions of
`get_candidate_for_review`, `list_candidates_for_review` and `review_candidate`.
They refuse services without the profile. For an already inspected candidate and
an explicitly collected decision:

```python
outcome = reviewer.review_candidate(
    candidate_id,
    action="promote",  # Only after the operator approves the inspected state.
    reason=decision_reason,
    expected_revision=inspected["revision"],
    idempotency_key=operation_key,
)
```

Catch `AletheiaStaleRevisionError` to return to inspection. Neither SDK generates
a write key nor automatically retries. The generated TypeScript `Reviewer` and
real HTTP/browser harnesses live in `contracts/typescript` in the source archive;
see the [tooling instructions](../contracts/typescript/README.md). They are not a
separately published npm SDK.

## List semantics and invalidation

The list requires an explicit namespace. Optional filters are `status`,
`memory_type` and `project_id`; `limit` defaults to 50 and permits 1–200. The
envelope's pagination contains `limit`, `count` and nullable `next_cursor`.
Continue with the same filters and limit plus `cursor`. Ordering is
`created_at DESC, id ASC`; one extra authorized row establishes continuation.
Hidden rows do not create skipped visible results. There is no total-count claim.

Cursors are encrypted, expire after 15 minutes and bind filters, limit, access,
service instance and review state. Changed binding gives 409 `stale_cursor`;
malformed/expired cursors give 400 `invalid_cursor`. Restart from the first page.
A page scans at most 10,000 stored candidates; beyond that, 503
`review_scan_limit` asks the caller to narrow filters. This bound avoids an
unbounded privacy-filtering scan; it is not a guarantee about very large datasets.

Database-wide invalidation is intentionally conservative. Any domain or policy
write, even in another namespace, can invalidate inspections. Embedded, CLI,
HTTP, background, federation and restore writers participate. Returning a field
to its original value does not restore an old revision. Operational read logging
does not advance revisions. No claim of per-candidate revision precision is made.

## Legacy behavior and storage

Unconditioned calls without the profile retain legacy response shapes and write
meaning. Supplying `expected_revision` opts into the entire guarded workflow,
including the required key and receipt response, even without the header.
Unsupported profile headers are refused. The legacy console refuses supplied
revision fields and directs callers to these endpoints. Legacy replay also
checks current access; a changed stored promotion result returns 409
`replay_result_changed` instead of obsolete content. This is an intentional
safety correction, not a new legacy replay guarantee.

Storage advances from 1.3.0 to **1.3.1**, independently of software release
version. Read the [migration and recovery guide](v1_4_0_migration_guide.md) before
opening an existing database with migration enabled. The complete trigger
inventory and operational exclusions are in the [storage design](v1_4_0_review_migration_design.md).
