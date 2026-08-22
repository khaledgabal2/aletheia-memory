# Changelog

All notable public changes to Aletheia are tracked here.

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
