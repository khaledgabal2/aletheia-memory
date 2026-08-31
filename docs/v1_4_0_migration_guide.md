# Review storage upgrade and recovery

The published Memory 1.3.1 binary uses storage 1.3.0. The 1.4.0 implementation
uses storage **1.3.1**. Do not equate the storage marker with the software version.
Retain a matching older binary and a verified encrypted backup before upgrading.
Default `Memory.open()` can migrate, so make the backup before opening the old
database that way. Stop ordinary writers during a planned upgrade.

The new CLI's `backup` and `migrate` commands open existing nonempty databases
without an implicit upgrade. `migrate apply --backup-before` therefore captures
the previous schema before changing it. Migration is atomic; a failure rolls
back schema creation, backfills, triggers and version marking. Planning records
an operational plan row; use `doctor --read-only` for a non-mutating inspection.

For passphrase entry without putting it in shell history or process arguments,
run this with the **new** Python environment and your existing database path:

```python
from getpass import getpass
from pathlib import Path
from aletheia import Memory

database = Path(input("Existing database path: ")).expanduser()
if not database.is_file() or database.stat().st_size == 0:
    raise SystemExit("An existing nonempty database is required.")
archive = Path(input("New encrypted backup path: ")).expanduser()
if archive.exists():
    raise SystemExit("Choose a new backup path.")
memory = Memory.open(str(database), auto_migrate=False)
try:
    print(memory.migration_plan())
    if input("Apply this migration? Type migrate: ").strip() != "migrate":
        raise SystemExit("No migration applied.")
    result = memory.migration_apply(
        backup_before=True, backup_output=str(archive),
        passphrase=getpass("Backup passphrase: "), verify_after=True,
    )
    print(result.status)
finally:
    memory.close()
```

Keep the archive and passphrase securely. Check the reported verification and
perform a restore rehearsal on a separate destination. Do not edit the schema
version marker to force a downgrade. Default older binaries refuse the new
storage. `auto_migrate=False`, raw SQLite access and manual DDL are not supported
ways to make an older binary safe on upgraded data. Every application table must
be classified in the trigger inventory; adding extension tables directly can
make the schema integrity check fail. Missing or altered review triggers must
be repaired through explicit migration, not bypassed by a service startup flag.

For rollback, stop the new service and use the retained **published 1.3.1 Python
environment** to restore the pre-upgrade archive to a fresh path:

```python
from getpass import getpass
from aletheia.core.hardening import restore_backup

result = restore_backup(
    backup_path=input("Pre-upgrade archive: "),
    target_db_path=input("New recovery database path: "),
    mode="new_database", passphrase=getpass("Backup passphrase: "),
    dry_run=False,
)
print(result.status)
```

Open the recovered file with that older binary and verify retrieval, evidence,
candidates and permissions before switching service paths. Opening it with the
new default binary will upgrade it again. New-version writes made after the
backup are absent from this recovery; preserve them separately if needed.

Restoring with the new binary uses SQLite's backup API, preserving WAL-backed
state and avoiding raw replacement of a live database file. Existing-target
overwrite/in-place modes create a separate pre-restore snapshot. The prepared
restore receives a new generation and no replay receipts before it is exposed;
a running service detects this and changes its cache identity. Refresh all
clients and request new decisions after restore. Stop writers first when
possible; a copy stalled by locks for ten seconds fails safely and can be retried.
See [SQLite backup semantics](https://www.sqlite.org/backup.html) and
[Python's backup API](https://docs.python.org/3/library/sqlite3.html#sqlite3.Connection.backup).

The actual published-binary migration/recovery check is reproducible with:

```sh
python -m scripts.v1_4_migration_check --legacy-package .legacy-1.3.1
```

It uses disposable data, checks the published module hashes, preserves domain
and permission rows, verifies retrieval/provenance, tests older-binary refusal,
and restores the encrypted pre-upgrade backup using the older implementation.
