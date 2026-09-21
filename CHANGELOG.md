# Changelog

All notable public changes to Aletheia are tracked here.

## Unreleased

## 1.6.0

Beta audit-remediation release. Includes all 29 original audit repairs and the
nine residual defects found by independent behavioral review. Python remains
3.11+, the API remains v1, and the storage schema remains 1.3.1. See the
[beta upgrade guide](docs/v1_6_0_upgrade.md) before reusing existing data.

- Recheck current authority and sources for conflict resolution and cached
  mutation replies. Rejected replay does not repeat the original mutation;
  deletion removes cached content while retaining operation keys.
- Scope operational reports and metrics before aggregation; exclude legacy
  snapshots without verified scope metadata.
- Preserve claims-only federation privacy, scrub retained conflict snapshots,
  and restrict deletion notices to objects actually disclosed to recipients.
- Release the daemon lock during provider work, preserve durable job ownership,
  and reject stale results after inputs or permissions change.
- Apply project relevance and conflict/duplicate penalties before retrieval
  truncation; honor the active context budget in Python, HTTP, and CLI traces.
  See [follow-up verification](docs/audit_followup_verification.md).
- Require cryptography 50.0.1 or newer and update the development OpenAPI
  toolchain to resolve js-yaml 4.3.2 through @redocly/openapi-core 1.34.20.
- Refresh the packaged TypeScript schema for policy selection and context
  defaults. Publication now runs the existing release gates at the publishing
  commit, including installed upgrade/recovery checks from published 1.5.0.

- Execute applied ranking/context policy versions in reads and evaluations;
  validate configuration and make activation, gates, and rollback atomic.
- Apply supported sync conflict decisions to stored memories and provenance,
  enforce effect permissions, and reject unsupported strategies without receipts.
- Require behavioral adapter evidence for certification. Structural conformance
  and missing probes no longer produce behavioral passes or satisfy the v1 gate.
  See [behavior verification](docs/behavior_verification.md) for upgrade details.
- Exclude unreviewed legacy candidate claims from default retrieval/context and
  enforce claim/scope validity before selection, including normalized timestamps.
- Rank eligible memories across their full history before bounding reranking;
  apply HTTP privacy and scope checks before result limits and context budgets.
- Run governed HTTP provider construction and inference outside the service lock
  and database transaction, then recheck current access and source inputs before
  using results. Concurrent idempotent requests retain one provider execution;
  queued jobs preserve durable ownership and retry accounting during waits.
- Reject redirects in both Python SDK clients so service credentials and request
  bodies cannot be forwarded. See
  [retrieval and provider execution](docs/retrieval_execution_boundaries.md).
- Omit plaintext span copies of protected evidence across extraction, HTTP,
  plugins, and federation; clear existing span/risk copies when opening a database.
- Reject unsupported JSONL encryption and physical backup auth exclusion before
  writing output. Redacted exports use reviewed structural column allowlists.
- Preserve archive source evidence, privacy, and identity; make archive/federation
  reimports reuse mapped objects and honor deletion notices. Legacy or changed
  sources require review rather than another copy or an implicit overwrite.
- Apply the requested forget mode and follow transitive redaction dependencies,
  including source documents and promoted candidates/inferences; scrub retained
  derivatives and purge content snapshots/indexes atomically. See
  [storage privacy boundaries](docs/storage_privacy_boundaries.md).
- Enforce stored object scope and source privacy across HTTP session, feedback,
  review, reasoning, evaluation, and policy operations. Session summaries now
  default to reviewable candidates; active summaries require explicit active
  mode and active-write capability, with atomic session/summary changes.
- Filter HTTP trace content before storage and recheck current access on reads.
  Authorize LLM sources before provider construction, including conflict and
  duplicate-merge sources. HTTP Python providers must be enabled `llm_provider`
  installations with approved permissions, selected by installation ID or name.
- Require an explicit namespace for scoped operational lists and filter federation
  history before pagination. Signed federation imports authorize the grant's
  actual scope and reject content outside that namespace. See
  [HTTP access boundaries](docs/service_access_boundaries.md) for migration details.
- Add explicit federation recovery: verified encrypted decryption-key archives,
  fingerprint-confirmed peer replacement, trust reset and grant revocation,
  and encrypted recovery of historical bundles for review without importing.
  Rotation now requires an expected fingerprint and a fresh recovery path;
  HTTP rotation/replacement require admin capability. Identity responses and
  CLI output contain public data only. See the
  [operator procedure](docs/federation_key_recovery.md).
- Repair federation bundle identity serialization, pinned-key verification,
  import revocation checks, candidate-only policy enforcement, and share read
  permissions. Invalid imports leave content and federation state unchanged.
- Require explicit `read_evidence` permission to export source evidence; `read`
  grants claim access only. Dry-run imports enforce normal trust checks.
  See the [security guide](docs/security_privacy_guide.md) for compatibility
  and recovery considerations for previously distributed bundles.

## 1.5.0

- Automatically advertise participating local POSIX daemons with owner-only,
  expiring registrations and explicit opt-out; clean up on normal exit/SIGTERM.
- Add local pairing v1: owner-issued single-use codes, explicit limited grants,
  persistent database-bound TLS identity, expiring credentials, and self-revocation.
- Require the original encrypted transport for pairing-issued HTTP credentials;
  record secret-free issuance/revocation audit events. Existing API/storage
  contracts remain compatible; no database migration is added.
- Validate the new contract and lifecycle with 17 pairing tests plus the
  home-relative startup regression; full regression suite: 330.
  See [local pairing](docs/local_pairing_v1.md) for scope and platform limits.
- Preserve home-relative database paths for pairing and validate installed wheel
  and source packages through startup, restart, crash recovery, and backup restore.
  Runtime dependencies and the storage schema are unchanged from 1.4.1.
- Expand quoted `~` database paths during the service schema precheck so an
  existing database starts without requiring `--auto-migrate`.
- Refresh the packaged TypeScript starter's generated schema with the new
  pairing model definitions; existing endpoint types remain unchanged.

## 1.4.1

Packaging metadata correction.

- Replace repository-relative README links with absolute GitHub links so the
  project description links work when rendered on PyPI.
- Extend the release gate to reject relative README links before publication.
- Refresh the tracked `uv` lockfile to match the package version and declared
  development dependencies.

## 1.4.0

Integration contracts and developer experience release.

- Separate software, API, storage and negotiated profile versions; preserve the
  published 1.3.1 SDK compatibility bridge. Add scoped current-principal discovery.
- Advertise typed `memory-read-v1`, `memory-review-v1` and
  `agent-onboarding-v1` with actual HTTP/generated-client conformance.
- Enforce current scope/privacy for selected reads and replay. Governed candidate
  review uses atomic revisions, explicit operation keys and audited replay;
  stale decisions require fresh inspection. Same-origin browser transport stays
  narrow; no wildcard CORS, SSE, Relay or Desktop dependency is introduced.
- Add safe starter generation, read-only diagnostics and an offline reviewed
  memory tutorial. Package embedded Python, scoped HTTP/Python and TypeScript
  agent examples with a separate operator approval step.
- Add optional, explicitly configured local embedding/LLM recipes, input-aware
  embedding index identity, structured extraction schemas and safe failures.
  Core remains model-free. No models or Node dependencies are installed by pip.
- Upgrade storage 1.3.0 to 1.3.1 atomically for durable revision/replay state.
  Back up before upgrade. Older binaries refuse the new schema; recovery uses
  the preserved pre-upgrade archive, not an in-place downgrade. Restore resets
  revision identity and clears stale replay state.

Compatibility limits: new profiles require discovery; old clients keep the
legacy route surface but do not gain negotiated write guarantees. Unknown
contract headers, invalid profiled fields, unsafe output overwrites and stale
write preconditions are explicitly refused. No npm package is published.

Behavior changes to account for when upgrading:

- Session identifiers are authorization-checked and can now return 403/404
  where an unscoped value previously passed through.
- Operation keys accept ASCII letters, digits, dots, underscores, colons and
  hyphens. Raw base64 keys containing `+`, `/` or `=` must use a safe encoding.
- Integer fields reject fractional values instead of truncating them, and
  privacy levels reject unknown spelling or capitalization.
- Replaying a legacy operation can return `replay_result_changed` if its stored
  result no longer matches current state. Credential-scoped 1.4 operation keys
  do not reuse unscoped pre-upgrade idempotency records.
- `aletheia api ping` accepts loopback service URLs only. Remote deployments
  should perform health checks at their trusted proxy boundary.
- Tokenless `/v1/auth/me` is available only when the local service is explicitly
  unauthenticated and unprotected; configured deployments return 401 without a
  bearer or console credential.

See the [release handoff](docs/v1_4_0_release_handoff.md) for evidence and the
release verification record.

## 1.3.1

Patch release to align the PyPI distribution with the current GitHub release
state.

- Includes the documented `aletheia_client.py` compatibility import module in
  the wheel distribution.
- Adds the GitHub Actions Trusted Publishing workflow for TestPyPI and PyPI.
- No runtime behavior changes.

## 1.3.0

Initial public release of `aletheia-memory`.

- Ships the local SQLite memory kernel, CLI, HTTP service, Python SDK clients,
  MCP tools, and generic adapter surfaces.
- Includes evidence-backed memory lifecycle support: evidence, candidate
  memories, review and promotion, claims, retrieval, context packs, feedback,
  conflicts, confidence, and audit records.
- Adds local production controls for protected mode, scoped tokens, encrypted
  backups, restore verification, redaction, forget tombstones, retention,
  diagnostics, readiness checks, release gates, and compatibility reports.
- Includes federation-beta support, governed semantic retrieval, and
  review-first LLM memory formation.
- Packages the public documentation set with the wheel.
