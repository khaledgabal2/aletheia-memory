# Upgrade to Aletheia Memory 1.8.0

Python remains 3.11+, API v1 and the storage marker remains 1.3.1. Stop writers,
retain the old environment and make an authenticated backup before opening data
with the new default `Memory.open()`, which can automatically migrate it. Rehearse
restore into a separate private location using the [operations guide](operations_guide.md).

```sh
python -m pip install --upgrade aletheia-memory==1.8.0
aletheia --help
```

## Existing databases

The predicate declaration table and trigger inventory are additive schema changes,
including for 1.7.0 databases already marked 1.3.1. Services configured with
`auto_migrate=False` refuse an incomplete schema. Before starting them, apply the
migration with the new environment and an unused private backup destination:

```sh
aletheia migrate apply --db /absolute/path/memory.db --backup-before \
  --backup-output /absolute/private/path/pre-1.8.0.alet --verify-after
```

Follow the [migration guide](v1_4_0_migration_guide.md) for passphrase handling,
verification and recovery. Retain the backup, passphrase and matching older binary.
Do not reopen upgraded data with older software for rollback; restore the older
backup instead. Normal restarts preserve pairing credentials; restored/relocated
databases require fresh pairing because TLS identity binds to the database file.

## Predicate policy and caller changes

Undeclared predicates remain `single`; declare genuine set membership explicitly:

```python
from aletheia import Memory

memory = Memory.open("/absolute/path/memory.db")
try:
    memory.set_predicate_semantics("likes", cardinality="multiple", namespace="personal")
finally:
    memory.close()
```

Declarations are namespace-scoped and apply to future detection/screening. Review
existing disputed families explicitly; declaration changes do not rewrite prior
resolutions. HTTP changes require admin access and an explicit namespace. See the
[HTTP reference](http_api_reference.md) and [CLI reference](cli_reference.md).

Conflict detection now enforces namespace-wide review authorization before mutation.
Project-only grants cannot run namespace-wide detection. Single-valued third
assertions join unresolved disputes, and malformed or incomplete resolution outcomes
raise validation errors atomically. Integrations must handle these refusals. If an
application pins Aletheia, update that dependency and run its integration checks.
