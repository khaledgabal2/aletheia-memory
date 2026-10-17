# Repeatable beta pressure evaluation

## Objective and acceptance

Exercise disposable synthetic memory across the documented lifecycle and every
published interface, identify reproducible defects, and retain executable steps
and receipts. Passing a smoke test does not establish production readiness.
No release tag, publication, existing user database, or production service is
part of this campaign.

Production qualification requires resolved reproducible correctness/security
failures, real-provider quality evidence, installed-artifact checks, interface
coverage, recovery evidence, and explicit limits on supported platforms and load.
Untested combinations remain pending. Types are extensible strings: “every
type” means all built-in policy/candidate types plus a custom-type check, not an
exhaustive enumeration of arbitrary strings.

## Reproduction

Use the repository development environment with pytest and package dependencies:

```sh
.venv/bin/python scripts/beta_pressure_harness.py \
  --output output/beta-pressure-UNIQUE-RUN --live-models
# Installed artifacts, real advisory tasks, TypeScript and socket checks:
.venv/bin/python scripts/beta_pressure_harness.py \
  --output output/beta-pressure-UNIQUE-EXTENDED --phase extended --live-models
# Focused repeat: edge cases, load, crash recovery and interface failures:
.venv/bin/python scripts/beta_pressure_harness.py \
  --output output/beta-pressure-UNIQUE-TARGETED --phase targeted \
  --artifact-run output/beta-pressure-UNIQUE-EXTENDED
# Exact assertion traces from historical scorecards:
.venv/bin/python scripts/beta_pressure_harness.py \
  --output output/beta-pressure-UNIQUE-DIAGNOSTICS --phase diagnostics
.venv/bin/python scripts/beta_surface_inventory.py --output output/surface-UNIQUE.json
# Bounded browser fixture; use printed URLs, complete read checks before review:
.venv/bin/python scripts/beta_browser_fixture.py --output output/browser-UNIQUE
```

The output directory must not exist. The harness deliberately configures both
providers before validation and uses the existing private shared resource-lock
inode. It refuses lock contention without scoring an attempt. Check current
actual inference clients and ownership before launching; the harness also checks
Ollama connections immediately before its live recipe. Never remove the lock,
terminate another owner's work, or change their model to obtain capacity.

Models: `llama3.1:8b`, temperature zero, structured JSON, 4096 context, 60-second
request timeout, unload after request; `nomic-embed-text:latest`, 768 dimensions,
`search_document: ` and `search_query: ` prefixes. The packaged local recipe
checks exact documented digests before inference. Only synthetic source text is
sent to loopback Ollama; no model downloads or hosted credentials are needed.

Each stage records command, start, duration, outcome and SHA-256 log digest in
`receipt.json`. Python API signatures and source hashes are inventoried. Logs,
JUnit, live-model output, and adversarial case receipts are retained. Historical
scorecards create their own temporary databases; the new pressure cases retain
their disposable databases for diagnosis. Synthetic records and test credentials
must stay out of commits. Interrupted/running steps are never counted as passes.

## Production qualification repeats

The continuation journal and acceptance boundaries are in
[`production_qualification.md`](production_qualification.md). Use fresh unique
output directories and execute these phases serially on frozen Python source:
`production`, `coverage`, `models --live-models`, `extended`, `interop`,
`http-surface`, `resources`, and `reliability --soak-seconds 1800`. Pass
`--artifact-run` pointing at the new extended output for interop. Coverage needs
coverage.py; interop needs the official MCP SDK in the selected interpreter.
The local tooling interpreter used for this campaign is recorded in the local
manifest; it is not a portable installation requirement.

Review every real extraction candidate triple **and its attached scope**, including
negation, reported attribution, date direction, absence of invented opposite
bounds and project inclusion/exclusion. Machine semantic checks alone previously
missed wrong scopes; retain both the failure and corrected oracle evidence.
Native Windows ACL checks must execute on Windows with a readable restricted-token
positive control. POSIX skips cannot qualify that boundary.

The reliability duration uses monotonic execution time. Host suspension can make
wall-clock completion much longer. Inspect `reliability/soak-progress.json`, then
require a terminal passed receipt, `source_stable=true`, all cases passed and
`cleanup.json` confirming shutdown. A process-scoped temporary sleep assertion
can help unattended execution but cannot prove continuous execution through every
host suspension. Never count a running campaign or elapsed wall time as a pass.

## Initial coverage map (historical)

| Area | Baseline evidence | Additional adversarial evidence |
| --- | --- | --- |
| Evidence, claim CRUD, provenance, persistence | MVP, M1, pytest | Unicode, SQL-like strings, 100k-character payload |
| Types, decay, confidence, curation | M1/M2, pytest | All built-in candidate/policy types, custom type, nonfinite confidence |
| Ingest, extraction, candidate review | M3/M12, review contracts | Real LLM extraction; missing model and secret-source refusal |
| Conflicts, scoping, correction | M2/M4, pytest | All resolution strategy entry points |
| Feedback, outcomes, learning, optimization | M2/M5, pytest | All ten signals; 100 assistant confirmations |
| Rules, inference, reflections, abstractions, invalidation | M4, pytest | Baseline only initially; adversarial expansion pending |
| Lexical, semantic, hybrid, index lifecycle | M1/M3/M11 | Real Nomic paraphrase recall, dimension/revision mismatch |
| Context, projects, sessions, budgets | MVP/M1/M4 | Baseline initially; large/malformed budget expansion pending |
| HTTP, authentication, scoped clients, sync/async SDK | M6, pytest | Live socket coverage and bulk/concurrency expansion tracked separately |
| MCP modes and tool registry | M6, pytest | Transport versus direct registry coverage must be distinguished |
| Console, CSRF, metrics, review tasks, exports | M7, pytest | Browser interaction/accessibility remains separate from route tests |
| Backup, restore, protection, forget, retention, integrity | M8, pytest | Recovery/kill-point expansion pending |
| Plugins, adapters, compatibility, docs/examples | M9, pytest | Installed wheel and TypeScript checks pending |
| Federation, grants, trust, bundles, replay | M10, pytest | Existing security/recovery regressions; network/platform matrix pending |
| Local discovery, TLS pairing, recovery | pytest | Installed-artifact validation pending |
| Bounded load | Baseline scorecards | 500 claims / 100 searches; 4 writers / 100 writes |

The generated public API inventory is a denominator, not a claim of per-method
semantic coverage. Each uncovered interface or workflow remains visible here.

## Execution journal — October 16, 2026 (America/Chicago)

1. Read repository instructions, README, package metadata, contributor release
   requirements, core concepts, lifecycle, interfaces, local model recipes, MCP
   and operations documentation. Inspected scorecard and runtime entry points.
2. Recorded initial dirty state: pre-existing untracked `output/`; no tracked
   source edits. Baseline commit: `4ad75a8a98b86d1606a4f2cead7f0cdfe63c3826`.
3. Inspected installed model tags/digests, resident model, processes and actual
   TCP clients. A resident Muse model was not treated as active inference.
   No established client was reported before admission. The historical Ultron
   resource schedule paths were absent; no schedule was invented or modified.
4. Added the campaign runner and adversarial cases. Compilation succeeded.
   Kept product implementation unchanged. Corrected harness keyword-only call
   mistakes during preparation; those are harness errors, not product defects.
5. Acquired the existing same-owner private resource lock and launched run 1 at
   19:23 CDT. Evidence: `output/beta-pressure-2026-10-16-run1/`.
6. Real embedding and LLM recipe passed in 17.182 seconds: three meaningful
   pending extraction samples, zero new active claims, semantic paraphrase
   recall, incompatible-index refusal, unavailable-provider handling and secret
   source exclusion. Full outputs and exact model/configuration are in receipts.
7. Observed development-environment installed metadata reports `1.6.0` while
   source package metadata is `1.6.3`. This is an environment attribution issue
   until reproduced in a fresh wheel installation; do not label the source run
   a published 1.6.3 artifact verification.
8. Started complete pytest regression suite, then all existing milestone
   scorecards, adversarial pressure cases and release gate serially.

An early suspicion that M7 masks failures was withdrawn after reading its
reporting function: it raises `SystemExit(1)` on failed cases. No product finding
is claimed from that suspicion.

9. Full regression completed: **846 passed**, 164.94 seconds. Generic repository
   release gate passed. All 14 historical scorecards ran; their initial aggregate
   was 181 passing and 37 failing cases, not a successful qualification gate.
10. Ran the extended phase with real LLM advisory tasks, actual socket and SDK
    pressure, wheel/sdist build, isolated installation, published 1.6.2 upgrade
    fixture, onboarding, TLS pairing lifecycle and TypeScript contracts. All
    artifact/TypeScript stages passed; advisory and MCP checks failed.
11. Preserved a resource-deferred focused receipt when another owner's worker
    held the shared lock. No checks started in that receipt. After the lock was
    released, continued in new directories without terminating the other worker.
12. Focused repeats supplied protected, federation and recovery keys explicitly,
    increased load from 500 to 5,000 memories, added crash recovery, checked all
    documented memory types including reflection, and reproduced negative cases.
    Latest focused evidence is `beta-pressure-2026-10-16-targeted3`.
13. Corrected an artifact-inspection harness bug: email metadata must be decoded
    as UTF-8 before comparing Unicode README text. Correct comparison passed for
    both wheel and sdist. Clean isolated import reports 1.6.3 from site-packages,
    with matching runtime and installed metadata. Initial failing receipt remains.
14. Exercised real browser clients and operator console. Initial combined browser
    fixture incorrectly seeded a duplicate and changed a domain table after
    taking its read-only baseline. Those failures were fixture contamination,
    corrected in browser2; they are not product findings. Corrected read and
    governed-review checks visibly passed. Console login/dashboard/trace/
    integrity/contracts/federation/logout were exercised; logout retains panels.
15. Used trace capture to retain exact assertion sites from historical scorecards.
    With corrected key setup, diagnostics recorded 189/218 passing cases and 29
    failures. These receipts remain failures. See the classification below.
16. Inspected actual provider output keys from the retained live database in
    read-only mode. Two advisory cases initially appeared to pass because API
    defaults supplied fields. Neither provider supplied those fields; all eight
    advisory tasks lacked their expected substantive output field. The separate
    `live-workflows/quality-review.json` preserves this correction. The reusable
    live harness now checks provider output keys for scope and merge tasks.
17. Saved browser screenshots/state and verified both owned browser fixtures
    stopped. Product source remains unchanged. The canonical later receipts copy
    executed harness sources; early source inventories were launch-time hashes
    while the new harness was still being prepared. Use later source snapshots
    for exact repeatability, not a claim that early harness preparation was an
    immutable test artifact.

## Results

| Check | Observed outcome |
| --- | --- |
| Existing pytest suite | 846 passed |
| Real local model recipe | Passed; 3 extraction samples, paraphrase recall, governance and provider-failure checks |
| New focused pressure cases | 28/31 passed; feedback-zero, invalid budgets and empty-scope resolution failed |
| Memory types | 20 built-in/documented/custom type names round-tripped with filtered retrieval and provenance |
| Feedback/conflicts | All 10 signals and 10 resolution strategy entry points exercised; zero strength and staged scoping deficiencies recorded |
| Bulk lexical retrieval | 5,000 claims, 100 searches; median 45.0 ms, maximum 49.1 ms in targeted3; no production SLA inferred |
| Concurrent writes/recovery | 4 connections / 100 writes passed; abrupt exit in uncommitted transaction recovered with integrity and rollback |
| HTTP and Python SDK | 100 sync reads, 100 async calls, 32 concurrent idempotent candidate writes, denied mutations passed |
| Stdio interfaces | Default namespace custom protocol passed; nondefault namespace and standard MCP initialization failed |
| Real LLM advisory quality | 8/8 lacked expected provider-generated task fields; no active memory created |
| Adversarial extraction | Governance held in 6 probes; four rejected bad source spans, one retained a quoted third-party statement, one produced an invalid whitespace candidate; not a quality pass |
| Installed artifacts | Fresh 1.6.3 import/onboarding, 1.6.2 data compatibility, TLS pairing lifecycle and recovery passed |
| README/package attribution | Wheel and sdist README match; isolated runtime and distribution version both 1.6.3 |
| TypeScript | 24 tests passed, typecheck/build and all four live contract flows passed |
| Actual browser | 7 read checks and 6 review checks passed; console logout retained displayed results |
| Historical scorecards | 189/218 cases passed in diagnostics; 29 failures retained and classified |
| Public surface inventory | 317 Memory methods, 284 CLI leaf commands, 221 HTTP operations, 19 MCP tools |

The static inventory lists direct test references and signatures. A matching
name is not proof of execution or semantic correctness; a missing direct name
can also be exercised indirectly. It is not an exhaustive coverage certificate.

## Historical scorecard failure classification

Exact functions and lines are retained in diagnostics `*-exceptions.json` files.

- MVP, polish, M1–M7 and M10 schema assertions still expect 1.3.0 instead of
  current 1.3.1. M1/M2 also fabricate databases older than the supported migration
  floor. These expectations must be versioned rather than weakening migration
  refusal or accepting a mismatched schema.
- M1 expects ordinary retrieval to persist a confidence recomputation; current
  reads are non-mutating by default. M6 expects a project containing secret
  provenance to be listed for a lower-privacy caller; current aggregate source
  authorization refuses it. M7's failing initial setup skips its milestone seed,
  cascading into a later active-claim metric assertion.
- M8 recreates an existing backup path inside its restore case; current code
  correctly refuses overwrite. Its crypto check expects `enc:v2:` while current
  protected storage writes v3. Its archive import expects a redacted/metadata-only
  export to restore content; current import correctly refuses that operation.
- M10 reuses an encrypted bundle addressed to another local identity. Current
  recipient validation refuses it; preserve that security boundary.
- M11 expects a stale embedding row after redaction; current privacy cleanup
  removes that row. The old script then indexes into `None`. This is not evidence
  of continued vector disclosure.
- M9/M12 expect structural conformance to pass as behavioral assurance. Current
  conformance returns incomplete/structural evidence and the in-database v1 gate
  remains failed, as documented in `behavior_verification.md`. The separate
  repository packaging gate passing does not override that result.

## Qualification limits and next work

The bounded campaign is complete; production qualification is **not** complete.
Findings and suggested repairs are in [beta_pressure_findings.md](beta_pressure_findings.md).
All documented interface families were exercised, but exhaustive per-operation,
per-input and cross-interface semantic parity is not established for the full
317/284/221/19 inventory. Some legacy assertions stop before later workflow steps;
their failed gates are not counted as passes. No Linux/Windows or Python 3.11/3.12
runtime matrix, prolonged soak, memory/disk exhaustion, disk-full recovery,
multi-process HTTP saturation, exhaustive crash points or statistically powered
LLM quality benchmark was run on this macOS/Python 3.13 host.

Before production: resolve/retest the seven findings or explicitly narrow the
supported promises; update legacy fixtures without relaxing security; strengthen
postconditions for each resolution strategy; complete behavioral conformance
suites; map unverified inventory entries to real workflow assertions; and run
the supported platform/load/recovery matrix. Keep evidence of rejected LLM spans
and improve output quality without relaxing provenance validation.

The built artifacts are evaluation artifacts, built before the final evaluation
documents. They are not a release candidate for publication. A future release
must rebuild from finalized source/docs and follow CONTRIBUTING.md.


## Fix campaign reproduction

The original journal and receipts above are historical evidence. The follow-up
fix campaign is described in `beta_pressure_resolution.md`; do not interpret the
original failures as the current result, or replace a failed receipt with a pass.

Additional phases use the same model configuration, resource admission and
immutable output directories:

```sh
.venv/bin/python scripts/beta_pressure_harness.py --phase regression --output output/fixes-regression-UNIQUE
.venv/bin/python scripts/beta_pressure_harness.py --phase models --live-models --output output/fixes-models-UNIQUE
.venv/bin/python scripts/beta_pressure_harness.py --phase reliability --output output/fixes-reliability-UNIQUE
# Isolated extra test tooling, not Aletheia runtime dependencies:
uv venv /tmp/aletheia-evaluation-tools
uv pip install --python /tmp/aletheia-evaluation-tools/bin/python -e '.[dev]' coverage 'mcp==1.30.0'
/tmp/aletheia-evaluation-tools/bin/python scripts/beta_pressure_harness.py --phase coverage --output output/fixes-coverage-UNIQUE
/tmp/aletheia-evaluation-tools/bin/python scripts/beta_pressure_harness.py --phase interop --artifact-run output/fixes-extended-UNIQUE --output output/fixes-interop-UNIQUE
```

Coverage measures this pytest process, including threads; independent CLI child
processes are not included in its percentage. A method with an executed body is
not thereby tested for every branch, argument, authorization combination or
provider. Reliability uses SQLite page-capacity exhaustion rather than filling
the host filesystem, eight independent HTTP clients, and a bounded two-minute
workflow soak. It does not establish multi-day reliability or a load SLA.


## Follow-up interface and resource phases

The current correction journal is `docs/beta_pressure_resolution.md`. Historical
counts above remain unchanged. The SDK request denominator is 142 (75 sync and
67 async), with four additional async response properties. Current measured body
coverage is distinct from successful semantic assertions and route coverage.

```sh
.venv/bin/python scripts/beta_pressure_harness.py --phase http-surface --output output/http-UNIQUE
.venv/bin/python scripts/beta_pressure_harness.py --phase resources --output output/resources-UNIQUE
.venv/bin/python scripts/beta_pressure_harness.py --phase reliability --soak-seconds 1800 --output output/soak-UNIQUE
```

HTTP coverage runs record method/template/status only, never request data, IDs
or credentials. The separate socket sweep tests every current OpenAPI operation
with bounded missing-object/empty-state requests. It does not replace positive
workflow tests. Installed-artifact extended runs also launch every CLI leaf's
`--help` from an empty working directory and assert no storage is created;
that qualifies discoverability and parsing, not every command's semantics.

Resource pressure never exhausts host storage. On macOS it mounts an owned
64 MiB disk image beneath the output directory, fills it to ENOSPC, checks failed
SQLite write rollback/recovery, and detaches it in finally. On Linux it uses an
owned child with a 256 MiB address-space limit, verifies MemoryError, restores
its limit, and checks subsequent database write/reopen/integrity. Those are
bounded failure paths, not every SQLite/crypto allocator or crash point.

The longer reliability phase continuously exercises governed lifecycle writes
until its 5,000-cycle budget, then continues reads until the selected deadline.
It saves periodic progress, final assertions and cleanup. A long run must retain
its logs and receive a scheduled result follow-up; running/deferred is never a
pass. It qualifies that workload and duration only, not a multi-day reliability
claim, production traffic distribution or load SLA.

For browser repeats: open the printed read URL, run its checks to PASS, then run
review checks to PASS. Console uses a separate synthetic database and private
fixture token. Exercise console actions, verify scoped failures are visible,
then verify logout clears panels/inputs. Save browser states, error logs and
screenshots. Never commit fixture tokens, synthetic key files or databases.
