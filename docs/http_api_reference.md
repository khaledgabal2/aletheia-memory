# HTTP API Reference

The v1 HTTP API is published as OpenAPI:

```bash
aletheia api openapi --db ./aletheia.db --output ./openapi.json
```

M9 platform routes include:

- `/v1/contracts`
- `/v1/deprecations`
- `/v1/compatibility/report`
- `/v1/plugins`
- `/v1/conformance/suites`
- `/v1/adapters/scaffold`
- `/v1/docs/status`
- `/v1/examples`
- `/v1/doctor/run`
- `/v1/v1-gate/run`

State-changing platform routes require admin capability when service auth is enabled.

M12 governed LLM routes:

- `POST /v1/llm/expand-query`
- `POST /v1/llm/summarize-evidence`
- `POST /v1/llm/suggest-entities`
- `POST /v1/llm/suggest-categories`
- `POST /v1/llm/suggest-scope`
- `POST /v1/llm/suggest-duplicate-merge`
- `POST /v1/llm/explain-conflict`
- `GET /v1/llm/runs`

These routes produce suggestions, drafts, provenance records, or query expansions only. They do not promote claims, resolve conflicts, mutate scope, or merge duplicates.
