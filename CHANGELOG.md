# Changelog

All notable public changes to Aletheia are tracked here.

## 1.4.0rc1 (unpublished)

Integration contracts and developer experience release candidate. No public
release, advisory publication or protected-branch merge has occurred.

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
See the [release handoff](docs/v1_4_0_release_handoff.md) for evidence, remaining
checks and approval boundaries.

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
