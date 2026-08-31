# Phase 4 verification: governed review

Recorded 2026-08-30 in the isolated implementation worktree on
`codex/v1.4-review-contract`, based on Phase 3 `b4ca771`. The accepted
[release plan](v1_4_0_contract_hardening_and_developer_experience_plan.md), D5/D6
and [pre-implementation storage design](v1_4_0_review_migration_design.md) govern
this slice. This evidence authorizes no merge or publication.

## G3 result

`memory-review-v1` is implemented and advertised on the development branch.
The profile covers candidate listing/inspection, promotion and rejection; other
writes do not gain this guarantee. The [contract](v1_4_0_review_contract.md)
documents the database-wide invalidation tradeoff and legacy differences.

| Gate | Observed evidence |
| --- | --- |
| Python matrix | All **243 tests** pass on Python 3.11.15, 3.12.11 and 3.13.13 on macOS; includes 33 new review cases. |
| Atomic review | Two independent SQLite connections cannot commit competing decisions. Injected decision, scope and receipt failures roll back all domain rows, audit and revision state. |
| Writer coverage | Embedded review, CLI edits, legacy HTTP writes, a background indexing worker, federation import and restore invalidate earlier inspections. Returning text to its original value does not revive a revision. |
| Complete inventory | 124 invalidating tables, 372 triggers, 56 pre-existing operational exclusions plus two protocol tables. Missing trigger definitions or unclassified tables fail schema integrity. |
| Replay and authorization | Original receipt and operation ID survive replay/restart; transport IDs are fresh. Same-key changed payload/action conflicts; credentials sharing a client remain separate. Current scope, capability, privacy and revocation are checked before replay. |
| Uncertain responses | The actual HTTP fixture deliberately closes the first successful response connection. Retrying the same key returns exactly one committed decision. Expired keys cannot duplicate promotion. |
| Lock/error behavior | SQLite contention returns a structured 503. Operational logging failure cannot replace that response or a committed receipt; governance audit remains part of the atomic write. |
| Pagination | Tied timestamps, hidden candidates, continuation, tampering, filter changes and intervening writes pass actual-response schema checks. List limits and encrypted cursor bounds are documented. |
| Python SDK | Synchronous and asynchronous guarded methods pass real-service checks. Missing profiles refuse explicitly. Stale decisions use a dedicated error; no automatic keys, force or write retries. |
| Generated TypeScript | Baseline, discovery, read and review schemas regenerate and compile. All four actual-service consumers pass; review includes inspection, keyset listing, rejection, stale refusal, new approval, promotion, replay and audit. All five Node polling/timeout tests pass. |
| Browser | The Codex in-app browser passes the Memory-owned same-origin read and review pages. Verified real headers, stale refusal, replay, revocation, scope clearing, cancellation and read-only polling. No Desktop checkout or application is used. |
| Real legacy storage | A database created by the actual published 1.3.1 implementation upgrades while preserving claim/evidence/candidate/permission row hashes, retrieval and provenance. The older default binary refuses the upgraded file and restores the encrypted pre-upgrade archive to storage 1.3.0. |
| Failed migration/restore | Injected migration failure preserves old data/version and removes partial schema work. In-place restore with an active service clears replay records, changes cache identity and refuses old revisions. |
| Packaging | Wheel and source distribution build offline and install in fresh core-only environments. Each passes all 11 installed onboarding checks outside the checkout, including socket-blocked embedded examples and disposable HTTP agents. |
| Boundary | Generic baseline and whitespace gates pass. The original checkout's tracked files are unchanged. No main push, merge, advisory publication or package publication occurs. |

The CI workflow now includes review schema generation, TypeScript execution and
the real published-binary migration/recovery check. Private security forks do
not run GitHub Actions; these local macOS results are not Linux CI evidence.

## Reproduce

```sh
python -m pytest
python -m scripts.v1_4_review_contract --output contracts/typescript/generated/review.json
npm run generate:review --prefix contracts/typescript
npm run check --prefix contracts/typescript
npm run build --prefix contracts/typescript
python -m scripts.v1_4_review_contract --typescript
python -m scripts.v1_4_migration_check --legacy-package .legacy-1.3.1
python -m scripts.v1_4_review_contract --browser
```

Generate discovery/read declarations first on a fresh checkout using the
[tooling guide](../contracts/typescript/README.md). The legacy-package argument
must point to the actual published modules with matching recorded hashes.

## Remaining release work

Software metadata remains 1.3.1 until the Phase 6 prerelease build; storage is
now 1.3.1. The agent-onboarding profile and packaged TypeScript starter remain
Phase 5 work, alongside separate live local embedding/LLM smoke tests. No
model-quality claim follows from deterministic core tests. Human five-minute
onboarding validation, cold-network installation timing and final release
approval remain unmeasured or pending; none is implied by this evidence.

All implementation history after Phase 1 remains in the existing private
advisory fork. Its PRs use cumulative diffs against the public discovery branch
because GitHub rejects private-only branches as security-fork PR bases. Review
this phase locally as `b4ca771...codex/v1.4-review-contract`. No implementation
branch is copied to public main to work around that restriction.
