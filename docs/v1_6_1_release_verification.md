# 1.6.1 release verification

Published and verified October 13, 2026 (America/Chicago). This historical record
covers **1.6.1** on [GitHub](https://github.com/khaledgabal2/aletheia-memory/releases/tag/v1.6.1)
and [PyPI](https://pypi.org/project/aletheia-memory/1.6.1/).
Software: 1.6.1 beta; API: v1; storage: 1.3.1; automatic migration minimum: 1.3.0.

The [review resolution](v1_6_0_review_resolution.md) maps every verified finding
to its issue and acceptance evidence. [PR #62](https://github.com/khaledgabal2/aletheia-memory/pull/62)
is merged, and all 52 tracked issues #10–#61 are closed. The accepted source
commit is `2f8cc18c3809837f7585562406b65a00d787d8b6`, tagged `v1.6.1`.

## Acceptance gates

- The complete local isolated source archive passed 836 tests on Python 3.13.
- [Release Gates](https://github.com/khaledgabal2/aletheia-memory/actions/runs/38353584725)
  passed all seven jobs, including 836 cases on each of Python 3.11, 3.12 and
  3.13, generated contract consumers and packaged TypeScript starters.
- The accepted merge has an identical Git tree to the tested PR head. Its
  [main-branch gates](https://github.com/khaledgabal2/aletheia-memory/actions/runs/38354618592)
  also passed.
- Wheel and source archive passed strict Twine metadata checks. Both minimal
  installations passed Python/TypeScript onboarding and installed 1.6.0
  upgrade/recovery checks outside the checkout.
- Legacy 1.3.1 compatibility and authenticated physical-snapshot rollback passed.
- Third-party actions are pinned to exact commits. Manual publication requires
  a matching package-version tag; local checks refused branches and mismatched tags.

Validation used synthetic stores/providers. No live Ollama inference was used
and no other owner's workload was interrupted or changed.

## Publication and installed verification

The [trusted publishing workflow](https://github.com/khaledgabal2/aletheia-memory/actions/runs/38386396532)
completed successfully, including release checks, distribution build and PyPI
publication. GitHub's latest release endpoint and PyPI's public version metadata
confirmed 1.6.1. Both the wheel and source archive are available on PyPI, with
SHA256 digests matching the verified GitHub assets. The release carries
checksums, source provenance and publication verification evidence.

A fresh uncached installation from `https://pypi.org/simple` passed on Python
3.13.13 outside the checkout. Installed metadata reported 1.6.1, imports resolved
to the new environment's site-packages, dependencies were compatible and the
CLI started. Python/TypeScript onboarding passed in 22.973 seconds, exercising
scoped agents, review/promotion, persistence, revoked tokens and safe generation.

```bash
python -m pip install aletheia-memory==1.6.1
```

Read [the upgrade guide](v1_6_1_upgrade.md) for the deliberate access, import,
passphrase, lifecycle, archive compatibility and job-recovery changes.
