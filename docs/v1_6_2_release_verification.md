# 1.6.2 release verification

Published and verified October 16, 2026 (America/Chicago). Version **1.6.2** is
available on [GitHub](https://github.com/khaledgabal2/aletheia-memory/releases/tag/v1.6.2)
and [PyPI](https://pypi.org/project/aletheia-memory/1.6.2/).
Software: 1.6.2 beta; API: v1; storage: 1.3.1; Python: 3.11+.

[PR #65](https://github.com/khaledgabal2/aletheia-memory/pull/65) fixed issue #64;
[PR #66](https://github.com/khaledgabal2/aletheia-memory/pull/66) prepared the
patch release. Tag `v1.6.2` points to accepted merge commit
`42e7525ca9dad2e88b41d7810493d72f71df0bae`.

## Acceptance and publication

- The [release PR gates](https://github.com/khaledgabal2/aletheia-memory/actions/runs/38906602254)
  passed all seven checks, including Python 3.11/3.12/3.13, distribution builds,
  generated contract consumers and installed TypeScript starters.
- The [trusted publishing workflow](https://github.com/khaledgabal2/aletheia-memory/actions/runs/38908071274)
  reverified the tagged commit (846 tests passed on each Python version),
  built wheel/sdist, passed strict Twine checks,
  and published successfully to PyPI.
- Both actual workflow distributions were downloaded and their SHA256 digests
  matched public PyPI metadata. The same files, checksums, source provenance and
  publication verification receipt are attached to the GitHub release.
- Unchanged installed Desktop 0.1.0 build `b6fc845` passed actual Nomic retrieval
  validation against the isolated fixed service. SDK and Desktop scores matched
  exactly, pending corrections reported lexical fallback, and superseded/forgotten
  facts were excluded. See [the issue verification record](issue_64_verification.md).
  The test pairing was revoked and temporary service stopped; no user database
  or model/profile was changed.

| Distribution | SHA256 |
| --- | --- |
| `aletheia_memory-1.6.2-py3-none-any.whl` | `117b3c66c0a06fe441082b972447ec8b992fee239663745e091eae0c093b348c` |
| `aletheia_memory-1.6.2.tar.gz` | `8787c3b6dd16b19f011253efd40289923e2251d197a612f1ef6f9f4d71c66578` |

## Fresh installed verification

A fresh uncached installation from `https://pypi.org/simple` reported 1.6.2 on
Python 3.13.13 outside the checkout. Imports resolved to the new environment's
site-packages, the CLI started, and all installed dependencies were compatible.
The first index lookup briefly did not list the newly uploaded version; a fresh
uncached retry succeeded after public version metadata was confirmed.

Installed Python/TypeScript onboarding passed in 23.781 seconds of automated
execution, exercising approve/refuse flows, scoped agents, persistence, revoked
tokens, safe generation, and transport deadline/cancellation behavior. This is
automated execution time, not installation time or a measured human walkthrough.
Logs and verification receipts are retained locally under
`/tmp/aletheia-release-1.6.2/`.

```bash
python -m pip install --upgrade aletheia-memory==1.6.2
```

Read [the upgrade guide](v1_6_2_upgrade.md) for the explicit server provider
setting and retrieval result changes. The release-tag source and distributions
are immutable snapshots; this postpublication verification record and corrected
publication wording live on `main`. No tag was moved or package republished.
