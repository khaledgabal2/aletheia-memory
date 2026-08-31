# Examples

Start with the [zero-model quickstart](quickstart.md). Its Python example works
with published 1.3.1. The generators and read-only diagnostics below require
**1.4.0 or later**; installing 1.3.1 does not add them.

## Embedded Python Starter

Generate a new directory, then run the packaged example:

```bash
aletheia examples create --type embedded --output ./memory-demo
cd memory-demo
python memory_demo.py
```

The program captures synthetic evidence, extracts a candidate, shows its source,
and waits for explicit approval. Only then does it produce lexical context,
show provenance and reopen persisted memory. Declining or closing input leaves
the candidate pending. No model, server, account, Desktop or Relay is needed.

## Scoped HTTP Agent Starter

From a separate working directory using the same installed 1.4.0 build:

```bash
aletheia examples create --type http-agent --output ./http-memory-demo
cd http-memory-demo
python operator_demo.py
```

This operator-owned program starts an authenticated disposable service on a
literal loopback address. It runs `agent.py` as a separate process with only
`memory:read`, `memory:context` and `memory:write_candidate`. The operator retains
the separate review credential, inspects the candidate and its source, and
decides whether to approve. The agent cannot promote candidates or write active
claims. Both tokens expire after 30 minutes and are revoked when the demo exits
normally. Tokens are not printed or written to configuration files. As with
other local processes, a privileged OS user can inspect process memory or environment.

The agent checks current-principal discovery and both `memory-read-v1` and `agent-onboarding-v1` before using
the service. The operator uses revision-checked `memory-review-v1` approval.
Creation and review each retain an explicit operation key. There are no
automatic write retries; uncertain writes require operator inspection.

The generated README explains how to run the agent against an independently
operated, trusted Memory service. The self-contained demo needs no other product
and no model provider. Optional models have a separate [local recipe guide](v1_4_0_local_model_recipes.md).

## TypeScript Agent Starter

Install Node 22+ (verified with Node 26.0.0) only if using this starter. The
Python engine itself does not require Node. From another fresh directory:

```sh
aletheia examples create --type typescript-agent --output ./typescript-memory-demo
cd typescript-memory-demo
npm ci --ignore-scripts --no-audit --no-fund
npm run check
npm run build
python operator_demo.py
```

`npm ci` deliberately downloads the dependencies pinned in the packaged lockfile.
The starter includes generated contract types; no repository or global generator
is needed. A separate TypeScript process gets only the agent credential. It
checks identity/profiles, creates a candidate with an explicit operation key,
reads empty trusted context before approval, and reads context/provenance after
the Python operator makes a revision-checked decision. Both languages exercise
the same real local service. The generated README describes independent use.

## Inspect And Rerun Safely

All three generators refuse any existing output directory. All demos refuse any
existing database, including symlinks or orphaned WAL/SHM/journal files. Preserve
those companion files for possible recovery. To repeat a demo, use a different empty
directory. Retain the old database until you decide it is no longer needed.
No existing project, configuration or database is replaced.

After the embedded demo:

```bash
aletheia doctor --read-only --db ./aletheia-demo.db --namespace user/demo --query architecture
```

For the HTTP demo, use `./aletheia-http-demo.db` after it stops. Diagnostics
do not promote, migrate or repair anything. See [troubleshooting](troubleshooting.md)
for pending review, query mismatch, permissions and optional provider checks.

## Installed Help And Legacy Adapter Templates

List installed help:

```bash
aletheia docs list
aletheia docs show index
```

The older adapter scaffolds remain available. Unlike the new standalone
starters, these commands open the selected database and register their output:

```bash
aletheia examples create --db ./aletheia.db --type python-sdk --name python-sdk-agent --output ./examples/python-sdk-agent
aletheia examples test --db ./aletheia.db
```

Existing output directories are now refused for these templates too. Choose a
new path instead of relying on the old overwrite behavior.

Build generated docs and check example registrations:

```bash
aletheia docs build --db ./aletheia.db --output ./site
aletheia docs status --db ./aletheia.db
```

`examples test` and `docs test-examples` check registered example metadata;
they do **not** execute the tutorial. The Phase 3 installed-package gate
(`scripts/v1_4_onboarding_check.py`) executes the actual packaged documentation
and the Python starters outside the checkout; `--typescript` additionally compiles and runs the installed TypeScript starter, including approval and refusal paths.

List registered legacy examples:

```bash
aletheia examples list --db ./aletheia.db
```
