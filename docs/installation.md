# Installation

This guide covers Aletheia 1.4.0, verifying the command line,
initializing a local database, and finding installed help. Follow the
[zero-model quickstart](quickstart.md) for the primary first-run journey:
evidence, candidate, explicit review, lexical context, provenance and reopen.
Memory needs neither Desktop nor Relay, and the core demo needs no models.

## Requirements

- Python 3.11 or newer.
- SQLite, provided by Python's standard `sqlite3` module.
- A writable local path for the Aletheia database.
- Optional: `uv` for repository development workflows.

The Python package name is `aletheia-memory`. The console script is named
`aletheia`.

## Install From PyPI

Install the published package:

```bash
python -m pip install aletheia-memory
```

Then verify the CLI:

```bash
aletheia --help
aletheia docs list
```

## 1.4.0 Upgrade And Packaged Starters

Use `python -m pip install aletheia-memory==1.4.0` for this release, or install
the reviewed `aletheia_memory-1.4.0-py3-none-any.whl` or matching source archive
by local path. Before publication, only the reviewed local artifacts are available.

Before opening any existing database, read the
[migration/backup guide](v1_4_0_migration_guide.md). Storage moves from 1.3.0 to
1.3.1; older software cannot open the upgraded database. Keep the pre-upgrade
backup and old binary for recovery. From the 1.4.0 environment:

```bash
aletheia examples create --type embedded --output ./memory-demo
cd memory-demo
python memory_demo.py
aletheia doctor --read-only --db ./aletheia-demo.db --namespace user/demo --query architecture
```

The starter creates a new database itself and refuses an existing one. See
[examples](examples.md) for the separate scoped HTTP agent/operator demo.

## Install From GitHub

For an unreleased source checkout, install the public repository directly:

```bash
python -m pip install "git+https://github.com/khaledgabal2/aletheia-memory.git"
```

The source checkout can contain unreleased changes. Prefer the PyPI package for
the published version.

## Install From A Release Wheel

Install a downloaded release artifact into your environment:

```bash
python -m pip install ./dist/aletheia_memory-1.4.0-py3-none-any.whl
```

Then verify the CLI:

```bash
aletheia --help
aletheia docs list
```

## Install From Source

From the repository root:

```bash
git clone https://github.com/khaledgabal2/aletheia-memory.git
cd aletheia-memory
python -m pip install -e ".[dev]"
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
record. It is a write operation, including when the file already exists.
The new 1.4 development mode reserves a fresh path and refuses existing files
or symlinks; read-only diagnostics never initialize a missing database:

```bash
aletheia init --new --db ./fresh-demo.db
aletheia doctor --read-only --db ./fresh-demo.db
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

## Trusted Operator CLI Reference

For the primary first-run experience, use the Python quickstart above. This
lower-level CLI example writes an already-reviewed, active memory directly;
it is not the candidate-first agent workflow:

```bash
aletheia remember \
  --db ./aletheia.db \
  --namespace user/default \
  --type preference \
  --subject user \
  --predicate prefers \
  --object "careful architecture notes"
```

Search it:

```bash
aletheia search \
  --db ./aletheia.db \
  --namespace user/default \
  --mode lexical \
  "architecture"
```

Build context for an agent:

```bash
aletheia context-pack \
  --db ./aletheia.db \
  --namespace user/default \
  --mode lexical \
  "architecture"
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
