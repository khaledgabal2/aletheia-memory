# Memory 1.5.0 release verification

Memory 1.5.0 adds automatic local registration and explicit, scoped pairing to
the 1.4.1 baseline. Storage remains 1.3.1; no storage code, migration, or locked
dependency version changes. The release is independent of Desktop packaging.

## Source and correction

The release branch retains both original commits from
`codex/local-registration-pairing`: implementation `a3f0863` and pairing path
normalization `1d6fe1d`, based on released 1.4.1 (`5e0c92b`).

Installed-artifact validation reproduced an additional startup failure:
`aletheia serve --db '~/…/existing.db'` reported a missing database unless
`--auto-migrate` was supplied. Commit `12a80c2` expands the path during the
service schema precheck, matching storage and pairing behavior. Its regression
also checks that a missing path is refused without creating a database.
Release preparation updates metadata to 1.5.0 and adds the repeatable installed
recovery gate to the required CI build job.

The generated-contract CI gate also identified a stale packaged TypeScript
schema. Regenerating it adds the new pairing model definitions to the bundled
component types; existing endpoint types are unchanged.

## Local evidence

Validated on macOS 26.6.2 arm64 with Python 3.13.13 using synthetic data and
disposable service, discovery, identity, and installation directories.

| Gate | Evidence |
| --- | --- |
| Full suite | 330 tests, including 17 pairing cases and the additional startup regression |
| Wheel installation | Fresh core-only environment; cryptography 49.0.0 (declared minimum); dependency check passes |
| Source installation | Fresh core-only environment; cryptography 50.0.1 (resolver selection); dependency check passes |
| Existing-data baseline | Actual published 1.4.1 in a separate environment, creating claims, evidence, and candidates |
| Installed onboarding | Both distributions pass packaged documentation/embedded and HTTP starter flows: explicit approval, decline, persistence, safe rerun, and read-only diagnosis |
| Generated TypeScript | Baseline, discovery, reads, review, and onboarding consumers pass against actual services; type-check/build and 24 transport/polling checks pass on Node 26.0.0 |
| CLI and startup | Installed console script, packaged pairing help, fresh initialization, service readiness, and quoted home-relative paths without automatic migration |
| Pairing | Exact owner grants, one-use completion, authenticated access over verified TLS, and plaintext rejection |
| Running lifecycle | Actual 10-second lease renewal, SIGTERM removal, restart with the same certificate and credential, and rejection of unused codes from the old instance |
| Crash recovery | SIGKILL, preserved data and certificate on restart, actual expiry of the 30-second crash hint, and preservation of another running service's registration |
| Backup recovery | Encrypted backup creation/verification, restore dry-run leaves the target absent, applied restore with matching claims/evidence/candidates, and fresh pairing required for the restored file |
| Identity recovery | Identity-directory loss rejects old credentials; fresh pairing and self-revocation work |
| Downgrade | Owner revocation of paired credentials followed by 1.4.1 reopening the data without storage changes |
| Opt-outs | Service starts with advertising and pairing both disabled |
| Packaging | Wheel and source archive build; Twine metadata/description checks, README release boundary, and documentation file links pass |

Cryptography 50.0.1 in a disposable clean installation is not a lockfile upgrade.
All tracked dependency versions match 1.4.1. The full OpenAPI document contains
205 paths. Its canonical JSON SHA-256 is
`c2feda20a3baf2aa3ea9bb7ddb1cf795b88718d599bf5e151cf4e517628dff5b`
using sorted keys and compact separators. Software-version metadata changes from
the development build; the five pairing operations and principal contract are
unchanged.

Reproduce installation recovery with:

```bash
python scripts/v1_5_install_recovery_check.py --python /fresh/venv/bin/python --previous-python /1.4.1/venv/bin/python
```

Run once per distribution. The worker verifies imports come from site-packages,
runs outside the checkout, and prints no codes or bearers. The existing
`scripts/v1_4_onboarding_check.py` separately validates packaged examples and
keeps discovery/identity files in its disposable directory.

## Protected publication gates

The ordinary PR must pass all Release Gates jobs, including Python 3.11–3.13,
the installed wheel/source recovery checks, generated consumer contracts, and
packaged TypeScript starters. Merge without bypassing branch rules, then create
the `v1.5.0` GitHub release at the verified merge commit. The existing Trusted
Publishing workflow publishes to PyPI. Verify public distributions, hashes,
version, and clean installed behavior after publication.

## Recovery and supported scope

See [local pairing recovery](local_pairing_v1.md#recovery-and-downgrade). Revoke
paired credentials before downgrading to 1.4.1, which lacks their TLS restriction.
Restoring or relocating a database, or losing identity files, requires fresh
pairing. Crash registrations expire but are not automatically pruned.

Local registration/pairing supports POSIX loopback services. Windows ACL support,
LAN/remote pairing, automatic stale-record pruning, signed Desktop distribution,
and Desktop browsing/review screens remain outside this release. Automated
validation is not an independent security audit or a clean-machine Desktop
packaging certification.
