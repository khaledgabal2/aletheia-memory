# Contributing To Aletheia

Thanks for helping improve Aletheia. The project is local-first by design, so
changes should preserve provenance, reviewability, scoped access, privacy
ceilings, and auditable memory lifecycles.

## Development Setup

```bash
git clone https://github.com/khaledgabal2/aletheia-memory.git
cd aletheia-memory
python -m pip install -e ".[dev]"
pytest
```

If you use `uv`, the equivalent verification command is:

```bash
uv run --extra dev pytest
```

## Before Opening A Pull Request

- Run `pytest` or `uv run --extra dev pytest`.
- Run `python scripts/release_gate.py --branch main` before changes targeting
  the generic public baseline.
- Update docs when changing CLI commands, HTTP routes, MCP tools, public Python
  APIs, security behavior, storage schema, or release policy.
- Add or update tests for behavior changes.
- Keep generated databases, support bundles, private logs, credentials, tokens,
  and environment files out of commits.

## Before Publishing A Release

- Finalize and review README/PyPI description, changelog, upgrade guidance,
  security/version statements, packaged docs and release notes before tagging
  or starting the publication workflow.
- Use stable latest-release links or version-accurate wording. Documentation
  must read correctly when the tagged package is published; do not ship pending
  placeholders or defer known wording corrections until after publication.
- Build the wheel and source distribution from the final release source. Verify
  their embedded README/description matches the finalized source, then run the
  metadata checks and required release gates before publication.
- Do not plan a release followed by another package release just for omitted
  documentation. Fix known documentation problems before the first publication.
- After publication, verify PyPI's actual description as well as version, file
  hashes and fresh installation. Add publication-only results to the existing
  GitHub release notes or verification assets; they do not require another
  package release.

## Design Boundaries

Open an issue or discussion before introducing:

- New persistent schema or migration behavior.
- New network behavior or external provider defaults.
- New active-write paths for agents.
- Changes to token, protected-mode, backup, retention, redaction, federation, or
  plugin permission semantics.

Agent integrations should prefer candidate-first writes unless they have an
explicitly trusted active-write policy.
