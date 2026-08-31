# Phase 6: 1.4.0rc1 integration evidence

Recorded 2026-08-30, America/Chicago. Candidate software version: **1.4.0rc1**;
storage version: **1.3.1**; API major: **v1**. This follows Phase 5 commit
`6bba7f83697aa7ab67a97f2c6d9e2afc6616fae9` on
`codex/v1.4-release-candidate`. The wheel and source distribution are local,
unpublished artifacts. No tag, public release or approval is implied.

## Verification matrix

| Gate | Result and evidence |
| --- | --- |
| Source-distribution regression, Python 3.11.15 | 269 passed, fresh artifact environment; approximately 68 seconds |
| Source-distribution regression, Python 3.12.11 | 269 passed; approximately 72 seconds |
| Source-distribution regression, Python 3.13.13 | 269 passed; approximately 68 seconds |
| Actual generated TypeScript | All five consumers pass: baseline, discovery, read, review, onboarding; all current projections regenerated/validated from RC HTTP; bundled starter schema matches |
| Node transport lifecycle | Five tests pass: non-overlap, obsolete result suppression, bounded retry, stalled-body timeout, changed authorization |
| Real browser reads | PASS: authenticated same-origin generated reads/provenance, cache/correlation headers, privacy changes, revocation, cancellation, reconnect and no domain writes from polling |
| Real browser review | PASS: opaque revisions, explicit rejection, stale approval refusal, new decision, promotion, replay and revocation; no automatic resubmission |
| Published SDK → new service | Frozen/hash-checked published 1.3.1 client passes legacy version bridge and supported workflows in the suite/harness |
| New SDK → published service | Separate subprocess loads actual published 1.3.1 modules; legacy lexical reads/context pass and missing principal/review profiles are explicit |
| Real old database upgrade/recovery | Actual published binary seeds the database; atomic upgrade preserves claims, evidence, candidates, permissions and retrieval; old binary refuses new storage; encrypted pre-upgrade backup restores using old binary |
| Installed wheel, core-only | 11 Python onboarding checks pass, plus a separate 11-check run including installed TypeScript compilation/execution |
| Installed source distribution, core-only | Same Python and TypeScript checks pass outside the checkout |
| Published primary example compatibility | Exact RC embedded tutorial also runs with installed public 1.3.1: explicit review, context, provenance, restart |
| Optional models from installed RC wheel | [Separate live report](../contracts/v1.4.0/evidence/local-model-smoke-rc1.json): embedding and LLM checks pass; 16.329 seconds, no downloads, three pending candidates, zero active claims |
| Distribution/boundary | Wheel/sdist metadata and bundled files inspected; no node_modules, compiled JavaScript, database, bytecode or Desktop runtime dependency; generic release boundary and whitespace checks pass |

Local runtime: macOS 26.5.1 ARM64, Apple M4 Max, 48 GiB unified memory. Node
26.0.0, TypeScript 5.9.3, openapi-typescript 7.13.0, openapi-fetch 0.17.0.
Fresh Python environments used cryptography 50.0.1. Artifact dependency installs
used the local cache. Automated installed examples took approximately 3.4 seconds
for Python and 8.7 seconds including cached npm setup/compilation for TypeScript.
These numbers exclude download time and human review/thinking time.

## Standalone and artifact proof

Only Memory's source archive is extracted into each regression working directory.
Tests and installed examples use disposable Memory-owned databases and generic
Python/TypeScript/browser clients. No Desktop repository, React application,
native shell, Desktop state, Relay or external account is installed or invoked.
The installed-example worker uses isolated Python mode, verifies its import path
is in site-packages, verifies packaged docs/source match, and asserts core-only
installation. The embedded tutorial runs with network connections blocked.
Agent demos use only their authenticated loopback fixture and explicit review;
credentials are scoped, expire and are revoked on shutdown. Approval, decline,
empty recall, persistence, provenance and no-overwrite paths are exercised.

The final artifact filenames are `aletheia_memory-1.4.0rc1-py3-none-any.whl` and
`aletheia_memory-1.4.0rc1.tar.gz`. Local delivery includes an external
`SHA256SUMS` manifest so artifact hashes do not create a circular embedded hash.
Rebuilds with evidence/documentation changes are rechecked before handoff.

CI now runs the full Python matrix from built source archives and includes
separate installed wheel/sdist examples and the generated TypeScript matrix.
Model use remains a separate manual, explicitly configured workflow.

## Reproduce and release boundaries

Build with `python -m build`. Install each artifact into a fresh core-only venv,
then execute:

```sh
python scripts/v1_4_onboarding_check.py --python /fresh/wheel/bin/python
python scripts/v1_4_onboarding_check.py --python /fresh/sdist/bin/python --typescript
python scripts/v1_4_compatibility_check.py --legacy-package /published/1.3.1
python -m scripts.v1_4_migration_check --legacy-package /published/1.3.1
```

The legacy package must be the actual, unchanged published modules matching
recorded hashes. For each Python version, install the wheel with dev extras,
extract the sdist into a new directory and run `python -m pytest` from that
archive root. Follow the [toolchain guide](../contracts/typescript/README.md)
for generation and browser fixtures. Model smoke is explicitly optional; its
prerequisites, license/data implications and limitations are in the
[recipe guide](v1_4_0_local_model_recipes.md).

**Historical status at the RC checkpoint** (superseded for final preparation by
[final verification](v1_4_0_final_verification.md) and the current handoff): independent required CI including Linux (security forks do not
run Actions, and this host has no Docker/Podman/Colima runtime); human five-minute
onboarding/cold-install timing; final code/security review; owner approval;
protected-branch/advisory merge and disclosure; final 1.4.0 version-only rebuild;
authorized publication and verification of the public artifact. Local macOS
results must not be reported as Linux CI. Phase 7 and G6 remain incomplete until
these release requirements are met. See the [handoff](v1_4_0_release_handoff.md).
