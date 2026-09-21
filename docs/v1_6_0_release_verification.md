# Memory 1.6.0 beta release verification

1.6.0 prepares the original 29 audit repairs and all nine independent follow-up
corrections for release. The reviewed audit baseline is commit `6a589c5`.
See [the follow-up findings](audit_followup_verification.md) and
[the beta upgrade guide](v1_6_0_upgrade.md) for behavior and compatibility.
The release remains beta: API v1, storage 1.3.1, Python 3.11+.

## Release changes

- Bump distribution metadata and the lockfile to 1.6.0; retain the Beta classifier.
- Require cryptography 50.0.1 and lock that version. This includes the fix for
  [GHSA-g6cj-pr64-35w5](https://github.com/pyca/cryptography/security/advisories/GHSA-g6cj-pr64-35w5).
- Update the compatible development dependency @redocly/openapi-core to 1.34.20,
  resolving js-yaml 4.3.2 and
  [GHSA-2883-xcg3-v3hh](https://github.com/nodeca/js-yaml/security/advisories/GHSA-2883-xcg3-v3hh).
- Regenerate the packaged TypeScript schema to expose policy selection and
  reflect context policy defaults from the actual service contract.
- Reuse the installed startup/recovery check for 1.6.0 against published 1.5.0.
  Its historical filename and original version defaults remain for reproducibility;
  CI passes the versions explicitly.
- Require the existing Release Gates workflow at the publishing commit before
  building distributions for either index. Check release-tag/version agreement
  and distribution metadata before upload. This uses GitHub's
  [same-commit reusable workflow behavior](https://docs.github.com/en/actions/how-tos/reuse-automations/reuse-workflows#calling-a-reusable-workflow).

## Local validation

Validation uses synthetic data and temporary environments on macOS arm64,
Python 3.13.13 and Node 26.0.0. No model service is used.

| Check | Result |
| --- | --- |
| Full repository regression suite | 768 passed with cryptography 50.0.1 |
| Python dependency audit | 28 locked runtime/development packages; no known vulnerabilities reported |
| npm dependency audit | Contract tooling and packaged starter: no known vulnerabilities reported |
| Generated contracts | Baseline, discovery, read, review, and onboarding clients pass against running services; TypeScript check/build pass |
| Transport and polling | All 24 cases pass |
| Older compatibility | SDK reads against published 1.3.1; actual 1.3.1 database migration and encrypted backup recovery pass |
| Wheel and source installation | Fresh core-only environments with cryptography 50.0.1; both dependency checks pass |
| Installed onboarding | Both distributions pass all 12 checks, including packaged documentation, embedded/HTTP examples and the compiled TypeScript starter |
| Installed upgrade and recovery | Both distributions pass all seven groups: actual 1.5.0 data preserved without migration, TLS pairing, restart/crash lifecycle, encrypted restore, identity loss/re-pairing/revocation, and opt-outs |
| Packaging | Wheel/sdist build and strict Twine checks pass; release metadata, required dependency, packaged guides/schema and absence of build caches verified |
| Repository and publication configuration | Generic-main boundary, changed documentation links, diff/syntax checks and matching/mismatched release-tag checks pass |

Reproduce installed startup and recovery once per distribution:

```bash
python scripts/v1_5_install_recovery_check.py \
  --python /fresh/venv/bin/python \
  --previous-python /published-1.5.0/venv/bin/python \
  --expected-version 1.6.0 --previous-version 1.5.0
```

Run `scripts/v1_4_onboarding_check.py --python /fresh/venv/bin/python --typescript`
for packaged documentation, Python examples, and the compiled TypeScript starter.
The workers run outside the checkout and assert imports come from site-packages.
Dependency audit results describe the advisory databases at validation time,
not a guarantee about undiscovered defects.

## Publication and follow-up

Release preparation does not publish packages. The release PR must pass the
Linux Python 3.11–3.13 matrix and all installed/contract jobs before integration.
After an approved merge, publish the `v1.6.0` GitHub release as a beta/prerelease
at the verified commit. The PyPI workflow runs the release gates again before
uploading. Verify the public wheel/sdist, hashes, installed version and a fresh
onboarding run after publication.

Existing beta installations can start with disposable data or follow the
data-preserving upgrade guide. Historical key exposure or recipient copies
require attention only where the affected features and real data were used;
they are not declared resolved by these tests. A general historical-recovery
scanner, real-model/load qualification and production deployment certification
are deferred beyond this beta's release scope.
