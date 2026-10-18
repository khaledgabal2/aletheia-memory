# Aletheia Memory 1.8.0 release verification

## Scope

The release includes PR #72 (implementation and seven review fixes), merged as
`a59869164403771b407f961f65981616458cf255`. Its 16 checks passed, including the
nine native Linux/macOS/Windows × Python 3.11/3.12/3.13 jobs, installed recovery,
contract tooling and packaged TypeScript starter checks.

Release preparation checks cover the final versioned source, complete local
Python suite, generic baseline gate, wheel/source metadata and embedded README,
and installed onboarding/recovery. The release PR and publication workflow run
the full native matrix again against the release source. A release is tagged only
after the required release PR checks pass. Publication verifies its tag against
the package version and reruns release gates before uploading distributions.

Publication-only verification (PyPI description, hashes and fresh pinned install)
is recorded in the GitHub release notes and attached receipts. The
[1.7.0 qualification](v1_7_0_release_verification.md) remains historical evidence;
its live-model and soak measurements are not claimed as newly run for 1.8.0.
