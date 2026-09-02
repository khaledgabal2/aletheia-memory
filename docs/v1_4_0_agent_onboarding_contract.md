# Agent onboarding contract

`agent-onboarding-v1` is a client-neutral, candidate-first profile for 1.4 builds.
It includes discovery, the read operations in `memory-read-v1`, and typed
`POST /v1/remember`. Discover support through `/v1/auth/me`; older services do
not acquire this guarantee merely because `/v1/remember` exists.

Creation requires `X-Aletheia-Contract: agent-onboarding-v1`, an explicit
`Idempotency-Key` (1–200 ASCII letters, digits, `.`, `_`, `:`, `-`), a bearer
credential, and `memory:write_candidate`. Send namespace, memory type, subject,
predicate, object and evidence text. `write_mode` must be `candidate` or omitted.
Project, session and privacy are checked against current authority. Optional
extension fields remain accepted for legacy compatibility; they confer no rights.
The complete request/response definition is emitted by the service OpenAPI;
`onboarding_document` projects the stricter negotiated subset for generation.

The result is a candidate receipt with evidence, never an active claim. Domain
validation can mark a candidate invalid, duplicate or needing conflict resolution;
a returned candidate is not proof that its contents are true or promotable.
Candidate creation does not require or grant permission to browse other
candidates. Keep `memory:review`, `memory:write_active` and `memory:admin` out of
agent credentials. The separate operator inspects source and candidate, then
uses the [review contract](v1_4_0_review_contract.md) for an explicit decision.

Creation, evidence, candidate audit and replay receipt commit together under
SQLite's immediate transaction. A retry with the same credential, key and
canonical JSON payload returns the original creation result, with a fresh
transport request ID. A changed payload returns 409. Current authorization and
source visibility are checked before replay; revoked credentials cannot retrieve
old receipts. A changed candidate returns `replay_result_changed` (409), rather
than an obsolete candidate snapshot. Responses use `Cache-Control: no-store`.

Keep the operation key and complete payload after an uncertain response. No SDK
or example invents a replacement key or automatically repeats the write. Receipts
expire after 24 hours: after expiry, replay can create another candidate. Ask an
operator to inspect the original operation instead of blindly retrying an old key.
A review revision is not a creation precondition: supplied `expected_revision`
is refused. Creation does not certify arbitrary legacy writes or admin endpoints.

The Python helper accepts `remember_candidate(..., contract="agent-onboarding-v1",
idempotency_key=operation_key)`; sync and async clients use the same protocol.
It refuses a `write_mode` override. Calls without the profile retain the legacy
surface and its client-scoped key identity, not the new credential-scoped promise.
Direct embedded `Memory.remember()` still means a trusted active write.

Generate [the packaged Python or TypeScript agent](examples.md), or reproduce
conformance with `python -m scripts.v1_4_agent_contract --typescript` after the
[toolchain generation steps](../contracts/typescript/README.md). Tests exercise
actual HTTP, schema validation, namespace/project/session/privacy denial,
redaction/revocation before replay, lost responses, concurrent retry and rollback.
No Desktop code or runtime participates.
