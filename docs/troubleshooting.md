# Troubleshooting

Use this guide when installation, database setup, service access, retrieval,
docs, or release checks do not behave as expected.

## Start With Diagnostics

Run:

```bash
aletheia doctor --db ./aletheia.db
aletheia readiness check --db ./aletheia.db --namespace user/default
aletheia integrity check --db ./aletheia.db --namespace user/default --deep
```

If the service is running:

```bash
aletheia api ping --url http://127.0.0.1:8765
aletheia service status --db ./aletheia.db
```

## `aletheia` Command Not Found

Confirm the package is installed in the environment you are using:

```bash
python -m pip show aletheia-memory
python -m pip install aletheia-memory
```

From a source checkout, either install the package:

```bash
python -m pip install ".[dev]"
```

or run through `uv`:

```bash
uv run --extra dev aletheia --help
```

## Installed Docs Are Missing

Check the docs root:

```bash
aletheia docs path
aletheia docs list
```

If this fails after installing from a wheel, the wheel was likely built without
package data. Rebuild from a source tree that includes `docs/` and the
`tool.hatch.build.targets.wheel.force-include` mapping in `pyproject.toml`.

From source, the CLI falls back to the repository `docs/` directory.

## Database Does Not Exist

Initialize it:

```bash
aletheia init --db ./aletheia.db
```

Most commands create or migrate the database when they open it, but explicit
initialization is easier to diagnose.

## Migration Fails

Preview first:

```bash
aletheia migrate plan --db ./aletheia.db
```

Apply with backup and verification:

```bash
aletheia migrate apply \
  --db ./aletheia.db \
  --backup-before \
  --backup-output ./pre-migration.alet \
  --verify-after
```

Then run:

```bash
aletheia migrate verify --db ./aletheia.db --deep
```

## Search Returns Nothing

Check these conditions:

- You are using the right `--namespace`.
- The claim status is included by the search.
- The query matches stored subject, predicate, object, or content.
- You did not filter by the wrong `--type`, `--project`, `--session`, or category.
- The claim was promoted from candidate state.

Inspect claims:

```bash
aletheia claims list --db ./aletheia.db --namespace user/default
aletheia candidates list --db ./aletheia.db --namespace user/default
```

For semantic or hybrid search, verify the index:

```bash
aletheia index status --db ./aletheia.db --namespace user/default
aletheia index verify --db ./aletheia.db --namespace user/default
```

## Context Pack Omits Expected Memory

Try a wider budget and inspect warnings:

```bash
aletheia context-pack \
  --db ./aletheia.db \
  --namespace user/default \
  --token-budget 3000 \
  --include-candidate-warnings \
  "your query"
```

Trace context selection:

```bash
aletheia traces context \
  --db ./aletheia.db \
  --namespace user/default \
  --query "your query"
```

Check whether the memory is disputed, archived, rejected, scoped to another
project/session, stale under policy, or below confidence filters.

## Candidate Did Not Become A Claim

Candidates require promotion:

```bash
aletheia candidates show cand_... --db ./aletheia.db
aletheia candidates promote cand_... --db ./aletheia.db --reason "Reviewed against source."
```

If promotion fails, inspect evidence and risk flags. Candidate promotion can be
blocked when governance checks fail.

## API Returns Unauthorized Or Forbidden

Create a client and token:

```bash
aletheia clients create --db ./aletheia.db --name local-agent --type agent

aletheia auth create-token \
  --db ./aletheia.db \
  --client local-agent \
  --namespace user/default \
  --capabilities memory:read,memory:context,memory:write_candidate,memory:feedback,memory:audit
```

Verify that:

- The `Authorization: Bearer ...` header is present.
- The token has a namespace grant for the requested namespace.
- The token privacy ceiling is high enough for the requested data.
- The token capability matches the route.
- State-changing requests include any required idempotency or console CSRF state.

## Service Will Not Start

Check whether the port is already in use and whether the DB path is writable:

```bash
aletheia serve --db ./aletheia.db --host 127.0.0.1 --port 8765
```

Use another port if needed:

```bash
aletheia serve --db ./aletheia.db --host 127.0.0.1 --port 8766
```

For non-loopback binding, pass `--allow-remote` intentionally and keep auth
enabled. Do not expose unauthenticated memory routes to a network.

## Protected Mode Cannot Write Sensitive Content

Protected mode requires key material. Check status:

```bash
aletheia encrypt status --db ./aletheia.db
aletheia keys list --db ./aletheia.db
```

For passphrase-based backup encryption, provide the same passphrase to verify
and restore commands.

## Backup Verification Fails

Use the exact passphrase or key ID used for creation:

```bash
aletheia backup verify ./aletheia.alet --db ./aletheia.db --passphrase "change-me"
```

Try a shallow check only when diagnosing archive readability:

```bash
aletheia backup verify ./aletheia.alet --db ./aletheia.db --shallow
```

Do not restore from an archive that does not verify.

## Plugin Is Blocked

Inspect the manifest, installation, and logs:

```bash
aletheia plugins show plug_... --db ./aletheia.db
aletheia plugins logs plug_... --db ./aletheia.db
```

Common causes:

- Manifest is missing required fields.
- Plugin compatibility does not match Aletheia v1.3.0.
- Required permissions were not approved at enable time.
- The plugin tried a high-risk operation such as active claim writing.

Run conformance:

```bash
aletheia conformance run --db ./aletheia.db --suite plugin --target plug_...
```

## Release Gate Fails On `main`

Run:

```bash
python scripts/release_gate.py --branch main
```

The generic production baseline rejects product-specific integration paths.
Keep personal or product-specific layers on a branch or fork.

Also run:

```bash
aletheia v1-gate run --db ./aletheia.db
aletheia release check --db ./aletheia.db
```

## Need A Support Bundle

Create a redacted bundle:

```bash
aletheia support bundle --db ./aletheia.db --output ./aletheia-support.zip
```

Use `--include-raw-content` only in trusted local debugging contexts where raw
memory content is safe to share.
