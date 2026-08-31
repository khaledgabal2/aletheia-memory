# 1.4.0 release handoff (approval pending)

The current artifact is **1.4.0rc1**, built locally and not published. Storage is
1.3.1; HTTP major is v1. Memory owns all required schemas, fixtures, installation
and runtime paths. Desktop and Relay are optional downstream consumers and do
not gate this release.

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
The implementation is in the private security advisory fork for
`GHSA-v96m-pj74-648h`. Do not copy private branches or patch details into a public
PR to work around the security-fork base restriction. Private PRs are cumulative
against `codex/v1.4-discovery`; review the phase-specific ranges recorded below.

| Slice | Branch | Review starting commit |
| --- | --- | --- |
| Phase 2 read contract | `codex/v1.4-read-contract` | `860ab144fc6f520dc15f53d9a06837ff844588fc` |
| Phase 3 onboarding | `codex/v1.4-onboarding` | `3817e9a683d2a83154483ef9834ba131c50f8f23` |
| Phase 4 governed review | `codex/v1.4-review-contract` | `b4ca771ced2ee05b3151c5b1f7a2602b9d98acd3` |
| Phase 5 providers/examples | `codex/v1.4-providers-and-examples` | `0c48452e93f02c614ab1aef04e6829cc50bfa9ee` |
| Phase 6 candidate integration | `codex/v1.4-release-candidate` | `6bba7f83697aa7ab67a97f2c6d9e2afc6616fae9` |

GitHub security forks do not execute Actions, and their PR merge workflow differs
from ordinary forks. After approval, coordinate the advisory's patch/merge and
disclosure as one reviewed operation; do not blindly merge every cumulative PR.
Preserve branch protection. If required checks cannot be satisfied in that
workflow, resolve the maintainer-approved confidential review path first—do not
bypass protection or expose the fix to obtain a green check.

## Remaining steps before calling 1.4.0 shipped

1. Review the final code, evidence, compatibility decisions and known limits.
   Complete independent required CI, including Linux; private-fork macOS runs
   are not evidence that GitHub Actions ran. A maintainer-provisioned optional
   local-model runner is separate and is not needed by ordinary CI.
2. Perform the human first-run walkthrough and record installation/review time.
   Automated warm-cache execution does not validate the approximately five-minute
   human adoption target or cold-network installation time.
3. Obtain the owner's explicit merge/disclosure/release approval. Merge only
   through the approved protected-branch/security-advisory workflow. Do not push
   directly to main, enable auto-merge, or silently publish the advisory.
4. Prepare a reviewed version-only change from 1.4.0rc1 to **1.4.0**, update the
   unpublished messaging, build final artifacts and repeat version/packaging/
   compatibility gates on that exact final commit. Do not relabel an rc wheel.
5. After publication is specifically authorized, use the existing Trusted
   Publishing workflow and tagged-release process. TestPyPI also counts as
   publication and requires approval. No npm package is part of this release.
6. Verify the new public package in fresh environments, its hashes/version,
   packaged docs/starters, model-free lifecycle and declared profiles. Only then
   mark G6 and Phase 7 complete and communicate downstream integration notes.

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
