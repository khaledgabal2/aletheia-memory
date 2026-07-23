Aletheia M8 Contract

Milestone: Production Hardening, Data Protection, Backup, Restore, and Release Readiness

⸻

1. Milestone Summary

M0 proved that Aletheia can remember.
M1 proved that Aletheia can recall across sessions and projects.
M2 proved that Aletheia can maintain trust through confidence, contradiction, decay, and curation.
M3 proved that Aletheia can ingest raw material and form candidate memories.
M4 proved that Aletheia can reason, infer, reflect, and preserve derivation lineage.
M5 proved that Aletheia can evaluate and improve itself safely.
M6 proved that Aletheia can serve local agents through HTTP and MCP.
M7 proved that Aletheia can be operated and governed through a local console.
M8 must prove that Aletheia can survive real-world production use.

M8 is where Aletheia becomes hardened.

M0 = Remember
M1 = Recall
M2 = Trust
M3 = Understand
M4 = Reason
M5 = Improve
M6 = Connect
M7 = Operate
M8 = Harden

The core M8 promise:

Aletheia can protect memory data, back itself up, restore reliably, encrypt sensitive content, enforce retention and deletion policies, verify database integrity, migrate safely, benchmark performance, package releases reproducibly, and provide local diagnostic bundles without leaking private memory.

M8 is not about adding more intelligence.
M8 is about making sure the intelligence does not lose, leak, corrupt, or rot the user’s memory.

⸻

2. M8 Name

M8 — Production Hardening

Fuller name:

M8 — Production Hardening, Data Protection, Backup, Restore, and Release Readiness

Recommended short name:

M8 — Production Hardening

⸻

3. M8 Contract Status

milestone: M8
name: Production Hardening
depends_on: M7
version_target: 0.9.0
stability: release-candidate
breaking_changes_allowed: minimal
storage_migration_required: yes
daemon_required: yes
console_required: yes
backup_required: yes
restore_required: yes
encryption_supported: yes
encryption_required_for_protected_mode: yes
cloud_required: no
external_telemetry_required: no
enterprise_acl_required: no
primary_theme: reliability_security_data_protection_release_readiness

Important clarification:

M8 must harden local production use.
M8 must not require cloud services.
M8 must not send telemetry by default.
M8 must not weaken any M0–M7 governance.
M8 must not treat backup, restore, encryption, or deletion as optional polish.

⸻

4. M7 Assumptions

M8 assumes M7 already provides:

- Local daemon
- HTTP API
- MCP server
- API tokens and capabilities
- Local console
- Review queue
- Memory browser
- Evidence viewer
- Context-pack inspector
- Retrieval traces
- Confidence/conflict/curation views
- Inference/reflection/derivation views
- Policy/procedure review
- Jobs and health reports
- Service logs
- Report exports
- All M0–M6 memory/kernel/service features

M8 strengthens the system beneath all of that.

It does not replace the memory kernel, service layer, or console. It hardens them.

⸻

5. M8 Primary Objective

M8 must make this flow work reliably:

aletheia backup create \
  --db ./aletheia.db \
  --output ./backups/aletheia-2026-06-30.alet \
  --encrypt

Then:

aletheia integrity check \
  --db ./aletheia.db

Then:

aletheia restore verify \
  --backup ./backups/aletheia-2026-06-30.alet

Then, on a fresh machine:

aletheia restore apply \
  --backup ./backups/aletheia-2026-06-30.alet \
  --target ./restored-aletheia.db

Expected behavior:

- Backup contains database, blobs, indexes metadata, schema version, manifests, checksums, and selected config.
- Backup can be encrypted.
- Restore verifies checksums before writing.
- Restore can run dry-run first.
- Restored database passes integrity checks.
- No unrestricted API token is created during restore.
- All evidence, claims, candidates, reflections, derivations, policies, jobs, audit records, and console metadata remain consistent.

M8 must also support protected-mode operation:

aletheia init \
  --db ./aletheia.db \
  --protected

Expected behavior:

- Sensitive content is encrypted at rest.
- Secret content is not written into plaintext indexes by default.
- Backup encryption is required by default.
- Dangerous deletion/redaction operations create tombstones and invalidate derived memory.

⸻

6. M8 Non-Negotiable Principles

6.1 No backup, no production

Aletheia should not call itself production-ready unless it can back up and restore.

Backup must be:

verifiable
portable
versioned
checksum-protected
optionally encrypted
restorable into a new database
auditable

⸻

6.2 Restore must be safer than backup

Backup creation matters, but restore correctness matters more.

M8 must test restore paths, not merely create backup files.

Every backup format must support:

manifest validation
schema version validation
checksum validation
dry-run restore
restore report
post-restore integrity check

⸻

6.3 Encryption must not be theater

Encryption must have a clear threat model.

M8 should distinguish:

encrypted backup archive
encrypted evidence/content fields
encrypted blob store
optional full-database encryption
plaintext operational metadata
plaintext indexes

If FTS or semantic indexes contain sensitive text, protected mode must either:

avoid indexing sensitive/secret content,
redact indexable text,
or require an explicitly enabled encrypted-index strategy.

Aletheia must not claim content is protected while duplicating it into plaintext search tables.

⸻

6.4 Raw keys must not be stored

Aletheia may store:

key identifiers
key metadata
salt
KDF parameters
key version
rotation events

It must not store raw passphrases or raw encryption keys in the database.

⸻

6.5 Deletion must propagate

If evidence is deleted or redacted, derived records must be invalidated or refreshed.

Deletion/redaction must propagate to:

claims
candidate claims
inferences
reflections
abstractions
semantic indexes
FTS indexes
context traces
reports
exports
backup manifests where applicable

⸻

6.6 Deletion has physical limits

Aletheia can delete or redact its own records and blobs.

It cannot honestly guarantee physical erasure from:

old backups
filesystem snapshots
SSD wear leveling
OS caches
external copies
logs exported elsewhere

The system must make this clear in deletion reports.

⸻

6.7 Migrations must be planned, reversible where possible, and testable

M8 must improve migration safety.

A migration should support:

plan
dry-run
backup-before-migrate
apply
verify
rollback when feasible
post-migration integrity check

Irreversible migrations must be marked clearly before execution.

⸻

6.8 Performance must be measured, not guessed

M8 must introduce benchmark profiles.

Performance regressions should be caught by tests and benchmark comparisons.

At minimum, benchmark:

write_event
remember
retrieve lexical
retrieve hybrid
context_pack
candidate extraction
confidence recomputation
backup create
restore verify
integrity check
daemon endpoint latency
console dashboard load

⸻

6.9 Diagnostics must be redacted by default

Support bundles must default to:

metadata only
redacted logs
schema information
version information
metrics
integrity findings
configuration without secrets

They must not include raw memory content unless explicitly requested.

⸻

6.10 Release artifacts must be reproducible enough to trust

M8 must formalize:

versioning
changelog
migration notes
dependency locks
package build checks
test matrix
release manifest
hashes
artifact verification

A production memory library needs boring release discipline.

⸻

7. M8 Scope

In Scope

M8 includes:

1. Backup service
2. Restore service
3. Backup verification
4. Backup manifests and checksums
5. Encrypted backup archives
6. Protected-mode initialization
7. Content encryption layer
8. Key provider interface
9. Key rotation records
10. Secret-safe indexing policy
11. Redaction and forget workflows
12. Retention policies
13. Tombstone model
14. Derived-memory invalidation after deletion/redaction
15. Database integrity checker
16. Index consistency checker
17. Audit consistency checker
18. Migration planner
19. Migration dry-run and verify
20. Backup-before-migrate option
21. Database compaction/vacuum workflow
22. Import/export archive format
23. Local support bundle export
24. Performance benchmarks
25. Soak/load test profiles
26. Release manifest
27. Compatibility matrix
28. Packaging hardening
29. Configuration profiles
30. Production readiness checklist
31. CLI and console support for all of the above
32. Migration from M7 to M8
33. Golden hardening tests

⸻

Out of Scope

M8 explicitly excludes:

Cloud backup
Cloud sync
Hosted key management
Enterprise SSO
Distributed replicas
Multi-node clustering
Remote team collaboration
Mobile app
External telemetry
Public hosted dashboard
Guaranteeing physical erasure from SSDs or third-party backups

M8 may prepare interfaces for future cloud or enterprise deployment, but it must remain local-first.

⸻

8. M8 Deliverables

8.1 Library Deliverables

- BackupService
- RestoreService
- BackupVerifier
- BackupManifest model
- RestoreRun model
- EncryptionService
- KeyProvider interface
- PassphraseKeyProvider
- EnvironmentKeyProvider
- FileKeyProvider
- Optional OSKeyringProvider
- KeyRotationService
- RedactionService
- ForgetService
- RetentionPolicyService
- TombstoneService
- IntegrityChecker
- IndexConsistencyChecker
- AuditConsistencyChecker
- MigrationPlanner
- MigrationVerifier
- DatabaseCompactor
- ImportExportService
- SupportBundleService
- BenchmarkRunner
- ReleaseManifest model
- ProductionReadinessChecker

⸻

8.2 Storage Deliverables

M8 adds:

- backup_manifests
- backup_items
- backup_verification_runs
- restore_runs
- encryption_key_records
- key_rotation_events
- protected_mode_config
- redaction_events
- deletion_tombstones
- retention_policies
- retention_runs
- integrity_check_runs
- integrity_findings
- index_consistency_runs
- migration_plans
- migration_runs
- compaction_runs
- export_manifests
- import_runs
- support_bundles
- benchmark_runs
- benchmark_results
- release_manifests
- production_readiness_checks

⸻

8.3 CLI Deliverables

M8 adds or improves:

aletheia backup
aletheia restore
aletheia encrypt
aletheia keys
aletheia redact
aletheia forget
aletheia retention
aletheia integrity
aletheia compact
aletheia export
aletheia import
aletheia support
aletheia benchmark
aletheia release
aletheia readiness
aletheia migrate plan
aletheia migrate verify

Existing M0–M7 CLI commands must remain valid.

⸻

8.4 Console Deliverables

M8 adds console pages or sections for:

Backup and Restore
Encryption and Keys
Redaction and Forget Requests
Retention Policies
Integrity Checks
Migration Plans
Performance Benchmarks
Support Bundles
Release/Version Information
Production Readiness

⸻

8.5 Test Deliverables

- Backup tests
- Restore tests
- Encrypted backup tests
- Key provider tests
- Key rotation tests
- Protected-mode tests
- Redaction tests
- Forget propagation tests
- Retention tests
- Integrity checker tests
- Migration planner tests
- Migration rollback tests where feasible
- Index consistency tests
- Import/export tests
- Support bundle redaction tests
- Benchmark harness tests
- Packaging/release tests
- Golden hardening tests

⸻

9. Backup Contract

9.1 Backup modes

M8 must support at least two backup modes.

Logical backup

Exports Aletheia objects through the application layer.

Includes:

evidence metadata
encrypted or redacted evidence content
claims
candidate claims
conflicts
confidence history
sessions
projects
entities
categories
semantic metadata
inferences
reflections
derivations
evaluations
policies
jobs
audit records
console/review metadata
service/auth metadata

Useful for portability.

⸻

Physical backup

Copies the SQLite database and managed blob directory safely.

Requires:

SQLite backup API or equivalent safe snapshot
WAL handling
manifest
checksums
schema version
post-backup verification

Useful for fast local recovery.

⸻

9.2 Backup archive format

M8 should define a portable archive extension:

.alet

Example:

aletheia-2026-06-30.alet

Archive contents:

manifest.json
database.sqlite or logical/*.jsonl
blobs/
indexes_metadata/
config_redacted.json
checksums.sha256
release_info.json

If encrypted:

manifest.json
encrypted_payload.bin
checksums.sha256
encryption_metadata.json

The manifest itself may contain non-sensitive metadata. Sensitive filenames, titles, or source URIs must be redacted when configured.

⸻

9.3 BackupManifest model

@dataclass
class BackupManifest:
    id: str
    namespace: str | None
    backup_type: str
    format_version: str
    schema_version: str
    created_at: datetime
    created_by: str
    encrypted: bool
    encryption_key_id: str | None
    db_path: str
    archive_path: str
    item_counts: dict
    checksums: dict
    privacy_mode: str
    includes_auth_metadata: bool
    includes_raw_content: bool
    metadata: dict

Allowed backup_type:

logical
physical
hybrid

Allowed privacy_mode:

full
redacted
metadata_only
namespace_filtered

⸻

9.4 memory.create_backup()

def create_backup(
    self,
    *,
    output_path: str,
    backup_type: str = "physical",
    namespace: str | None = None,
    encrypt: bool = True,
    privacy_mode: str = "full",
    include_auth_metadata: bool = True,
    include_indexes: bool = False,
    passphrase: str | None = None,
    key_id: str | None = None,
    verify_after: bool = True,
) -> BackupManifest:
    ...

Required behavior:

- Create consistent snapshot.
- Write manifest.
- Write checksums.
- Encrypt if requested.
- Exclude inaccessible namespaces if namespace-filtered.
- Verify backup if verify_after=True.
- Write audit event.
- Store backup manifest record.

⸻

9.5 memory.verify_backup()

def verify_backup(
    self,
    *,
    backup_path: str,
    passphrase: str | None = None,
    key_id: str | None = None,
    deep: bool = True,
) -> BackupVerificationRun:
    ...

Required checks:

archive readable
manifest valid
format version supported
schema version supported
checksums match
encrypted payload decrypts
required files present
object counts consistent
logical links valid

⸻

9.6 Backup CLI

aletheia backup create \
  --db ./aletheia.db \
  --output ./backups/aletheia.alet \
  --type physical \
  --encrypt
aletheia backup verify \
  --backup ./backups/aletheia.alet
aletheia backup list \
  --db ./aletheia.db
aletheia backup show bkp_001 \
  --db ./aletheia.db

⸻

10. Restore Contract

10.1 Restore modes

M8 must support:

restore to new database
restore over existing database with pre-restore backup
restore selected namespace from logical backup
restore dry-run

Default must be safest:

restore to new database

⸻

10.2 RestoreRun model

@dataclass
class RestoreRun:
    id: str
    backup_manifest_id: str | None
    backup_path: str
    target_db_path: str
    mode: str
    dry_run: bool
    verified_before_restore: bool
    restored_item_counts: dict
    warnings: list[str]
    status: str
    started_at: datetime
    finished_at: datetime | None
    metadata: dict

Allowed statuses:

planned
running
completed
failed
cancelled
verified

⸻

10.3 memory.restore_backup()

This may be implemented as a standalone function or service because it creates/opens a target DB.

def restore_backup(
    *,
    backup_path: str,
    target_db_path: str,
    mode: str = "new_database",
    namespace: str | None = None,
    passphrase: str | None = None,
    key_id: str | None = None,
    dry_run: bool = True,
    verify_before: bool = True,
    run_integrity_after: bool = True,
) -> RestoreRun:
    ...

Required behavior:

- Verify backup before restore unless explicitly disabled.
- Refuse overwrite unless mode allows it.
- Create pre-restore backup before in-place restore.
- Preserve audit records.
- Rebuild indexes if needed.
- Run integrity check after restore.
- Report warnings clearly.

⸻

10.4 Restore CLI

aletheia restore verify \
  --backup ./backups/aletheia.alet
aletheia restore dry-run \
  --backup ./backups/aletheia.alet \
  --target ./restored.db
aletheia restore apply \
  --backup ./backups/aletheia.alet \
  --target ./restored.db
aletheia restore namespace \
  --backup ./backups/aletheia.alet \
  --target ./aletheia.db \
  --namespace user/default/projects/aletheia

⸻

11. Encryption Contract

11.1 Protected mode

M8 introduces protected mode:

aletheia init --db ./aletheia.db --protected

Protected mode requires:

content encryption enabled
secret-safe indexing enabled
encrypted backups by default
request body logging disabled
support bundles redacted by default

⸻

11.2 Encryption targets

M8 must support encryption for:

evidence content
source document content
blob store files
backup archives
support bundles when requested
sensitive exported reports

M8 may support encryption for:

full database file
semantic vector blobs
selected metadata fields

Full database encryption may depend on optional backends, but content-level encryption must exist for protected mode.

⸻

11.3 Encryption metadata

Aletheia may store:

key_id
key_version
algorithm
salt
KDF parameters
created_at
rotated_at
status

Aletheia must not store:

raw passphrase
raw encryption key
unencrypted key material

⸻

11.4 KeyProvider interface

class KeyProvider(Protocol):
    name: str
    def get_key(self, key_id: str | None = None) -> bytes:
        ...
    def create_key(self, *, label: str, metadata: dict | None = None) -> str:
        ...
    def rotate_key(self, *, old_key_id: str, label: str | None = None) -> str:
        ...

Required providers:

PassphraseKeyProvider
EnvironmentKeyProvider
FileKeyProvider

Optional providers:

OSKeyringProvider
HardwareKeyProvider

Cloud KMS providers are out of scope for M8.

⸻

11.5 Secret-safe indexing

Protected mode must prevent sensitive and secret content from leaking into plaintext FTS or semantic indexes by default.

Allowed indexing policies:

index_public_and_personal_only
index_redacted_sensitive
no_sensitive_indexing
explicit_sensitive_indexing

Default protected-mode policy:

index_public_and_personal_only

⸻

11.6 Key rotation

def rotate_key(
    self,
    *,
    old_key_id: str,
    new_key_label: str,
    target: str = "content",
    dry_run: bool = True,
) -> KeyRotationEvent:
    ...

Required behavior:

- Identify encrypted records using old key.
- Re-encrypt with new key when dry_run=False.
- Preserve audit trail.
- Refuse rotation if backup is recommended and missing, unless forced.
- Write key rotation event.

⸻

11.7 Encryption CLI

aletheia encrypt status \
  --db ./aletheia.db
aletheia encrypt enable \
  --db ./aletheia.db \
  --protected
aletheia keys create \
  --db ./aletheia.db \
  --provider passphrase \
  --label local-protected-key
aletheia keys rotate \
  --db ./aletheia.db \
  --old-key key_001 \
  --label rotated-2026-06

⸻

12. Redaction, Forget, and Deletion Contract

12.1 Deletion modes

M8 must support distinct deletion modes.

Mode	Meaning
redact_content	Replace sensitive content with redaction marker, keep record
tombstone	Remove usable content, keep deletion marker and provenance shell
hard_delete	Delete Aletheia-managed record/blob where safe
namespace_forget	Apply deletion policy across a namespace
derived_invalidate	Invalidate derived memories without deleting source

Default for evidence:

tombstone

Default for claims:

archive or tombstone depending on reason

⸻

12.2 DeletionTombstone model

@dataclass
class DeletionTombstone:
    id: str
    namespace: str
    target_id: str
    target_type: str
    deletion_mode: str
    reason: str
    deleted_by: str
    created_at: datetime
    affected_derived_count: int
    backup_warning: str | None
    metadata: dict

⸻

12.3 memory.redact()

def redact(
    self,
    *,
    target_id: str,
    target_type: str,
    reason: str,
    replacement_text: str = "[REDACTED]",
    actor: str = "user",
    dry_run: bool = True,
) -> RedactionEvent:
    ...

Required behavior:

- Show affected records in dry-run.
- Redact target content when applied.
- Update or remove FTS entries.
- Update semantic index records.
- Invalidate derived records.
- Write audit event.
- Create redaction event.

⸻

12.4 memory.forget()

def forget(
    self,
    *,
    selector: dict,
    mode: str = "tombstone",
    reason: str,
    actor: str = "user",
    dry_run: bool = True,
) -> ForgetRun:
    ...

Selector examples:

{"namespace": "user/default/projects/old_project"}
{"target_type": "evidence", "target_id": "evt_001"}
{"privacy_level": "secret", "older_than_days": 365}

Required behavior:

- Dry-run by default.
- Show affected evidence, claims, candidates, inferences, reflections, indexes, reports.
- Require confirmation for destructive modes.
- Apply derived-memory invalidation.
- Write tombstones.
- Write audit events.
- Warn about old backups and external copies.

⸻

12.5 Forget CLI

aletheia forget preview \
  --db ./aletheia.db \
  --namespace user/default/projects/old_project
aletheia forget apply \
  --db ./aletheia.db \
  --namespace user/default/projects/old_project \
  --mode tombstone \
  --reason "Project no longer needed."
aletheia redact evidence evt_001 \
  --db ./aletheia.db \
  --reason "Contains secret credential-like content."

⸻

13. Retention Policy Contract

13.1 Purpose

Retention policies let users define how long different kinds of memory should remain active or stored.

⸻

13.2 RetentionPolicy model

@dataclass
class RetentionPolicy:
    id: str
    namespace: str | None
    memory_type: str | None
    privacy_level: str | None
    source_type: str | None
    action: str
    after_days: int
    enabled: bool
    reason: str
    created_at: datetime
    updated_at: datetime

Allowed actions:

archive
redact_content
tombstone
hard_delete
queue_review
lower_salience

Default should be conservative:

queue_review

not automatic deletion.

⸻

13.3 Retention CLI

aletheia retention policy create \
  --db ./aletheia.db \
  --namespace user/default/projects/temp \
  --memory-type session_summary \
  --after-days 90 \
  --action archive \
  --reason "Temporary project session summaries age out after 90 days."
aletheia retention run \
  --db ./aletheia.db \
  --namespace user/default \
  --dry-run
aletheia retention apply \
  --db ./aletheia.db \
  --namespace user/default

⸻

14. Integrity Check Contract

14.1 IntegrityChecker purpose

Aletheia must be able to inspect itself for corruption, orphaned records, index drift, and broken provenance.

⸻

14.2 Required integrity checks

M8 must check:

schema version valid
required tables exist
foreign-link consistency
claims have evidence unless explicitly allowed
candidate evidence spans valid
derived records have derivation edges
reflections have sources
tombstoned evidence not used as active support
invalidated records excluded from active context
FTS index consistency
semantic index consistency
content hashes match
backup manifest references valid
audit events exist for state-changing operations
policy active versions valid
token hashes present but raw tokens absent
review tasks target valid objects

⸻

14.3 IntegrityCheckRun model

@dataclass
class IntegrityCheckRun:
    id: str
    namespace: str | None
    scope: str
    status: str
    finding_count: int
    critical_count: int
    started_at: datetime
    finished_at: datetime | None
    metadata: dict

Allowed statuses:

passed
passed_with_warnings
failed
cancelled

⸻

14.4 IntegrityFinding model

@dataclass
class IntegrityFinding:
    id: str
    run_id: str
    severity: str
    finding_type: str
    target_id: str | None
    target_type: str | None
    message: str
    repairable: bool
    recommended_action: str | None
    created_at: datetime

Allowed severities:

info
low
medium
high
critical

⸻

14.5 Integrity CLI

aletheia integrity check \
  --db ./aletheia.db
aletheia integrity check \
  --db ./aletheia.db \
  --namespace user/default \
  --deep
aletheia integrity repair \
  --db ./aletheia.db \
  --finding intfind_001 \
  --dry-run

Repairs must be conservative and auditable.

⸻

15. Migration Hardening Contract

15.1 Migration planner

M8 must make migrations inspectable.

aletheia migrate plan \
  --db ./aletheia.db

Should show:

current schema
target schema
migration steps
irreversible steps
backup recommendation
estimated affected tables
dry-run support

⸻

15.2 MigrationPlan model

@dataclass
class MigrationPlan:
    id: str
    from_version: str
    to_version: str
    steps: list[dict]
    irreversible: bool
    backup_required: bool
    warnings: list[str]
    created_at: datetime

⸻

15.3 MigrationRun model

@dataclass
class MigrationRun:
    id: str
    plan_id: str
    from_version: str
    to_version: str
    dry_run: bool
    backup_manifest_id: str | None
    status: str
    started_at: datetime
    finished_at: datetime | None
    warnings: list[str]
    metadata: dict

⸻

15.4 Required migration behavior

- Dry-run must not mutate DB.
- Backup-before-migrate must be available.
- Migration must record run metadata.
- Post-migration integrity check must be available.
- Irreversible steps must be explicitly marked.
- Failed migrations must leave clear recovery instructions.

⸻

16. Compaction and Maintenance Contract

16.1 Purpose

Long-running memory systems accumulate stale records, deleted content, index drift, and storage bloat.

M8 must provide safe maintenance.

⸻

16.2 Required maintenance operations

VACUUM / compact database
rebuild FTS index
rebuild semantic index metadata
remove orphaned blobs
archive old logs
prune expired idempotency records
prune expired console sessions
prune old rate-limit records
refresh integrity snapshots

⸻

16.3 Compaction CLI

aletheia compact preview \
  --db ./aletheia.db
aletheia compact run \
  --db ./aletheia.db \
  --backup-before

Compaction should recommend backup first.

⸻

17. Import and Export Contract

17.1 Export modes

M8 must support export for portability.

Allowed modes:

full_archive
namespace_archive
project_archive
memory_only
evidence_only
redacted_report

⸻

17.2 Export formats

Required:

.alet
jsonl
markdown report

Optional:

sqlite snapshot
csv

⸻

17.3 ExportManifest model

@dataclass
class ExportManifest:
    id: str
    namespace: str | None
    export_type: str
    format: str
    file_path: str
    encrypted: bool
    privacy_mode: str
    item_counts: dict
    created_at: datetime
    metadata: dict

⸻

17.4 ImportRun model

@dataclass
class ImportRun:
    id: str
    source_path: str
    target_namespace: str | None
    dry_run: bool
    imported_counts: dict
    skipped_counts: dict
    conflict_count: int
    status: str
    started_at: datetime
    finished_at: datetime | None
    warnings: list[str]

⸻

17.5 Import behavior

Import must:

- Run dry-run by default.
- Validate manifest and checksums.
- Avoid duplicate evidence by content hash.
- Preserve provenance where possible.
- Avoid overwriting active claims without conflict handling.
- Create import audit event.
- Create candidate memories when imported trust is uncertain.

⸻

17.6 Export/import CLI

aletheia export namespace \
  --db ./aletheia.db \
  --namespace user/default/projects/aletheia \
  --output ./aletheia-project.alet \
  --encrypt
aletheia import dry-run \
  --db ./target.db \
  --input ./aletheia-project.alet \
  --namespace user/default/projects/aletheia
aletheia import apply \
  --db ./target.db \
  --input ./aletheia-project.alet \
  --namespace user/default/projects/aletheia

⸻

18. Support Bundle Contract

18.1 Purpose

A user may need to share diagnostics without sharing private memory.

M8 must support redacted support bundles.

⸻

18.2 Support bundle contents

Default support bundle may include:

version information
schema version
platform information
redacted config
table counts
integrity findings
health report
recent error logs
service request metadata
migration history
benchmark summary
extension/plugin list

Default support bundle must not include:

raw evidence content
raw claim object text
secret source URIs
raw API tokens
encryption keys
full request bodies
sensitive memory snippets

⸻

18.3 SupportBundle model

@dataclass
class SupportBundle:
    id: str
    file_path: str
    privacy_mode: str
    encrypted: bool
    includes_raw_content: bool
    created_at: datetime
    metadata: dict

⸻

18.4 Support CLI

aletheia support bundle \
  --db ./aletheia.db \
  --output ./aletheia-support.zip
aletheia support bundle \
  --db ./aletheia.db \
  --output ./aletheia-support-encrypted.zip \
  --encrypt

To include raw content, require explicit flag:

--include-raw-content

and confirmation.

⸻

19. Performance and Benchmark Contract

19.1 Purpose

M8 must make performance visible and regression-testable.

⸻

19.2 Benchmark profiles

Required benchmark profiles:

tiny
small
medium
large

Suggested sizes:

Profile	Claims	Evidence events	Reflections	Candidates
tiny	100	100	10	20
small	1,000	1,000	50	200
medium	10,000	10,000	500	2,000
large	100,000	100,000	5,000	20,000

Large benchmarks can be optional in CI but must be runnable locally.

⸻

19.3 Required benchmark operations

write_event
remember
retrieve_lexical
retrieve_hybrid
context_pack
candidate_extract_rule_based
confidence_recompute
detect_conflicts
build_reflection
trace_context_pack
backup_create
backup_verify
restore_dry_run
integrity_check
daemon_context_endpoint
console_dashboard_overview

⸻

19.4 BenchmarkRun model

@dataclass
class BenchmarkRun:
    id: str
    profile: str
    operation: str
    item_count: int
    duration_ms: int
    p50_ms: float | None
    p95_ms: float | None
    p99_ms: float | None
    memory_mb: float | None
    created_at: datetime
    metadata: dict

⸻

19.5 Benchmark CLI

aletheia benchmark run \
  --db ./bench.db \
  --profile small
aletheia benchmark compare \
  --baseline bench_001 \
  --candidate bench_002

Performance regressions should be visible before release.

⸻

20. Release and Packaging Contract

20.1 ReleaseManifest model

@dataclass
class ReleaseManifest:
    id: str
    version: str
    git_commit: str | None
    build_time: datetime
    python_versions: list[str]
    platform_targets: list[str]
    package_files: list[dict]
    dependency_lock_hash: str | None
    migration_range: str
    test_summary: dict
    benchmark_summary: dict
    created_at: datetime

⸻

20.2 Required release checks

Before an M8 release candidate:

unit tests pass
integration tests pass
migration tests pass
restore tests pass
encrypted backup tests pass
privacy/redaction tests pass
HTTP/MCP tests pass
console tests pass
benchmark smoke tests pass
package build succeeds
package install succeeds in clean environment
OpenAPI schema generated
CLI help generated
changelog updated
migration notes written

⸻

20.3 Packaging expectations

M8 should support:

pip install aletheia-memory

Optional extras:

pip install "aletheia-memory[server]"
pip install "aletheia-memory[mcp]"
pip install "aletheia-memory[console]"
pip install "aletheia-memory[crypto]"
pip install "aletheia-memory[dev]"

The core package should remain usable without heavyweight optional dependencies.

⸻

21. Production Readiness Contract

21.1 memory.readiness_check()

def readiness_check(
    self,
    *,
    namespace: str | None = None,
    profile: str = "local_production",
) -> ProductionReadinessCheck:
    ...

Required checks:

schema current
backup exists and verified
integrity check passed
auth enabled for daemon
no unrestricted tokens
protected mode status known
secret-safe indexing policy known
unresolved critical conflicts absent
no failed critical jobs
retention policy reviewed
migration history clean
console access secured
request logging privacy-safe
support bundle redaction available

⸻

21.2 Readiness statuses

ready
ready_with_warnings
not_ready
unknown

⸻

21.3 Readiness CLI

aletheia readiness check \
  --db ./aletheia.db

Expected output:

Production Readiness: ready_with_warnings
Warnings:
- No verified backup in the last 7 days.
- Protected mode is disabled.
- 2 stale core memories need review.

⸻

22. HTTP and Console API Additions

M8 extends M6/M7 HTTP API.

All endpoints remain under:

/v1

⸻

22.1 Backup/restore endpoints

POST /v1/backups
GET  /v1/backups
GET  /v1/backups/{backup_id}
POST /v1/backups/{backup_id}/verify
POST /v1/restore/verify
POST /v1/restore/dry-run
POST /v1/restore/apply

Restore apply requires high-risk confirmation and admin capability.

⸻

22.2 Encryption/key endpoints

GET  /v1/encryption/status
POST /v1/encryption/enable
GET  /v1/keys
POST /v1/keys
POST /v1/keys/{key_id}/rotate

⸻

22.3 Redaction/forget endpoints

POST /v1/redactions/preview
POST /v1/redactions/apply
POST /v1/forget/preview
POST /v1/forget/apply
GET  /v1/tombstones

⸻

22.4 Integrity/maintenance endpoints

POST /v1/integrity/check
GET  /v1/integrity/runs
GET  /v1/integrity/findings
POST /v1/integrity/repair
POST /v1/compact/preview
POST /v1/compact/run

⸻

22.5 Import/export/support/benchmark endpoints

POST /v1/exports
POST /v1/imports/dry-run
POST /v1/imports/apply
POST /v1/support/bundle
POST /v1/benchmarks/run
GET  /v1/benchmarks
GET  /v1/readiness

All must respect namespace, privacy, and capability constraints.

⸻

23. Storage Contract

23.1 Schema version

M8 updates schema version to:

0.9.0

⸻

23.2 Required new tables

backup_manifests

CREATE TABLE backup_manifests (
    id TEXT PRIMARY KEY,
    namespace TEXT,
    backup_type TEXT NOT NULL,
    format_version TEXT NOT NULL,
    schema_version TEXT NOT NULL,
    archive_path TEXT NOT NULL,
    encrypted INTEGER NOT NULL,
    encryption_key_id TEXT,
    privacy_mode TEXT NOT NULL,
    includes_auth_metadata INTEGER NOT NULL DEFAULT 1,
    includes_raw_content INTEGER NOT NULL DEFAULT 1,
    item_counts_json TEXT,
    checksums_json TEXT,
    created_by TEXT,
    created_at TEXT NOT NULL,
    metadata_json TEXT
);

⸻

backup_items

CREATE TABLE backup_items (
    id TEXT PRIMARY KEY,
    backup_id TEXT NOT NULL,
    item_type TEXT NOT NULL,
    item_id TEXT,
    checksum TEXT,
    size_bytes INTEGER,
    created_at TEXT NOT NULL,
    metadata_json TEXT
);

⸻

backup_verification_runs

CREATE TABLE backup_verification_runs (
    id TEXT PRIMARY KEY,
    backup_id TEXT,
    backup_path TEXT NOT NULL,
    status TEXT NOT NULL,
    deep INTEGER NOT NULL DEFAULT 1,
    finding_count INTEGER NOT NULL DEFAULT 0,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    warnings_json TEXT,
    metadata_json TEXT
);

⸻

restore_runs

CREATE TABLE restore_runs (
    id TEXT PRIMARY KEY,
    backup_manifest_id TEXT,
    backup_path TEXT NOT NULL,
    target_db_path TEXT NOT NULL,
    mode TEXT NOT NULL,
    dry_run INTEGER NOT NULL DEFAULT 1,
    verified_before_restore INTEGER NOT NULL DEFAULT 0,
    restored_item_counts_json TEXT,
    status TEXT NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    warnings_json TEXT,
    metadata_json TEXT
);

⸻

encryption_key_records

CREATE TABLE encryption_key_records (
    id TEXT PRIMARY KEY,
    provider TEXT NOT NULL,
    label TEXT NOT NULL,
    status TEXT NOT NULL,
    algorithm TEXT,
    kdf TEXT,
    key_version INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    rotated_at TEXT,
    metadata_json TEXT
);

No raw keys are stored here.

⸻

key_rotation_events

CREATE TABLE key_rotation_events (
    id TEXT PRIMARY KEY,
    old_key_id TEXT NOT NULL,
    new_key_id TEXT NOT NULL,
    target TEXT NOT NULL,
    dry_run INTEGER NOT NULL,
    affected_count INTEGER NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    metadata_json TEXT
);

⸻

protected_mode_config

CREATE TABLE protected_mode_config (
    id TEXT PRIMARY KEY,
    enabled INTEGER NOT NULL,
    content_encryption_enabled INTEGER NOT NULL,
    backup_encryption_required INTEGER NOT NULL,
    indexing_policy TEXT NOT NULL,
    request_logging_policy TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    metadata_json TEXT
);

⸻

redaction_events

CREATE TABLE redaction_events (
    id TEXT PRIMARY KEY,
    namespace TEXT NOT NULL,
    target_id TEXT NOT NULL,
    target_type TEXT NOT NULL,
    replacement_text TEXT,
    reason TEXT NOT NULL,
    actor TEXT NOT NULL,
    dry_run INTEGER NOT NULL,
    affected_counts_json TEXT,
    created_at TEXT NOT NULL,
    metadata_json TEXT
);

⸻

deletion_tombstones

CREATE TABLE deletion_tombstones (
    id TEXT PRIMARY KEY,
    namespace TEXT NOT NULL,
    target_id TEXT NOT NULL,
    target_type TEXT NOT NULL,
    deletion_mode TEXT NOT NULL,
    reason TEXT NOT NULL,
    deleted_by TEXT NOT NULL,
    affected_derived_count INTEGER NOT NULL DEFAULT 0,
    backup_warning TEXT,
    created_at TEXT NOT NULL,
    metadata_json TEXT
);

⸻

retention_policies

CREATE TABLE retention_policies (
    id TEXT PRIMARY KEY,
    namespace TEXT,
    memory_type TEXT,
    privacy_level TEXT,
    source_type TEXT,
    action TEXT NOT NULL,
    after_days INTEGER NOT NULL,
    enabled INTEGER NOT NULL DEFAULT 1,
    reason TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    metadata_json TEXT
);

⸻

retention_runs

CREATE TABLE retention_runs (
    id TEXT PRIMARY KEY,
    namespace TEXT,
    dry_run INTEGER NOT NULL,
    matched_count INTEGER NOT NULL,
    applied_count INTEGER NOT NULL,
    status TEXT NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    warnings_json TEXT,
    metadata_json TEXT
);

⸻

integrity_check_runs

CREATE TABLE integrity_check_runs (
    id TEXT PRIMARY KEY,
    namespace TEXT,
    scope TEXT NOT NULL,
    status TEXT NOT NULL,
    finding_count INTEGER NOT NULL,
    critical_count INTEGER NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    metadata_json TEXT
);

⸻

integrity_findings

CREATE TABLE integrity_findings (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    severity TEXT NOT NULL,
    finding_type TEXT NOT NULL,
    target_id TEXT,
    target_type TEXT,
    message TEXT NOT NULL,
    repairable INTEGER NOT NULL DEFAULT 0,
    recommended_action TEXT,
    created_at TEXT NOT NULL,
    metadata_json TEXT
);

⸻

index_consistency_runs

CREATE TABLE index_consistency_runs (
    id TEXT PRIMARY KEY,
    namespace TEXT,
    index_type TEXT NOT NULL,
    status TEXT NOT NULL,
    checked_count INTEGER NOT NULL,
    drift_count INTEGER NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    metadata_json TEXT
);

⸻

migration_plans

CREATE TABLE migration_plans (
    id TEXT PRIMARY KEY,
    from_version TEXT NOT NULL,
    to_version TEXT NOT NULL,
    steps_json TEXT NOT NULL,
    irreversible INTEGER NOT NULL,
    backup_required INTEGER NOT NULL,
    warnings_json TEXT,
    created_at TEXT NOT NULL,
    metadata_json TEXT
);

⸻

migration_runs

CREATE TABLE migration_runs (
    id TEXT PRIMARY KEY,
    plan_id TEXT,
    from_version TEXT NOT NULL,
    to_version TEXT NOT NULL,
    dry_run INTEGER NOT NULL,
    backup_manifest_id TEXT,
    status TEXT NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    warnings_json TEXT,
    metadata_json TEXT
);

⸻

compaction_runs

CREATE TABLE compaction_runs (
    id TEXT PRIMARY KEY,
    namespace TEXT,
    dry_run INTEGER NOT NULL,
    backup_manifest_id TEXT,
    size_before_bytes INTEGER,
    size_after_bytes INTEGER,
    status TEXT NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    warnings_json TEXT,
    metadata_json TEXT
);

⸻

export_manifests

CREATE TABLE export_manifests (
    id TEXT PRIMARY KEY,
    namespace TEXT,
    export_type TEXT NOT NULL,
    format TEXT NOT NULL,
    file_path TEXT NOT NULL,
    encrypted INTEGER NOT NULL,
    privacy_mode TEXT NOT NULL,
    item_counts_json TEXT,
    created_at TEXT NOT NULL,
    metadata_json TEXT
);

⸻

import_runs

CREATE TABLE import_runs (
    id TEXT PRIMARY KEY,
    source_path TEXT NOT NULL,
    target_namespace TEXT,
    dry_run INTEGER NOT NULL,
    imported_counts_json TEXT,
    skipped_counts_json TEXT,
    conflict_count INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    warnings_json TEXT,
    metadata_json TEXT
);

⸻

support_bundles

CREATE TABLE support_bundles (
    id TEXT PRIMARY KEY,
    file_path TEXT NOT NULL,
    privacy_mode TEXT NOT NULL,
    encrypted INTEGER NOT NULL,
    includes_raw_content INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    metadata_json TEXT
);

⸻

benchmark_runs

CREATE TABLE benchmark_runs (
    id TEXT PRIMARY KEY,
    profile TEXT NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    status TEXT NOT NULL,
    metadata_json TEXT
);

⸻

benchmark_results

CREATE TABLE benchmark_results (
    id TEXT PRIMARY KEY,
    benchmark_run_id TEXT NOT NULL,
    operation TEXT NOT NULL,
    item_count INTEGER,
    duration_ms INTEGER NOT NULL,
    p50_ms REAL,
    p95_ms REAL,
    p99_ms REAL,
    memory_mb REAL,
    created_at TEXT NOT NULL,
    metadata_json TEXT
);

⸻

release_manifests

CREATE TABLE release_manifests (
    id TEXT PRIMARY KEY,
    version TEXT NOT NULL,
    git_commit TEXT,
    build_time TEXT NOT NULL,
    python_versions_json TEXT,
    platform_targets_json TEXT,
    package_files_json TEXT,
    dependency_lock_hash TEXT,
    migration_range TEXT,
    test_summary_json TEXT,
    benchmark_summary_json TEXT,
    created_at TEXT NOT NULL,
    metadata_json TEXT
);

⸻

production_readiness_checks

CREATE TABLE production_readiness_checks (
    id TEXT PRIMARY KEY,
    namespace TEXT,
    profile TEXT NOT NULL,
    status TEXT NOT NULL,
    checks_json TEXT NOT NULL,
    warnings_json TEXT,
    recommendations_json TEXT,
    created_at TEXT NOT NULL,
    metadata_json TEXT
);

⸻

24. Console Contract

M8 console additions must include pages for:

Backups
Restore
Encryption
Keys
Redaction/Forget
Retention
Integrity
Migration
Compaction
Import/Export
Support Bundle
Benchmarks
Production Readiness

24.1 Backup page

Must show:

backup list
backup type
created date
encrypted status
schema version
item counts
verification status
restore action

24.2 Restore page

Must support:

verify backup
dry-run restore
restore to new DB
show warnings
show post-restore integrity result

24.3 Redaction/forget page

Must show:

affected records preview
derived-memory impact
index impact
backup warning
confirmation requirement
audit reason

24.4 Integrity page

Must show:

latest integrity check
findings by severity
repairable findings
recommended actions
run check button

24.5 Readiness page

Must show:

production readiness status
missing backup warning
auth status
protected mode status
critical conflicts
failed jobs
schema/migration status
recommendations

⸻

25. CLI Contract

25.1 aletheia backup

aletheia backup create \
  --db ./aletheia.db \
  --output ./backups/aletheia.alet \
  --encrypt
aletheia backup verify \
  --backup ./backups/aletheia.alet
aletheia backup list \
  --db ./aletheia.db

⸻

25.2 aletheia restore

aletheia restore dry-run \
  --backup ./backups/aletheia.alet \
  --target ./restored.db
aletheia restore apply \
  --backup ./backups/aletheia.alet \
  --target ./restored.db

⸻

25.3 aletheia encrypt and aletheia keys

aletheia encrypt status --db ./aletheia.db
aletheia encrypt enable --db ./aletheia.db --protected
aletheia keys create --db ./aletheia.db --provider passphrase --label main
aletheia keys rotate --db ./aletheia.db --old-key key_001

⸻

25.4 aletheia redact and aletheia forget

aletheia redact evidence evt_001 \
  --db ./aletheia.db \
  --reason "Contains sensitive content."
aletheia forget preview \
  --db ./aletheia.db \
  --namespace user/default/projects/old_project
aletheia forget apply \
  --db ./aletheia.db \
  --namespace user/default/projects/old_project \
  --mode tombstone \
  --reason "Project retired."

⸻

25.5 aletheia retention

aletheia retention policy create ...
aletheia retention run --dry-run ...
aletheia retention apply ...

⸻

25.6 aletheia integrity

aletheia integrity check --db ./aletheia.db
aletheia integrity repair --db ./aletheia.db --finding intfind_001 --dry-run

⸻

25.7 aletheia compact

aletheia compact preview --db ./aletheia.db
aletheia compact run --db ./aletheia.db --backup-before

⸻

25.8 aletheia export and aletheia import

aletheia export namespace \
  --db ./aletheia.db \
  --namespace user/default/projects/aletheia \
  --output ./aletheia-project.alet \
  --encrypt
aletheia import dry-run \
  --db ./target.db \
  --input ./aletheia-project.alet

⸻

25.9 aletheia support

aletheia support bundle \
  --db ./aletheia.db \
  --output ./support.zip

⸻

25.10 aletheia benchmark

aletheia benchmark run \
  --db ./bench.db \
  --profile small

⸻

25.11 aletheia release

aletheia release check
aletheia release manifest --output ./release-manifest.json

⸻

25.12 aletheia readiness

aletheia readiness check \
  --db ./aletheia.db

⸻

26. Backward Compatibility Contract

M8 must preserve M7 behavior.

The following must still work:

Library mode
CLI mode
Daemon mode
MCP mode
Console mode
All M0–M7 APIs
All M0–M7 CLI commands
All M6 HTTP API contracts
All M7 console routes

Allowed M8 changes:

- Add backup/restore APIs.
- Add encryption/protected-mode support.
- Add redaction/forget workflows.
- Add integrity checks.
- Add migration planning.
- Add benchmark and readiness tooling.
- Add package/release metadata.

Not allowed:

- Breaking existing local databases without migration.
- Requiring cloud services.
- Requiring encryption for non-protected existing installs without explicit migration.
- Silently changing indexing behavior without warning.
- Deleting or redacting data without dry-run or confirmation.
- Creating unrestricted tokens during backup/restore/migration.
- Sending diagnostic data externally by default.

⸻

27. Migration Contract

27.1 Migration path

M8 must support:

0.8.x → 0.9.0

⸻

27.2 Migration rules

- Existing evidence remains unchanged.
- Existing claims remain unchanged.
- Existing candidates remain unchanged.
- Existing service/auth/console data remains unchanged.
- New backup/encryption/integrity tables are added.
- Protected mode is not enabled automatically for existing installs.
- No backup is created automatically unless migration command uses --backup-before.
- No keys are created automatically unless requested.
- No data is encrypted automatically unless requested.
- No data is deleted or redacted automatically.
- Migration must be idempotent.

⸻

27.3 Recommended migration command

aletheia migrate plan --db ./aletheia.db

Then:

aletheia backup create \
  --db ./aletheia.db \
  --output ./backups/pre-m8.alet \
  --encrypt

Then:

aletheia migrate apply \
  --db ./aletheia.db \
  --to 0.9.0 \
  --verify-after

⸻

28. Test Contract

28.1 Backup tests

Required tests:

test_backup_create_physical
test_backup_create_logical
test_backup_manifest_contains_schema_version
test_backup_checksums_verify
test_backup_encrypted_payload_not_plaintext
test_backup_verify_detects_corruption
test_backup_records_audit_event

⸻

28.2 Restore tests

Required tests:

test_restore_dry_run_mutates_nothing
test_restore_to_new_database
test_restore_verifies_before_apply
test_restore_rebuilds_indexes
test_restore_preserves_claim_evidence_links
test_restore_preserves_derivation_edges
test_restore_preserves_policy_versions
test_restore_integrity_check_passes

⸻

28.3 Encryption tests

Required tests:

test_protected_mode_encrypts_evidence_content
test_raw_key_not_stored
test_passphrase_provider_unlocks_content
test_secret_content_not_written_to_fts_by_default
test_encrypted_backup_requires_key_to_restore
test_key_rotation_reencrypts_content
test_key_rotation_dry_run_mutates_nothing

⸻

28.4 Redaction and forget tests

Required tests:

test_redact_evidence_updates_content
test_redact_removes_fts_entry
test_redact_invalidates_derived_reflection
test_forget_preview_mutates_nothing
test_forget_apply_writes_tombstone
test_forget_warns_about_backups
test_hard_delete_requires_confirmation
test_deleted_evidence_not_used_as_active_support

⸻

28.5 Retention tests

Required tests:

test_retention_policy_create
test_retention_run_dry_run
test_retention_apply_archives_old_session_summaries
test_retention_does_not_delete_by_default
test_retention_writes_audit_event

⸻

28.6 Integrity tests

Required tests:

test_integrity_check_passes_clean_database
test_integrity_finds_orphan_claim_evidence_link
test_integrity_finds_missing_reflection_source
test_integrity_finds_fts_drift
test_integrity_finds_tombstoned_evidence_used_by_active_claim
test_integrity_finding_repair_dry_run

⸻

28.7 Migration tests

Required tests:

test_migration_plan_created
test_migration_dry_run_mutates_nothing
test_migration_backup_before_apply
test_migration_verify_after_apply
test_migration_from_m7_to_m8_adds_tables
test_migration_preserves_existing_data
test_migration_does_not_enable_protected_mode_automatically
test_migration_is_idempotent

⸻

28.8 Import/export tests

Required tests:

test_export_namespace_archive
test_export_redacted_report
test_import_dry_run_detects_duplicates
test_import_apply_preserves_provenance
test_import_uncertain_claims_as_candidates
test_import_writes_audit_event

⸻

28.9 Support bundle tests

Required tests:

test_support_bundle_created
test_support_bundle_redacts_raw_memory_by_default
test_support_bundle_excludes_raw_tokens
test_support_bundle_excludes_keys
test_support_bundle_encrypt_option

⸻

28.10 Benchmark tests

Required tests:

test_benchmark_tiny_profile_runs
test_benchmark_results_persisted
test_benchmark_compare_detects_regression

⸻

28.11 Console/API tests

Required tests:

test_console_backup_page_loads
test_console_integrity_page_loads
test_console_forget_requires_confirmation
test_api_backup_create_requires_admin
test_api_restore_apply_requires_confirmation
test_api_redaction_respects_privacy_and_capability

⸻

29. Golden M8 Tests

Golden test 1 — Backup and restore round trip

Given:

A database with evidence, claims, candidates, conflicts, reflections, policies, jobs, audit logs, and console review tasks.

When:

Backup is created and restored to a new database.

Expected:

- Restored DB passes integrity check.
- Claims still link to evidence.
- Reflections still expand to sources.
- Policies still have versions.
- Audit trail remains intact.
- No unrestricted token is created.

⸻

Golden test 2 — Protected mode prevents index leakage

Given:

Secret evidence content exists.
Protected mode is enabled.

When:

FTS index is rebuilt.

Expected:

- Secret content is not present in plaintext FTS.
- Retrieval does not expose secret content to lower privacy tokens.
- Integrity check confirms protected indexing policy.

⸻

Golden test 3 — Redaction invalidates derived memory

Given:

Reflection ref_001 depends on evidence evt_001.

When:

evt_001 is redacted.

Expected:

- evt_001 content is redacted.
- FTS/index entries are updated.
- ref_001 is marked stale or invalidated.
- Context pack does not present ref_001 as fresh.
- Audit explains why.

⸻

Golden test 4 — Corrupt backup is rejected

Given:

A backup archive with modified payload.

When:

restore verify runs.

Expected:

- Checksum mismatch detected.
- Restore apply is refused.
- Finding is recorded.

⸻

Golden test 5 — Support bundle is safe by default

Given:

Database contains personal and secret memories.

When:

support bundle is created with default settings.

Expected:

- Bundle contains version, schema, metrics, integrity findings.
- Bundle does not contain raw memory text.
- Bundle does not contain raw tokens or keys.
- Bundle records privacy mode as redacted.

⸻

Golden test 6 — Migration requires visible plan

Given:

A database at schema 0.8.x.

When:

aletheia migrate plan is run.

Expected:

- Plan shows 0.8.x → 0.9.0.
- New tables are listed.
- Irreversible steps are identified.
- Backup recommendation is shown.
- Dry-run makes no changes.

⸻

30. Acceptance Criteria

M8 is complete only when all of the following are true.

30.1 Backup acceptance

[ ] Backup creation works.
[ ] Backup verification works.
[ ] Encrypted backup works.
[ ] Backup manifest includes schema version, item counts, and checksums.
[ ] Backup records are auditable.

⸻

30.2 Restore acceptance

[ ] Restore dry-run works.
[ ] Restore to new database works.
[ ] Restore verifies backup first.
[ ] Restored DB passes integrity check.
[ ] Restore does not create unrestricted tokens.

⸻

30.3 Encryption acceptance

[ ] Protected mode exists.
[ ] Content encryption exists.
[ ] Raw keys are not stored.
[ ] Secret-safe indexing policy exists.
[ ] Key rotation works.
[ ] Encrypted backups require key/passphrase to restore.

⸻

30.4 Redaction/forget acceptance

[ ] Redaction preview works.
[ ] Redaction apply works.
[ ] Forget preview works.
[ ] Forget apply writes tombstones.
[ ] Derived records are invalidated.
[ ] Indexes are updated.
[ ] Backup limitations are clearly reported.

⸻

30.5 Retention acceptance

[ ] Retention policies can be created.
[ ] Retention dry-run works.
[ ] Retention apply works.
[ ] Retention defaults are conservative.
[ ] Retention actions are audited.

⸻

30.6 Integrity acceptance

[ ] Integrity check works.
[ ] Broken links are detected.
[ ] Index drift is detected.
[ ] Tombstone misuse is detected.
[ ] Findings have severity and recommendations.

⸻

30.7 Migration acceptance

[ ] Migration plan works.
[ ] Migration dry-run works.
[ ] Migration apply works.
[ ] Migration verify-after works.
[ ] M7 database migrates to M8.
[ ] Migration is idempotent.

⸻

30.8 Import/export acceptance

[ ] Namespace export works.
[ ] Redacted export works.
[ ] Import dry-run works.
[ ] Import preserves provenance.
[ ] Duplicate evidence is detected.

⸻

30.9 Support/readiness acceptance

[ ] Support bundle works.
[ ] Support bundle redacts content by default.
[ ] Readiness check works.
[ ] Readiness check warns about missing backup, auth weakness, protected-mode status, and integrity failures.

⸻

30.10 Performance/release acceptance

[ ] Benchmark runner works.
[ ] Benchmark results persist.
[ ] Release manifest works.
[ ] Package build/install checks pass.
[ ] Production readiness checklist exists.

⸻

30.11 Console/API acceptance

[ ] Console exposes backup/restore/integrity/encryption/readiness views.
[ ] Dangerous operations require confirmation.
[ ] HTTP endpoints are capability-gated.
[ ] Existing M7 console still works.

⸻

31. M8 Demo Script

This should be the official M8 demo.

⸻

Step 1 — Migrate from M7

aletheia migrate plan \
  --db ./aletheia.db

Expected:

Migration plan: 0.8.x → 0.9.0
Backup recommended.
No mutation performed.

Then:

aletheia backup create \
  --db ./aletheia.db \
  --output ./backups/pre-m8.alet \
  --encrypt

Then:

aletheia migrate apply \
  --db ./aletheia.db \
  --to 0.9.0 \
  --verify-after

⸻

Step 2 — Run integrity check

aletheia integrity check \
  --db ./aletheia.db \
  --deep

Expected:

Integrity check completed.
Status: passed or passed_with_warnings.

⸻

Step 3 — Enable protected mode

aletheia encrypt enable \
  --db ./aletheia.db \
  --protected

Expected:

Protected mode enabled.
Content encryption active.
Secret-safe indexing policy active.
Encrypted backups required by default.

⸻

Step 4 — Create encrypted backup

aletheia backup create \
  --db ./aletheia.db \
  --output ./backups/aletheia-m8.alet \
  --encrypt

Expected:

Backup created.
Manifest written.
Checksums written.
Verification passed.

⸻

Step 5 — Verify backup

aletheia backup verify \
  --backup ./backups/aletheia-m8.alet

Expected:

Backup verification passed.

⸻

Step 6 — Restore to a new DB

aletheia restore dry-run \
  --backup ./backups/aletheia-m8.alet \
  --target ./restored.db

Then:

aletheia restore apply \
  --backup ./backups/aletheia-m8.alet \
  --target ./restored.db

Expected:

Restore completed.
Post-restore integrity check passed.

⸻

Step 7 — Redact sensitive evidence

aletheia redact evidence evt_001 \
  --db ./aletheia.db \
  --reason "Contains sensitive content."

Expected:

Evidence redacted.
Derived records invalidated or queued for refresh.
FTS/index entries updated.
Audit event written.

⸻

Step 8 — Create support bundle

aletheia support bundle \
  --db ./aletheia.db \
  --output ./support.zip

Expected:

Support bundle created.
Raw memory content excluded.
Tokens and keys excluded.

⸻

Step 9 — Run readiness check

aletheia readiness check \
  --db ./aletheia.db

Expected:

Production Readiness:
ready or ready_with_warnings
Warnings clearly listed.

⸻

Step 10 — Run benchmark

aletheia benchmark run \
  --db ./bench.db \
  --profile small

Expected:

Benchmark completed.
Results persisted.

⸻

32. M8 Implementation Checklist

Backup and restore

[ ] Add BackupManifest model
[ ] Add BackupService
[ ] Add BackupVerifier
[ ] Add RestoreRun model
[ ] Add RestoreService
[ ] Implement physical backup
[ ] Implement logical backup
[ ] Implement encrypted backup
[ ] Implement restore dry-run
[ ] Implement restore apply
[ ] Implement post-restore integrity check

⸻

Encryption and keys

[ ] Add EncryptionService
[ ] Add KeyProvider interface
[ ] Add PassphraseKeyProvider
[ ] Add EnvironmentKeyProvider
[ ] Add FileKeyProvider
[ ] Add protected mode config
[ ] Add content encryption
[ ] Add encrypted blob support
[ ] Add secret-safe indexing policy
[ ] Add key rotation

⸻

Redaction and forget

[ ] Add RedactionService
[ ] Add ForgetService
[ ] Add DeletionTombstone model
[ ] Add redaction events
[ ] Update FTS after redaction
[ ] Update semantic indexes after redaction
[ ] Invalidate derived records after deletion/redaction
[ ] Add backup limitation warnings

⸻

Retention

[ ] Add RetentionPolicy model
[ ] Add retention dry-run
[ ] Add retention apply
[ ] Add conservative defaults
[ ] Add audit events

⸻

Integrity and maintenance

[ ] Add IntegrityChecker
[ ] Add IntegrityFinding model
[ ] Add index consistency checker
[ ] Add audit consistency checker
[ ] Add repair dry-run
[ ] Add database compaction
[ ] Add FTS rebuild
[ ] Add orphaned blob cleanup

⸻

Migration hardening

[ ] Add MigrationPlanner
[ ] Add migration plan CLI
[ ] Add migration dry-run
[ ] Add backup-before-migrate
[ ] Add verify-after-migrate
[ ] Add migration run records

⸻

Import/export/support

[ ] Add ExportManifest
[ ] Add ImportRun
[ ] Add .alet archive support
[ ] Add namespace export
[ ] Add import dry-run
[ ] Add import apply
[ ] Add support bundle service
[ ] Redact support bundles by default

⸻

Benchmarks and release

[ ] Add BenchmarkRunner
[ ] Add benchmark profiles
[ ] Add benchmark comparison
[ ] Add ReleaseManifest
[ ] Add release check command
[ ] Add readiness check
[ ] Add compatibility matrix

⸻

Console/API

[ ] Add backup/restore console pages
[ ] Add encryption/key console pages
[ ] Add redaction/forget console pages
[ ] Add integrity console page
[ ] Add readiness console page
[ ] Add M8 HTTP endpoints
[ ] Add capability checks
[ ] Add dangerous action confirmations

⸻

Tests

[ ] Backup tests
[ ] Restore tests
[ ] Encryption tests
[ ] Key rotation tests
[ ] Redaction tests
[ ] Forget tests
[ ] Retention tests
[ ] Integrity tests
[ ] Migration tests
[ ] Import/export tests
[ ] Support bundle tests
[ ] Benchmark tests
[ ] Console/API tests
[ ] Golden M8 tests

⸻

33. M8 Definition of Done

M8 is done when this statement is true:

Aletheia can protect, back up, restore, verify, migrate, redact, retain, benchmark, diagnose, and release its memory system without weakening provenance, auditability, privacy, or local control.

More practically, M8 is complete when Aletheia can do all of this:

- Create encrypted backups.
- Verify backups.
- Restore into a fresh database.
- Pass post-restore integrity checks.
- Run protected mode.
- Encrypt sensitive content.
- Avoid plaintext indexing of secret content.
- Rotate keys.
- Redact evidence safely.
- Forget namespaces or records with tombstones.
- Invalidate derived memories after deletion/redaction.
- Apply retention policies conservatively.
- Detect broken provenance or index drift.
- Plan and verify migrations.
- Compact and maintain the database.
- Export/import archives.
- Create redacted support bundles.
- Run benchmarks.
- Produce release manifests.
- Run production readiness checks.
- Preserve every M0–M7 behavior.

M8 is where Aletheia becomes hard to break.
Not because it remembers more, but because it can survive the things that eventually happen to every serious system: corruption, mistakes, migration, deletion, recovery, secrets, and time.