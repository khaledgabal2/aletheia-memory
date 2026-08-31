# 1.4.0 final pre-publication verification

**Superseded for release readiness:** the final review found five defects at
`d051598` despite the successful checks recorded below. Their corrections and
expanded 283-test, client, installed-artifact and browser verification are in
[final-review corrections](v1_4_0_review_closure.md). The older counts and timings
below remain historical evidence, not verification of the corrected artifacts.

Recorded 2026-08-30, America/Chicago. Software **1.4.0**, storage **1.3.1**,
HTTP major **v1**. This final preparation follows RC commit
`1a68eed4687054d927bf44d12493c913fcd467a4` on the isolated
`codex/v1.4-final-release` branch. Artifacts remain local and unpublished;
Phase 7/G6 still require owner approval, protected-branch CI/merge, publication,
and verification of the public package.

## Final changes and review

- Set final 1.4.0 metadata and service-starter minimum versions; reconcile the
  installation, discovery, read-profile, example and release documentation.
- Linux verification exposed a stalled-body cancellation failure in the
  generated read consumer when it constructed an extra `Request` around the
  fetch input. Passing headers, cache policy and the abort signal directly to
  `fetch(request, init)` preserves cancellation through body consumption.
- Strengthen the real-socket tests: wait for partial response data, require the
  expected deadline/caller-cancellation error, bound fixture lifetime and close
  the listener before destroying remaining connections. Both cancellation paths
  now pass on Linux and macOS; the real-browser read fixture also passes.
- Recheck the selected authority boundaries: authentication inside the review
  write transaction, current access before replay, revision comparison before
  mutation, candidate-only negotiated agent creation, conservative revision
  invalidation, and explicit backup recovery. Existing adversarial regressions
  remain intact. This is an implementation review by the same coding agent,
  not an independent security audit or a maintainer approval.

The final preparation does not widen a profile, add a runtime dependency, or
change the storage migration from the verified RC. Desktop and Relay remain
absent from all required installation and verification paths.

## Verification results

| Gate | Result |
| --- | --- |
| Ubuntu 24.04 ARM64, Python 3.11.15 | 269 regression tests passed from the source archive |
| Ubuntu 24.04 ARM64, Python 3.12.11 | 269 regression tests passed from the source archive |
| Ubuntu 24.04 ARM64, Python 3.13.13 | 269 regression tests passed from the source archive |
| macOS ARM64, Python 3.13.13 | 269 regression tests passed |
| Generated TypeScript against actual Linux HTTP | Baseline, discovery, read, review and agent consumers passed; generated starter schema matches the packaged schema |
| Node 26.0.0 on Linux and macOS | Six lifecycle checks passed, including stalled-body deadline and caller cancellation |
| Real browser, corrected read consumer | Authentication/provenance, response headers, privacy changes, revocation, cancellation, reconnect and absence of polling domain writes passed |
| Published-version compatibility | New SDK against the actual published 1.3.1 service passed; frozen published SDK against the new service remains covered by the regression/client matrix |
| Upgrade/recovery | Actual published binary creates the old database; new binary preserves data/provenance/permissions; old binary refuses upgraded storage and restores the encrypted pre-upgrade backup |
| Installed wheel and source archive on Linux | Each passes 11 core-only Python checks and a separate 11-check run including installed TypeScript examples |
| Package boundary | Final metadata, bundled docs/starters, model-free lifecycle and generic baseline checked; no Node dependency, user database or Desktop runtime is packaged |

The earlier RC's Python 3.11–3.13 macOS, review-browser and optional live-model
results are retained in [Phase 6 evidence](v1_4_0_phase6_evidence.md). The final
version does not relabel those historical results as a new model evaluation.

## Confidential Linux environment

The Linux run used a disposable local Lima 2.2.0 Apple Virtualization VM with
4 CPUs, 4 GiB RAM and a 16 GiB sparse disk, Ubuntu 24.04.4 LTS / kernel
6.8.0-134-generic on ARM64. The official portable Lima archive and Ubuntu image
were SHA-256 verified. The VM had no host directory mounts, no forwarded SSH
agent, no host credentials, and no Desktop checkout. Only Memory artifacts and
verification scripts were copied into it. Node 26.0.0 was verified against its
official checksum; Python environments used uv and cryptography 50.0.1.

This is real Linux execution but **not GitHub Actions, not x86-64 coverage, and
not an independent reviewer**. It does not satisfy or replace required GitHub
status checks. Security advisory forks cannot run Actions.

To reproduce the gate contents, use the commands in
[the TypeScript toolchain guide](../contracts/typescript/README.md) and
[Phase 6](v1_4_0_phase6_evidence.md), or the ordinary
[release-gates workflow](../.github/workflows/release-gates.yml). Run the Python
matrix from an extracted source archive with installed wheel development
requirements. Run core-only examples in separate installed wheel/sdist venvs.
All databases and credentials used by these checks are synthetic and disposable.

## Cold-install and explicit review walkthrough

A fresh Python environment installed the local final-version wheel with pip's
cache disabled and public dependency downloads. Environment creation took
1.701 seconds; installation took 1.510 seconds. The coding agent generated the
embedded starter, ran the documented flow, inspected the pending candidate and
its source with zero trusted results before approval, explicitly typed
`approve`, verified context/provenance/reopen, and ran read-only diagnostics.
Elapsed time through that sequence was 73.249 seconds, including unrelated VM
coordination. No model or external Memory service was used.

This is a measured **agent-run** walkthrough, not a first-time human usability
study. It does not prove every developer can install and understand the workflow
in five minutes, and it used a reviewed local wheel rather than a public 1.4.0
download. The approximate five-minute target remains a human usability target;
its limits must remain visible in release review.

## Artifact identity and remaining approval

The final artifacts are `aletheia_memory-1.4.0-py3-none-any.whl` and
`aletheia_memory-1.4.0.tar.gz`. An external `SHA256SUMS` and review manifest bind
the delivery to its source commit; hashes are intentionally not embedded in the
artifacts they identify. Rebuilds are followed by artifact checks before handoff.

See the [release handoff](v1_4_0_release_handoff.md) for the exact remaining
protected CI, merge, coordinated disclosure and publication steps. Neither a
successful local test nor final version metadata authorizes those actions.
