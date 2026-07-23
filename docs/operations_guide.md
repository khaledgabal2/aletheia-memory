# Operations Guide

This guide explains how to run, inspect, harden, and release Aletheia as a
local-first memory system.

## Operating Modes

Aletheia can run in several modes:

| Mode | Use when | Entry point |
| --- | --- | --- |
| In-process Python | A Python app can own the database connection. | `from aletheia import Memory` |
| CLI automation | A human or script is managing local state. | `aletheia ...` |
| HTTP sidecar | Other processes or languages need memory access. | `aletheia serve` |
| MCP tools | An MCP-capable agent host needs local memory tools. | `aletheia mcp` |
| Console | A local operator needs review, metrics, traces, and reports. | `aletheia console serve` |

Use the smallest boundary that fits your deployment. The HTTP service is the
cleanest boundary for multiple local agents.

## Database Setup

Initialize or migrate:

```bash
aletheia init --db ./aletheia.db
aletheia migrate plan --db ./aletheia.db
aletheia migrate apply --db ./aletheia.db --verify-after
```

Run integrity checks:

```bash
aletheia integrity check --db ./aletheia.db --namespace user/default --deep
```

Use WAL-backed file databases for normal local operation. Avoid letting many
uncoordinated long-running processes write the same database file directly;
prefer the HTTP service for that shape.

## Service Operation

Create a service client and token:

```bash
aletheia clients create --db ./aletheia.db --name local-agent --type agent

aletheia auth create-token \
  --db ./aletheia.db \
  --client local-agent \
  --namespace user/default \
  --capabilities memory:read,memory:context,memory:write_candidate,memory:feedback,memory:audit
```

Start the service on loopback:

```bash
aletheia serve \
  --db ./aletheia.db \
  --host 127.0.0.1 \
  --port 8765
```

Inspect routes and schema:

```bash
aletheia api routes --db ./aletheia.db
aletheia api openapi --db ./aletheia.db --output ./openapi.json
aletheia api ping --url http://127.0.0.1:8765
```

Inspect service state:

```bash
aletheia service status --db ./aletheia.db
aletheia service requests --db ./aletheia.db --limit 50
aletheia service mcp-log --db ./aletheia.db --limit 50
```

If the service binds to anything other than loopback, keep auth enabled, use
scoped tokens, and terminate TLS at an external reverse proxy.

## MCP Operation

List MCP tools:

```bash
aletheia mcp \
  --db ./aletheia.db \
  --namespace user/default \
  --mode read_write_candidate \
  --list-tools
```

Recommended modes:

- `read_only` for context-only agents.
- `read_write_candidate` for normal agents.
- `read_write_active` only for trusted tools.
- `admin` only for operational tools.

## Console And Review Queues

Run the console through the HTTP daemon:

```bash
aletheia console serve \
  --db ./aletheia.db \
  --host 127.0.0.1 \
  --port 8765
```

Create a login token:

```bash
aletheia console login-token --db ./aletheia.db
```

Review tasks and candidate queues:

```bash
aletheia reviews list --db ./aletheia.db --namespace user/default
aletheia candidates list --db ./aletheia.db --namespace user/default
```

Console state-changing calls use authenticated sessions and CSRF checks.

## Observability

Capture metric snapshots:

```bash
aletheia metrics snapshot --db ./aletheia.db --namespace user/default
aletheia metrics list --db ./aletheia.db --namespace user/default
```

Trace retrieval or context behavior:

```bash
aletheia traces retrieval \
  --db ./aletheia.db \
  --namespace user/default \
  --query "response style"

aletheia traces context \
  --db ./aletheia.db \
  --namespace user/default \
  --query "write the next milestone"
```

Export an operational report:

```bash
aletheia reports export \
  --db ./aletheia.db \
  --namespace user/default \
  --type memory_health \
  --format markdown \
  --output ./memory-health.md
```

## Backup And Restore

Create encrypted backups for production data:

```bash
aletheia backup create \
  --db ./aletheia.db \
  --namespace user/default \
  --output ./aletheia.alet \
  --encrypt \
  --passphrase "change-me"
```

Verify backups:

```bash
aletheia backup verify ./aletheia.alet --db ./aletheia.db --passphrase "change-me"
```

Dry-run restores before applying:

```bash
aletheia restore dry-run ./aletheia.alet \
  --db ./aletheia.db \
  --target-db ./restored.db \
  --passphrase "change-me"
```

## Protected Mode, Redaction, And Forget

Protected mode encrypts sensitive stored content when key material is available:

```bash
aletheia encrypt status --db ./aletheia.db
aletheia encrypt enable --db ./aletheia.db --protected
```

Protected content encryption currently applies to secret-tier evidence content.
Set key material with `ALETHEIA_PROTECTED_KEY` or `ALETHEIA_KEY_<key_id>` before
writing secret evidence. See `encryption_layer.md` for the full encryption
model.

Preview destructive privacy operations before applying:

```bash
aletheia redact evidence evt_... \
  --db ./aletheia.db \
  --reason "Remove sensitive source content."

aletheia forget preview \
  --db ./aletheia.db \
  --namespace user/default \
  --claim clm_... \
  --reason "User requested removal."
```

Apply only after checking the preview:

```bash
aletheia forget apply \
  --db ./aletheia.db \
  --namespace user/default \
  --claim clm_... \
  --reason "User requested removal." \
  --confirm yes
```

Forget and redaction workflows preserve auditability through tombstones and
audit records.

## Retention, Compaction, And Support

Create retention policies:

```bash
aletheia retention policy create \
  --db ./aletheia.db \
  --namespace user/default \
  --privacy-level personal \
  --action queue_review \
  --after-days 365 \
  --reason "Annual review of personal evidence."
```

Run retention:

```bash
aletheia retention run --db ./aletheia.db --namespace user/default
```

Preview compaction:

```bash
aletheia compact preview --db ./aletheia.db
```

Create a redacted support bundle:

```bash
aletheia support bundle --db ./aletheia.db --output ./aletheia-support.zip
```

## Stable Platform Operation

Run diagnostics:

```bash
aletheia doctor --db ./aletheia.db
aletheia compatibility report --db ./aletheia.db
aletheia contracts list --db ./aletheia.db
```

Manage plugins:

```bash
aletheia plugins discover ./plugins/demo --db ./aletheia.db
aletheia plugins install ./plugins/demo --db ./aletheia.db
aletheia plugins enable plug_... --db ./aletheia.db --reason "Local approved plugin."
aletheia conformance run --db ./aletheia.db --suite plugin --target plug_...
```

Generate docs and validate examples:

```bash
aletheia docs build --db ./aletheia.db --output ./site
aletheia docs test-examples --db ./aletheia.db
```

## Release Gate

Before a generic production release from `main`:

```bash
python scripts/release_gate.py --branch main
aletheia v1-gate run --db ./aletheia.db
aletheia release check --db ./aletheia.db
aletheia readiness check --db ./aletheia.db --namespace user/default
```

The generic baseline must not include product-specific integration paths. Keep
branch-only integrations isolated from `main`.

## Operator Checklist

- Database initializes and migrates cleanly.
- `doctor` reports healthy or known acceptable warnings.
- Auth is enabled for service use.
- Tokens have least-privilege capabilities and namespace grants.
- Normal agent writes are candidate-first.
- Backups are encrypted and verified.
- Restore has been dry-run for the release.
- Protected mode and key material are configured when sensitive evidence exists.
- Integrity and readiness checks pass.
- Docs are packaged and discoverable with `aletheia docs list`.
- Release gate passes on `main`.
