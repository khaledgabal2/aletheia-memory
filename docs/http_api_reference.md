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

Retrieval checks status, validity, scope, and caller visibility before selection
and limits. Provider construction and inference release the service lock;
completion rechecks access and rejects changed inputs with
`409 provider_input_changed`. The Python SDK rejects 3xx redirects with
`AletheiaClientError(code="redirect_blocked")` and does not retry them. See
[retrieval and provider execution](retrieval_execution_boundaries.md) for the
full behavior and compatibility boundaries.

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

## Predicate semantics

`GET /v1/predicate-semantics?namespace=user%2Fdefault&predicate=likes` reads a
namespace-wide declaration. It requires `memory:read` (or `memory:admin`) and a
namespace grant. `namespace` and `predicate` are required query parameters,
each supplied exactly once; no other query fields are accepted. An undeclared
predicate returns the default `single` / `exclusive_value` without creating a
declaration.

`POST /v1/predicate-semantics` sets a declaration. It requires `memory:admin`
and a namespace grant, including when authentication is configured in tokenless
mode. Review or active-write capability alone is insufficient. Project-only
grants cannot read or change these namespace-wide declarations. The JSON body
requires exactly these fields, with no query parameters:

```json
{"namespace": "user/default", "predicate": "likes", "cardinality": "multiple"}
```

`namespace` and `predicate` must be nonblank strings; `cardinality` accepts
`single` or `multiple`. `single` means exclusive values; `multiple` means
independent positive set membership. Names do not implicitly select cardinality.
The response uses the standard success envelope:

```json
{
  "data": {
    "namespace": "user/default",
    "predicate": "likes",
    "cardinality": "multiple",
    "semantics": "set_membership"
  },
  "request_id": "example-request",
  "warnings": [],
  "pagination": null
}
```

Predicate lookup is case-insensitive; namespace lookup is exact. Responses use
`Cache-Control: no-store`. Invalid input returns `400`, missing/invalid
credentials `401`, and insufficient capability or namespace access `403`.
POST accepts the standard optional `Idempotency-Key`: retry an uncertain write
with the same key and identical body. A changed body with the same key returns
`409`; cached receipts recheck current authority. Configure each database
explicitly; declarations are not federation-replicated.

The synchronous and asynchronous Python SDKs expose matching methods. Unlike
the embedded API, their `namespace` argument is required:

```python
from aletheia import AletheiaClient, AsyncAletheiaClient

client = AletheiaClient(base_url, admin_token)
meaning = client.set_predicate_semantics(
    "likes", namespace="user/default", cardinality="multiple",
    idempotency_key="declare-likes-1",
)
meaning = client.get_predicate_semantics("likes", namespace="user/default")

async def configure():
    client = AsyncAletheiaClient(base_url, admin_token)
    await client.set_predicate_semantics(
        "likes", namespace="user/default", cardinality="multiple",
        idempotency_key="declare-likes-async-1",
    )
    return await client.get_predicate_semantics("likes", namespace="user/default")
```

Both methods return the unwrapped declaration dictionary. SDK errors use the
existing typed exceptions, including `AletheiaForbiddenError` and
`AletheiaValidationError`. The compatibility imports from `aletheia_client`
expose the same clients and methods.

Declare semantics before storing or extracting facts. Changes invalidate review
snapshots but do not resolve existing conflicts or rewrite candidate risk flags.
Ordinary recall keeps disputed records excluded. Set membership does not parse
natural-language negation; see [modeling guidance](core_concepts.md#predicate-cardinality-and-semantics).

## Conflict detection and resolution boundaries

`POST /v1/conflicts/detect` requires `memory:review` (or `memory:admin`) and
namespace-wide access. A project-only grant is insufficient, even if the body
contains a matching `project_id`. That legacy label does not narrow the scan or
its authorization. Optional `subject` / `predicate` filters select a property
group; `claim_id` selects the stored claim's namespace and property after
checking its visibility. Every selected active/core/disputed claim and its
provenance must be visible before any creation/mutation; otherwise the request
returns `403` atomically. Returned families are visibility-filtered, including
`create: false` requests, which only return existing families. Property filters
also constrain returned families.

Single-valued disputes retain subsequent assertions as disputed members rather
than allowing the next value into ordinary recall. Identifier and object
comparison follow the [shared comparison policy](core_concepts.md#predicate-cardinality-and-semantics).
Accepted scope resolutions survive a rescan while their approved scopes remain
unchanged. A new assertion is evaluated against existing members.

`POST /v1/conflicts/{conflict_id}/resolve` requires review authority and visibility
of the whole family. Explicit outcomes must be unique, disjoint and complete;
a selected winner cannot also be superseded/rejected. A manual decision with
no outcomes is invalid. Invalid requests return `400` without status, scope,
audit or resolution mutations. Scope resolutions must specify every member,
with distinct contextual labels or nonoverlapping time intervals for conflicting
values. Distinct free-text contextual labels reflect an explicit reviewer
decision; they do not imply natural-language contradiction inference.

To reconcile an old family after declaring its predicate multivalued:

```json
{"strategy": "coexist", "note": "Both values are compatible positive memberships"}
```

`coexist` requires a multivalued declaration and accepts no winner, discard list
or scope assignments. It restores all members to active (preserving core) and
closes the family. Changing the declaration alone leaves existing reviews
pending. Use the normal optional `Idempotency-Key` for uncertain retries.

The complete published OpenAPI document declares every URI template parameter
and is validated as a whole, including legacy conflict and claim routes.
