# Beta pressure findings: fix and verification record

This is the follow-up to the seven findings in `beta_pressure_findings.md`.
It records changes and verification separately from the original campaign.
No production release, tag or publication is authorized by this report.

## Changes and regression evidence

| Finding | Change | Regression boundary |
| --- | --- | --- |
| Zero-strength feedback changed trust/status | Validate finite numeric strength, preserve zero through scoring and return before applying effects; repeated assistant confirmation without evidence is inert | All ten signals, full frozen-time confidence breakdown, status/verification, 100 repetitions |
| Invalid context budget | Reject noninteger, negative, boolean and nonfinite budgets before reads/writes; permit zero | Embedded invalid inputs with zero domain mutation, empty zero-budget result |
| Scope resolution without scopes | Require complete unique scoped_claims for every family member, validate predicates/time bounds, commit together | Both strategies, omitted/partial/invalid scopes, HTTP/CLI refusal then successful atomic resolution |
| False-success advisory LLM results | Eight task-specific prompts and typed contracts; refuse missing/blank/malformed or forged metadata and self-approval; remove reflection placeholders | Malformed output across eight tasks, no active claim/reflection/conflict mutation; real Llama outputs |
| Nonstandard MCP wire | Implement JSON-RPC lifecycle, tools/list and tools/call, ping, bounded framing and typed arguments; keep legacy input compatibility | Real subprocess initialization, discovery, candidate mode, namespace/write denial, malformed arguments; official SDK separately |
| Wrong local MCP namespace | Open Memory with the selected CLI namespace | Default and custom namespace subprocess calls |
| Console retains data after logout | Clear rendered panels, queries, token and CSRF immediately; discard responses from an ended session | Execute actual console JavaScript under Node for logout, auth loss and a held in-flight response; real browser separately |

The implementation also replaces missing built-in conformance probes with
isolated behavioral checks for all 17 suites. Results record the installed
implementation digest. The v1 gate rejects stale, structural and caller-forged
behavioral results; external unit/integration evidence is still required.
Assertions disabled by optimized Python cannot produce a passing certificate.
These probes have explicit bounded scope, documented in behavior_verification.md.

## Step-by-step follow-up journal

1. Preserved all original receipts and source snapshots; inspected the working
   tree and existing resource lock before live execution.
2. Implemented the seven corrections and focused regression tests. First focused
   run: 106 passed. Expanded conformance run exposed two fixture errors (missing
   HTTP headers and plugin approval reason); retained that failed receipt and
   corrected the fixtures. Next run: 145 passed.
3. Configured Llama 3.1 8B and Nomic Embed Text with the packaged local recipe
   before live calls. `output/beta-fixes-models1` passed: all eight real advisory
   tasks returned substantive required fields. Six extraction adversarial probes
   preserved governance; this does not mean all six extracted content correctly.
4. `output/beta-fixes-baseline1`: 907 pytest tests passed; adversarial pressure
   passed. Four historical scorecards failed. Missing schema imports and old
   staged scope resolution were harness defects and were corrected.
5. The migration scorecard exposed an additional product defect: unsupported
   migration refusal changed the SQLite journal-mode header. Move WAL setup after
   successful migration and test byte-for-byte preservation. No unsupported
   legacy migration is represented as a successful upgrade.
6. Added bounded storage recovery, eight-process HTTP retrieval, repeated
   review/recall/feedback lifecycle, official MCP SDK interoperability, runtime
   coverage and native OS/Python CI matrix. Initial reliability fixture expected
   no retrieval fallback hits; corrected it to check candidate exclusion. The
   original failed receipt remains in `beta-fixes-reliability1`.

Further results are appended after execution, with failed and deferred work
kept distinct from passing checks. Beta status remains until all required
release evidence and quality decisions are reviewed.

7. `output/beta-fixes-reliability2` passed: bounded SQLITE_FULL refusal left
   integrity intact and recovered after capacity was increased; eight separate
   processes completed 400 real retrievals; the 120-second soak completed 200
   candidate/operator-review/idempotent-replay/recall/feedback/context cycles plus
   1,208 further reads. The fixture stopped its own server cleanly. This is a
   bounded run, not a multi-day soak or physical-disk exhaustion test.
8. Saved review branch `codex/beta-pressure-fixes`. Automatic approval review
   required explicit authorization for a public draft PR; the user supplied it.
   Draft PR #69 triggers actual native Linux/macOS/Windows jobs for Python
   3.11, 3.12 and 3.13. No release workflow was started.

9. `beta-fixes-coverage1` passed 915 tests with 83.2% statement and 64.5%
   branch coverage inside pytest; 269/317 public Memory bodies were observed.
   Independent subprocess work is excluded from those percentages. The remaining
   M10 scorecard expected a structural certificate to say passed; corrected it.
10. `beta-fixes-extended1` passed advisory/model, HTTP/SDK concurrency, installed
    artifact README/version, onboarding/recovery, and all TypeScript stages.
    Official MCP SDK 1.30.0 passed against the installed 1.6.3 wheel in
    `beta-fixes-interop2`. The initial interoperability fixture resolved the
    virtualenv Python symlink to base Python and lost site-packages; that harness
    failure is retained in interop1.
11. Added a 142-case SDK request-facade sweep using actual handlers and independent
    OpenAPI paths, plus positive lifecycle tests for clustering, inference
    rejection, operator dismissal/snoozing, catalog persistence and membership
    removal. Added all 19 MCP tools through JSON-RPC. Retained fixture failures
    for missing example seed and missing encrypted-backup key (regression4/5).
12. First native macOS/Python 3.13 run passed 913 tests and failed two CLI
    advertisement startup cases. The old tests discarded subprocess output;
    added saved startup diagnostics for the repeat. No platform pass is inferred
    from the local macOS result. Remaining native jobs are pending.

13. Expanded focused verification: `beta-fixes-regression6` passed 304 tests,
    including all 19 MCP tools and all 142 SDK request facades. The independent
    SDK route oracle is OpenAPI; positive domain semantics are tested separately.
14. Browser2 passed all seven read and six review checks. Exercising all 17 console
    actions exposed four unhandled errors: Encryption/Support Bundle correctly
    refuse scoped access but did not explain the refusal; Shares/Conflicts omit
    their required namespace. Add visible action-error status and encoded selected
    namespace; preserve server authorization. Logout clears all results/inputs.
15. Initial native Windows 3.12 run: 884 passed, 17 expected POSIX pairing skips,
    14 failures. LF checkout fixes hashed fixture transformations. Correct native
    Path/home/TOML test setup, condition POSIX mode assertions on POSIX rather
    than certifying Windows ACLs, and refuse an existing dangling symlink before
    exclusive database reservation. Retain all original failures and repeat.

16. Browser3 verified visible scoped-access refusal, working Shares/Conflicts,
    no new unhandled browser errors and cleared logout state. Screenshots and
    per-step states remain under `output/beta-fixes-browser3`.
17. `beta-fixes-coverage4`: 1,069 passed, 85.0% statement / 65.8% branch coverage.
    Bodies observed: Memory 317/317, sync SDK 75/75, async SDK 71/71 (including
    four response properties), MCP registry 4/4. The request-facade sweep contains
    142 methods (75 sync + 67 async); the earlier 144 count was incorrect.
    Executed bodies do not establish every argument, branch or provider behavior.
18. Route instrumentation observed 134/221 operations inside pytest. A separate
    actual-socket sweep then exercised all 221 declared operations with explicit
    missing-object/empty-state contracts. Its first fixture treated Prometheus
    as JSON; corrected that format assumption. Disabled console/pairing responses
    were not accepted as positive implementation evidence.
19. The socket sweep exposed two additional product defects: HTTP compaction
    attempted checkpoint/VACUUM inside the service transaction, and an absent
    share-import file became HTTP 500. Idle-connection handling and a clear
    validation error fix those paths. The reader denial remains unchanged.
    `beta-fixes-http3` passed all 221 operations, with no unexpected server error,
    retained namespace intact and database integrity intact. This is route/error
    qualification; positive semantic workflows remain separately tested.
20. `beta-fixes-resources1` filled only a disposable 64 MiB HFS+ disk image.
    SQLite rolled back and recovered, but nested rollback masked SQLITE_FULL as
    a missing-savepoint error. Preserve the original error after SQLite aborts
    its entire transaction; restore depth even if creating a savepoint fails.
    `beta-fixes-resources2` passed actual ENOSPC, SQLITE_FULL=13, atomic rollback,
    integrity, subsequent write/reopen, and image detachment. Host storage was
    never filled. Added deterministic regressions for both transaction failures.
21. The macOS address-space limit attempt was refused by the OS and remains a
    failed capability probe, not an application failure or a memory-pressure
    pass. Linux CI now runs the bounded 256 MiB child-allocation/recovery probe.
    Native resource phases select the host-supported probe explicitly.
22. `beta-fixes-regression8` passed 312 focused tests, including the new HTTP and
    transaction corrections and both real CLI lifecycle subprocesses. Native
    Linux 3.11/3.12/3.13 and Windows 3.11/3.13 passed on the earlier fix revision.
    macOS native children remained alive beyond the original 10-second lifecycle
    deadline without startup output. The repeat allows a bounded minute and
    captures periodic Python stacks; no startup-latency SLA is claimed. The next
    native run is still required. CI now retains verbose case names and bounded
    stall diagnostics instead of leaving an indefinite silent job.
