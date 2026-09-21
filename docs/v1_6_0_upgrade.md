# Memory 1.6.0 beta upgrade

1.6.0 contains the 29 audit repairs and nine follow-up corrections to access,
privacy, deletion, federation, ranking, and provider execution. All Memory
releases so far are beta, intended for development and evaluation. This release
keeps Python 3.11+, API v1, and storage schema 1.3.1; it tightens behavior that
previously accepted unsafe or ineffective requests.

## Choose how to handle existing beta data

For disposable experiments, stop the old daemon and start with a new database
path. Keep any old files you want to inspect separately; there is no need to
delete them or run a historical recovery campaign simply to try the new beta.
After installing 1.6.0:

```bash
aletheia init --new --db ./aletheia-1.6-beta.db
aletheia doctor --read-only --db ./aletheia-1.6-beta.db
aletheia serve --db ./aletheia-1.6-beta.db
```

Use a path that does not already exist. Re-pair clients and recreate only the
grants and peer relationships needed for the new database. Import only reviewed
source data when starting fresh; restoring the old database brings its old
records with it. This procedure does not erase external copies or revoke
credentials on an old service left running.

For data you want to retain:

1. Stop writers. Keep the previous environment and a verified encrypted backup
   before opening the database with the new version. Retain the protected
   content keys and pairing/federation identity material needed for recovery.
2. Install the reviewed 1.6.0 wheel in a separate environment, or use
   `python -m pip install 'aletheia-memory==1.6.0'` there. A new
   environment also installs the patched cryptography dependency.
3. Run `aletheia doctor --read-only --db /path/to/existing.db`, then start the
   new service on the same database path. Upgrading from 1.5.0 requires no
   storage migration. Keep writers stopped if diagnosis reports a problem.
4. Check the namespace and privacy grants used by your clients, read a known
   reviewed memory, exercise candidate review, and check any enabled federation
   transfer before resuming ordinary use. Retry denied operations only after
   resolving the underlying authorization or provenance issue.

For older storage, use the [backup and migration procedure](v1_4_0_migration_guide.md).
For a restored/moved database or missing identity files, follow
[pairing recovery](local_pairing_v1.md#recovery-and-downgrade). Reverting to an
older binary also restores its bugs; storage compatibility is not a recommended
security rollback.

## Compatibility changes to check

| Area | What a client or operator may need to change |
| --- | --- |
| HTTP access | Supply an explicit namespace for scoped operational lists. Source and target checks now apply to conflict/review operations and cached responses as well as ordinary reads. A previously successful cached response may now be denied without repeating its mutation. |
| Session summaries | Summaries default to reviewable candidates. Active writes require the explicit active mode and active-write capability. |
| HTTP Python providers | Select an enabled, approved `llm_provider` installation by ID or name. Sources, current access, and provider permissions are checked before results are used. |
| Reports and traces | Reports filter before aggregation. Legacy metric snapshots without verified scope metadata are excluded; generate a new snapshot with namespace-wide authority. Context traces use the active budget unless explicitly overridden. |
| Federation | Claims-only exports retain privacy labels. Re-export older claims-only bundles that lack labels. Evidence export requires `read_evidence`; `read` alone authorizes claims. Changed or unmapped historical imports require review. |
| Deletion and reimport | Forget modes now apply their stated effects and tracked derivatives are scrubbed or invalidated. Old bundles cannot recreate mapped deleted content; deletion notices cover only actually disclosed objects. |
| Backups | Encrypted JSONL and physical backups that claim to exclude authentication metadata are rejected. Use encrypted `.alet` archives and logical export where appropriate. |
| Adapters and policies | Structural adapter checks no longer stand in for behavioral verification. Applied ranking/context policies execute during reads and evaluation. Unsupported conflict strategies fail without success receipts. |

See [HTTP boundaries](service_access_boundaries.md),
[storage and deletion](storage_privacy_boundaries.md),
[retrieval and providers](retrieval_execution_boundaries.md), and
[behavior verification](behavior_verification.md) for detailed contracts.

## Historical data and sharing

Opening an existing database removes redundant span/risk text for already
encrypted sources. It does not retroactively correct all imported privacy
labels, recover lost keys, or remove old exports, backups, or recipient copies.

If you used real sensitive data with the affected import/sharing features,
review the relevant retained copies and grants. Use the existing
[security/privacy guide](security_privacy_guide.md) and
[federation key recovery procedure](federation_key_recovery.md) when applicable.
Beta status alone does not prove exposure, and it does not prove absence of
exposure. Disposable local experiments can use the fresh-start option above.

A general historical-data scanner and production deployment certification are
outside the scope of this beta release. The
[release verification record](v1_6_0_release_verification.md) distinguishes
completed package checks from publication and post-installation follow-up.
