# 1.4.0 external audit closure

**Historical gate:** a later independent re-review found and corrected four
residual release issues. See the authoritative
[final independent re-review closure](v1_4_0_rereview_closure.md).

Recorded 2026-09-01. This closes the findings in the Claude review of
`codex/v1.4-plan` at `c75dfb9`. That review examined the pre-implementation
baseline and did not run the test suite. Each finding was therefore reproduced
or reconciled against the completed 1.4.0 branch before code changed.

The release findings from the final Codex audit were corrected first in
`8f4e9e7`: release and migration metadata now come from independent software and
storage authorities, all public projections agree on the tested 1.3.0 to 1.3.1
path, and packaged installation guidance describes the already-published 1.3.1
baseline accurately. The Claude critical and high findings were then closed in
`73c1b67`; the remaining verified medium and low findings are closed by the
subsequent correction set recorded here.

Nothing in this work was merged, pushed to `main`, disclosed, or published.

## Critical and high findings

| ID | Disposition | Closure |
| --- | --- | --- |
| C1 | Fixed before this audit pass | The HTTP service serializes the full request lifecycle on one reentrant service lock, including authentication, reads, writes, idempotency, and best-effort request logging. Logging errors cannot terminate a response. Concurrent service/review suites exercise the live path. |
| C2 | Fixed and extended | Governed review uses `BEGIN IMMEDIATE`, one atomic decision transaction, conditional replay/revision checks, and cross-connection conflict tests. Embedded review now also refuses every terminal candidate state; a promoted, rejected, merged, or duplicate candidate cannot be reopened or promoted twice. |
| C3 | Fixed before this audit pass | Software 1.4.0 and storage 1.3.1 are independent. The authentic frozen 1.3.1 SDK accepts the new service through the legacy bridge, while current clients use canonical discovery fields. |
| H1 | Fixed | Report export applies the same configured safe-root containment as every other administrative file output. A read token cannot write outside those roots. |
| H2 | Fixed | Failed bearer authentication is charged to an anonymous/local source bucket before the 401 is returned. Repeated invalid credentials produce a 429 envelope. |
| H3 | Fixed | Generic idempotency is credential-scoped, validates keys, reserves an in-progress row atomically across service instances, and never stores console login/logout secrets. Competing operations are refused and replays still pass current authorization in the negotiated profiles. |
| H4 | Closed to the 1.4 contract | The selected `memory-review-v1` surface has opaque revisions, atomic compare-and-apply, stale refusal, current-scope checks, conservative invalidation, and cross-process tests. The plan does not advertise optimistic concurrency for every legacy mutation, so no unsupported global revision promise was added. |
| H5 | Fixed | SQLite runs in explicit autocommit mode; all multi-row authentication operations use store transactions; archive import is one immediate transaction. Reopen tests prove imported data is committed and no hidden transaction remains. |
| H6 | Fixed | Applied restore requires an authenticated encrypted archive by default. Checksum-only archives are clearly marked unauthenticated and require an explicit provenance-trust flag. Attacker-controlled PBKDF2 work factors are bounded. |
| H7 | Closed to the 1.4 compatibility decision | `doctor --read-only` never creates, migrates, or records data; `init --new`, migration planning/backup guards, starter refusal, and service `auto_migrate=False` provide explicit safe paths. Historical mutating CLI commands retain compatibility as required by the source-of-truth plan. `api ping` now also runs before database opening and accepts loopback URLs only. |

## Medium and low findings

| ID | Disposition | Closure |
| --- | --- | --- |
| M1 | Fixed | Release, discovery, doctor, backup, and compatibility output use software or schema versions according to their actual meaning. Shared migration-range authority prevents another projection from drifting. |
| M2 | Fixed within both modes | Read-only doctor is the safe default workflow and returns nonzero on errors without storage mutation. Legacy recorded doctor now returns nonzero when unhealthy and tests MCP, console, SDK-contract, Python, and SQLite availability instead of inserting unconditional passes. |
| M3 | Fixed | Every HTTP numeric conversion uses validation helpers. Invalid query/body numbers return a 400 `validation_error` envelope rather than a 500. |
| M4 | Fixed | PUT and PATCH enter the JSON service boundary; unsupported routes return normal envelopes. Unsupported transfer encodings are refused, body reads have a configurable socket deadline, and timed-out bodies return 408 when possible. |
| M5 | Fixed | Unexpected 500s retain the redacted client envelope and emit a server traceback with request ID and endpoint for operators. |
| M6 | Fixed | Scaffolds reserve a fresh directory and never overwrite existing paths. Documentation validation now generates all packaged starters, compiles Python sources and adapters, parses TypeScript manifests, validates CLI examples, OpenAPI paths, MCP tools, and public contracts; a failed check makes the documentation build fail. |
| M7 | Fixed with migration compatibility | New secret hashes and encrypted content use 600,000 PBKDF2-SHA256 iterations. Stored iteration counts are bounded. Current content is self-describing `enc:v3`; legacy v2/v1 content remains readable at its historical work factor. A successfully authenticated unsalted legacy API token is immediately rehashed. |
| M8 | Fixed before this audit pass | The single SQLite connection is protected by full request serialization, and the worker uses the same service lock. Concurrent read/review tests cover independent handler and database connections. |
| M9 | Fixed | The Python SDK maps URL, timeout, and non-JSON failures to `AletheiaTransportError`; retries one safe GET only; never blindly retries a mutation; and serializes the sync transport/last-response snapshot used by its async facade. |
| M10 | Fixed | New console login tokens and sessions carry high-entropy lookup digests, so authentication performs one PBKDF2 verification instead of scanning every session. Legacy lookup is bounded. Remote cookies include `Secure`, default grants are the configured namespace rather than `*`, and failed authentication is rate-limited. |
| L1 | Fixed | Response headers use a private `_ServiceData` carrier. A stored preference named `_headers` remains ordinary response data and cannot become an HTTP header. |
| L2 | Fixed | Tokenless MCP mode capabilities are passed into the service authorization context; active/admin modes no longer pass the registry and then fail at HTTP. Query parameters use URL encoding and the dead token helper is gone. |
| L3 | Fixed | Claim and conflict evidence hydration is batched; event listing no longer re-queries each row. Empty lexical queries use a bounded claims query and do not scan the FTS virtual table. |
| L4 | Fixed | Top-level and API dispatch reject impossible fallthroughs, API ping uses the loopback/no-redirect validator without opening storage, MCP rejects process-visible `--token` secrets in favor of `--token-env`, and newly created SQLite files are reserved with mode 0600. |
| L5 | Fixed | Remember validates the privacy vocabulary and credential ceiling once, then stores the same level on evidence and candidates or active evidence. Unknown levels return 400 and over-ceiling levels return 403. |
| L6 | Fixed after live verification | Applied content rotation now requires distinct key-specific environment material, decrypts and re-encrypts every old-key payload in one immediate transaction, verifies none remain, and retires the old key only after success. Dry-run reports a deterministic new key ID without creating a key. |

## Verification

| Gate | Result |
| --- | --- |
| Complete Python suite | 304 tests passed on macOS ARM64 / Python 3.13.13, including real loopback HTTP, authentic legacy SDK, concurrency, migration/recovery, crypto, package, and onboarding coverage. |
| Affected regression set | 105 service, retrieval, hardening, platform, onboarding, and crypto tests passed. |
| TypeScript | `tsc --noEmit` passed. |
| Node transport | 24/24 real-socket cancellation, timeout, polling, authorization, and scope tests passed. |
| Distribution build | `uv build` produced the 1.4.0 wheel and source archive. Wheel inspection confirmed version metadata, bundled docs, all three starters, and the top-level compatibility client. A fresh environment then installed that exact wheel and verified version 1.4.0, schema 1.3.1, packaged assets, database initialization, and the public `Memory` API. |
| Hygiene | Changed Python modules compile; `git diff --check` passes. |

The automated evidence closes the reported implementation defects. It is not a
human security certification and does not replace protected-branch CI. Owner
approval, private/public PR handling, protected merge, coordinated disclosure,
publication, and verification of the public package remain Phase 7 controls.
