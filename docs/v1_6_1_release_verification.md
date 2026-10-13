# 1.6.1 release verification

Release preparation date: October 13, 2026 (America/Chicago). Software: 1.6.1;
API: v1; storage: 1.3.1; automatic migration minimum: 1.3.0.

The [review resolution](v1_6_0_review_resolution.md) maps every verified finding
to its GitHub issue and acceptance evidence. The latest published release was
confirmed as 1.6.0 on GitHub and PyPI before reserving 1.6.1.

## Gates

- Local Python 3.13: 835 tests passed in the final full run; the additional
  curation regression passed separately (836 cases in the current suite).
- Generic-main release boundary, Python syntax compilation and diff whitespace
  checks passed.
- Wheel and source archive pass strict Twine metadata checks. Both minimal
  installations pass Python/TypeScript onboarding and installed 1.6.0
  upgrade/recovery checks outside the checkout.
- GitHub Release Gates must pass the complete isolated source-archive suite on
  Python 3.11/3.12/3.13, contract generation, TypeScript starter and installation
  gates before integration/publication.
- All referenced third-party actions were resolved through the GitHub API and
  pinned to their exact commits. Manual publication requires a tag whose name
  equals `v` plus the package metadata version. The extracted workflow guard
  accepts v1.6.1 and rejects a branch or mismatched tag in local checks.

All local validation uses synthetic stores/providers. Real Ollama workloads
were not requested or used for these repairs. A separate owner's workload was
left untouched.

## Publication

The GitHub draft and PyPI distributions are preparation artifacts. Publishing
is pending until the accepted commit and above gates are verified. The existing
`publish-pypi.yml` workflow uses the configured trusted-publisher environments;
recent 1.6.0 publication completed successfully. Never publish a stale build
from a different commit or attempt to overwrite an existing package version.

Read [the upgrade guide](v1_6_1_upgrade.md) for the deliberate access, import,
passphrase, lifecycle and job-recovery changes.
