# Installation

This guide covers installing Aletheia v1.3.0, verifying the command line,
initializing a local database, and finding the help documents that ship with
the package.

## Requirements

- Python 3.11 or newer.
- SQLite, provided by Python's standard `sqlite3` module.
- A writable local path for the Aletheia database.
- Optional: `uv` for repository development workflows.

The published Python package is named `aletheia-memory`. The console script is
named `aletheia`.

## Install From A Release Wheel

Install the release artifact into your environment:

```bash
python -m pip install aletheia-memory
```

Then verify the CLI:

```bash
aletheia --help
aletheia docs list
```

If you are installing from a local wheel file instead of an index:

```bash
python -m pip install ./dist/aletheia_memory-1.3.0-py3-none-any.whl
```

## Install From Source

From the repository root:

```bash
python -m pip install ".[dev]"
```

For local development with `uv`, commands in this repository commonly use:

```bash
uv run --extra dev aletheia --help
uv run --extra dev pytest
```

## Initialize A Database

Aletheia is local-first. You choose the SQLite database file:

```bash
aletheia init --db ./aletheia.db
```

The command creates or migrates the database and prints the current health
record. For repository development, use:

```bash
uv run --extra dev aletheia init --db ./aletheia.db
```

## Verify Installed Help

The canonical docs are packaged under `aletheia/docs` in installed wheels. Use
the CLI to find them:

```bash
aletheia docs path
aletheia docs list
aletheia docs show index
```

To locate one document:

```bash
aletheia docs path architecture
aletheia docs show memory-lifecycle
```

To copy the installed docs into a local directory:

```bash
aletheia docs build --db ./aletheia.db --output ./site
```

The build command also writes `openapi.generated.json` when API reference
generation is enabled.

## First Memory Check

Store a reviewed explicit memory:

```bash
aletheia remember \
  --db ./aletheia.db \
  --namespace user/default \
  --type preference \
  --subject user \
  --predicate prefers_response_style \
  --object "practical and direct"
```

Search it:

```bash
aletheia search \
  --db ./aletheia.db \
  --namespace user/default \
  "response style"
```

Build context for an agent:

```bash
aletheia context-pack \
  --db ./aletheia.db \
  --namespace user/default \
  "How should I answer?"
```

## Development Verification

Run the test suite:

```bash
uv run --extra dev pytest
```

Run the generic release gate:

```bash
python scripts/release_gate.py --branch main
```

Run production readiness checks against a local database:

```bash
aletheia readiness check --db ./aletheia.db
```

## Uninstall

Uninstalling the package does not delete your database:

```bash
python -m pip uninstall aletheia-memory
```

Remove database, backup, or generated docs files separately only when you no
longer need them.
