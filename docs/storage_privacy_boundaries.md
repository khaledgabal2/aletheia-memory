# Storage Privacy, Imports, And Deletion

These rules apply to the embedded API and the CLI/HTTP operations that call it.
They tighten storage behavior without changing the database schema.

## Protected source text

Protected mode encrypts evidence content labeled `private`, `sensitive`, or
`secret`. Evidence spans for encrypted sources retain offsets and omit their
redundant text. Candidate reads reconstruct the span from the decrypted source.
Extraction, service, plugin, and federation candidate writers follow this rule.
Content-risk flags also omit protected span text while retaining classification
and offsets.

Opening a database clears existing span and risk-flag text copies whose source
is already encrypted. This repair does not need the content key; reading the
protected source still does. It does not encrypt claim/candidate summaries,
titles, or all other metadata, and it does not erase older SQLite pages, WALs,
backups, or external copies. Use disk encryption for whole-file protection.

## Export and backup choices

| Requested operation | Behavior |
| --- | --- |
| JSONL with `encrypt=True` | Rejected before writing the output or recording a successful export. Use `.alet`. |
| JSONL while protected mode requires encrypted backups | Rejected, including `encrypt=False`. |
| Plain JSONL without an encryption requirement | Available; manifest reports `encrypted=False`. |
| Logical `redacted` or `metadata_only` export | Includes reviewed structural columns only, excluding source/claim/reflection text, titles, descriptions, reasons, and arbitrary JSON. |
| Physical/hybrid backup with `include_auth_metadata=False` | Rejected; a SQLite snapshot cannot promise to exclude authentication records. Use a logical backup. |
| Logical `namespace_filtered` export | Requires an explicit namespace; evidence links are restricted to that namespace too. |

Structural exports still contain identifiers, namespace/project identifiers,
timestamps, status, counts, and operational manifest fields such as paths.
They are not anonymous datasets. Review them before sharing.

## Import identity and provenance

`import_archive` accepts full or namespace-filtered `.alet` backups, including
logical, physical, and hybrid payloads. Redacted/metadata-only archives are for
inspection, not for reconstructing source content. Import is a content merge
of evidence and claims; use the separate restore operation for a whole database.

Imported claims link to all their source evidence, including evidence reached
through derivation edges. Missing provenance, cross-namespace evidence, and
missing privacy labels cause rejection. Identical text does not merge sources
with different privacy or provenance. Source evidence retains its privacy label
and is marked imported rather than inheriting source trust. Eligible claims
arrive with candidate status; existing archived/rejected status is retained.

Protected source evidence requires its original content key during import,
in addition to any archive passphrase. Configure `ALETHEIA_KEY_<source_key_id>`
and the target's separate active key when importing into protected mode. The
importer decrypts the source and encrypts its local copy with the target key.

Successful imports persist source IDs, source namespace, destination namespace,
local IDs, and source fingerprints in the import run. Reimporting unchanged
sources reuses those objects, including after a restart. Importing into a
different destination namespace creates separate copies. Changed sources are
rejected for review instead of overwriting a locally reviewed copy. Local
deletions and imported source tombstones prevent older archives from restoring
removed content. Tombstones affect mapped copies, not unrelated local IDs.
Any failure rolls back the content, mappings, and audit changes together.

Earlier importer versions did not retain these mappings and could manufacture
lower-privacy evidence for claims. Recognized legacy imports stop for provenance
review before another copy is created. This release does not automatically
repair historical imports or infer missing identity from equal text. Assess
those copies against a trusted source archive; a clean target or a trusted
backup from before the import provides a safer recovery basis than editing
import history to bypass the guard.

Federation imports likewise reuse peer/source mappings across repeated bundles
and preserve local review outcomes. Changed sources and multiple historical
copies require review. Deletion notices invalidate and scrub mapped descendants;
replayed notices or older content do not create fresh copies. A notice must match
the imported source's type and namespace.

## Deletion semantics

An explicit target must include its supported type and ID. A namespace selector
must be nonempty. Dry runs record the preview without changing target content.

| Forget mode | Applied behavior |
| --- | --- |
| `tombstone` | Retains content, archives/rejects the target when applicable, invalidates descendants, and records a tombstone. |
| `redact_content` | Replaces target and dependent content, invalidates descendants, removes index/trace snapshots, and records tombstones. |
| `hard_delete` | Deletes the selected claim, evidence, or source-document row and its required links; scrubs and invalidates retained descendants. |
| `namespace_forget` | Applies hard deletion to claims, evidence, and source documents selected in that namespace. |
| `derived_invalidate` | Invalidates descendants while retaining the selected root's content and status. |

Applied `hard_delete` and `namespace_forget` still require confirmation text
`forget memory`. A claim-specific operation does not delete its original
source evidence; select that evidence or source document when removing the
source is intended. Namespace selection includes both claims and their sources.

Redaction follows evidence links, candidate promotions, inference promotions,
reflection/abstraction sources, and transitive derivation edges, with cycle
detection. Source-document redaction includes evidence linked through its
ingestion batch. Affected claims are archived, candidates rejected, and derived
records marked stale. Content snapshots in traces and associated metadata are
removed along with searchable claim entries and embedding vectors. Failures
roll back the entire mutation.

These operations change the live records and their tracked dependencies. They
cannot erase old backups, SQLite free pages, filesystem snapshots, OS caches,
unlinked copies, or data already held by another device. Retain structural audit
history and handle external copies through the deployment's retention process.
