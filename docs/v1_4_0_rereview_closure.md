# 1.4.0 final independent re-review closure

Recorded 2026-09-01. The independent re-review examined
`codex/v1.4-final-release` at `db1d440` and confirmed 22 of the earlier 26
closures at source level. It found four residual release findings and eight
follow-up groups. The four release findings and the safe, localized follow-ups
listed below are corrected on the same isolated branch. Nothing was pushed to
the public implementation repository, merged, tagged, or published.

## Release findings

| ID | Correction | Regression evidence |
| --- | --- | --- |
| R1: report export could overwrite the live database | A custom `output_path` additionally requires `memory:admin`; omitted paths use a service-controlled `reports/` directory. The resolved database, WAL, shared-memory and rollback-journal paths are refused for every administrative output. | A read token can create only a default controlled report. Custom reader output is 403; an administrator can write a safe custom report; database and sidecars return 400 and the live database remains healthy. OpenAPI describes the conditional capability. |
| R2: proxy auth-failure buckets trusted the spoofable XFF edge | Trusted-proxy mode uses the rightmost proxy-appended `X-Forwarded-For` hop. Default mode continues to ignore forwarding headers. | Two invalid credentials with different attacker-controlled left hops and one shared proxy-appended right hop consume the same bucket and return 401 then 429. |
| R3: `force=True` bypassed terminal candidate protection | Terminal candidate status is checked before overridable promotion-quality failures. Force can no longer reopen promoted, rejected, merged or duplicate candidates. | Embedded promotion, forced duplicate promotion and late rejection produce one claim, one link and one promotion decision. |
| R4: embedded evidence accepted unknown privacy levels | `write_event` validates the shared privacy vocabulary before deduplication, encryption or persistence, covering `ingest`, `remember` and CLI entry points. | Unknown, empty, case-mismatched and null values raise `ValidationError` and write no evidence. |

## Additional follow-ups corrected now

- Review schema integrity requires every known table and trigger but tolerates
  unrelated plugin-owned tables.
- Notification dismiss/snooze resolves the target first and enforces its
  namespace grant.
- MCP interpolated path segments are percent-encoded, not only query strings.
- Python client last-response metadata is cleared before a request, so failures
  cannot expose a stale successful response snapshot.
- Direct embedded `review_candidate(decision="promote")` is refused; promotion
  must use `promote_candidate()` and create the governed claim/link/decision.
- Evidence redaction records the real prior claim status, including `core`.
- The changelog names the upgrade-visible validation, operation-key, replay,
  ping and authentication behavior changes.
- Package-bound release records no longer include the private advisory
  identifier or private-fork URLs.

## Known follow-ups that do not block 1.4.0

| Area | 1.4 disposition |
| --- | --- |
| Whole-service request serialization | Retained as the correctness-first SQLite design. Provider I/O, health fast paths and duplicate authentication work should be separated in a later performance design with concurrency tests. |
| Generic idempotency crash window | Negotiated review and onboarding writes are crash-atomic. The broad legacy route surface retains a mutation/completion crash window and should gain per-operation transactional receipts in a later contract. |
| Global review epoch | Deliberately conservative and fail-closed for 1.4. Per-resource or namespace epochs can reduce reviewer churn later without weakening stale-write protection. |
| Dashboard overview scaling | The authorized overview can scan a namespace and returns explicit unavailable operational sections. Query aggregation and a versioned response optimization remain future work. |
| Disclosure-bound package docs | Source and package publication remain ordered after coordinated disclosure. Private advisory coordinates have been removed from package-bound docs. |
| Bounded/legacy behavior | The polling client intentionally caps server-directed waits at 60 seconds; edited candidates return to pending review; legacy recorded doctor remains mutating unless `--read-only` is selected. These limits are documented behavior, not silent release claims. |

## Verification

| Gate | Result |
| --- | --- |
| Complete Python suite | 311 tests passed across 23 files on macOS ARM64 / Python 3.13.13. |
| Re-review affected suites | 121 tests passed across memory, ingestion, HTTP service, console/observability, production hardening and negotiated review suites. |
| Negative security cases | Database/sidecar overwrite, forged proxy chain, forced double promotion, invalid embedded privacy and cross-namespace notification mutation are explicitly refused. |
| Historical unchanged gates | The previously recorded 24 Node transport tests and TypeScript no-emit check remain applicable because this correction does not alter TypeScript sources. They will run again in protected CI on the public reviewed head. |

This closure does not convert an independent source review into a security
certification. Protected public CI, owner review, coordinated disclosure,
protected merge, publication and public-artifact verification remain Phase 7
controls.
