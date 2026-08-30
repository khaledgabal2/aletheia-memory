# 1.4.0 Phase 2 verification

Prepared 2026-08-30 on `codex/v1.4-read-contract`, based on discovery commit
`860ab144fc6f520dc15f53d9a06837ff844588fc`. The
[release plan](v1_4_0_contract_hardening_and_developer_experience_plan.md) remains
authoritative. This is development evidence, not release or merge approval.

## G2 result

The local G2 checks pass for `memory-read-v1`: six discovery operations, six
canonical read operations and the two preserved read aliases. The branch
advertises that profile only. The [read contract](v1_4_0_read_contract.md) records
its permissions, transport, redaction, limits, intentional compatibility changes
and remaining limitations. The Phase 0 inventory remains a historical proposal;
current executable definitions live in the service contract modules.

| Check | Observed result |
| --- | --- |
| Supported Python matrix | All 183 tests pass on Python 3.11.15, 3.12.11 and 3.13.13 on macOS. Includes 17 read conformance cases. |
| Actual-service schemas | OpenAPI 3.1 projection validates. Populated overview/review sections, claim, explanation, all audit variants, context and ranked/empty retrieval responses validate against generated definitions. |
| Negative read cases | Namespace/project/session restrictions, privacy ceilings, candidate-review permissions, redaction, derived-source filtering, target types and changed permissions pass across sibling routes. |
| Inputs and errors | Canonical type/limit failures, missing/denied resources, request-body limits and rate limiting return typed errors with no-store/correlation headers. Legacy numeric coercions and extension fields remain accepted. |
| Repeated reads | Twelve concurrent overview/retrieve/context calls complete. Every database table is unchanged except permitted operational request/rate counters. Explicit context usage records only delivered items. |
| Generated consumer | Locked openapi-typescript 7.13.0, openapi-fetch 0.17.0, TypeScript 5.9.3 and Node 26.0.0 regenerate, compile and execute actual authenticated reads without domain payload casts. Baseline and discovery consumers still pass. |
| Client lifecycle | Five Node tests pass: no overlap/late results; hidden/offline pause and reconnect; capped retry/backoff and permanent-error stop; stalled response-body timeout; changed scope during a request and unsupported profile rejection. |
| Actual browser | Memory-owned page in the in-app browser passes seven checks: authenticated reads/provenance, response headers, narrowed privacy, revoked credentials/cache clearing, cancellation, fresh-credential reconnect and domain-table stability. Live Connect/Narrow/Revoke controls also show one result, then zero, then 401 with no cached data. Final compiled client and service were rechecked after timeout/profile changes. |
| Local transport | Malformed/untrusted Host and Origin are rejected before body reads; same-origin authenticated requests pass. No CORS expansion or new OPTIONS policy. Existing console/CSRF regressions remain green. |
| Old SDK → new service | Authentic published 1.3.1 SDK still completes the candidate/review/read/context/provenance lifecycle in the regression suite. |
| New SDK → old service | Separately installed, hash-verified 1.3.1 service accepts legacy reads/context; unavailable principal/profile features are explicit. |
| Distribution checks | Wheel and sdist build. All 183 tests pass again from the extracted sdist. Read modules/docs and source-only browser tooling are present; Node dependencies, generated outputs and Python caches are excluded. |
| Clean wheel installation | Installed outside the checkout with core dependencies only. Profile/schema imports work. The exact bundled tutorial runs with network connections blocked for approval and refusal, and preserves the existing database on rerun. |
| Repository boundary | Generic release-boundary and whitespace checks pass. Original checkout stays clean on `codex/v1.4-plan`; no main push or merge. |

The browser check is a recorded real-browser validation, not an unattended CI
browser claim. CI includes the Python matrix, packaging, schema/client generation,
real-service consumers and Node lifecycle tests. Temporary private security forks
may not run Actions; local macOS results do not imply a Linux CI result.

Reproduction commands are in
[`contracts/typescript/README.md`](../contracts/typescript/README.md); run the
Python suite with `python -m pytest`. Fixtures use disposable databases and
synthetic data. No user database or credential was used.

## Review and release boundary

The network decision was recorded in design issue #3 before implementation.
Security-related regression details are kept private under `SECURITY.md`; the
review branch must not be pushed to a public PR before coordinated remediation.
The implementation is committed locally. Creating the private advisory/fork was
blocked by auto-review pending explicit authorization to upload the security
details. No advisory, private fork or Phase 2 PR has been created or uploaded.
No advisory publication, CVE request, private-reporting setting change, main
push, merge or package publication is authorized by this evidence.

There is no storage migration or package version bump. Core installation remains
Python-only with its existing cryptography dependency. Node and schema validation
tools remain development-only.

G2 covers search-backed read integration, not exhaustive enumeration, large-data
performance, cross-origin deployment or a complete operational dashboard.
Memory has no dependency on Desktop or Relay. G3 review revisions/replay, G4
onboarding and diagnostics, G5 provider recipes/starters and G6 release checks
remain separate work. The next roadmap slice is Phase 3, the zero-model developer
experience.
