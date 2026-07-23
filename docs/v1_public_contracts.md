# Aletheia v1 Public Contracts

Aletheia v1.0.0 treats these surfaces as stable public contracts:

- Python package API: `Memory`, `AletheiaClient`, `AsyncAletheiaClient`, and plugin protocols in `aletheia.plugins`.
- HTTP API: `/v1/*` routes published by `aletheia api openapi`.
- MCP tool names and request shapes published by `aletheia mcp --list-tools`.
- CLI command groups: `doctor`, `compatibility`, `plugins`, `conformance`, `adapters`, `docs`, `examples`, `contracts`, `deprecations`, and `v1-gate`.
- Archive and context-pack formats.
- Database migration behavior from 0.9.x to 1.0.0.

Semver policy:

- Patch releases preserve all stable v1 contracts.
- Minor releases may add fields, commands, routes, or plugin permissions.
- Deprecations require a notice, replacement when available, and a removal version no earlier than a future minor release.
- Experimental contracts are clearly marked and are not covered by v1 stability guarantees.
