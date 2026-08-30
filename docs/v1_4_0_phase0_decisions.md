# 1.4.0 Phase 0: scope, baseline and contract decisions

Status: **G0 accepted by the maintainer on 2026-08-30; implementation may proceed**.
Prepared 2026-08-30. The [release plan](v1_4_0_contract_hardening_and_developer_experience_plan.md)
is the source of truth. This record makes its Phase 0 choices concrete; it does
not authorize release, deployment, direct pushes to main, or protection changes.

## Decisions in plain language

The maintainer accepted these recommendations in the project conversation and
asked that future uncertainty be explained simply before requesting a choice.

1. Start with a small, clearly tested set of features for reading memory,
   reviewing candidates and connecting agents. Other existing features stay available.
2. Report the right software version without breaking older clients.
3. Let a connected client see who it is and what it is allowed to access,
   without exposing credentials or other users' information.
4. Start with a simple local browser connection and periodic refresh. Avoid
   opening broader network access merely to make a demo work.
5. Refuse a review decision if the memory changed after it was inspected.
   Retrying the same successful decision must not apply it twice. The first
   implementation may sometimes ask for review again after unrelated changes.
6. Let clients load candidate lists in manageable batches without silently
   skipping records when the list changes.
7. Use the existing Python methods for the first tutorial. Add another helper
   only if a real walkthrough shows that it is needed. Review stays explicit.
8. Generate client types from Memory's own API description and test them
   against a running service. Desktop remains completely optional.

G0 acceptance is permission to proceed with these choices, not permission to
merge a PR, publish a release, or change branch protection.

## Baseline and ownership

The reviewed production baseline is `1cb3e607450b2d0d345cc3c06d73223b7f3e3fe4`
(1.3.1). The implementation branch starts from `c75dfb9`, which adds only the
release plan. Remote main was verified at the production baseline with protection
enabled on 2026-08-30. Work is isolated on `codex/v1.4-phase0`; the original
checkout stays on `codex/v1.4-plan`.

Memory owns every contract, test fixture, provider recipe and release gate here.
Required tests never import, install, check out, launch, or wait for Desktop or
Relay. Python installation never requires Node. TypeScript tooling is a separate,
private development harness; it is not a runtime dependency or an npm release.

## D1. Freeze three initial profiles

The machine-readable inventory is
[`contracts/v1.4.0/profiles.json`](../contracts/v1.4.0/profiles.json).
It records each operation's owner, request inputs, planned response type,
permissions, scope/privacy expectations, errors, pagination, side effects,
headers, captured evidence and future gate/test identifier. Planned schema names
and conformance identifiers are **not implemented schemas or passing tests**.

Shared discovery: health, readiness, version, enveloped OpenAPI, compatibility
report, and proposed current principal (`GET /v1/auth/me`).

| Profile | Beyond shared discovery | Limits |
| --- | --- | --- |
| `memory-read-v1` | Overview, retrieval, context, claim, explanation, audit | Search-backed exploration; no exhaustive claim/evidence browser. Audit still needs `memory:audit`. |
| `memory-review-v1` | Candidate list/detail, promotion, rejection, audit | Candidate reads require `memory:review`; no claim editing or conflict-resolution promise. |
| `agent-onboarding-v1` | Candidate-first remember, retrieval/context, claim/explanation/audit | Agent token has no review or active-write capability; approval is a separate operator action. |

Use `/v1/retrieve` and `/v1/context-pack` in new examples; preserve `/v1/search`
and `/v1/context`. Keep `/v1/console/session` compatible. No supported profile
will be advertised until its actual-service acceptance tests pass. Permission
requirements remain per operation, not an implicit permission bundle assigned
to a client because it names a profile.

The inventory includes legacy extension policy and current defaults. It does
not authorize silently rejecting existing request fields or changing HTTP
retrieval's current `hybrid` default. All model-free examples explicitly select
`lexical`.

## D2. Versions and the legacy bridge

Canonical software reporting comes from installed distribution metadata, with
a tested source-tree/build fallback; it must not import the database schema
constant as its software version. Health and OpenAPI report the shipped service
version; `/v1/version` retains `service_version` and `api_version` while adding
`software_version`, `supported_profiles` and `service_identity`.

`supported_profiles` is a list of implemented profile identifiers (initially
empty). Profile membership is an all-or-nothing compatibility commitment for
the selected scope, separate from resource authorization. Publishing a schema
alone must never turn on a profile flag.

Compatibility-report transition:

| Field | 1.4.0 meaning |
| --- | --- |
| `software_version` | Installed software version, canonical. |
| `api_version` | Protocol family, `v1`. |
| `schema_version` | Actual persisted schema version. |
| `aletheia_version` | Deprecated historical expected-schema value. Equals actual `schema_version` on compatible storage; a mismatch still fails the old SDK check. Not software version. |
| `supported_profiles` | Only profiles whose gates passed. |
| `service_identity` | Opaque identity for this running service instance. |

Phase 1 clarified the bridge against the published SDK: preserve its rejection
of unsupported storage, rather than making the equality check pass unconditionally.
The alias receives explicit deprecation documentation; removal is outside this
release. The 1.3.1 SDK fixture remains byte-identical to the published package.
The new SDK checks API compatibility and explicitly requested profile support,
not software/schema equality. With an old service, legacy operations remain
usable, discovery limitations are reported, and negotiated review is refused.
An API-v1 response alone must not imply principal discovery or revision support.

Use a random **per-service-instance** identity in Phase 1, stable while that
service runs and changed after restart. It is not a database path, credential,
hardware identifier, or stable database identity. Clients discard/isolate cached
data on identity or effective-scope changes. A restart may conservatively clear
a cache; no persistent identity migration is needed in Phase 1.

Compatibility matrix: preserved published 1.3.1 SDK against the new service;
new SDK against an isolated installed 1.3.1 service with explicit limited mode;
generated TypeScript client against the new service. Test the new compatibility
logic on synthetic future software versions with unchanged API/profile support
as well as missing profiles. Python release CI remains 3.11–3.13.

## D3. Principal discovery and permission vocabulary

Propose `GET /v1/auth/me` through ordinary service authentication. Return only:
`authentication_mode` (`bearer`, `console_session` where supported, or
`local_tokenless`), safe `principal` metadata or null, effective capabilities,
namespace grant patterns, privacy ceiling, expiry or null, and service identity.
Capability discovery includes effective administrative privileges while retaining
the real grants; document that admin never bypasses namespace or privacy checks.

Normal valid tokens do not need admin or even `memory:read` to inspect themselves.
Invalid/expired/revoked credentials and disabled clients return 401. In deliberate
local tokenless mode, report the effective least-privilege local scope with null
principal; do not invent an authenticated user. Protected mode never grants this
fallback. Keep existing console login/session/CSRF behavior.

`memory:review` governs promotion, rejection and candidate inspection. Do not
introduce `memory:promote`. Namespace patterns do not enumerate available
namespaces; the first client supplies an explicit namespace validated by Memory.
No provider secrets, raw tokens, token hashes, or unrelated principal metadata
appear in discovery or diagnostics.

## D4. Browser transport and polling

Choose a **same-origin local deployment or controlled same-origin proxy**.
Direct cross-origin requests, permissive CORS, wildcard origins, a new `OPTIONS`
policy, and unauthenticated cross-origin local service access are deferred.
This decision avoids a new network exposure in Phase 0/1. A future cross-origin
requirement needs its own origin/authentication threat review before code.

G2 must exercise a Memory-owned minimal test page in a real browser, using the
selected same-origin topology, real authentication and response headers. No
Desktop code is needed. Preserve loopback binding and auth protections; reject
untrusted proxy/Host assumptions. Sensitive responses use `Cache-Control:
no-store`; clients keep tokens and sensitive results out of persistent browser
storage. Preserve existing console session and CSRF defenses.

Client policy: one in-flight poll per resource, cancellation on unmount/scope
change, 10-second request timeout, nominal 5-second polling interval, capped
backoff to 60 seconds with jitter, pause while hidden/offline, refresh on
reconnection. Retry bounded reads on transient failures; honor a documented
retry hint when available. Do not retry authorization/validation errors.
Background retrieval/context explicitly disables usage recording. Overview
must not create domain snapshots simply because a client is polling. Operational
request/rate-limit logs are separately documented permitted side effects.

Every request carries an opaque correlation ID. Preserve response-envelope
semantics and expose the ID in an HTTP header for generic clients. Uncertain
writes retain the same idempotency key and serialized payload. Never retry a
stale review automatically or replace its idempotency key to force it through.

## D5. Revisions, atomic review, and storage boundary

Propose an additive, negotiated review contract using
`X-Aletheia-Contract: memory-review-v1`, an opaque `expected_revision` in the
mutation body, and an `Idempotency-Key`. Existing routes remain usable without
that header under documented legacy semantics. A supplied precondition is always
enforced, even on a legacy call; it is never silently ignored.

Profiled review errors: missing revision 428 (`precondition_required`), mismatch
412 (`stale_revision`), missing idempotency key 400, reused key with a different
operation/payload 409. None of these failures commits a governance decision.
Legacy missing-field/validation changes need explicit compatibility review.

Use durable monotonic revision state at the SQLite boundary, not timestamps or
HTTP process locks. Start conservatively with a database-wide review epoch:
changes to any review-relevant domain state invalidate inspected revisions,
including unrelated changes. This sacrifices some concurrency to avoid missing
dependencies and ABA changes. Document that clients may need to re-review even
when the visible candidate text is unchanged.

The Phase 4 migration adds revision state and database triggers on the complete
review dependency set: candidates; evidence and spans; evidence/candidate/claim
links; extraction decisions; labels/entities/scopes; risk/conflict/trust/policy
state; and deletion/redaction/retention changes affecting these resources.
Inventory every relevant mutation table from the domain call graph before
merging the migration. Operational request logs, token last-use timestamps and
read-only diagnostics must not invalidate revisions. Trigger coverage tests
must exercise embedded, CLI, HTTP, background, restore and federation writers
that can affect the profiled resources; raw unsupported SQL is not a public API.

Begin the complete profiled review under an outer **write transaction before
reading the revision or governance inputs** (SQLite `BEGIN IMMEDIATE`, retaining
safe nested savepoints). Reauthorize first. Resolve replay within that same
transaction before evaluating the old precondition; successful replay returns
the original outcome even though the original write changed the revision.
Then atomically perform comparison, validation, claim/decision/link/scope writes,
audit, and idempotency storage. Roll back all of them together on failure.
Current multi-transaction promotion must be enclosed/refactored accordingly.

For negotiated requests, bind replay identity to the authenticated credential
or equivalent scope identity, HTTP method, operation/target, namespace, and key;
include the precondition in the operation fingerprint. Recheck current access
before returning stored data. Do not reuse the existing client-ID-only replay
partition as the stronger contract. Audit records retain the original operation
ID; replay carries a fresh transport correlation ID without creating another
review decision. Preserve legacy replay semantics separately.

This is a real storage change, not a version-field fix. Its migration identifier
is finalized with the Phase 4 migration and must be independently reported.
Before implementing it, open the issue/discussion required by CONTRIBUTING.md
covering the dependency/trigger inventory, backup/restore behavior, upgrade from
1.3.0 storage, integrity checks and refusal by unsupported older binaries.
Restoring or rolling back a database must change the service cache identity and
invalidate outstanding review tokens. No migration is implemented in Phase 0.

## D6. Pagination and result limits

Baseline candidate list is top-N, ordered `created_at DESC, id ASC`, with a
configured default 50 and maximum 200. Its envelope always has a null cursor;
it does not support exhaustive traversal. The reported limit currently may
reflect the un-clamped request rather than the effective bound.

For the review profile, add opt-in keyset continuation under the negotiated
profile header, tied to namespace, filters, effective scope and the conservative
review epoch. Page limits reflect the applied bound. Use one extra authorized
row to decide continuation; opaque cursors never encode unrestricted data.
Changed scope/filter/review epoch requires restarting the list, not silently
skipping records. Legacy bounded-list behavior remains supported. G3 tests
ties, redaction, empty/final pages, mutation between pages and tampered cursors.
Retrieval remains ranked and bounded, not a claim enumeration API.

## D7. Existing APIs first; defer a speculative helper

The existing public API supports the complete deterministic journey:

```python
memory = Memory.open(path, namespace="user/phase0-demo")
batch = memory.ingest("user/phase0-demo", source_type="manual",
                      content="User prefers careful architecture notes.",
                      trust_level="user_asserted")
run = memory.extract_candidates("user/phase0-demo", batch_id=batch.id,
                                extractor="rule_based")
candidates = memory.list_candidates("user/phase0-demo", extraction_run_id=run.id)
# Inspect candidates and explicitly approve one before calling promote_candidate.
# See scripts/v1_4_phase0.py for the complete automated evidence harness.
```

The prototype uses returned batch/run/candidate/claim objects and no manually
copied IDs. Therefore **no new scoped helper API is selected for Phase 0**.
Use `Memory.open`, `ingest`, `extract_candidates`, `list_candidates`,
`promote_candidate`, `retrieve`, `context_pack`, `explain_claim`, `read_event`
and `close`. Phase 3 can propose a narrowly justified helper only if a timed
human walkthrough demonstrates friction these existing handles cannot remove.
That requires an additive API decision before coding it, not a parallel kernel.

The automated prototype supplies an explicit documented fixture review decision.
The interactive tutorial must display the candidate/evidence and wait for the
developer's approval. Pending candidates are absent from trusted lexical results;
after promotion, query `architecture` returns the claim with source provenance,
including after close/reopen. The bounded rule-based example is not an arbitrary
natural-language understanding promise. No model, index, account or provider is
needed, and the offline test blocks network connections during this lifecycle.

Embedded `Memory.remember()` retains its active-write default and is documented
as trusted local code. The HTTP starter uses existing
`AletheiaClient.remember_candidate()` with a scoped agent token. Reviewer/operator
credentials are separate and are never emitted into generated examples.

The measured automated lifecycle takes milliseconds, but that is **not evidence
of a five-minute human onboarding experience**. Record installation separately,
then time human reading, setup, inspection and explicit review in G4. Test the
actual published example from a built wheel outside the source checkout.

## D8. Authoritative contracts and generator

Use a Python-owned contract registry to enrich the existing OpenAPI builder for
the selected operations. Runtime request/response/error conformance tests are a
mandatory reconciliation mechanism; a parallel handwritten schema that is never
checked against runtime is insufficient. Preserve legitimate legacy extension
fields. Do not introduce a broad framework rewrite or runtime Node dependency.

Pin development tooling with package-lock.json:
`openapi-typescript` 7.13.0, `openapi-fetch` 0.17.0, TypeScript 5.9.3, and Node
types 26.4.0. The generator explicitly declares a TypeScript 5.x peer dependency;
TypeScript 7.0.2 was rejected during evaluation, and no force/legacy-peer-deps
override was used. Local toolchain validation uses Node 26.0.0. Phase 2 CI must
pin and test its selected Node runtime, independently of Python installation.

The [generator documentation](https://openapi-ts.dev/introduction) supports
OpenAPI 3.1, and [openapi-fetch](https://openapi-ts.dev/openapi-fetch/) consumes
its generated types. Phase 0 extracts the real HTTP schema from its envelope,
retains the selected paths, generates declarations, compiles a consumer and
executes discovery/read requests against a disposable authenticated service.
The old schema still yields unknown domain payloads and missing path/query
types. This smoke test proves only the toolchain/transport wiring. G2 requires
typed domain fields, request validation, errors, redaction and pagination
conformance with no handwritten payload substitutions.

## Gaps and gate ownership

| ID | Evidence / limitation | Required resolution |
| --- | --- | --- |
| P0-01 | Baseline has 199 paths, 213 operations, two envelope schemas, 121 unrestricted bodies, zero operation IDs/path/query parameters. | CH-2/G2: typed selected operations, strict schema validation and actual-service cases. |
| P0-02 | Published 1.3.1 SDK compares schema version to historical aletheia_version; software currently reports 1.3.0. | CH-3/G1: tested canonical fields and legacy bridge. |
| P0-03 | Ordinary token can read console-session capability/grant metadata; identity/privacy ceiling missing. | CH-4/G1: safe complete principal discovery. |
| P0-04 | Overview contains multiple sections with different permission/scope requirements. | CH-4/CH-5/G2: verify section permissions and namespace/privacy boundaries across sibling routes; detailed security findings are handled privately under SECURITY.md. |
| P0-05 | Consistent resource/privacy enforcement requires more evidence than happy-path retrieval. | CH-4/G2: validate detail/explanation/audit/candidate privacy and resource scope with comprehensive negative tests; private findings must be resolved before profile support. |
| P0-06 | Dashboard source creates a metric snapshot when none exists. | CH-5/G2: side-effect-free domain reads under the profile; test polling repeatedly. |
| P0-07 | Candidate pagination is bounded top-N with no continuation and inconsistent reported limit. | CH-2/CH-6/G3: explicit negotiated continuation per D6; preserve legacy path. |
| P0-08 | Atomic promotion, retry and authorization behavior needs cross-writer verification. | CH-6/G3: atomic operation/replay with credential and scope reauthorization; two writers and rollback tests. |
| P0-09 | No browser proof, migration proof, reverse SDK matrix or live model recipe validation in Phase 0. | Required in G2, G3/G6, G1/G6 and G5 respectively; no completion claim now. |

The synthetic response fixtures document historical behavior only. Detailed
security reproductions are retained locally outside the repository, following
SECURITY.md; no working vulnerability probes are included in this public PR.
Fixing authorization holes
must be reviewed and documented as security corrections, never hidden as schema
tightening. Complete sibling-path analysis belongs to the respective gate.

## G0 review checklist and next PRs

- [x] Original checkout isolated; baseline and plan commit identified.
- [x] Three profiles and operation inventory proposed; exclusions explicit.
- [x] Published legacy SDK retained with provenance and hash.
- [x] Real HTTP schema/responses captured using only disposable synthetic data.
- [x] Existing API lifecycle prototyped with explicit automated review.
- [x] Generator pinned, compiled and exercised over real HTTP.
- [x] Baseline and new harness checks recorded in the evidence document.
- [x] Maintainer accepted the recommendations in the project conversation on 2026-08-30.

G0 is accepted; G1–G6 still need their implementation evidence. Phase 1 implements version
reporting/legacy compatibility and principal discovery in small PRs; Phase 2
establishes safe typed reads and real-browser proof. Phase 3 delivers the public
first-run experience; Phase 4 implements the separately reviewed storage/write
contract; Phase 5 validates optional local providers; Phase 6 verifies release
artifacts. Each supported profile is enabled only after its gate passes.

PR review and release authorization remain separate. No direct pushes to main,
automatic merge, publishing, or branch-protection changes are part of this PR.
