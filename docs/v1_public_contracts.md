# Aletheia v1 Public Contracts

Aletheia's v1 interface commitments cover these public surfaces. The current
1.6.0 package is beta; interface stability does not certify production readiness.

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
