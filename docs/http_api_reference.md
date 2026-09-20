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

HTTP `provider` values accept built-in IDs or `plugin:<installation ID>` (also
accepting the registered plugin name). An enabled `llm_provider` installation
and approved permissions are required; raw Python entrypoints are rejected
before import. Every referenced source must meet the caller's current scope
and privacy policy before a provider is constructed.

`POST /v1/sessions/{session_id}/end` defaults to `write_mode: "candidate"`
when saving a summary. `write_mode: "active"` additionally requires
`memory:write_active`. Both require `memory:write_candidate` and access to the
stored session's namespace/project. `remember_summary: false` ends the session
without saving the supplied summary.

Operational lists, including `/v1/llm/runs` and `/v1/traces`, require an explicit
authorized `namespace` unless the caller holds the `*` namespace grant.
See [HTTP access boundaries](service_access_boundaries.md) for all affected
routes, provider setup, trace compatibility, and Python SDK examples.

Storage operations follow the same [storage privacy boundaries](storage_privacy_boundaries.md)
as the embedded API: protected candidate spans omit plaintext copies; JSONL
cannot promise encryption; physical backups cannot exclude auth metadata;
archive imports retain source privacy and reject incomplete provenance; and
forget/redaction modes apply their documented content and dependency changes.


## Federation key recovery

`POST /v1/federation/identity/rotate` requires `memory:admin` and the JSON
fields `expected_fingerprint`, `recovery_path`, and `reason`. `recovery_path`
is a new server-side file under an admin safe root. Configure
`ALETHEIA_FEDERATION_RECOVERY_KEY` on the server; the API does not accept a
recovery passphrase in the body. The operation verifies an encrypted
retired-decryption-key archive before replacing keys, revokes prior shares,
and returns the public identity without private key records.

`POST /v1/peers/{peer_id}/replace-key` requires `memory:admin` and the JSON
fields `peer_identity`, `expected_fingerprint`, `confirmed_fingerprint`, and
`reason`. Confirm the new fingerprint independently. Replacement retains the
instance ID, retires both old public keys, revokes old grants, and returns a
peer whose trust status is `unknown`; approving trust is a separate action.
Ordinary peer addition and incoming bundles cannot replace pinned keys.

Historical bundle decryption is available only through the local CLI and
embedded API and produces an encrypted review artifact without importing.
See [Federation key recovery](federation_key_recovery.md) for the operator
procedure and recovery-secret handling.
