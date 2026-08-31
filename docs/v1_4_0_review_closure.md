# 1.4.0 final-review corrections

Recorded 2026-08-30. All five findings from the review of `d051598` are corrected
on the isolated `codex/v1.4-final-release` branch. This record supersedes the
earlier claim that only release approval remained at that commit. Nothing has
been merged, disclosed publicly or published by this correction work.

## Findings and verification

| Finding | Correction | Regression evidence |
| --- | --- | --- |
| P1: quoted `~` database paths could migrate before backup/planning | Expand the database path before both the existence check and `Memory.open`; retain fresh-path and `:memory:` behavior. | Six combinations of absolute/tilde paths and backup/plan/apply; old schema, original evidence and encrypted archive contents checked. The actual published 1.3.1 binary reads storage after planning and restores the pre-upgrade archive for both spellings. |
| P2: review/starter cancellation could miss a deadline under GC | Attach the live signal directly to fetch, retain cancellation through body consumption and clean up timers/listeners. The packaged agent uses its tested `transport.ts` for every call. | Shared real-socket GET/POST tests stall headers and bodies, force GC and require the expected timeout/cancellation without retries. The actual installed agent must honor its default 10-second deadline; a 13-second fixture kill fails the test. |
| P2: explicit unsupported read profiles silently used legacy coercion | Only an absent header selects legacy behavior. Wrong, empty and unknown profiles return `409 unsupported_contract`; shared reads use `memory-read-v1` in all projections. | All eight read operations/aliases tested with four unsupported values. No usage record is written. Absent-header compatibility and canonical boolean validation remain covered. |
| P2: runtime database-busy responses were absent from schemas | Add 503 to all discovery/read responses and 409 to reads; regenerate all projections and the packaged starter declarations. | Real independent SQLite write/exclusive locks produce schema-conforming `503 database_busy`, including no-store/correlation headers. Failed usage writes roll back and succeed after lock release. |
| P2: migration discovery advertised an obsolete target | Report tested storage 1.3.0 → the authoritative current storage version (1.3.1), preserve legacy field types, and describe backup/recovery limits. | Actual HTTP/generated consumers assert metadata values. Old/current schemas have the tested path; untested older, unknown and newer markers are not advertised as safe. Authentic old-binary upgrade/recovery remains tested. |

The six new path tests first reproduced the three tilde failures before the
normalization change; all pass afterward. The cancellation regressions extend
the original GC-sensitive Linux reproductions rather than accepting any eventual
network error as success. Watchdog expiry is always failure.

`migration_support.safe` means the stored version has a tested upgrade/no-op
path **under the documented procedure**. It does not attest that the operator
has already stopped writers or retained a verified encrypted pre-upgrade backup.
There is no in-place downgrade; restoring the old archive omits subsequent
writes. See the [migration guide](v1_4_0_migration_guide.md).

## Gates

| Gate | Result |
| --- | --- |
| macOS ARM64, Python 3.13.13 | 283 tests passed; focused discovery/read/review run: 85 passed |
| Ubuntu 24.04 ARM64, Python 3.11.15 / 3.12.11 / 3.13.13 | 283 tests passed per interpreter from the source archive with wheel development requirements |
| Actual generated TypeScript HTTP consumers | Baseline, discovery, read, review and onboarding passed; no handwritten domain casts; packaged declarations match generation |
| Node 26.0.0 on macOS/Linux | 24 reference-client/polling tests passed, including 18 shared transport cases |
| Node 22.23.2 on Linux | The same 24 tests and installed agent checks passed; official runtime checksum verified |
| Fresh Linux wheel and sdist | Each passed 11 core-only checks and a separate 12-check TypeScript run, including the ten transport/CLI regressions |
| Fresh macOS wheel | Installed TypeScript run passed, including the actual agent deadline under GC |
| Real browser | Read and governed-review fixtures passed: scoped data/provenance, cancellation, privacy/revocation, stale decisions, replay, headers and no polling domain writes |
| Actual published 1.3.1 binary | Reverse SDK compatibility and absolute/tilde upgrade/recovery passed; old binary refuses upgraded storage |

The source commit, rebuilt wheel/sdist hashes and verification logs are bound in
the external delivery manifest. Final delivery checks use those artifacts, not
an editable install of the original checkout. The pre-fix artifacts and review
evidence remain historical and must not be substituted for the corrected build.

No runtime dependency, profile scope, storage version or Desktop/Relay dependency
was added. New tests use only disposable synthetic data and loopback services.
The existing protected branch rules and private advisory boundary remain intact.

## Remaining release controls

The five review findings are closed by the implementation and verification
above. Phase 7/G6 is still open: owner approval, public protected PR checks,
merge, coordinated disclosure, publication and public-artifact verification.
Local Linux execution does not replace required GitHub Actions, and the advisory
merge action must not bypass branch protection. See the
[release handoff](v1_4_0_release_handoff.md).

This was a review and correction by the implementing coding agent, not an
independent security audit. No fresh model-quality evaluation or first-time human
five-minute usability study is claimed; their previously documented limits remain.
