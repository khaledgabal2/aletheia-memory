# Discovery foundation for 1.4.0

This document describes the discovery changes on the 1.4.0 implementation
branch. They are not a claim that a 1.4.0 package has been published. The
installed package version still comes from its build metadata.

## What clients can now learn

The health, readiness, version and compatibility endpoints report the software
version separately from the database schema. A new `GET /v1/auth/me` endpoint
reports only the caller's identity and effective access. The service also
publishes typed discovery schemas that generated clients can use directly.

Existing routes, aliases, envelopes and write defaults remain supported. The original discovery foundation did not require a database migration or
Desktop installation. The complete 1.4.0 release has a separate
[storage upgrade](v1_4_0_migration_guide.md).

| Endpoint | Access | Result |
| --- | --- | --- |
| `GET /v1/health` | Public | Health plus software/API/profile/instance metadata; actual schema version retained. |
| `GET /v1/ready` | Public | Existing readiness result plus the same metadata. Readiness semantics are unchanged. |
| `GET /v1/version` | Public | Software version, API family, available features/profiles and service identity. |
| `GET /v1/openapi.json` | Public | Existing envelope containing the complete OpenAPI document. |
| `GET /v1/compatibility/report` | `memory:read` or effective admin | Existing report plus canonical software metadata and explicit legacy-field deprecation. |
| `GET /v1/auth/me` | Valid caller credentials, or explicit unprotected local tokenless mode | Current caller's safe identity and access, with no read/admin capability requirement. |

These six operations have operation IDs, parameters, typed envelopes and error
responses in `aletheia/service/contracts.py`. The published schema is checked
against actual service responses. The read, review and onboarding registries
extend these schemas for their selected operations. Other paths retain their existing legacy representation;
discovery alone does not certify arbitrary administrative operations.

## Versions and features

- `software_version`: installed distribution metadata, with a source-checkout
  fallback to this project's pyproject.toml. If neither is available, `0+unknown`
  explicitly reports that uncertainty. It never falls back to the schema number.
- `service_version`: preserved field, now accurately reporting the software version.
- `api_version`: `v1`, independent of the software release number.
- `schema_version`: actual persistent schema: 1.3.1 in Memory 1.4.0 (see the migration guide).
- `supported_features`: currently includes `current-principal`.
- `supported_profiles`: advertises a profile only after its complete gate passes.
  Memory 1.4.0 advertises `memory-read-v1`, `memory-review-v1`, and
  `agent-onboarding-v1`; older discovery-only builds may advertise none.
- `service_identity`: random identity stable for one running service instance.
  Restarting the service changes it. It contains no path, token or hardware identity.

The compatibility report's `aletheia_version` retains its historical schema-alias
meaning as the engine's expected schema version. It equals the actual schema
on a compatible database; a mismatch still makes the old SDK reject the service.
This preserves the published 1.3.1 check rather than making it always pass. New
clients must use `software_version` for release display. `deprecated_fields`
explains the old alias; there is no removal in 1.4.0.
This does not change legacy plugin min/max compatibility policy; reviewing that
separate policy is outside the discovery slice.

Software version reporting also corrects diagnostics, documentation-build
metadata, newly registered contract introduction versions and release-gate run
metadata. Existing migration, backup/archive format and seeded historical
contract versions retain their original storage/format meanings.

## Self discovery

`/v1/auth/me` returns `authentication_mode`, `authenticated`, nullable `principal`,
`granted_capabilities`, effective `capabilities`, `namespace_grants`,
`privacy_ceiling`, nullable `expires_at`, and the discovery metadata above.
A bearer principal contains only `id`, `name`, and `client_type`.
Console sessions may have no registered API principal; they report
`console_session` and a null principal rather than inventing an identity.

Admin implies the server's capability vocabulary, so `capabilities` expands
that implication while `granted_capabilities` retains the original grants.
Neither list expands namespace access or the privacy ceiling. Promotion and
candidate inspection continue to require `memory:review`, not `memory:promote`.
Grant patterns are not a list of all existing namespaces, and discovering a
capability does not prove access to a particular resource.

Client and token metadata, raw tokens, token prefixes/hashes, provider secrets
and other principals' access are never serialized by this endpoint. Query
parameters cannot select a different principal. Bearer grants are reloaded for
each request, so changes become visible without relying on a cached profile.

Missing credentials on an authenticated service, invalid/expired/revoked tokens,
and tokens belonging to disabled clients return 401 without principal data.
Local tokenless mode is explicitly identified, with null principal and the
least-privilege configured local scope. Protected mode does not use this fallback.
A supplied invalid token never downgrades to tokenless access on this new endpoint.

Existing console session and CSRF behavior is retained. Console logout keeps
its pre-existing CSRF exemption; other console mutations still require CSRF.

## Client behavior

```python
from aletheia import AletheiaClient

client = AletheiaClient(service_url, token=token)
principal = client.current_principal()
compatibility = client.check_compatibility(required_profiles=["memory-read-v1"])
if not compatibility["compatible"]:
    print("Unavailable:", compatibility["missing_profiles"])
```

The example requires the read profile and refuses a server without it. Memory
1.4.0 supports it; older discovery-only builds do not. Existing legacy v1
operations remain usable without asking for a profile. The async SDK offers
the same methods and arguments.

`check_compatibility()` preserves its previous result keys and adds
`supported_profiles`, `missing_profiles`, `limited_capabilities`, and
`service_identity`. It checks API and requested profile support; software/schema
equality is irrelevant. `limited_capabilities` means an older server lacks
usable profile-discovery metadata. On 1.3.1, old v1 reads/context still work,
requested new profiles are refused, and `current_principal()` raises
`AletheiaUnsupportedFeatureError` instead of inventing identity or access.
Authentication errors are propagated, never treated as missing feature support.
The new error is importable from `aletheia.client` and the existing
`aletheia_client` compatibility module.

## Transport and verification

Discovery HTTP responses, including errors, use `Cache-Control: no-store`.
The envelope retains request correlation. Printable ASCII request IDs of at
most 200 characters are also returned in `X-Request-ID`; other IDs remain in the
JSON envelope but are not reflected into an HTTP header. No CORS or broader
network exposure is introduced.

The following command starts a disposable loopback service, extracts the real
published document from its envelope, projects the six discovery paths, and
validates OpenAPI 3.1 before generation:

```sh
python -m scripts.v1_4_discovery_contract --output contracts/typescript/generated/discovery.json
```

Generate with
`npm run generate:discovery --prefix contracts/typescript`, compile the consumer,
then use `python -m scripts.v1_4_discovery_contract --typescript` for real HTTP
calls. The consumer accesses domain fields using generated types without casts.

The published 1.3.1 SDK fixture is exercised against the new service. The reverse
check runs an independently installed 1.3.1 service in a separate process with
source hashes verified against the retained provenance. Temporary credentials
travel only through pipes/environment and are not written to fixtures or logs.
All harnesses are Memory-owned and independent of Desktop.

Remaining gates include complete resource authorization/redaction for reads,
real-browser topology tests, pagination, atomic review/replay, first-run
diagnostics and a measured human tutorial. Discovery does not enable those
profiles prematurely. The [release plan](v1_4_0_contract_hardening_and_developer_experience_plan.md)
remains the source of truth.
