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

Tests used disposable synthetic HTTP embedding providers, not local Ollama
inference. Active model clients were inspected before validation; no model job
was started or interrupted. Logs were saved locally under
`/tmp/aletheia-issue64-{pytest,focused}.log` (not committed).

An installed Desktop/Nomic end-to-end recheck remains pending. Do not count the
consumer parser check as that live acceptance test. The fix is unreleased; the
published 1.6.1 runtime remains unchanged.
