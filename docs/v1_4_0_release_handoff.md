# 1.4.0 release handoff (approval pending)

The current artifact is **1.4.0**, built locally and not published. Storage is
1.3.1; HTTP major is v1. Memory owns all required schemas, fixtures, installation
and runtime paths. Desktop and Relay are optional downstream consumers and do
not gate this release.

Final pre-publication checks are recorded in [final verification](v1_4_0_final_verification.md).
The subsequent five findings and their verified corrections are recorded in
[final-review corrections](v1_4_0_review_closure.md), which supersedes the earlier
readiness claim and identifies the expanded gates for the corrected build.
The later baseline review and reconciled corrections are recorded in the
[external audit closure](v1_4_0_external_audit_closure.md). The subsequent
[final independent re-review](v1_4_0_rereview_closure.md) and its 311-test gate
are authoritative for the current branch.
This document prepares Phase 7. It does not authorize merging, advisory
publication, GitHub release creation, TestPyPI/PyPI uploads or branch-rule changes.
The owner asked to review approvals only after implementation and verification.

## Supported contract surface

| Consumer | Intended behavior |
| --- | --- |
| Published 1.3.1 Python SDK → candidate service | Legacy version-equality bridge and existing supported workflows; no invented revision guarantees |
| New SDK → published 1.3.1 service | Legacy reads/context continue; principal/profile requirements report explicit absence |
| Generated TypeScript → candidate service | Discovery, reads, candidate-first creation, separate governed review, context and provenance |
| `memory-read-v1` | Scoped search/overview/context, claim detail/explanation/audit; no exhaustive evidence browser |
| `memory-review-v1` | Candidate keyset pagination, inspect, promote/reject, atomic revision/key/replay/audit handling |
| `agent-onboarding-v1` | Typed, atomic, explicitly keyed candidate creation with scoped authority; operator review is separate |
| Embedded Python / CLI / HTTP / MCP | Existing standalone surfaces remain available; embedded trusted active-write semantics are unchanged |

See the [read](v1_4_0_read_contract.md), [review](v1_4_0_review_contract.md),
[agent](v1_4_0_agent_onboarding_contract.md), and
[migration/backup](v1_4_0_migration_guide.md) contracts. Phases 0–5 evidence is in
the [documentation index](index.md). The Phase 0 inventory and baseline fixtures
are historical scope inputs, not live supported-profile discovery.

## Review order and disclosure boundary

Public planning/discovery PRs and private implementation PRs remain unmerged.
The implementation is in the private security advisory fork. Keep private
branches and patch details private until the owner approves
coordinated disclosure and the protected release path below. Private PRs are cumulative
against `codex/v1.4-discovery`; review the phase-specific ranges recorded below.

| Slice | Branch | Review starting commit |
| --- | --- | --- |
| Phase 2 read contract | `codex/v1.4-read-contract` | `860ab144fc6f520dc15f53d9a06837ff844588fc` |
| Phase 3 onboarding | `codex/v1.4-onboarding` | `3817e9a683d2a83154483ef9834ba131c50f8f23` |
| Phase 4 governed review | `codex/v1.4-review-contract` | `b4ca771ced2ee05b3151c5b1f7a2602b9d98acd3` |
| Phase 5 providers/examples | `codex/v1.4-providers-and-examples` | `0c48452e93f02c614ab1aef04e6829cc50bfa9ee` |
| Phase 6 candidate integration | `codex/v1.4-release-candidate` | `6bba7f83697aa7ab67a97f2c6d9e2afc6616fae9` |
| Final release preparation | `codex/v1.4-final-release` | `1a68eed4687054d927bf44d12493c913fcd467a4` |
| Final-review corrections | `codex/v1.4-final-release` | `d0515980de763d554ad08d9ca1e657ddf1224951` |
| External-audit corrections | `codex/v1.4-final-release` | `e8b0c5897d85b2a35debc94a5a7edf3942623865` |

GitHub security forks do not execute Actions. GitHub also documents that its
advisory merge action does not enforce branch protection. Do not use that action
as a substitute for this repository's required status checks. See
[GitHub's advisory-fork guidance](https://docs.github.com/en/code-security/tutorials/fix-reported-vulnerabilities/collaborate-in-a-fork).

The active **Protect main** ruleset (21462001) requires a PR, an up-to-date
branch, resolved review threads, and Actions checks `baseline-boundary`,
`tests (3.11)`, `tests (3.12)`, `tests (3.13)`, and `build`. It blocks deletion and
non-fast-forward updates. Legacy branch-protection API output alone does not
represent this ruleset. No protection setting was changed for this release.

## Completed final preparation

Final 1.4.0 metadata/docs and corrected artifacts are prepared. The latest
macOS gate passes 311 regressions; the prior Linux Python 3.11–3.13 gate passed
283 tests per interpreter before the external-audit corrections and must be
rerun by protected CI. All generated HTTP clients,
24 Node lifecycle/transport checks, actual browser reads/reviews, old-binary
upgrade/recovery for absolute/tilde paths, and installed wheel/sdist examples
pass. The starter also passes ten cancellation/CLI checks on Node 26 and 22.
All final-review and reconciled external-audit findings are corrected, with
regression evidence above. A cold-install
and explicit-review walkthrough is measured, with its agent-run/human-usability
limits documented. Source/code review was performed by the implementing agent;
it is not an independent security audit. The five-minute human target remains
unverified by a first-time human participant.

## Remaining steps before calling 1.4.0 shipped

1. Obtain the owner's approval for the final private PR and the combined public
   PR/disclosure, protected merge and 1.4.0 publication operation. The patch
   becomes public when the ordinary PR is opened, before package publication;
   coordinate those steps in one release window. No independent human review or
   blanket security certification is claimed by the automated evidence.
2. After that approval, push only the reviewed final implementation branch to
   the public repository and open an ordinary PR against `main`. Run the real
   GitHub Actions matrix. Require **all** release jobs, including the generated
   contract and packaged TypeScript jobs, to pass on the final reviewed head.
   Resolve any failures and rerun the relevant gates; never fabricate statuses,
   weaken rules or use an administrative bypass.
3. Merge through the normal protected PR workflow only after the exact head is
   verified. Do not push to main directly, enable automatic merging, or merge
   each cumulative private PR. Mark the earlier PRs superseded as appropriate.
4. Create the reviewed `v1.4.0` tag/release at the merged commit and use the
   existing Trusted Publishing workflow. Publishing a GitHub release triggers
   the PyPI workflow. TestPyPI is also publication and is not an approval bypass.
   Do not publish an npm package or create a duplicate package upload.
5. Verify the public package in fresh environments: version and hashes,
   packaged docs/starters, core-only lifecycle and all declared profiles. Confirm
   the source tag and distribution correspond to the reviewed commit.
6. Finish coordinated advisory disclosure with the verified patched version and
   scoped impact. Do not automatically request a CVE or broaden the affected
   version range without evidence. Retain the existing credential/scope limits
   in the impact statement. Mark Phase 7/G6 complete only after publication and
   public artifact verification; communicate the client-neutral integration
   notes above. Stop disposable verification services/VMs when finished.

## Deferred capabilities and practical limits

SSE, Relay/federation consumer profiles, hosted model recipes, exhaustive evidence
browsing, broad administrative typing, and Desktop UI/integration work are not
advertised by these profiles. Revision safety does not retroactively certify
unnegotiated legacy mutations. Read/write behavior outside selected profiles
retains its existing public compatibility surface.

Local model evidence covers a small synthetic smoke set on the recorded hardware,
not production accuracy. Models can produce invalid or incorrect candidates;
review and privacy rules stay in place. The chosen runtime must be trusted.
Schema upgrades require pre-upgrade backup; old binaries refuse new storage and
cannot perform an in-place downgrade. Restore from the preserved old backup to
recover an old-compatible database, with its corresponding data-loss window.
