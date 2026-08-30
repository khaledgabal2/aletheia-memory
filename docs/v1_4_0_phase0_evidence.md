# 1.4.0 Phase 0 verification evidence

Recorded 2026-08-30 in an isolated Memory worktree. Production baseline:
`1cb3e607450b2d0d345cc3c06d73223b7f3e3fe4`. Source-of-truth plan:
[`v1_4_0_contract_hardening_and_developer_experience_plan.md`](v1_4_0_contract_hardening_and_developer_experience_plan.md).
Review choices and unresolved gates in [the decision record](v1_4_0_phase0_decisions.md).

## Checks performed

| Check | Result | Limits |
| --- | --- | --- |
| Unchanged baseline Python suite | 141 passed in 15.29 seconds on Python 3.13.13. | Local macOS run; the existing CI matrix separately covers Python 3.11–3.13. |
| Baseline boundary script | `python scripts/release_gate.py --branch main` passed. | Does not approve publishing or modify branch protections. |
| Full suite with Phase 0 checks | 145 passed in 10.68 seconds. | Includes authentic legacy SDK over HTTP and model-free lifecycle with outbound connections blocked. |
| Actual HTTP baseline capture | 26 synthetic response cases; selected OpenAPI paths extracted from the envelope. | Captures current shortcomings; does not certify new profiles. |
| Published SDK provenance | Unmodified 1.3.1 client matches baseline repository bytes; SHA-256 recorded. | Reverse new-SDK → old-service matrix belongs to G1/G6. |
| TypeScript toolchain | Generator 7.13.0, openapi-fetch 0.17.0, TypeScript 5.9.3; generated, checked and compiled on Node 26.0.0. | Old schema still has unknown domain payloads and missing parameters; G2 remains open. |
| Generated consumer runtime | Authenticated version discovery and empty lexical retrieval passed against a real temporary Memory service. | Node HTTP test, not real-browser proof. |
| Packaging | Built source distribution and wheel; inspected contents; 145 tests also pass from the extracted sdist (10.98 seconds). | Version remains 1.3.1 for this development baseline; no artifact was published. |
| Clean wheel installation | Installed into a new environment outside the checkout; imported Memory from site-packages using Python isolated mode. | A local wheel test, not public-index verification of a future 1.4.0 release. |
| Installed model-free lifecycle | Candidate pending → explicit fixture approval → lexical result/context/provenance → reopen succeeded with network connections blocked. | Automated lifecycle only, not human onboarding timing. |

The first sandboxed baseline run had 140 passes and one failure because the
sandbox denied socket binding. Re-running with loopback access produced the
141-pass baseline above. No failing test was removed or skipped. Archive inspection caught local Node
dependencies entering the sdist; explicit exclusions now remove node_modules,
generated output and Python caches while preserving the contract fixtures.
Dependency
installation uses explicit network access; the core lifecycle does not.

The generator's declared peer range rejected TypeScript 7.0.2. The toolchain was
corrected to supported TypeScript 5.9.3, then installed and tested without force
or legacy-peer-dependency overrides. A lockfile preserves the resolved graph.

## Captured artifacts

- [Profile operation inventory](../contracts/v1.4.0/profiles.json): 17 unique
  operations across three proposed profiles, including one new principal route.
- [Capture summary](../tests/fixtures/v1_3_1/summary.json): full baseline counts,
  full-schema digest, observed runtime and lifecycle timing.
- [Historical OpenAPI subset](../tests/fixtures/v1_3_1/openapi.json): selected
  existing paths with the original envelope schemas.
- [Synthetic HTTP responses](../tests/fixtures/v1_3_1/responses.json): success,
  replay and 400/401/403/404/409 errors. Detailed security reproductions remain
  private outside the repository, following SECURITY.md.
- [Published client provenance](../tests/fixtures/v1_3_1/provenance.json):
  distribution version, source, SDK hash and runtime hashes for safe recapture.
- [Executable harness](../scripts/v1_4_phase0.py) and
  [baseline tests](../tests/test_v1_4_phase0.py).

These repository/development resources are in the source distribution; Node
tooling and historical test clients are not part of the Python wheel runtime.

## Measured first-run prototype

Input: `User prefers careful architecture notes.` Query: `architecture`.
Existing rule-based extraction created one pending candidate, and trusted
retrieval returned no result before approval. The explicitly supplied automated
review created a claim; retrieval/context included it with evidence preserved
across database reopen.

The capture's automated lifecycle took 0.040 seconds, and the clean installed
wheel run took 0.038 seconds. These measurements exclude installation, reading,
typing and human inspection/review. Cached offline wheel installation reported
5 ms resolution, 15 ms preparation and 3 ms installation; these are tool phase
timings, not an end-to-end installation or network benchmark. The five-minute
human target remains unvalidated until G4's actual tutorial walkthrough.

No embeddings, LLM, model download, account, configured provider, Desktop code,
or Relay service was needed. The harness opens only temporary demo databases,
and its service fixture binds `127.0.0.1` on an ephemeral port. Test tokens are
ephemeral and never saved in the fixtures or source files.

## Reproduction

From the isolated checkout, using its own virtual environment:

```sh
python -m pip install -e ".[dev]"
python -m pytest
python scripts/release_gate.py --branch main
python scripts/v1_4_phase0.py --output /tmp/new-phase0-evidence
npm ci --prefix contracts/typescript --ignore-scripts --no-audit --no-fund
npm run generate --prefix contracts/typescript
npm run check --prefix contracts/typescript
npm run build --prefix contracts/typescript
python scripts/v1_4_phase0.py --typescript
```

The capture command requires unmodified published 1.3.1 runtime module hashes
and a new output directory. After runtime implementation changes, use the
Phase 0 commit or an isolated installed 1.3.1 runtime to recapture it; never
replace the historical fixtures with new-service outputs.

Build using the repository's existing `python -m build` workflow (or `uv build`).
For clean-install lifecycle verification, install the wheel into a fresh venv,
copy only `scripts/v1_4_phase0.py` as the test driver outside the repository,
load that driver using `importlib.util.spec_from_file_location`, and call
`lifecycle()` with a temporary database path. Run Python with `-I`, assert the
imported `aletheia.__file__` lives in site-packages, and replace
`socket.socket.connect` with a function that raises before calling the lifecycle.
The copied driver is a test harness, not a new public package API.

## What is not passed

The maintainer accepted G0 on 2026-08-30 in the project conversation. G1–G6
are not certified by these checks. In particular, typed domain schemas,
principal discovery, privacy/permission corrections, browser topology, atomic
revisions/replay, reverse compatibility, migration/restore behavior, the human
tutorial and live local-model recipes remain roadmap work. No service profile
flag, production API, database migration or package version was changed here.
