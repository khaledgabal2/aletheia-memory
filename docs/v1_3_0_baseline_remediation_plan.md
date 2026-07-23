# Aletheia v1.3.0 Baseline Remediation Plan

Status: Draft implementation plan  
Baseline: `production-v1.3.0-baseline` / `v1.3.0`  
Review source: `CODE_REVIEW.md`  
Scope: Aletheia baseline on `main`

## Goal

Close the v1.3.0 baseline review findings without making core Aletheia product-specific. sample adapter compatibility remains on a separate branch or fork and must not be merged into `main` until its own review findings are closed.

## Non-Negotiables

1. `main` remains Aletheia-generic and contains no sample adapter-specific runtime routes, models, docs, SDKs, or CLI commands.
2. Security fixes land before any non-loopback deployment guidance is relaxed.
3. Every closed review item must cite evidence: tests, changed code, migration behavior, docs, or a follow-up issue link.
4. The public baseline version can remain `1.3.0` only for compatible hardening. Any breaking API or schema behavior requires an explicit version decision.
5. Cryptography uses vetted primitives from maintained libraries. No new XOR, hash-as-signature, or self-derived key schemes.

## Workstream 0: Branch Hygiene And Release Guard

Objective: Preserve an agnostic production baseline while allowing adapter experiments outside core.

Tasks:
- Keep `main` at the baseline and commit the review/plan/checklist there.
- Keep sample adapter integration on `codex/sample_adapter-compatibility-layer` or a fork.
- Add a release-gate checklist entry requiring no product-specific integration files on `main`.
- Before future releases, run `git diff --name-only production-v1.3.0-baseline..main` and confirm no sample adapter paths.

Exit criteria:
- `CODE_REVIEW.md`, this plan, and the closure checklist are committed on `main`.
- `main` has no tracked `aletheia/integrations/sample_adapter.py`, sample adapter docs, sample adapter SDK, or sample adapter fixtures.

## Workstream 1: Security Blockers

Objective: Make baseline safe enough to discuss deployment boundaries.

Addresses: C1, C2, C3, C4, H1, H2, H3, H4, H5, H6, H7, H8, H11, medium crypto/path/auth concerns.

Implementation sequence:

1. Add a `SecurityMode` policy surface.
   - Explicitly distinguish `embedded_trusted`, `local_loopback`, and `hardened_service`.
   - Replace unauthenticated god-context defaults with least-privilege defaults.
   - Require explicit opt-in for admin/secret no-auth contexts in tests and development.

2. Replace token hashing and comparisons.
   - Store versioned token hashes.
   - New tokens use a keyed slow hash or HMAC with server secret plus constant-time comparison.
   - Keep backward verification for existing SHA-256 tokens during a migration window.
   - Apply constant-time comparison to console login, session, and CSRF tokens.

3. Replace home-grown crypto.
   - Introduce one crypto utility for authenticated encryption.
   - Federation bundle encryption uses random nonce + AEAD and a caller-provided or configured key.
   - Protected content fails closed when no configured key is available in hardened mode.
   - Federation identity/signature uses real signing keys and verification.

4. Fix federation trust rules.
   - Peer key changes reset trust or require explicit rotation proof.
   - Dry-run imports must be read-only.
   - Expired share grants cannot export or sync.

5. Constrain filesystem and network admin surfaces.
   - Add configured safe roots for backup, restore, import, export, plugin install, and support bundle paths.
   - Add path canonicalization and deny traversal outside configured roots.
   - Restrict `doctor` service URLs to loopback or allowlisted hosts by default.

6. Harden HTTP request handling and errors.
   - Check `Content-Length` before reading request bodies.
   - Handle malformed `Content-Length` with a 400 response.
   - Replace raw internal exception messages with generic server errors and audit-log details.

7. Fix backup privacy semantics.
   - Redacted/metadata-only backups must not embed raw DB snapshots or token hashes.
   - Manifest `includes_raw_content` must match the actual archive contents.

Exit criteria:
- New security tests prove no-auth least privilege, token migration, constant-time verification paths, request-size enforcement, redacted backup contents, federation dry-run non-mutation, expired grant denial, and key-substitution rejection.
- Docs clearly state what is and is not safe outside loopback.

## Workstream 2: Governance And Correctness Landmines

Objective: Preserve the core candidate/promotion trust boundary under review, curation, conflicts, and transactions.

Addresses: H9, H13, H14, H15, H16, H17, H19, H20, medium mass-assignment/read-before-authz/LLM provenance issues.

Implementation sequence:

1. Remove duplicate policy method shadowing.
   - Delete or rename the duplicate `_active_ranking_policy_version_id`.
   - Add tests for non-default ranking policy selection.

2. Add a transaction/unit-of-work helper.
   - Centralize transaction ownership in storage/repository code.
   - Disallow nested sqlite context managers.
   - Convert conflict resolution, federation mutations, hardening forget/redact, and candidate promotion paths first.

3. Validate all edit and curation paths.
   - Candidate edits validate enum fields, clamp confidence/importance, and cannot set terminal statuses directly.
   - Inference edits follow the same validation style.
   - `curate()` cannot use `force=True` for core promotion without explicit policy and tests.

4. Fix conflict poisoning behavior.
   - New contradictions must not demote or hide `core` memories by default.
   - Conflict families should preserve retrievable active/core memories while warning about unresolved conflict.

5. Make FTS integrity repair namespace-safe.
   - Repair only affected namespace/claim rows.
   - Wrap repair in a transaction.
   - Add multi-namespace regression tests.

6. Fix CLI parser clobbering.
   - Remove duplicate `--db` definitions or normalize parent/leaf parser behavior.
   - Add tests for `migrate --db custom.db apply` and other nested subcommands.

7. Fix misleading model properties.
   - `ConflictResolution.status` must reflect stored state or be removed if it is not a stored field.

8. Whitelist service payload fields.
   - Replace raw `**payload` route calls with explicit argument builders.
   - Check authorization before reading sensitive objects when possible.
   - Preserve indistinguishable 403/404 behavior where enumeration is a risk.

9. Harden LLM extraction trust boundaries.
   - Model output cannot overwrite trusted provenance/provider keys.
   - Candidate privacy cannot be lower than source evidence privacy.
   - Evidence span offsets/text must be validated against source content.
   - LLM-suggested confidence must be clamped.

Exit criteria:
- Governance tests cover candidate edit bypass attempts, curation gate behavior, core conflict preservation, transaction rollback, namespace-safe FTS repair, parser DB targeting, and read-before-authz enumeration behavior.

## Workstream 3: Performance And Scale

Objective: Make read paths predictable and keep telemetry growth bounded.

Addresses: C5, H18, medium migration/job/storage/index issues.

Implementation sequence:

1. Remove confidence recomputation from default reads.
   - `retrieve()` defaults to no writes.
   - Add explicit recompute jobs or scheduled maintenance.
   - Context generation can request freshness checks only when needed.

2. Batch retrieval hydration.
   - Add SQL limits where safe.
   - Batch evidence, conflict, scope, project, and relationship hydration.
   - Avoid blank-query full scans unless explicitly requested with an admin/maintenance mode.

3. Fix migration startup behavior.
   - Read and enforce `schema_version`.
   - Run migrations/backfills only when needed.
   - Fail safely on forward-incompatible schema versions.

4. Fix job claim races.
   - Atomically claim jobs using status-guarded updates.
   - Add a two-worker regression test.

5. Fix storage path and index uniqueness issues.
   - Apply `expanduser()` consistently to connection paths.
   - Review shared SQLite connection locking.
   - Make nullable unique-key columns deterministic or non-null where needed.

Exit criteria:
- Read-only retrieval leaves write counters unchanged.
- Retrieval performance tests use bounded query counts.
- Migrations do not rerun backfills on every `Memory.open()`.
- Concurrent job runner test proves a job runs once.

## Workstream 4: Retention, Backup, And Operations

Objective: Make operational promises match behavior.

Addresses: H5, medium retention and support-bundle concerns.

Implementation sequence:

1. Complete retention actions.
   - Implement or reject every configured action explicitly.
   - Honor privacy/source filters.
   - Add dry-run/apply parity tests.

2. Rework backup/export classes.
   - Physical full DB backup is clearly labeled as raw and sensitive.
   - Redacted/metadata exports are logical exports without token hashes or raw evidence.
   - Support bundles default to redacted.

3. Add operational readiness checks.
   - Warn when default keys, no-auth admin, unsafe roots, or raw backup settings are active.

Exit criteria:
- Backups and exports have tests inspecting archive contents.
- Readiness check fails hardened profile when unsafe defaults are enabled.

## Workstream 5: sample adapter Branch Gate

Objective: Keep main agnostic while preserving a possible external adapter path.

Addresses: H10, H12, H21 and sample adapter medium issue.

Implementation sequence:

1. Do not merge sample adapter compatibility into `main`.
2. On the sample adapter branch or fork, require read/write capability checks before duplicate/conflict lookups.
3. Apply privacy filtering to any lookup that returns claim IDs, evidence IDs, or content.
4. Replace raw SQL candidate creation with a governed kernel API or add a generic baseline candidate writer that computes duplicate/contradiction risk.
5. Make duplicate remember actually merge/append evidence or return `related`, not `merged`.
6. Keep sample adapter tests on the sample adapter branch and extend them to cover H10/H12.

Exit criteria:
- `main` contains no sample adapter runtime surface.
- sample adapter branch has tests proving no read oracle, no raw SQL candidate path, and correct duplicate semantics.

## Workstream 6: Structural Decomposition

Objective: Reduce the chance of recurrence after high-risk bugs are closed.

Implementation sequence:

1. Extract storage repositories around transaction ownership.
2. Split `core/memory.py` by lifecycle: evidence, claims, candidates, retrieval, governance, hardening, federation, platform.
3. Split HTTP routing by route family.
4. Split CLI parser/runner by command group.
5. Add module-level ownership tests and static checks for duplicate method definitions.

Exit criteria:
- No single module owns unrelated lifecycle stages.
- Transaction helper is the only production path for write transactions.
- CI catches duplicate method names in large classes.

## Release Gates

Before declaring the review closed:

- Full test suite passes.
- Security-focused tests pass under hardened service profile.
- Performance tests establish bounded read-path query/write behavior.
- `docs/v1_3_0_review_closure_checklist.md` has every issue marked `Closed`, `Accepted Risk`, or `Out Of Baseline Scope`.
- Every `Closed` item has evidence.
- Any `Accepted Risk` has an explicit owner, expiry/review date, and deployment boundary.
