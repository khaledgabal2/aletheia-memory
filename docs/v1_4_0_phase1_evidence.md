# 1.4.0 Phase 1 verification

Prepared 2026-08-30 against `codex/v1.4-discovery`, based on the accepted Phase 0
branch. The [release plan](v1_4_0_contract_hardening_and_developer_experience_plan.md)
remains authoritative. This records discovery evidence, not release approval.

## G1 scope

The [discovery contract](v1_4_0_discovery_contract.md) implements software/API/schema
separation, the published 1.3.1 SDK bridge, current-principal metadata, six typed
discovery operations and generated-client execution. No read/review/onboarding
profile is advertised yet. There is no database migration, new review behavior,
Desktop dependency, package version bump or publication in this phase.

D1–D8 were accepted in the project conversation. The Phase 0 record now explains
them in plain language. D2's legacy alias retains the engine's expected schema
value, preserving the old SDK's rejection of incompatible storage as well as
its acceptance of compatible storage.

## Verification results

Local environment: Python 3.13.13, Node 26.0.0; the generator and TypeScript
versions remain pinned by the Phase 0 lockfile.

| Check | Evidence |
| --- | --- |
| Python regression suite | 166 tests pass, including 21 discovery cases. |
| Canonical software version | Build metadata and source fallback tested, including synthetic 1.4.0 and future releases with unchanged storage. Health, version, compatibility, OpenAPI and diagnostics agree. |
| Authentic old client → new service | Byte-identical published 1.3.1 SDK executes compatibility, candidate creation/replay, explicit review, retrieval/context, explanation and audit against a running service. It still rejects mismatched storage. |
| New client → authentic old service | Independently installed 1.3.1 service runs in a separate process with module hashes verified. Legacy reads/context work; missing principal discovery and required profiles are explicit. |
| Principal boundaries | Scoped caller needs no read/admin capability to inspect itself. Invalid, expired, revoked and disabled-client credentials fail. Other-principal selection, credential serialization and admin scope widening are rejected. Changed grants are reflected immediately. |
| Local/console behavior | Explicit local tokenless scope, supplied-credential validation, fail-closed protected state, console header/cookie authentication, legacy session shape, CSRF enforcement and logout regression checks pass. |
| Actual HTTP schemas | OpenAPI 3.1 validation passes for the six-operation projection; real responses validate against published schemas, including populated plugin/SDK/matrix arrays, nullable runtime fields, authentication errors and rate limiting. |
| Generated TypeScript | Generated domain fields compile without casts and execute against a real authenticated service. Baseline consumer continues to pass. |
| Packaging | Wheel and sdist build; discovery modules, docs and source harness files are present. Node dependencies, generated TypeScript output, Python caches and tests are excluded from the wheel. Core install does not require schema validators or Node. |
| Installed tutorial | Exact packaged Python block runs outside the source checkout with network connections blocked, for both approval and refusal. Provenance/reopen checks pass, and repeated runs preserve the existing database. |
| Repository safety | Generic release-boundary and diff-whitespace checks pass. Original checkout remains unchanged; work is isolated from it and from main. |

CI runs Python 3.11–3.13, package builds, the generic baseline boundary, and both
directions of client compatibility plus generated consumers. The PR's checks
are the authoritative CI result and must pass before any merge. Local evidence
alone does not substitute for that matrix.

Reproduce the Python checks with `python -m pytest`. The exact generation and
real-service commands are in
[`contracts/typescript/README.md`](../contracts/typescript/README.md).
Schema validation libraries are development dependencies only.

## Onboarding and remaining gates

The [tutorial draft](v1_4_0_quickstart_draft.md) uses existing public APIs and waits
for explicit approval after showing the candidate and source. The scoped-helper
decision remains D7: no new helper unless a real walkthrough demonstrates the
need. The HTTP agent starter will use candidate-first calls and separate operator
credentials, as already specified in that decision.

Automated tutorial execution does not establish the five-minute human target.
Safe initialization, diagnostics, starters and measured human onboarding remain
G4 work. Full read authorization/redaction, browser transport and polling remain
G2; durable review revisions and atomic replay remain G3. Optional provider
recipes and release verification remain G5/G6.

The 1.4.0 work continues through PRs. G0 acceptance and G1 evidence authorize no
merge, direct push to main, deployment, publication or branch-protection change.
