# 1.6.0 review verification and resolution

Date: October 13, 2026 (America/Chicago). Reviewed baseline: main `18b884b` / `v1.6.0`. Fix release: prepared `1.6.1`.

The original [Claude review](v1_6_0_code_review.md) was independently checked against the source. The highest-impact findings were reproduced on the unfixed baseline before patching. Existing issue #10 was retained; 51 new issues (#11–#61) track the other verified findings, with the low-severity group split into separate defects. The complete mapping is in [github-issues.json](review-v1.6.0/github-issues.json).

Implementation and local acceptance are complete. Issues close only after the accepted fixes are integrated. GitHub/PyPI publication remains a separate release step.

## Acceptance evidence

The final local Python 3.13 full suite passed **835 tests**; the additional curation regression also passed (836 cases in the current suite). Release CI re-runs the complete source-archive suite on Python 3.11, 3.12 and 3.13. Test sources: [review regressions](../tests/test_v1_6_review_regressions.py), [service security](../tests/test_service_security.py), [federation security](../tests/test_federation_security.py), [storage security](../tests/test_storage_security.py), and [provider concurrency](../tests/test_retrieval_boundaries.py).

All databases, keys, identities, providers, ports and messages in acceptance tests are synthetic. No live model was called, no other owner’s job was stopped and no model profile was changed.

## Numbered findings

| Finding | Issue | Verified fix and acceptance |
|---|---|---|
| 1. Share-recipient injection via forged federation bundle | [#11](https://github.com/khaledgabal2/aletheia-memory/issues/11) | Forged unpaired-origin collision rejects before peer/recipient mutation; exact grant and collection bindings are checked. |
| 2. Namespace-scoped admin can destroy other namespaces | [#12](https://github.com/khaledgabal2/aletheia-memory/issues/12) | Selector, target-ID, redaction, integrity-repair and whole-database escape regressions deny without changing foreign memory. |
| 3. Issue #10 — active-write replay returns 409 | [#10](https://github.com/khaledgabal2/aletheia-memory/issues/10) | Immediate creation/replay, post-usage replay and changed lifecycle checks; creation returns the persisted claim. |
| 4. Legacy candidate promote/reject replay always returns 403 | [#15](https://github.com/khaledgabal2/aletheia-memory/issues/15) | Legacy promote and reject both replay successfully with captured receipt authority. |
| 5. List endpoints bypass the privacy ceiling | [#16](https://github.com/khaledgabal2/aletheia-memory/issues/16) | Secret conflict and candidate review lists are filtered; session/project and derived lists use source access checks. |
| 6. /v1/remember accepts status: "core" | [#13](https://github.com/khaledgabal2/aletheia-memory/issues/13) | Core, disputed and superseded active writes are rejected before persistence. |
| 7. /v1/ingest ignores the privacy ceiling | [#14](https://github.com/khaledgabal2/aletheia-memory/issues/14) | Personal-ceiling ingest refuses secret evidence before persistence. |
| 8. Procedure updates clobber unrelated procedures | [#17](https://github.com/khaledgabal2/aletheia-memory/issues/17) | Independent title-based procedure histories and rollback preserve unrelated active versions. |
| 9. Feedback bypasses _set_claim_status | [#18](https://github.com/khaledgabal2/aletheia-memory/issues/18) | Wrong feedback invalidates a dependent reflection; core status is retained. |
| 10. resolve_conflict demotes a core winner | [#19](https://github.com/khaledgabal2/aletheia-memory/issues/19) | A selected core conflict winner remains core. |
| 11. Inference promotion is re-runnable and non-atomic | [#20](https://github.com/khaledgabal2/aletheia-memory/issues/20) | Injected lineage failure rolls back promotion; repeated terminal review/promotion cannot duplicate claims. |
| 12. FTS index out of sync on object updates | [#21](https://github.com/khaledgabal2/aletheia-memory/issues/21) | Updated procedure text is searchable; the removed text no longer matches FTS. |
| 13. Generic write path is not atomic with its idempotency record | [#22](https://github.com/khaledgabal2/aletheia-memory/issues/22) | Injected receipt-storage failure rolls back database writes. Interrupted external file operations retain uncertain reservations after timeout and cannot repeat. |
| 14. enc: sniffing poisons reads | [#23](https://github.com/khaledgabal2/aletheia-memory/issues/23) | New reserved plaintext markers are refused at storage boundaries; legitimate legacy marker text is identified by its saved plaintext digest and remains readable without key derivation or span loss. Stored v3 KDF cost is restricted. |
| 15. Archive import decrypts foreign ciphertext with the local key | [#24](https://github.com/khaledgabal2/aletheia-memory/issues/24) | Foreign archive ciphertext is rejected without calling local event decryption. |
| 16. Backup manifest unauthenticated; import_archive lacks the trust_unauthenticated gate | [#25](https://github.com/khaledgabal2/aletheia-memory/issues/25) | Changed encrypted manifest fields fail authentication; unauthenticated imports require explicit trust and destination namespace. |
| 17. Lookup-by-remote-controlled-name | [#26](https://github.com/khaledgabal2/aletheia-memory/issues/26) | Exact identifiers resolve first; inspection fallback names must be unique. Mutations reject display-name aliases without changing state; existing trust/key/revocation race suites pass. |
| 18. benchmark_run leaves a DB snapshot in /tmp | [#27](https://github.com/khaledgabal2/aletheia-memory/issues/27) | Benchmark snapshots and writes use a temporary synthetic store, with encrypted archive cleanup and no live content changes. |
| 19. Deferred BEGIN defeats busy_timeout | [#28](https://github.com/khaledgabal2/aletheia-memory/issues/28) | A competing writer waits before reading a stale snapshot, then completes successfully. |
| 20. ASCII-only tokenizer | [#29](https://github.com/khaledgabal2/aletheia-memory/issues/29) | Japanese queries return matching Unicode content and never unrelated memory; nonword text is not an empty search. |
| 21. Provider clients forward Authorization across redirects | [#30](https://github.com/khaledgabal2/aletheia-memory/issues/30) | Default LLM and embedding redirects never reach a second host with credentials; SDK redirect regressions remain enforced. |
| 22. LLM extraction skips injection flagging | [#31](https://github.com/khaledgabal2/aletheia-memory/issues/31) | Model metadata cannot suppress injection flags, including when its chosen span omits malicious source text. |
| 23. Protected-mode auth and ignored bearer | [#32](https://github.com/khaledgabal2/aletheia-memory/issues/32) | Protected-mode tokenless access is refused; supplied revoked credentials are rejected even with auth disabled. |
| 24. Writes with memory:read | [#33](https://github.com/khaledgabal2/aletheia-memory/issues/33) | Read-only report export is denied; latest metrics do not persist snapshots; notification mutations require administration. |
| 25. PBKDF2 per request under the global lock | [#34](https://github.com/khaledgabal2/aletheia-memory/issues/34) | Repeated valid tokens invoke the slow verifier once while revocation and live grants remain enforced. |
| 26. Stale-return / split-transaction pattern (family of #3) | [#35](https://github.com/khaledgabal2/aletheia-memory/issues/35) | Public multi-step mutators use an outer transaction; stale claim creation is re-read; existing nested rollback and provider concurrency suites pass. |
| 27. Proposal review has no state machine | [#36](https://github.com/khaledgabal2/aletheia-memory/issues/36) | Rejected/applied procedure proposals cannot be re-approved; equivalent policy proposal guards apply. |
| 28. write_event dedup ignores stricter privacy | [#37](https://github.com/khaledgabal2/aletheia-memory/issues/37) | Deduplication atomically escalates stricter privacy and uses configured protection; original trust provenance is retained. |
| 29. Redaction residue | [#38](https://github.com/khaledgabal2/aletheia-memory/issues/38) | Associated conflict labels/review tasks, semantic labels, entities/aliases and status-history reasons are scrubbed. |
| 30. recompute_confidence cost and growth | [#39](https://github.com/khaledgabal2/aletheia-memory/issues/39) | Batched confidence matches scalar calculations, uses fewer than 15 SELECTs for 20 claims, avoids unchanged history growth, resolve_claim is read-only, and paged curation covers more than 1,000 claims. |
| 31. Archive file permissions | [#40](https://github.com/khaledgabal2/aletheia-memory/issues/40) | New archives are 0600; existing output is preserved and overwrite is refused. JSONL output follows the same policy. |

## Smaller findings

| Finding | Issue | Resolution |
|---|---|---|
| 32a | [#41](https://github.com/khaledgabal2/aletheia-memory/issues/41) | Required reasons use structured field validation. |
| 32b | [#42](https://github.com/khaledgabal2/aletheia-memory/issues/42) | One shared error-code set feeds the OpenAPI/review contracts. |
| 32c | [#43](https://github.com/khaledgabal2/aletheia-memory/issues/43) | Absent and inaccessible object IDs produce the same generic unavailable error; capability and CSRF diagnostics remain explicit. |
| 32d | [#44](https://github.com/khaledgabal2/aletheia-memory/issues/44) | Standard-input passphrases and environment resolution are supported; argv is deprecated in help and the primary guide. |
| 32e | [#45](https://github.com/khaledgabal2/aletheia-memory/issues/45) | Legacy SDK path identifiers and namespace queries are encoded. |
| 32f | [#46](https://github.com/khaledgabal2/aletheia-memory/issues/46) | SDK/provider response bodies are bounded. |
| 32g | [#47](https://github.com/khaledgabal2/aletheia-memory/issues/47) | ZIP total decompressed size, member count and duplicate member names are checked before reads. |
| 32h | [#48](https://github.com/khaledgabal2/aletheia-memory/issues/48) | Embedding provider payloads retain model/input and omit nonstandard namespace/privacy metadata. |
| 32i | [#49](https://github.com/khaledgabal2/aletheia-memory/issues/49) | Persistent worker identity, conservative dead-owner recovery, explicit unknown-owner confirmation, and retry backoff. Non-POSIX foreign processes are never signaled. |
| 32j | [#50](https://github.com/khaledgabal2/aletheia-memory/issues/50) | Resolved/dismissed risk flags do not generate another automatic task for the unchanged flag. |
| 32k | [#51](https://github.com/khaledgabal2/aletheia-memory/issues/51) | Source-authorized candidate/stale warnings are retained; inaccessible sources remain hidden. |
| 32m | [#52](https://github.com/khaledgabal2/aletheia-memory/issues/52) | Claim importance/half-life/duplicate evidence and job attempts/timestamps are validated before writes. |
| 32n | [#53](https://github.com/khaledgabal2/aletheia-memory/issues/53) | Inference-claim invalidation preserves terminal/core status and records lifecycle history. |
| 32p | [#54](https://github.com/khaledgabal2/aletheia-memory/issues/54) | Feedback explicitly scoped to a namespace cannot mutate a foreign claim or use foreign evidence. |
| 32q | [#55](https://github.com/khaledgabal2/aletheia-memory/issues/55) | Current-schema repairs skip historical M2/M3 audit backfills; unsupported pre-1.3.0 automatic upgrades are refused without data changes. |
| 32r | [#56](https://github.com/khaledgabal2/aletheia-memory/issues/56) | Restore verification cannot be disabled; warning statuses are consistent and readiness requires successful backup verification. |
| 32s | [#57](https://github.com/khaledgabal2/aletheia-memory/issues/57) | Sync imports match the requested signer, grant and collection and honor trust_policy. |
| 32t | [#58](https://github.com/khaledgabal2/aletheia-memory/issues/58) | Revocation merges metadata rather than dropping pairing/session identity. |
| 32u | [#59](https://github.com/khaledgabal2/aletheia-memory/issues/59) | Actions are pinned to resolved commits; release-version checks derive from metadata and apply to manual publication. |
| 32v | [#60](https://github.com/khaledgabal2/aletheia-memory/issues/60) | Malformed archive/bundle fields are validation errors, with rollback rather than partial imports. |

## Additional verified acceptance finding

[#61](https://github.com/khaledgabal2/aletheia-memory/issues/61): procedure rollback now restores its linked claim text and lexical index atomically. A regression test verifies that the restored text is retrieved and the superseded text is absent.

## Review statements retained or narrowed

- Candidate edits intentionally return to pending review: changing reviewed content invalidates its previous approval. This is retained rather than treating old validation as current.
- Embedded/library APIs may intentionally list across namespaces when explicitly passed no namespace. They are local operator APIs; HTTP lists still require scope and privacy access. By-ID APIs without an explicit namespace similarly identify a global local-store object. Explicit namespace parameters must not contradict their targets.
- The legacy token-hash upgrade already existed in AuthService; the review itself also identifies that path as sound. It remains covered rather than opening a duplicate defect for its absence.
- Changed remote objects continue to stop the bundle for explicit review, as the existing protocol documents. Converting that behavior to partial conflict imports would change the contract.
- A verified historical backup record is evidence of past verification, not proof that an externally modified file remains valid. Failed verifications are retained for audit and do not establish readiness.
- Database mutations and their receipts commit together. Files and separate restore destinations cannot participate in the same SQLite commit; their uncertain in-progress reservations are retained instead of automatically re-executing the operation after five minutes.

## Release handoff

See [1.6.1 upgrade guidance](v1_6_1_upgrade.md) and [release verification](v1_6_1_release_verification.md). Keep publication pending until the accepted commit, built wheel/source distribution, installed checks and GitHub release matrix are verified. A draft GitHub release must target the accepted implementation commit and carry the reviewed artifacts; publishing it starts the existing trusted PyPI workflow.
