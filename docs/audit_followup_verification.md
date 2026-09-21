# Independent audit follow-up repairs

An independent review of the original 29 repairs found nine residual defects
affecting audit items 04, 07, 08, 11, 16, 22, and 27. Its original acceptance
checks produced 15 failing assertions and seven passing controls, while all
385 existing audit regressions passed. The follow-up suite preserves those
behavioral checks and adds boundary and compatibility cases.

| Review finding | Resulting behavior |
| --- | --- |
| R1 / 04 | Console and ordinary conflict resolution authorize current sources and all targets. Core resolution rejects nonmembers before writing; rejected requests leave memory, resolutions, and confirmations unchanged. |
| R2 / 07, 16 | Cached mutation results recheck current authority, provenance, scope, and provider approval without repeating the operation. Redaction erases affected cached content while retaining the operation key. |
| R3 / 08 | Namespace-scoped activity reports and request/latency/evaluation aggregates filter before limits or aggregation. Old metric snapshots without verified scope metadata are excluded and latest metrics are regenerated. |
| R4 / 11 | Signed claims carry effective privacy independently of evidence-text permission. Imports preserve the stricter claim/source label, including synthetic source evidence and candidate spans. |
| R5 / 16 | Deletion scrubs both local and remote federation-conflict snapshots. Reads recheck current source visibility and snapshot consistency. |
| R6 / 11 | Evidence-only grants can propagate deletion notices. Notices are restricted to objects actually disclosed through the collection's export history. |
| R7 / 22 | The real daemon worker releases the service lock and database transaction during provider work. Durable ownership prevents duplicate execution; changed inputs, failures, and shutdown cannot commit stale results or strand owned jobs. |
| R8 / 27 | Actual project relevance and conflict/duplicate penalties participate before candidate truncation in every retrieval mode. The bounded result uses the same scoring and tie breakers as selection. |
| R9 / 27 | Context traces inherit the active budget through Python, HTTP, and CLI, record it accurately, and honor explicit overrides. |

## Compatibility

Older full-evidence federation bundles can recover claim privacy from their
labeled sources. Older claims-only bundles lacking a privacy label must be
exported again; importing them fails without partial changes. Existing imported
data is not retroactively relabeled by these code repairs. For the beta release,
see the [1.6.0 fresh-start and upgrade options](v1_6_0_upgrade.md).

Tombstones for never-disclosed objects are no longer exported. Existing export
history supplies the disclosure record; no recipient content scan is required.
Old metric snapshots remain in storage for local inspection, but are not served
as verified scoped snapshots. Previously exported report files and backups are
not recalled or rewritten.

Operational metrics aggregate namespace-wide activity. A project annotation
does not restrict those aggregates, so snapshot creation requires authority
over the entire namespace; a project-only grant is insufficient.

Cached replies denied after a policy change do not rerun their mutations. Old
generic receipts without authorization evidence are denied. Source redaction
scrubs stored receipts and preserves their keys as tombstones. The creator's
candidate receipt retains its existing current-object validation.

## Verification boundaries

`tests/test_audit_followup.py` exercises public memory operations, HTTP responses,
signed bundle export/import, the actual daemon worker, resulting rankings,
context contents, persisted deletion effects, and competing SQLite connections.
Providers and all data are synthetic. This validates application behavior and
access boundaries; it does not measure real-model quality or production load.

The unchanged audit regressions and the complete repository suite were also run
before local closure. The subsequent Python/platform matrix and package checks
are recorded in [1.6.0 release verification](v1_6_0_release_verification.md).
Real-model workloads, historical key exposure, and live-data recovery are not
established by these synthetic checks.

Final local verification passed all 768 tests, including 53 follow-up cases,
on Python 3.13.13/macOS arm64. The generic-main repository gate, compilation,
and diff checks passed. The original 29 code-repair items and all nine residual
review findings are locally closed; the operational boundaries above remain.
