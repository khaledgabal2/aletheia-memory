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
