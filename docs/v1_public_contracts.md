# Aletheia v1 Public Contracts

Aletheia 1.7.0 is production/stable within its [qualified boundaries](v1_7_0_release_notes.md#qualification-and-limits).
The v1 interface commitments below remain unchanged; interface stability alone
does not qualify every deployment or experimental surface.

- Python package API: `Memory`, `AletheiaClient`, `AsyncAletheiaClient`, and plugin protocols in `aletheia.plugins`.
- HTTP API: `/v1/*` routes published by `aletheia api openapi`.
- MCP tool names and request shapes published by `aletheia mcp --list-tools`.
- CLI command groups: `doctor`, `compatibility`, `plugins`, `conformance`, `adapters`, `docs`, `examples`, `contracts`, `deprecations`, and `v1-gate`.
- Archive and context-pack formats.
- Database migration behavior through storage 1.3.1, including the tested
  1.3.0-to-1.3.1 upgrade and encrypted backup recovery path.

Semver policy:

- Patch releases preserve all stable v1 contracts.
- Minor releases may add fields, commands, routes, or plugin permissions.
- Deprecations require a notice, replacement when available, and a removal version no earlier than a future minor release.
- Experimental contracts are clearly marked and are not covered by v1 stability guarantees.
