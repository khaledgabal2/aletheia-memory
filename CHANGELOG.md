# Changelog

All notable public changes to Aletheia are tracked here.

## 1.4.0

Integration contracts and developer experience release.

- Separate software, API, storage and negotiated profile versions; preserve the
  published 1.3.1 SDK compatibility bridge. Add scoped current-principal discovery.
- Advertise typed `memory-read-v1`, `memory-review-v1` and
  `agent-onboarding-v1` with actual HTTP/generated-client conformance.
- Enforce current scope/privacy for selected reads and replay. Governed candidate
  review uses atomic revisions, explicit operation keys and audited replay;
  stale decisions require fresh inspection. Same-origin browser transport stays
  narrow; no wildcard CORS, SSE, Relay or Desktop dependency is introduced.
- Add safe starter generation, read-only diagnostics and an offline reviewed
  memory tutorial. Package embedded Python, scoped HTTP/Python and TypeScript
  agent examples with a separate operator approval step.
- Add optional, explicitly configured local embedding/LLM recipes, input-aware
  embedding index identity, structured extraction schemas and safe failures.
  Core remains model-free. No models or Node dependencies are installed by pip.
- Upgrade storage 1.3.0 to 1.3.1 atomically for durable revision/replay state.
  Back up before upgrade. Older binaries refuse the new schema; recovery uses
  the preserved pre-upgrade archive, not an in-place downgrade. Restore resets
  revision identity and clears stale replay state.

Compatibility limits: new profiles require discovery; old clients keep the
legacy route surface but do not gain negotiated write guarantees. Unknown
contract headers, invalid profiled fields, unsafe output overwrites and stale
write preconditions are explicitly refused. No npm package is published.

Behavior changes to account for when upgrading:

- Session identifiers are authorization-checked and can now return 403/404
  where an unscoped value previously passed through.
- Operation keys accept ASCII letters, digits, dots, underscores, colons and
  hyphens. Raw base64 keys containing `+`, `/` or `=` must use a safe encoding.
- Integer fields reject fractional values instead of truncating them, and
  privacy levels reject unknown spelling or capitalization.
- Replaying a legacy operation can return `replay_result_changed` if its stored
  result no longer matches current state. Credential-scoped 1.4 operation keys
  do not reuse unscoped pre-upgrade idempotency records.
- `aletheia api ping` accepts loopback service URLs only. Remote deployments
  should perform health checks at their trusted proxy boundary.
- Tokenless `/v1/auth/me` is available only when the local service is explicitly
  unauthenticated and unprotected; configured deployments return 401 without a
  bearer or console credential.

See the [release handoff](docs/v1_4_0_release_handoff.md) for evidence and the
release verification record.

## 1.3.1

Patch release to align the PyPI distribution with the current GitHub release
state.

- Includes the documented `aletheia_client.py` compatibility import module in
  the wheel distribution.
- Adds the GitHub Actions Trusted Publishing workflow for TestPyPI and PyPI.
- No runtime behavior changes.

## 1.3.0

Initial public release of `aletheia-memory`.

- Ships the local SQLite memory kernel, CLI, HTTP service, Python SDK clients,
  MCP tools, and generic adapter surfaces.
- Includes evidence-backed memory lifecycle support: evidence, candidate
  memories, review and promotion, claims, retrieval, context packs, feedback,
  conflicts, confidence, and audit records.
- Adds local production controls for protected mode, scoped tokens, encrypted
  backups, restore verification, redaction, forget tombstones, retention,
  diagnostics, readiness checks, release gates, and compatibility reports.
- Includes federation-beta support, governed semantic retrieval, and
  review-first LLM memory formation.
- Packages the public documentation set with the wheel.
