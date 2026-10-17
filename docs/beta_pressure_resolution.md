# Beta pressure findings: fix and verification record

This is the follow-up to the seven findings in `beta_pressure_findings.md`.
It records changes and verification separately from the original campaign.
No production release, tag or publication is authorized by this report.

## Final campaign decision — October 16, 2026

The seven reported defects are fixed and the bounded follow-up campaign is
complete. **Retain beta; this is not production approval.** Implementation
revision `8dd1873` passed 1,074 local tests (including 324 focused regressions),
all 14 milestone scorecards, configured real Llama/Nomic checks, fresh-artifact
and interface checks, actual isolated disk-full recovery, and a 30-minute soak
with 2,516 complete lifecycle cycles and stable source. Statement coverage was
85.0%; branch coverage was 65.9%.

Native Actions [run 38997788906](https://github.com/khaledgabal2/aletheia-memory/actions/runs/38997788906)
passed every job at `8b02622`, including all nine Linux/macOS/Windows and Python
3.11/3.12/3.13 combinations. That revision changes only redirect test fixtures
and this journal relative to the tested implementation. Linux additionally
verified bounded MemoryError and write/reopen/integrity recovery. Windows 3.13
reported 1,057 passed and 17 POSIX-only skips. The earlier redirect failure is
preserved; the successful repeat does not prove its original root cause.

Coverage includes 221 HTTP empty/refusal route contracts, 19 positive MCP tool
calls, 142 SDK request facades, 284 installed CLI help leaves, and browser flows.
These counts do not establish every input, branch or positive workflow. All eight
real advisory tasks passed, but five of six adversarial extraction samples had
no usable candidate. Governance refusal remains intact; extraction quality is a
release blocker. Windows ACL isolation and a production startup-latency SLA are
unqualified; local pairing remains POSIX-only. These are explicit remaining
qualification gaps, not passing checks. No merge, tag or publication occurred.

The scripts and reproduction instructions in `beta_pressure_evaluation.md` are
reusable. Canonical receipts and source-stability evidence are retained locally
under `output/beta-fixes-continuation/state.json`; raw databases, keys, tokens and
logs are excluded from commits. The temporary follow-up is disabled when this
report is delivered. Later documentation-only commits do not change the tested
Python implementation.

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

23. The transaction retry guard now refuses further Memory writes inside an
    enclosing scope that SQLite already aborted, even if application code caught
    the inner error. A regression demonstrates that retry cannot escape the
    failed outer transaction. The harness now compares Python source hashes at
    start/end and invalidates any run with changed source. Coverage5 executed
    1,072 tests successfully but is superseded: its separate source-stability
    audit records edits during execution. It is not final-revision evidence.
24. Regression9 was resource-deferred before any test ran: another owner's model-validation
    job held the existing shared lock and an actual Ollama connection. No process,
    model or profile belonging to that job was changed. Pending local checks must
    resume in new output directories at the next available opportunity.
25. Review found that the byte-preservation correction delayed WAL until after
    normal initialization. Restore early WAL behind a read-only supported-version
    preflight, sharing the same range validator with migration. This preserves
    refused database bytes without imposing DELETE-journal initialization costs.
    Added a regression asserting WAL is active before valid migration. Native
    startup and platform timing repeats are required to confirm the performance.
26. Source is prepared for frozen validation; final local repeat, fresh artifacts,
    complete installed CLI help sweep, current native matrix, Linux memory probe
    and 30-minute lifecycle soak remain pending until their receipts are terminal.
    Pending, deferred and source-invalidated receipts never count as passing.

27. Prepared frozen revision: `8dd1873`. The current native matrix is
    Actions run `38993797582`. Earlier native repeats passed all three macOS
    combinations after allowing a bounded lifecycle wait. Linux native jobs also
    verified actual bounded MemoryError and subsequent write/reopen/integrity;
    the safe summary is retained in `beta-fixes-native-linux313-resources.log`.
    These prior results do not replace the final-revision repeat.
28. The second admission retry (`beta-fixes-regression10`) was also resource-
    deferred with no tests executed. A temporary in-thread follow-up named
    `finish-aletheia-beta-validation` is active every 15 minutes to resume the
    pending phases, review native results, and disable itself after the campaign
    report is delivered. Keep the computer and desktop app running for local work.

29. The resource became available. Regression11 passed **324 tests** on prepared
    revision `8dd1873`; automatic Python source stability was true.
30. Coverage6 passed **1,074 tests**, every milestone scorecard and adversarial
    pressure. Source stability was true. Statement coverage: 85.0%; branch: 65.9%.
    All 317 Memory, 75 sync SDK, 71 async SDK/property and four MCP registry
    bodies were observed. Route instrumentation and independent socket sweeps
    remain different scopes; no exhaustive input/branch claim is made.
31. Models2 passed the real Llama/Nomic recipe and all eight substantive advisory
    checks on this frozen revision. Extraction quality still failed five of six
    adversarial samples, separately from passing governance. No provenance
    checks were relaxed. Source stability was true.
32. HTTP4 passed all 221 actual-socket empty/refusal contracts; resources3 again
    passed actual isolated ENOSPC / SQLITE_FULL / rollback / write/reopen and
    detachment. Extended2 passed interface load, wheel/sdist README/version,
    fresh install/recovery, all 284 installed CLI help leaves with an unchanged
    working directory, and TypeScript checks/contracts. Interop3 passed official
    MCP SDK 1.30.0 against that fresh wheel. All source checks were stable.
33. The current native matrix has passed Linux/macOS on all three Python
    versions and Windows 3.12; two Windows jobs were still running at the latest
    inspection. macOS hosted CI recorded roughly 36-second CLI lifecycle calls
    within the bounded minute; startup latency has not been qualified to a
    production SLA. Do not infer that early WAL explained every hosted delay.
34. `beta-fixes-soak1` is now running the requested longer, 1,800-second bounded
    lifecycle/retrieval workload. Its final outcome is pending. The temporary
    scheduled follow-up will collect terminal results, update this journal and
    the canonical manifest, then disable itself when the campaign is complete.

35. Current native run completed: eight of nine OS/Python combinations passed.
    Windows 3.13 reported one failure (1,056 passed, 17 skipped): sync POST 307
    redirect test received `transport_error` instead of `redirect_blocked`.
    Preserve this failure; its cause is not established and it is not a pass.
    Diagnose after the active source-frozen soak; raw log is retained locally
    as `beta-fixes-native-ci5-failed.log`. All other workflow jobs passed.

36. Scheduled follow-up inspected the existing soak rather than duplicating it:
    progress recorded 1,550 lifecycle cycles with approximately 20 minutes left.
    PR #69 remains a draft at exact source revision `8dd1873`. Read-only redirect
    inspection found the test origin closes without consuming a POST body, and
    uses a two-second request deadline. A Windows reset or hosted timeout is a
    hypothesis, not a diagnosis: the failed assertion lacks its chained exception.
    After the soak, add diagnostic evidence and verify the fixture's HTTP exchange
    without relaxing destination no-forward or redirect-refusal assertions.

37. The next scheduled inspection found 2,350 lifecycle cycles with about
    4.5 minutes remaining. SQLite-capacity recovery and eight-process/400-request
    retrieval checks already have passing case receipts; the overall soak remains
    pending until final integrity, cleanup and source-stability checks complete.
    No duplicate workload or Python edit was started. PR head remains `8dd1873`;
    Ollama showed its listener only, with no active client observed.

38. Soak1 completed successfully on `8dd1873`: 1,800 seconds, 2,516 complete
    governed lifecycle cycles, eight-process/400-request retrieval pressure,
    SQLite-capacity recovery, final integrity/cleanup and source stability true.
39. With the campaign terminal, corrected the redirect test origin to consume
    and assert its POST body before closing, and declare Content-Length: 0 on
    redirects. Same-origin fixture also consumes the body. Failure assertions now
    include the chained transport cause. Destination no-forward assertions and
    SDK redirect policy are unchanged. All 28 focused redirect tests passed
    locally under the existing shared lock (`beta-fixes-redirect1`). Native
    Windows validation remains required; the original failure is not erased or
    conclusively attributed to the fixture. This test-only change does not
    invalidate the completed implementation soak.

40. Native repeat `38997788906` completed successfully at `8b02622`: all nine
    matrix combinations and every other job passed. Retained final Windows 3.13
    and Linux 3.13 logs. Linux observed bounded MemoryError and successful
    subsequent write/reopen/integrity; Windows 3.13 passed 1,057 tests with 17
    POSIX skips. Finalized the decision above, preserving prior failed, invalidated
    and resource-deferred receipts. The completed campaign supports retaining
    beta with explicitly documented extraction/platform/performance gaps.
