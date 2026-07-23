# Aletheia v1.3.0 Review Closure Checklist

Review source: `CODE_REVIEW.md`  
Implementation plan: `docs/v1_3_0_baseline_remediation_plan.md`  
Baseline branch: `main`  
Baseline tags: `v1.3.0`, `production-v1.3.0-baseline`

## Status Legend

- `[ ] Open`: not fixed.
- `[x] Closed`: fixed and evidence is linked.
- `[~] In Progress`: implementation exists but evidence is incomplete.
- `[!] Accepted Risk`: intentionally left with documented deployment boundary, owner, and review date.
- `[n/a] Out Of Baseline Scope`: not present on `main`; tracked in another branch/fork.

Every closed item must cite at least one of:

- Code commit hash.
- Test name or test file.
- Documentation update.
- Manual verification command and result.
- Migration/backward-compatibility note where relevant.

## Baseline Boundary Evidence

- [x] sample adapter integration is not on `main`.
  - Evidence: `origin/main` at `3121ab0` before final closure had no tracked sample adapter integration paths; `git ls-tree -r --name-only origin/main -- aletheia/integrations docs/ALETHEIA_SAMPLE_ADAPTER_COMPATIBILITY_LAYER_PLAN.md tests/fixtures/sample_adapter tests/test_sample_adapter_compatibility.py` returned no paths.
- [x] Baseline review file is tracked on `main`.
  - Evidence: this checklist is committed with `CODE_REVIEW.md` on `main`.

## Critical Issues

| Status | ID | Finding | Closure Evidence Required | Evidence |
|---|---|---|---|---|
| [x] | C1 | Federation bundle encryption uses manifest-derived XOR key. | AEAD implementation, bundle decrypt negative tests, docs. | Code: `aletheia/core/federation.py` uses `cryptography` AES-GCM content encryption with X25519 recipient key wrapping and rejects legacy unsigned bundles. Tests: `tests/test_m10_federated_memory.py::test_identity_peer_share_and_encrypted_bundle_export`, `tests/test_m10_federated_memory.py::test_tampered_sync_bundle_payload_or_signature_is_rejected`. |
| [x] | C2 | Federation trust model has no real keypairs/signatures. | Real signing key support, signature verification tests, forged bundle rejection tests. | Code: new federation identities use v2 Ed25519 signing keys plus X25519 encryption keys; bundle signatures and changeset signatures are Ed25519, and peer public keys must parse as v2 key material. Tests: `tests/test_m10_federated_memory.py::test_peer_identity_key_substitution_is_rejected`, `tests/test_m10_federated_memory.py::test_tampered_sync_bundle_payload_or_signature_is_rejected`. |
| [x] | C3 | Protected content falls back to compiled-in default key. | Fail-closed hardened mode, key configuration tests, readiness warning. | Code: `aletheia/core/hardening.py` removes the compiled-in fallback and adds `protected_content_key_configured` readiness evidence. Tests: `tests/test_m8_production_hardening.py::test_protected_mode_encrypts_secret_content_and_skips_secret_indexing`, `tests/test_m8_production_hardening.py::test_protected_secret_content_requires_configured_key`. |
| [x] | C4 | `auth_required=False` grants all capabilities and secret privacy. | Least-privilege no-auth defaults, explicit trusted mode, MCP/HTTP tests. | Code: `aletheia/service/auth.py` gives tokenless contexts local-agent capabilities, namespace-scoped grants, and personal privacy by default; `aletheia/service/http.py` scopes no-auth HTTP to `memory.namespace`. Tests: `tests/test_m6_memory_service.py::test_no_auth_context_is_least_privilege_for_local_namespace`, `tests/test_m6_memory_service.py::test_mcp_tools_are_candidate_first_logged_and_namespace_capability_aware`. |
| [x] | C5 | Reads recompute confidence and write telemetry by default. | Read-only retrieval tests, scheduled recompute path, query/write count tests. | Code: `Memory.retrieve()` defaults to `recompute_confidence=False` and `record_access=False`; `Memory.context_pack()` no longer writes context-pack telemetry unless `record_usage=True`; scheduled recompute remains available through `local_jobs` job type `recompute_confidence`. Test: `tests/test_m1_reliable_recall.py::test_retrieve_and_context_pack_are_read_only_by_default_with_bounded_queries`. |

## High-Severity Security Issues

| Status | ID | Finding | Closure Evidence Required | Evidence |
|---|---|---|---|---|
| [x] | H1 | Token hashes are unsalted SHA-256 and compared non-constant-time. | Versioned token hashing, constant-time comparisons, legacy-token compatibility tests. | Code: `aletheia/core/crypto.py` owns versioned salted PBKDF2 hashing and constant-time verification; `aletheia/service/auth.py`, `aletheia/service/http.py`, and `aletheia/cli/main.py` reuse that path. Tests: `tests/test_crypto.py::test_secret_hashing_is_versioned_salted_and_legacy_compatible`, `tests/test_m6_memory_service.py::test_auth_tokens_are_hashed_and_enforce_revoke_expiry_capability_namespace_and_privacy`, `tests/test_m7_observability_console.py::test_console_auth_session_csrf_dashboard_and_confirmed_actions`. |
| [x] | H2 | Admin endpoints accept unsafe caller-controlled paths and URLs. | Safe-root path validation, SSRF guard, route tests for traversal/unsafe URL denial. | Code: `aletheia/service/http.py` enforces admin safe roots for HTTP file paths; `aletheia/core/platform.py` restricts doctor `service_url` to loopback HTTP(S). Tests: `tests/test_m8_production_hardening.py::test_m8_cli_and_http_surfaces`, `tests/test_m9_stable_platform.py::test_m9_http_openapi_and_cli_surfaces`. |
| [x] | H3 | HTTP body read happens before max-size validation; malformed length uncaught. | Pre-read length validation tests, malformed `Content-Length` tests. | Code: `AletheiaRequestHandler._handle` validates `Content-Length` and rejects oversized requests before reading the body. Test: `tests/test_m6_memory_service.py::test_http_boundary_rejects_oversized_and_malformed_lengths_before_body_read`. |
| [x] | H4 | Catch-all returns raw internal exception strings. | Generic 500 response tests, audit/log detail preservation tests. | Code: `AletheiaService.handle_http` now returns a generic `internal_error` message at the service boundary. Test: `tests/test_m6_memory_service.py::test_http_catch_all_does_not_return_internal_exception_text`. |
| [x] | H5 | Redacted/metadata backup embeds raw DB and token table. | Archive content inspection tests, corrected manifest semantics. | Code: `aletheia/core/hardening.py` allows physical snapshots only for full backups, emits logical redacted backups without auth metadata, and redacts nested JSON details. Test: `tests/test_m8_production_hardening.py::test_redacted_logical_backup_excludes_raw_db_tokens_and_content`. |
| [x] | H6 | Peer key upsert keeps trusted status. | Key rotation policy, trust reset/rejection tests. | Code: `add_peer` rejects key/fingerprint substitution for an existing `peer_instance_id`. Test: `tests/test_m10_federated_memory.py::test_peer_identity_key_substitution_is_rejected`. |
| [x] | H7 | Federation import dry-run mutates peer/trust state. | Dry-run state-diff test proving no mutation. | Code: `import_share_bundle(..., dry_run=True)` now returns a planned `SyncRun` without calling peer import or writing sync rows. Test: `tests/test_m10_federated_memory.py::test_import_share_bundle_dry_run_does_not_mutate_peer_or_sync_state`. |
| [x] | H8 | Expired share grants are not enforced. | Expired export/sync denial tests. | Code: `export_share_bundle` and `sync` call `_require_active_share`, marking expired shares and denying use. Test: `tests/test_m10_federated_memory.py::test_expired_share_grants_cannot_export_or_sync`. |
| [x] | H9 | Contradictions can mark core claims disputed and hide them. | Conflict tests preserving core retrieval plus warnings. | Code: conflict detection preserves `core` claim status while still auditing/recording the unresolved conflict. Test: `tests/test_memory.py::test_core_claim_stays_retrievable_when_contradicted`. |
| [n/a] | H10 | sample adapter duplicate/conflict checks leak claim data before capability/privacy checks. | sample adapter branch/fork fix, no-read-oracle tests. | Not present on `main`; closed on `codex/sample_adapter-compatibility-layer` by commit `a2e8a27`. Tests on sample adapter branch: `tests/test_sample_adapter_compatibility.py::test_sample_adapter_candidate_write_does_not_probe_active_claims_before_authz`, `tests/test_sample_adapter_compatibility.py::test_sample_adapter_active_duplicate_and_conflict_honor_privacy_ceiling`. |
| [x] | H11 | Plugin install can bypass permission approval and gates. | Permission enforcement tests, install/enable separation tests. | Code: `aletheia/core/platform.py` keeps plugin install status as `installed` even when approval is requested; enablement still requires explicit approved permissions. Test: `tests/test_m9_stable_platform.py::test_m9_plugin_manifest_permissions_and_candidate_first_execution`. |
| [n/a] | H12 | sample adapter candidate creation hand-writes raw SQL and skips risk scoring. | sample adapter branch/fork fix or generic governed candidate API with tests. | Not present on `main`; closed on `codex/sample_adapter-compatibility-layer` by commit `a2e8a27`. Test on sample adapter branch: `tests/test_sample_adapter_compatibility.py::test_sample_adapter_candidate_creation_uses_governed_risk_scoring`. |

## High-Severity Correctness And Architecture Issues

| Status | ID | Finding | Closure Evidence Required | Evidence |
|---|---|---|---|---|
| [x] | H13 | `_active_ranking_policy_version_id` is defined twice. | Duplicate removed, non-default ranking policy test. | Code: duplicate helper removed; remaining helper accepts a `policy_id`. Test: `tests/test_m5_adaptive_memory.py::test_m5_migration_creates_default_policies_and_no_learning_runs`. |
| [x] | H14 | Nested sqlite transactions can commit partial writes. | Transaction helper, rollback tests across conflict/federation/hardening paths. | Code: `SQLiteStore.transaction()` now uses explicit transactions and nested savepoints; core/service write paths use the helper. Tests: `tests/test_m2_memory_integrity.py::test_nested_transaction_rolls_back_conflict_resolution`, `tests/test_m8_production_hardening.py::test_nested_transaction_rolls_back_hardening_write`, `tests/test_m10_federated_memory.py::test_nested_transaction_rolls_back_federation_identity`. |
| [x] | H15 | Candidate/inference edits can bypass validation/promotion gates. | Validation tests for invalid statuses, confidence clamps, privacy rules. | Code: candidate and inference edit paths now reject unsupported fields, terminal workflow statuses, invalid numeric bounds, invalid privacy levels, and malformed metadata. Tests: `tests/test_m3_intelligent_ingestion.py::test_candidate_edits_cannot_bypass_review_or_validation_gates`, `tests/test_m4_reasoned_memory.py::test_inference_edits_cannot_bypass_review_or_validation_gates`. |
| [x] | H16 | `curate()` auto-promotes to core with `force=True`. | Gate-respecting curation tests; explicit policy if force remains. | Code: automated curation now calls promotion with `force=False` and records skipped decisions when governance gates reject promotion. Test: `tests/test_m2_memory_integrity.py::test_curate_does_not_force_core_promotion_when_gates_fail`. |
| [x] | H17 | FTS repair deletes all namespaces then reindexes one. | Multi-namespace FTS repair regression test. | Code: FTS drift findings carry namespace metadata; repair deletes/rebuilds only the finding namespace when scoped. Test: `tests/test_m8_production_hardening.py::test_fts_repair_is_scoped_to_finding_namespace`. |
| [x] | H18 | Retrieval lacks SQL limit and has N+1 hydration. | Bounded query-count tests, SQL limit/batched hydration evidence. | Code: `SQLiteFTSRetriever.retrieve()` applies bounded SQL candidate limits and batches evidence/conflict/project hydration; semantic/hybrid retrieval uses `_governed_claim_rows(..., limit=...)` plus batched scope/evidence/conflict/project maps. Test: `tests/test_m1_reliable_recall.py::test_retrieve_and_context_pack_are_read_only_by_default_with_bounded_queries`. |
| [x] | H19 | Nested CLI `--db` parser can target wrong DB. | CLI parser tests for custom DB leaf commands. | Code: migrate leaf subcommands use `argparse.SUPPRESS` so parent `--db` is preserved unless explicitly overridden. Test: `tests/test_cli.py::test_cli_migrate_subcommands_preserve_parent_db`. |
| [x] | H20 | `ConflictResolution.status` property always returns resolved. | Model correction/removal and tests. | Code: `ConflictResolution.status` is now populated from persisted resolution metadata instead of a hardcoded property. Test: `tests/test_m2_memory_integrity.py::test_conflict_resolution_status_reflects_family_state`. |
| [n/a] | H21 | sample adapter integration had no tests when reviewed. | sample adapter branch tests. | Not present on `main`; closed on `codex/sample_adapter-compatibility-layer` by commit `a2e8a27`. Verification on sample adapter branch: `uv run pytest tests/test_sample_adapter_compatibility.py` passed with 14 tests. |

## Selected Medium Issues From Review

| Status | Finding | Closure Evidence Required | Evidence |
|---|---|---|---|
| [x] | Mass-assignment via raw `**payload` in HTTP handlers. | Whitelisted argument builders and route tests. | Code: `aletheia/service/http.py` replaces raw payload expansion with endpoint-specific argument builders. Test: `tests/test_m6_memory_service.py::test_http_claim_scope_whitelists_payload_fields`. |
| [x] | Read-before-authz in claim endpoint leaks existence. | Auth-before-read or indistinguishable 403/404 tests. | Code: claim/candidate/confidence/reflection/review routes now check coarse capability before target reads, then namespace after load. Test: `tests/test_m6_memory_service.py::test_claim_get_requires_capability_before_existence_lookup`. |
| [x] | Rate limiting exempts unauthenticated traffic and global lock serializes routes. | Rate limit tests for login/no-auth endpoints; lock narrowing evidence. | Code: `AletheiaService.handle_http()` now rate-limits anonymous identities derived from forwarded/real IP headers and no longer executes routes inside the global service lock; the lock is limited to rate-limit and idempotency bookkeeping. Test: `tests/test_m6_memory_service.py::test_rate_limit_applies_per_token_and_can_be_disabled`. |
| [x] | LLM output can overwrite provenance/privacy and unsafe span/confidence fields. | Extraction validation tests for metadata, privacy floor, span bounds, confidence clamps. | Code: `LLMExtractor` protects provenance metadata, floors privacy at source evidence level, and rejects invalid spans/confidence before candidate storage. Tests: `tests/test_m12_governed_llm_memory.py::test_llm_candidate_cannot_override_provenance_or_lower_privacy`, `tests/test_m12_governed_llm_memory.py::test_llm_unsafe_span_or_confidence_is_rejected_before_candidate_storage`. |
| [x] | Job runner race can run same job twice. | Atomic claim implementation and two-worker test. | Code: `_claim_pending_job()` atomically updates `pending` jobs to `running` with status/run-after/attempt guards before execution. Test: `tests/test_m5_adaptive_memory.py::test_job_claim_is_atomic_for_two_workers`. |
| [x] | Migrations rerun every open and lack forward-compat guard. | Version-gated migration tests and startup behavior tests. | Code: `SQLiteStore.migrate()` skips already-current initialized schemas and raises on schemas newer than supported before running migrations. Test: `tests/test_m8_production_hardening.py::test_migration_skips_current_schema_and_rejects_forward_schema`. |
| [x] | Retention ignores filters and some actions silently do nothing. | Retention dry-run/apply parity tests for all actions/filters. | Code: `run_retention()` now honors memory type, privacy, source, and age filters and implements `archive`, `queue_review`, `lower_salience`, `redact_content`, `tombstone`, and `hard_delete`. Test: `tests/test_m8_production_hardening.py::test_retention_filters_and_all_actions_have_dry_run_apply_parity`. |
| [x] | Home-grown crypto duplicated across modules. | Shared crypto utility, old helpers removed, crypto tests. | Code: `aletheia/core/crypto.py` centralizes PBKDF2 hashing, SHA-256 helpers, constant-time comparison, random bytes, and AES-GCM passphrase envelopes; `aletheia/service/auth.py`, `aletheia/core/hardening.py`, and `aletheia/core/federation.py` now call shared helpers. Backward compatibility: legacy XOR/HMAC decrypt support remains read-only for old protected content/backups. Tests: `tests/test_crypto.py`, `tests/test_m8_production_hardening.py::test_encrypted_backup_verify_restore_and_corruption_detection`, `tests/test_m8_production_hardening.py::test_protected_mode_encrypts_secret_content_and_skips_secret_indexing`, `tests/test_m10_federated_memory.py::test_identity_peer_share_and_encrypted_bundle_export`. |
| [n/a] | sample adapter duplicate "merged" does not merge evidence and is expensive. | sample adapter branch/fork duplicate semantics tests. | Not present on `main`; closed on `codex/sample_adapter-compatibility-layer` by commit `a2e8a27`, which appends duplicate evidence through `Memory.append_claim_evidence(...)`. Test on sample adapter branch: `tests/test_sample_adapter_compatibility.py::test_sample_adapter_duplicate_returns_merged_and_structured_conflict_returns_clarify`. |
| [x] | Storage path/thread/nullable-key issues. | Path expansion tests, connection/threading policy, unique-key regression tests. | Code: `SQLiteStore.open()` expands `~` before connecting; `SQLiteStore.transaction()` serializes writes with an `RLock`; the embeddings provider key uses `COALESCE(index_version, '')` and vector upsert handles that expression index. Test: `tests/test_m8_production_hardening.py::test_storage_expands_home_path_and_enforces_nullable_embedding_key`. |

## Positive Review Findings To Preserve

These are not defects, but they should be protected with regression evidence as remediation proceeds.

| Status | Finding | Preservation Evidence Required | Evidence |
|---|---|---|---|
| [x] | SQL injection review found no direct caller-value interpolation. | Existing parameterized SQL patterns preserved; add static review gate when route refactor starts. | Review note in `CODE_REVIEW.md`; no closure action needed yet. |
| [x] | Dataclasses avoid mutable default arguments. | Existing model tests continue passing. | Review note in `CODE_REVIEW.md`; full suite to be cited after each remediation phase. |
| [x] | Tests are isolated and behavioral. | `tmp_path` isolation preserved; new tests follow same pattern. | Review note in `CODE_REVIEW.md`. |
| [x] | Governance-first candidate/promotion architecture is sound. | New governance tests should preserve candidate-first flow. | Review note in `CODE_REVIEW.md`; remediation plan Workstream 2. |

## Phase Closure Checklist

### Phase 0: Baseline Guard

- [x] Commit `CODE_REVIEW.md` to `main`.
- [x] Commit remediation plan to `main`.
- [x] Commit closure checklist to `main`.
- [x] Keep sample adapter integration off `main`.
- [x] Add CI/release gate to detect product-specific integration files on `main`.
  - Evidence: `.github/workflows/release-gates.yml` runs `scripts/release_gate.py` for pushes/PRs targeting `main`; `tests/test_release_gate.py` covers allowed branch behavior and main-boundary path detection.

### Phase 1: Security Blockers

Latest verification: `uv run pytest` passed with 107 tests.

- [x] C1 closed.
- [x] C2 closed.
- [x] C3 closed.
- [x] C4 closed.
- [x] H1 closed.
- [x] H2 closed.
- [x] H3 closed.
- [x] H4 closed.
- [x] H5 closed.
- [x] H6 closed.
- [x] H7 closed.
- [x] H8 closed.
- [x] H11 closed.

### Phase 2: Governance And Correctness

Latest verification: `uv run pytest` passed with 121 tests.

- [x] H9 closed.
- [x] H13 closed.
- [x] H14 closed.
- [x] H15 closed.
- [x] H16 closed.
- [x] H17 closed.
- [x] H19 closed.
- [x] H20 closed.
- [x] Mass-assignment closed.
- [x] Read-before-authz closed.
- [x] LLM trust-boundary medium closed.

### Phase 3: Performance And Operations

Latest verification: `uv run pytest` passed with 131 tests.

- [x] C5 closed.
- [x] H18 closed.
- [x] Rate limiting/no-auth global lock medium closed.
- [x] Job runner race closed.
- [x] Migration rerun/forward-compat closed.
- [x] Retention implementation closed.
- [x] Storage path/thread/nullable-key issues closed.

### Phase 4: sample adapter Branch Gate

- [x] sample adapter integration isolated from `main`.
- [x] H10 closed on sample adapter branch/fork.
  - Evidence: `codex/sample_adapter-compatibility-layer` commit `a2e8a27`; tests `tests/test_sample_adapter_compatibility.py::test_sample_adapter_candidate_write_does_not_probe_active_claims_before_authz` and `tests/test_sample_adapter_compatibility.py::test_sample_adapter_active_duplicate_and_conflict_honor_privacy_ceiling`.
- [x] H12 closed on sample adapter branch/fork.
  - Evidence: `codex/sample_adapter-compatibility-layer` commit `a2e8a27`; test `tests/test_sample_adapter_compatibility.py::test_sample_adapter_candidate_creation_uses_governed_risk_scoring`.
- [x] H21 fully closed on sample adapter branch/fork with H10/H12 regression tests.
  - Evidence: `uv run pytest tests/test_sample_adapter_compatibility.py` passed with 14 tests on `codex/sample_adapter-compatibility-layer`.
- [x] sample adapter duplicate merge semantics fixed on sample adapter branch/fork.
  - Evidence: `codex/sample_adapter-compatibility-layer` commit `a2e8a27`; test `tests/test_sample_adapter_compatibility.py::test_sample_adapter_duplicate_returns_merged_and_structured_conflict_returns_clarify`.

## Final Review Closure Requirements

- [x] Every Open item above is either Closed, Accepted Risk, or Out Of Baseline Scope.
  - Evidence: no issue rows or phase checklist items remain open after the CI/release gate and shared crypto closures.
- [x] Every Closed item has evidence.
  - Evidence: closed rows cite code, tests, documentation, manual commands, or compatibility notes.
- [x] Every Accepted Risk has owner, deployment boundary, and review date.
  - Evidence: no `[!] Accepted Risk` entries are currently used.
- [x] Full baseline test suite passes.
  - Evidence: `uv run pytest` passed with 135 tests on `main`.
- [x] Hardened profile security tests pass.
  - Evidence: `uv run pytest tests/test_crypto.py tests/test_release_gate.py tests/test_m8_production_hardening.py tests/test_m10_federated_memory.py tests/test_m6_memory_service.py tests/test_m7_observability_console.py` passed with 52 tests.
- [x] Documentation accurately states deployment limits.
  - Evidence: `docs/security_privacy_guide.md` documents generic-baseline boundaries, auth/TLS expectations, protected-key requirements, backup limits, and encrypted federation expectations.
- [x] `main` remains Aletheia-generic.
  - Evidence: `git ls-tree -r --name-only origin/main -- aletheia/integrations docs/ALETHEIA_SAMPLE_ADAPTER_COMPATIBILITY_LAYER_PLAN.md tests/fixtures/sample_adapter tests/test_sample_adapter_compatibility.py` returned no paths before this final closure commit; `python scripts/release_gate.py --branch main` rejects sample adapter paths when they are present.
