# Issue 64: HTTP semantic provider selection

The HTTP retrieval handler omitted provider selection, so SDK calls with an
explicit external provider and HTTP requests queried different indexes. The core
also retained the requested semantic/hybrid label during lexical fallback.

The server now supports `server.semantic_provider` / `ALETHEIA_SEMANTIC_PROVIDER`.
The default stays `mock`. Search/retrieve requests use this operator-selected
provider; request extensions cannot redirect provider calls. Model, dimensions
and input prefixes still come from the existing provider configuration. No schema
migration or permission expansion is needed.

Fallback results report `retrieval_mode: lexical`. The additive `semantic_status`
field distinguishes positive vector matches (`indexed`), unavailable positive
matches (`unavailable`), and lexical requests (`not_requested`). Configured HTTP
embedding dimensions must match the index even without prefix configuration.

## Verification (October 16, 2026)

- Full pytest suite passed (845 cases at collection). The additional no-prefix
  dimension/privacy control passed in the final 10-case focused run.
- The 10 issue regressions compare authenticated `/v1/search` and `/v1/retrieve`
  with SDK results on the same indexed synthetic facts, in semantic and hybrid
  modes. They assert equal positive embedding scores and actual provider requests,
  including the query prefix/model, rather than mode labels alone.
- Superseding an indexed claim excludes it from active retrieval. Its unindexed
  replacement is labeled lexical/unavailable until explicitly indexed, then
  receives a positive score. Tombstoning excludes the replacement.
- Unauthorized namespaces and claims above the token's privacy ceiling cause no
  provider call. Lexical mode and the default mock fallback cause no external
  provider calls. Changed model/prefix/dimensions fail before inference.
- The unchanged Desktop Explorer request body is supported. Its existing
  `src/api/explorer-contract.ts` parser accepted a real authenticated response
  from the fixed service with a positive embedding score. Desktop source was not
  changed. This is consumer compatibility evidence, not an installed-app TLS
  pairing or real Nomic model validation.
- The generic-main release gate and `git diff --check` passed.

The automated tests used disposable synthetic HTTP embedding providers. Active model clients were inspected before validation; no foreign model job
was started or interrupted. Logs were saved locally under
`/tmp/aletheia-issue64-{pytest,focused}.log` (not committed).

## Installed Desktop and Nomic acceptance

The unchanged installed `/Applications/Aletheia.app`, Desktop 0.1.0 build
`b6fc845`, passed the live acceptance check against an isolated source-branch
service with a temporary database and TLS identity. Pairing granted only read
and audit access to `agents/semantic-repro`, with a personal privacy ceiling.
No user database, Desktop source, permission ceiling, or model configuration
was changed. The test service used `nomic-embed-text:latest`, 768 dimensions,
`search_document: ` / `search_query: ` prefixes, and local-only transport.

| Stage | SDK score | Installed Desktop HTTP score | Visible result |
| --- | ---: | ---: | --- |
| Indexed original | 0.877755446370685 | 0.877755446370685 | Solar skiff; semantic ranking |
| Correction awaiting index | — | 0.0 | Wind glider; lexical ranking / unavailable |
| Indexed correction | 0.8601711613401315 | 0.8601711613401315 | Wind glider; semantic ranking |
| Forgotten correction | — | No results | No visible matches |

The original superseded claim never returned after correction. A synthetic fact
in another namespace was not visible. Actual Nomic provider invocations and the
Desktop HTTP responses were captured in `/tmp/aletheia-issue64-live/events.jsonl`.
Desktop's accessibility state verified the active scope, selected Semantic mode,
rendered facts/ranking labels, and final empty result. The test pairing was then
revoked through Desktop, which confirmed the credential was revoked; its scope
was cleared. The temporary service stopped and released its shared resource
lease. The existing shared lock inode was retained; its drifted mode was restored
from 0644 to the controller-required 0600 before admission. No active Ollama
clients were present at admission and no foreign workloads were interrupted.

All seven PR CI checks passed on the implementation commit, including Python
3.11/3.12/3.13, package build, contracts, packaged TypeScript starter, and the
baseline boundary. The final evidence-only documentation update was checked
with the generic-main release gate and `git diff --check`; unchanged source
validation is reused. The fix is included in published 1.6.2; see the
[release verification](v1_6_2_release_verification.md).
