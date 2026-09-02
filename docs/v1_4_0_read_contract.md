# 1.4.0 read contract

Memory 1.4.0 advertises `memory-read-v1` after its conformance gates.
[Governed review](v1_4_0_review_contract.md) and
[agent onboarding](v1_4_0_agent_onboarding_contract.md) are separate profiles.
The original Phase 2 work introduced this read slice; the complete release also
includes the [storage upgrade](v1_4_0_migration_guide.md).

Memory owns the contracts, generated consumer, browser fixture and tests. None
requires Desktop, Relay, a model, a provider account or a user's existing database.

## Operations and permissions

The profile combines the [discovery foundation](v1_4_0_discovery_contract.md) with:

| Operation | Permission | Result |
| --- | --- | --- |
| `GET /v1/dashboard/overview` | `memory:read` | Scoped counts and bounded sections |
| `POST /v1/retrieve` | `memory:read` | Ranked claim results |
| `POST /v1/context-pack` | `memory:context` | Markdown, typed sections and source provenance |
| `GET /v1/claims/{claim_id}` | `memory:read` | Claim detail |
| `GET /v1/claims/{claim_id}/explain` | `memory:read` | Evidence, confidence and visible relationships |
| `GET /v1/audit/{target_type}/{target_id}` | `memory:audit` | Typed claim, candidate or evidence audit |

`/v1/search` and `/v1/context` remain aliases. Audit accepts `claim`,
`candidate_claim`/`candidate`, and `evidence`/`event`; mismatched or unknown target
types return 404. Candidate inspection, including candidate audit and overview
sections, additionally requires `memory:review`. Explanation audit/history
requires `memory:audit`; otherwise those arrays are empty. `memory:admin`
satisfies capability checks but never widens namespace grants or privacy ceilings.

Domain access uses stored namespace/project membership, session ownership,
evidence privacy and derivation sources. Caller-supplied project labels do not
authorize a resource. Tombstoned, missing or unknown provenance is unavailable;
legacy claims without evidence retain the personal privacy floor. Direct access
to an existing denied target returns 403 without its contents; missing targets
return 404. Lists omit denied items. These corrections apply to legacy callers
too; opting out of canonical input validation cannot opt out of access policy.

## Schema and input compatibility

`GET /v1/openapi.json` still returns the existing response envelope. Extract its
`data` before generation. The authoritative Python definitions are
`aletheia/service/contracts.py` and `read_contracts.py`, with domain fields derived
from the actual dataclasses. Request validation shares the canonical definitions.
Real HTTP responses are validated against those schemas in conformance tests.

New consumers send `X-Aletheia-Contract: memory-read-v1` after discovering profile
support. This additive negotiation validates known input types and these limits:

| Field | Canonical behavior |
| --- | --- |
| `namespace` | Required, nonempty; explicit for overview as well |
| Retrieval `limit` | Integer 1–200, default 10 |
| Context `token_budget` | Integer 1–12,000, default 1,500 |
| `mode` / `retrieval_mode` | `lexical`, `semantic`, or `hybrid`; legacy default `hybrid` retained |
| Flags | JSON booleans, not strings or numeric coercions |
| Optional project/session/policy IDs | String or null |
| Extension fields | Accepted; unknown fields do not become new supported behavior |

Without the header, existing coercions and extension inputs remain accepted.
An explicit unknown, empty or different profile returns `409 unsupported_contract`
before running the read. Shared read operations in the review and onboarding
projections also use `memory-read-v1`; those profile names apply to their own
candidate review/creation operations, as declared by each operation's schema.
New examples explicitly choose lexical mode and `record_usage: false`; lexical
retrieval matches words and does not promise arbitrary paraphrase understanding.

Retrieval is ranked top-N, not exhaustive enumeration. Authorization filtering
can reduce the returned count without refilling it. There is no cursor or total
count guarantee. Context has a token budget and the existing bounded candidate
selection. Overview returns at most ten items per available section. These
responses have null pagination; review-list continuation is defined by the
[review contract](v1_4_0_review_contract.md).

## Redaction and overview limits

Only fully authorized evidence/derivation sources can support returned memories.
Context markdown, typed items, warnings and provenance are produced from the
same filtered pack. Unclassified derivation graphs are null; typed source IDs
remain available. Hidden conflict references and related claim links are omitted.

Free-form audit `details` is the JSON string `"{}"`; history and review-decision
reasons are `[REDACTED]`, and decision edits are null. These fields lack independent
privacy labels. The embedded APIs remain trusted local interfaces and are not
changed into an authorization sandbox.

Overview computes current counts only from visible resources. It does not create
or return stored metric/health snapshots. Without review permission, candidate
and review-task arrays are empty and their counts are null (unavailable, not zero).
Jobs and service-request payloads lack per-record privacy classification, so
they are always empty in this view and listed in `unavailable_sections`.
Health warnings/recommendations are empty in this limited read view; use the
separately authorized operational APIs for operational diagnosis. This is a
deliberate reduction from the old broad overview, not a complete operations page.

## Browser transport and polling

D4 selects same-origin HTTP or a controlled same-origin proxy. Local mode accepts
one valid loopback Host (`127.0.0.1`, `localhost`, or `::1`) at the listening port.
If Origin is supplied it must exactly match that HTTP authority. Malformed,
foreign, null and duplicate authorities/origins are denied before reading the
body. A proxy must validate its browser-facing Origin, use a fixed upstream and
set the upstream Host; it must not blindly forward client authority headers.
Explicit remote mode retains its existing external TLS/proxy responsibility.
This phase does not add cross-origin CORS or OPTIONS support, relax authentication,
or change console sessions/CSRF policy.

Read and discovery responses use `Cache-Control: no-store` and carry an opaque
`X-Request-ID` alongside the existing envelope request ID. Canonical service
errors include 400, 401, 403, 404, 409, 413, 429, 500 and 503 as declared per
operation. `503 database_busy` indicates SQLite lock contention; a failed usage
write is rolled back. Correlation IDs with unsafe
header characters are not echoed as headers. Tokens and sensitive results stay
in memory, outside browser persistent storage and URLs.

The generated consumer has a 10-second deadline covering headers **and body**,
external cancellation, one in-flight poll, nominal 5-second intervals and capped
exponential backoff with jitter up to 60 seconds. It retries transient network,
429 and 5xx failures; other HTTP errors stop polling. Optional Retry-After seconds
or dates are honored within the 60-second cap; Memory currently supplies no retry
hint. Hidden/offline views cancel and clear; reconnect refreshes. Stopped or
obsolete requests cannot render a late result.

`ScopedReader` discovers the principal before and after a read group, verifies
profile support and rejects results if service identity, principal, grants or
privacy changed. UI owners must stop the old poller and reset the reader when
changing connection, credentials or selected scope, as the fixture demonstrates.
This cannot revoke bytes already delivered before a policy change; a fresh poll
checks current access. Results from unrelated resources need separate scope keys.

Background reads make no domain writes. Operational request/rate-limit records
remain permitted. Context `record_usage: true` is an explicit side effect and
records only the filtered pack actually delivered; do not use it for polling.
Read POSTs ignore idempotency replay caches so each call rechecks access. This
does not promise exactly-once usage recording. Governed mutation replay is
defined separately by the review and agent onboarding contracts.

HTTP handlers serialize access to their shared SQLite connection. Selected reads
evaluate authorization, provenance and result construction in one transaction.
This favors correctness; it is not evidence of high-throughput scalability, and
overview currently scans its scoped resources. No cross-writer mutation or stale
review guarantee is claimed here.

## Reproduce the checks

Follow [`contracts/typescript/README.md`](../contracts/typescript/README.md) for
generation, real-service consumers and the disposable browser page. Tooling is
development-only and absent from the installed Python runtime. Evidence and
remaining gates are recorded in [Phase 2 verification](v1_4_0_phase2_evidence.md).
