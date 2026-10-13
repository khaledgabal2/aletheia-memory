# 1.6.0 Code Review

Date: 2026-10-12. Target: tag `v1.6.0` (`main` at `18b884b` differs only by two docs commits). Trigger: issue #10 (active-write idempotent replay returns 409 `replay_result_changed`). Scope: the whole `aletheia/` package plus `tests/`, `scripts/`, CI workflows and packaging. No code was changed; this document is review output only.

Method: four parallel static reads of the package (core memory; core hardening/platform/federation/crypto; service layer; storage/retrieval/providers/SDK/CLI/models/packaging), followed by runtime reproduction of the highest-impact findings against disposable databases. The pytest suite could not be executed in the review sandbox (Python 3.10 only, no network; the project needs 3.11+), so the "Verified" column below says how each finding was confirmed: **run** = reproduced by executing the code, **static** = traced in source only. Items marked static should be confirmed with a regression test before fixing.

Line numbers refer to the `v1.6.0` tree.

## Summary

| # | Sev | Area | Finding | Verified |
|---|-----|------|---------|----------|
| 1 | Critical | Federation | Forged bundle from an unpaired third party adds its origin as an active recipient of a locally-owned share grant; next encrypted export is key-wrapped to the attacker | run |
| 2 | Critical | Service / M8 | Namespace-scoped `memory:admin` can hard-delete, redact, back up or export any other namespace via `selector.namespace` / `target_id` / omitted `namespace` | run |
| 3 | High | Service | Issue #10: active-write replay 409 (`write_claim` returns pre-recompute claim; replay compares full dataclass) | run |
| 4 | High | Service | Legacy candidate promote/reject replay always returns 403 (receipt stored without `_authorization`) | run |
| 5 | High | Service | List endpoints (`/v1/reviews`, `/v1/conflicts`, `/v1/inferences`, `/v1/reflections`, `/v1/sessions`, `/v1/projects`) bypass the privacy ceiling that single-object reads enforce | run (conflicts) |
| 6 | High | Service | `/v1/remember` active write accepts `status: "core"` (and `disputed`, `superseded`), bypassing the review-gated promote path | run |
| 7 | High | Service | `/v1/ingest` does not enforce the credential's privacy ceiling | run |
| 8 | High | Core | `apply_procedure_update` / `rollback_procedure` supersede and renumber unrelated procedures when `procedure_claim_id` is NULL | run (subagent) |
| 9 | High | Core | `_apply_feedback_to_claim` changes status with a raw UPDATE, bypassing `_set_claim_status` (no derived invalidation; `core` claims can be rejected by feedback) | run (subagent) |
| 10 | High | Core | `resolve_conflict` demotes a `core` winner to `active` | run (subagent) |
| 11 | High | Core | `promote_inference` / `review_inference` lack terminal-state guards and atomicity; a promoted inference can be promoted again, creating duplicate claims | run (subagent) |
| 12 | High | Core + Storage | `claims_fts` not updated when `claims.object` changes (procedure updates); lexical search returns stale matches | run (subagent) |
| 13 | Medium | Service | Generic write path is not atomic with the idempotency record: crash between mutate and store re-executes the mutation after 5 min | static |
| 14 | Medium | Core / hardening | Plaintext evidence beginning with `enc:` breaks `read_event`/`list_events` for the namespace; crafted marker forces 2M PBKDF2 iterations per read | static |
| 15 | Medium | Core / hardening | Archive import decrypts foreign `enc:` ciphertext with the local key and re-stores it as plaintext | static |
| 16 | Medium | Core / hardening | Backup manifest is outside the authenticated envelope; `import_archive` accepts unauthenticated archives without the `trust_unauthenticated` gate that `restore_backup` enforces | static |
| 17 | Medium | Federation | `get_peer` / `get_share_grant` / `get_sync_collection` match on remote-controlled `display_name`/`name` with `OR id = ?` | static |
| 18 | Medium | Hardening | `benchmark_run` writes a full (often unencrypted) DB snapshot to the shared temp dir and never deletes it; reachable via `POST /v1/benchmarks/run` | static |
| 19 | Medium | Storage | `transaction()` defaults to deferred `BEGIN`; cross-process writers fail instantly with `database is locked` despite `busy_timeout` | run (subagent) |
| 20 | Medium | Retrieval | ASCII-only tokenizer: non-Latin queries collapse to "return every eligible claim" | run (subagent) |
| 21 | Medium | Providers | LLM/embedding clients follow cross-host redirects and forward `Authorization` (SDK was hardened against this; providers were not) | run (subagent) |
| 22 | Medium | Extraction | LLM extraction skips `_risk_metadata` prompt-injection flagging; model controls arbitrary candidate metadata keys | static |
| 23 | Medium | Service / auth | Protected mode forces auth only on `/v1/auth/me`; in tokenless mode a supplied bearer is ignored entirely | static |
| 24 | Medium | Service | Write side effects with `memory:read` only (`/v1/reports/export` writes files, `GET /v1/metrics/latest` snapshots, notification dismiss/snooze) | static |
| 25 | Medium | Service / perf | Every request runs 600k-iteration PBKDF2 two to three times under the global lock; no verified-token cache | static |
| 26 | Medium | Core | Stale-return / split-transaction pattern across ~15 mutators (same family as #3) | static |
| 27 | Medium | Core | Policy/procedure proposal review has no state machine: rejected or applied proposals can be re-approved and re-applied | run (subagent) |
| 28 | Medium | Core | `write_event` dedup keeps the first privacy/trust level; re-writing identical content as `secret` leaves it `personal` and unencrypted | run (subagent) |
| 29 | Medium | Core / deletion | Redaction leaves subject/predicate text in `conflicts`, conflict review tasks, `semantic_clusters.label`, entities/aliases, status-history reasons | static |
| 30 | Medium | Core / perf | `recompute_confidence(namespace=...)` is O(N × ~12 statements), appends N snapshot rows every run, and is triggered by `resolve_claim` (a lookup) | static |
| 31 | Medium | Hardening | Backup/export archives written with default umask and silently overwrite, while the DB itself is 0600 | static |
| 32 | Low | Several | Misc: `KeyError` → 500 on missing `reason`; error-code enum drift in OpenAPI; existence oracle via 404-before-authz; passphrases on argv; SDK path params not URL-encoded; unbounded `response.read()`; zip-bomb on untrusted archives; jobs stranded in `running`; `curate` silently caps at 1000; migration re-run inserts spurious "M2/M3 backfill" audit rows; CI version pins | static |

## Critical

### 1. Share-recipient injection via forged federation bundle

`aletheia/core/federation.py:703-748` (`import_share_bundle`), `:1996-2021` (`_validate_import_grant`), `:2024-2079` (`_ensure_imported_share_and_collection`), `:649-655` (`export_share_bundle`).

A bundle's `share_grant.id` and `collection.id` are attacker-chosen and signed with the attacker's own key, which is accepted by design. `_validate_import_grant` only checks that a local row with that id, if present, is active; it never checks that the local share was imported from this origin rather than being a locally-owned outgoing grant. For an unknown origin, `import_share_bundle` auto-creates the peer with `trust_status="unknown"` (`:746`), then `_ensure_imported_share_and_collection` unconditionally runs `INSERT OR IGNORE INTO share_recipients (..., share_payload["id"], peer.id, peer.public_key, 'active', ...)`. `export_share_bundle` then accepts the new recipient because `recipient.recipient_public_key == peer.public_key` trivially holds.

Reproduced (`repro_federation.py`): A shares S with B. C, never paired with A, exports any bundle of its own, rewrites `share_grant.id`/`collection.id` to S's ids with an empty payload, re-signs with its own key. `A.import_share_bundle(forged, trust_policy="candidate_only")` returns `completed`, `share_recipients` for S gains C as `active`, and A's next `export_share_bundle(S, encrypt=True)` lists C's peer id in `encryption_metadata.json["recipients"]`, i.e. the content key is wrapped to C.

Fix: when a local `share_grants` row exists for the payload id and its metadata lacks `imported`/`origin_share`, reject the bundle unless the origin is already an active recipient of that grant; compare `row["namespace"]` with `share_payload["namespace"]`; never insert recipients for locally-owned grants. Add the reproduction above as a regression test in `tests/test_federation_security.py`.

### 2. Namespace-scoped admin can destroy other namespaces

`aletheia/service/http.py:2045-2049` (`_m8_endpoint` authorises `payload["namespace"]` only), `:2130-2139` (forget uses `payload.get("selector")` unchecked), `aletheia/core/hardening.py:2273-2290` (`_forget_targets` takes `selector["namespace"]` / `selector["target_id"]` with no relation to the authorised namespace).

Reproduced (`repro_http.py`): token with `memory:admin` granted on `user/replay-test` only; `POST /v1/forget/apply` with `{"namespace":"user/replay-test","selector":{"namespace":"user/bob"},"mode":"hard_delete","confirmation":"forget memory","reason":"x"}` returned 200 `completed` and `user/bob`'s events went from 1 to 0. The same shape applies to `/v1/redactions/apply` (`target_id`), `/v1/integrity/findings/{id}/repair`, and the whole-DB operations (`/v1/backups/create`, `/v1/exports`, `/v1/restore/apply`, `/v1/support/bundle` with `include_raw_content`) when `namespace` is omitted, which falls through to `require_capability` alone. `docs/v1_4_0_read_contract.md` / `read_contracts.py:157` promise that administrative capability never widens scope.

Fix: resolve each target's namespace (`_namespace_for_target` already exists at `http.py:2991`) and `require_namespace` on it; require `selector["namespace"] == namespace` for selector forgets; require a `"*"` grant for namespace-less whole-DB operations, as `/v1/policies/.../apply` already does (`:1248`).

## High

### 3. Issue #10 — active-write replay returns 409

`aletheia/core/memory.py:6453-6458`:

```python
claim = self.read_claim(claim_id)
if status in ACTIVE_STATUSES:
    self.detect_conflicts(namespace=namespace, claim_id=claim_id)
    claim = self.read_claim(claim_id)
self.recompute_confidence(claim_id=claim_id)   # persists a new confidence_effective
return claim                                   # stale
```

`aletheia/service/onboarding_contract.py:78-80` then treats any difference between `asdict(read_claim(id))` and the cached receipt as an external mutation. Reproduced: first `POST /v1/remember` 200, identical replay 409 `replay_result_changed`; response `confidence_effective` 0.749999999999766 vs stored 0.7499999999851249.

The issue's suggested fix (return the post-recompute claim) closes this case but not the class. The same comparison also fails after any recall that touches `last_accessed_at` (`memory.py:6620`), any confidence recompute (`curate`, jobs, `retrieve(recompute_confidence=True)`), or feedback. `reviews.py:218` has the identical comparison for legacy promote (currently unreachable because of #4).

Fix: (a) re-read after `recompute_confidence` in `write_claim` (and in `promote_candidate`, `promote_inference`, `remember`, see #26); (b) change the replay "unchanged" check to compare an identity/content projection (`id`, `namespace`, `subject`, `predicate`, `object`, `memory_type`, `status`, `evidence_ids`, `valid_from/to`) rather than the whole dataclass, or add a revision counter bumped only by user-visible mutations. Regression tests: immediate replay returns same claim id; replay after a `retrieve` that records usage still succeeds; replay after `supersede_claim`/`demote_claim` still returns 409.

### 4. Legacy candidate promote/reject replay always returns 403

`aletheia/service/reviews.py:224` stores the receipt with `_idempotency_store(**options, status_code=200, response=response)` — no `receipt_access`, so no `_authorization` is persisted. `http.py:2726-2728` then calls `validate_receipt` for every endpoint except `/v1/remember`, and `replay.py:58` raises `forbidden` when the receipt is missing. Reproduced: first promote 200, replay with the same `Idempotency-Key` 403 "Cached result is unavailable under the current access policy; the operation was not repeated." No test covers a successful legacy promote replay (`test_v1_4_review.py` only tests 403/412 legacy paths).

Fix: wrap `legacy_mutation` in `ReceiptAccess(context).capture()` and pass `receipt_access` to `_idempotency_store`, or skip `validate_receipt` for records without `_authorization` on these endpoints (they re-check `access.require("claim", ...)` themselves).

### 5. List endpoints bypass the privacy ceiling

`http.py:1135-1138` (`GET /v1/conflicts`), `:1171-1174` (`/v1/inferences`), `:1189-1192` (`/v1/reflections`), `:1096-1099` (`/v1/sessions`), `:1110-1117` (`/v1/projects`), `:1389-1402` (`GET /v1/reviews`). These call `_require(ctx, "memory:read", {"namespace"})` and return `asdict(item)` for every row, with no `ReadAccess.allowed()` filter. Single-object reads of the same types go through `OperationAccess.target`. Reproduced: a `memory:read`, `personal`-ceiling token gets 403 on `GET /v1/claims/{secret_claim}` but 200 on `GET /v1/conflicts?namespace=…` listing that claim's conflict family with `subject`/`predicate` and claim ids. `ReviewTask.description` is `claim_text(subject, predicate, object)` (`memory.py:5161`), so `/v1/reviews` leaks full candidate text to a token without `memory:review`; `ReadAccess.overview` (`reads.py:250-257`) already does this correctly.

Fix: filter list results with `ReadAccess.allowed(kind, id)`; for review tasks require `memory:review` for candidate tasks, matching `overview()`.

### 6. `/v1/remember` accepts `status: "core"`

`http.py:924` passes `payload.get("status", "active")` to `memory.remember`; `_validate_claim_input` only checks membership in `CLAIM_STATUSES`. Reproduced: `memory:write_active` token created a `core` claim directly, bypassing `/v1/claims/{id}/promote` and its integrity gates. Fix: restrict to `{"active", "candidate"}` at the service boundary.

### 7. `/v1/ingest` ignores the privacy ceiling

`http.py:681-684` and `_ingest_args` (`:3062`) pass `privacy_level` through with no `_requested_privacy` check, unlike `/v1/remember` and the LLM endpoints. Reproduced: `personal`-ceiling token ingested `privacy_level: "secret"` evidence, 200. Fix: call `self._requested_privacy(payload, auth_context)` in the ingest branch.

### 8. Procedure updates clobber unrelated procedures

`memory.py:4476-4499`, `4608-4618`. `WHERE namespace = ? AND status = 'active' AND (procedure_claim_id IS ? OR title = ?)`: when `procedure_claim_id` is NULL, `IS NULL` matches every title-based procedure in the namespace, so applying "Proc B" marks "Proc A" `superseded` and shares one version counter. `rollback_procedure` picks an arbitrary active version via `LIMIT 1`. `next_version` is also read outside the transaction. Fix: branch on NULL explicitly (`(? IS NOT NULL AND procedure_claim_id = ?) OR (? IS NULL AND procedure_claim_id IS NULL AND title = ?)`) and read the version inside the transaction.

### 9. Feedback bypasses `_set_claim_status`

`memory.py:12692-12742`: `UPDATE claims SET confidence_base=?, status=?, last_verified_at=?` directly. `_set_claim_status` (`:12625-12661`) is the only path that cascades `invalidate_derived`; so `feedback(signal="wrong")` rejects a claim while reflections/inferences built on it stay `active`, and it rejects `core` claims that conflict detection deliberately protects (`:12588-12598`). Fix: route through `_set_claim_status`; decide explicitly how `core` responds to `wrong`.

### 10. `resolve_conflict` demotes a `core` winner

`memory.py:7896-7907` unconditionally sets the selected claim to `active`. Fix: `status = "core" if current.status == "core" else "active"`.

### 11. Inference promotion is re-runnable and non-atomic

`memory.py:2176-2211` (`review_inference` has no terminal-state check), `:2244-2354` (`promote_inference` lacks `@_atomic_review`; `write_claim` commits before the link/status transaction). Sequence promote → `review_inference(validate)` → promote creates a second claim and two `derived_claim_links` rows. `_apply_invalidation_action` (`:10303-10310`) shows the intended guard. Fix: reject reviews when status in `{promoted, rejected}`; wrap `promote_inference` in `@_atomic_review` like `promote_candidate`.

### 12. FTS index out of sync on object updates

`memory.py:4536-4543` rewrites `claims.object`; `claims_fts` is content-only (`schema.sql:323-331`, no triggers) and `_index_claim` (`:12404`) is only called from `write_claim`. Lexical search then matches text the claim no longer contains and misses the new text. Fix: delete and re-index inside the same transaction, or add FTS5 `AFTER UPDATE` triggers.

## Medium

### 13. Generic write path is not atomic with its idempotency record
`http.py:431-475, 2707-2740, 2768-2791`. Reservation (`in_progress` row, committed), mutation (own transaction), store (third transaction). A crash between mutation and store leaves `in_progress`; retries get 409 for 5 minutes, then the row is deleted (`:2713-2715`) and the mutation re-executes. `onboarding_contract.py:37` does this correctly inside one `transaction(immediate=True)`. Fix: wrap reserve → route → store in one outer immediate transaction for state-changing endpoints.

### 14. `enc:` sniffing poisons reads
`hardening.py:822-870` dispatches purely on `content.startswith("enc:")`; `write_event` (`memory.py:936-966`) stores plaintext verbatim. A plaintext event starting with `enc:` makes `read_event` raise and `list_events` fail for the namespace; a crafted `enc:v3:<key>:2000000:…` marker forces max-iteration PBKDF2 on every read (`crypto.py:54` allows it). Also reachable via `archive_import.py:179` and `federation.py:2171-2177`. Fix: reject or escape plaintext with the prefix at write time; store an explicit `content_encrypted` flag; cap accepted `kdf_iterations` to what this instance writes.

### 15. Archive import decrypts foreign ciphertext with the local key
`archive_import.py:174-203`: `reveal_content_from_storage` on archive rows, then re-stored with the archive's `privacy_level`. Someone holding encrypted rows from a stolen backup but not the key can wrap them in an archive labelled `public`; import decrypts and stores plaintext. Fix: refuse `enc:` content from archives unless the archive is authenticated and originates from this instance, or import as opaque ciphertext.

### 16. Backup manifest unauthenticated; `import_archive` lacks the `trust_unauthenticated` gate
`hardening.py:203, 2045-2046` (`encrypt_bytes_with_passphrase` with no AAD), `:355-377`, `archive_import.py:117-121`. `manifest.json` (namespace, privacy_mode, encrypted flag, key id) is covered only by a rewritable checksum file. `restore_backup` mitigates with `trust_unauthenticated` (`:421-428`); `import_into` does not, and with `namespace=None` imports into any namespace named in the archive with no per-namespace authorisation hook. Fix: pass canonical manifest JSON as GCM AAD; require `trust_unauthenticated` or encryption in `import_into`; require an explicit target namespace.

### 17. Lookup-by-remote-controlled-name
`federation.py:310` (`get_peer … OR display_name = ?`), `:532` (`get_share_grant … OR name = ?`), `:609` (`get_sync_collection … OR name = ?`). `display_name` comes from the remote identity payload; imported share/collection names from the bundle. A peer can set its display name to another peer's id; `fetchone()` with `OR` returns whichever row SQLite finds first, so `trust_peer`, `revoke_peer`, `create_share_grant(recipient_peer_ids=…)`, `replace_peer_key`, `sync(peer_id=…)` can act on the wrong object. The import path was fixed (`:1977` comment); operator-facing lookups were not. Fix: resolve by id first; fall back to name only when no id matched and exactly one row matches; drop name lookup for security-relevant mutations.

### 18. `benchmark_run` leaves a DB snapshot in `/tmp`
`hardening.py:1731-1744`: `create_backup(output_path=tempfile.gettempdir()/…, encrypt=protected.backup_encryption_required)` — plaintext physical copy (all namespaces, token hashes, federation identity metadata) with default umask, never removed; also inserts benchmark events/claims into the live namespace (`:1725-1726`). Reachable via `POST /v1/benchmarks/run` (`http.py:2212`). Fix: `TemporaryDirectory()` with cleanup, force encryption, use a scratch namespace or DB.

### 19. Deferred `BEGIN` defeats `busy_timeout`
`sqlite.py:147-154`. In WAL mode a deferred read-then-write transaction cannot upgrade if another connection committed in between; SQLite returns `SQLITE_BUSY_SNAPSHOT` immediately. Subagent reproduced: deferred path fails after 0.00 s; `BEGIN IMMEDIATE` waits the full 5 s. 18 call sites pass `immediate=True`; 156 use the default. Impact: concurrent CLI + daemon produce spurious `OperationalError`s (no corruption). Fix: default `immediate=True`; keep deferred only for explicitly read-only snapshots.

### 20. ASCII-only tokenizer
`lexical.py:42-48` (`[A-Za-z0-9_]+`), `:265-284`. `"日本語のメモ"` → `""` → "empty search" branch → top-N claims by confidence/recency returned as hits with `lexical_score=0`. Same ASCII assumption in `semantic._semantic_tokens` and `llm._keywords`. Fix: Unicode `\w+` matching FTS5 `unicode61`; when the query had text but no tokens, return `[]`.

### 21. Provider clients forward `Authorization` across redirects
`llm.py:221-229`, `semantic.py:216-224`: default `urlopen` unless `*_LOCAL_ONLY`. Subagent reproduced the API key arriving at the redirect target. `client.py:14-20` and `tests/test_sdk_redirects.py` hardened the SDK against exactly this. Fix: build both openers with `NoRedirect()` unconditionally; cap `response.read()` (see #32).

### 22. LLM extraction skips injection flagging
`extraction.py:228-242` vs `:631-647`; gate at `memory.py:9040`. `_risk_metadata()` runs only in `RuleBasedExtractor`, so the `risk_severity in {high, critical}` promotion gate never fires for LLM-extracted candidates, and the model controls every non-protected metadata key. Fix: run `_risk_metadata(span_text)` in `_drafts_from_output` and merge after model metadata; whitelist model-supplied keys.

### 23. Protected-mode auth and ignored bearer
`http.py:2589-2598` vs `:2603-2610`: `/v1/auth/me` computes `auth_required = config.auth_required or protected is None or protected["enabled"]`; the general branch uses `config.auth_required` only. With `--no-auth` and protected mode on, `/v1/auth/me` returns 401 while data endpoints serve the tokenless context. In tokenless mode a supplied `Authorization` header is ignored (`auth.py:276-284`), so a revoked/narrow token "works" with default grants. Fix: hoist the protected check; validate a bearer whenever present.

### 24. Writes with `memory:read`
`http.py:1510-1533` (`/v1/reports/export` writes a file whose payload bypasses `ReadAccess`), `:1487-1491` (`GET /v1/metrics/latest` calls `metrics_snapshot`, a write that the POST gates behind admin), `:1499-1507` (notification dismiss/snooze). Fix: gate export behind `memory:audit`/`memory:admin` and run it through `ReadAccess`; make `metrics/latest` read-only.

### 25. PBKDF2 per request under the global lock
`auth.py:289-305`, `http.py:399-400, 600/605, 2771, 2728`. No verified-token cache; a write with `Idempotency-Key` authenticates up to three times at 600k iterations each, all under `self.lock`. Rate limiting runs after authentication (`:419`). Fix: cache `(token_prefix, sha256(raw)) → token_id` with invalidation on revoke, or carry the verified context through `previous` for bearer tokens.

### 26. Stale-return / split-transaction pattern (family of #3)
`promote_candidate` 1879-1963, `promote_inference` 2300-2354, `remember` 6523, `promote_claim`/`demote_claim` 7254-7317 (`_write_curation_decision` INSERT at 13387 runs outside any transaction), `feedback` 7344-7382, `resolve_conflict` 7825-7969, `supersede_claim` 8078-8099, `scope_claim` 8118-8128, `end_session` 7165-7197, `create_project` 7028-7084, `ingest` 1053-1138, `draft_reflection_with_llm` 1631-1648, `optimize_retrieval` 3832-3895. Only four public mutators use `@_atomic_review`. Fix: adopt it broadly and re-read before returning.

### 27. Proposal review has no state machine
`memory.py:4015-4048`, `4431-4464`; `apply_policy_proposal` only requires `status == "approved"` (`:4060`), so applied → approve → apply creates another version; rejected proposals can be approved. Fix: allow approve/reject/request_changes only from `pending_review`/`draft`.

### 28. `write_event` dedup ignores stricter privacy
`memory.py:947-959`; `stable_event_id` (`ids.py:9-27`) excludes privacy/trust. Re-writing identical content as `secret` leaves the row `personal` and unencrypted, silently. Existence check is also outside the transaction (TOCTOU `IntegrityError` for threaded library users). Fix: escalate privacy/re-encrypt when the request is stricter; `INSERT … ON CONFLICT DO NOTHING` inside the transaction.

### 29. Redaction residue
`deletion.py:76-158` scrubs claims, spans, mentions, audit, traces, review tasks by `target_id`, but not `conflicts`/`conflict_families` (`subject`, `predicate`), conflict review tasks (title `Resolve conflict for {subject}.{predicate}`, `memory.py:5175`), `semantic_clusters.label` (`{memory_type}:{predicate}`, `:10033`), `entities.canonical_name`/`entity_aliases.alias`, or `claim_status_history.reason`. Fix: extend the scrub list.

### 30. `recompute_confidence` cost and growth
`memory.py:7527-7567` → `compute_confidence` (~9 queries/claim) + `_persist_confidence_snapshot` (1 UPDATE + 2 INSERTs per claim, every run, even when unchanged). Triggered from `resolve_claim` (`:6991`, a lookup), `create_project` (`:7062`), `retrieve(recompute_confidence=True)` (`:6569`), `curate` (`:8140`), jobs. `curate` then processes only `limit=1000` claims (`:8146`). Fix: make `resolve_claim` read-only; batch factor loads; skip snapshot rows when values are unchanged; paginate `curate`.

### 31. Archive file permissions
`hardening.py:154-155` (`_write_zip` with plain `"w"`), `:2039-2042`, `:1598-1599`; CLI defaults `main.py:1382-1386` (`--type physical --privacy-mode full`, `--encrypt` off). The DB is created `O_EXCL|0o600` (`sqlite.py:64-68`) but a full physical copy lands at umask permissions and truncates any existing `--output`. Fix: `os.open(path, O_WRONLY|O_CREAT|O_EXCL, 0o600)`; refuse overwrite without a flag.

## Low

- `http.py:727, 729, 1064, 1066, 1071, 1180, 1182`: `payload["reason"]` → `KeyError` → 500 `internal_error` instead of 400.
- `http.py:3973-3986`: OpenAPI error-code enum omits `unsupported_contract`, `replay_result_changed`, `database_busy`, `service_closed`, `pairing_*`, `request_timeout`, `stale_revision`, `review_conflict`, `precondition_required`, `stale_cursor`, `invalid_cursor`, `review_scan_limit`, `provider_input_changed`; lists `conflict`, `integrity_gate_failed`, `unsupported_operation` which are never emitted. `review_contracts.py:16` carries a second partial list.
- `http.py:1465, 1539, 1684, 1803, 1502, 1414`; `reads.py:138-141`: object lookup before namespace check, and distinct "not found" vs "unavailable under access policy" messages, make other-namespace ids confirmable.
- `main.py:50, 1384, 1391, 1406, …` and `docs/backup_restore_guide.md:10-17`: `--passphrase` on argv (visible in `ps`); `mcp --token` is correctly rejected (`:3959-3962`) but passphrases are not, and the guide leads with argv.
- `client.py:218, 246, 249, 255, 330, 340, 343, 361-373, 397, 415-421`: path parameters not URL-encoded (review-profile methods at `:226, 241` do it right).
- `llm.py:229`, `semantic.py:224`, `client.py:492`: unbounded `response.read()`; `diagnostics.py:54-64` has the bounded reader to reuse. `hardening.py:378, 2034-2036`, `federation.py:1947-1952`: all zip members read fully into memory with no size cap.
- `semantic.py:206-215`: embedding request carries a non-standard top-level `metadata` (namespace, privacy level) to third-party providers; OpenAI's endpoint rejects unknown top-level args.
- `memory.py:11257-11313`: jobs crash-stranded in `running` are never reclaimed; `_fail_running_job` re-pends without backoff.
- `memory.py:5263-5286`: `generate_review_tasks` recreates risk-flag tasks after each resolve/dismiss.
- `memory.py:6768-6774`: with `_read_access` set (every HTTP request), `context_pack` drops all non-conflict warnings (`reflection_stale`, `inference_stale`, `candidate_memory`). Possibly intentional; no comment says so.
- `memory.py:1801-1802`: `review_candidate(decision="edit")` resets status to `pending_review`.
- `memory.py:6320-6362`: `importance` unclamped, `half_life_days<=0` accepted (`or` turns `0` into default), duplicate `evidence_ids` raise `sqlite3.IntegrityError` not `ValidationError`; `enqueue_job` (`:4809`) `int(payload.get("max_attempts"))` can raise; naive `run_after` compared as string to `utc_now_iso()` (`:4880, 11309`).
- `memory.py:10294-10331`, `:11325-11329`: raw status UPDATEs without status history or terminal guards.
- `memory.py:1368, 4832, 5557, 5747, 5843, 6063`: `list_llm_runs/jobs/traces/notifications/reports/categories` return all namespaces when `namespace` is omitted (other `list_*` default to `self.namespace`). Service layer appears to always pass one; not verified for every route.
- `memory.py:7335-7382` and siblings: kernel never checks target namespace on by-id mutations; `feedback(namespace=A, target_id=<claim in B>)` writes an `A`-tagged row and mutates B. HTTP compensates via `OperationAccess.target`; SDK/library/MCP-direct callers do not.
- `sqlite.py:340-409, 469-495`: re-running the migration re-executes `INSERT OR IGNORE` backfills, labelling current values as "M2/M3 migration backfill" audit rows for claims that never went through M2/M3; `SUPPORTED_MIGRATION_FROM` is not enforced. `sqlite.py:169-172`: savepoint rollback failure masks the original exception.
- `hardening.py:410-420, 448-449, 375-384`: `restore_backup(verify_before=False)` can never apply; encrypted verify returns `passed` even with warnings while plaintext returns `passed_with_warnings`. `:219-284`, `platform.py:1200-1201`: readiness/doctor "verified backup exists" counts manifests, not verifications; a failed `verify_after` leaves archive and manifest row behind.
- `federation.py:855-856`: `sync(input_path=…)` imports without binding to the requested collection or `trust_policy`. `:2151-2158`: one changed remote object aborts the whole bundle (documented as deliberate; consider per-object `sync_conflict`). `:712-715, 2171-2178, 2437-2441`, `archive_import.py:129-135`: untrusted bundle fields used without type validation → 500s. `crypto.py:144-146`: legacy unsalted SHA-256 hashes still accepted with no upgrade-on-verify.
- `auth.py:226-241`: `revoke_token` overwrites `metadata_json`, dropping `local_pairing_identity`/`console_session` markers.
- `.github/workflows/release-gates.yml:73-74` hardcodes `--expected-version 1.6.0 --previous-version 1.5.0`; `publish-pypi.yml:38-48, 86` skips the tag↔version check on `workflow_dispatch`; actions pinned by major tag, not SHA.

## Things checked and found sound

Bearer verification is constant-time (`crypto.py:142,146`) with salted PBKDF2 and legacy-hash upgrade on first use. Review-protocol replay is scoped `sha256([credential, key])` with a method/endpoint/namespace/payload fingerprint, 24h TTL, inside the same `BEGIN IMMEDIATE` as the mutation; cursors are Fernet-encrypted, scope-bound, 900 s TTL. Generic idempotency keys are per credential and endpoint; `validate_receipt` rejects replays when grants/ceiling changed. Pairing: 256-bit secret, 5-minute ticket, 5-failure lockout, pinned TLS, token bound to transport identity. Request handling rejects duplicate framing headers, chunked bodies, oversized bodies, non-loopback `Host`/`Origin`; `X-Request-ID` is validated before echo; console cookies are `HttpOnly; SameSite=Strict` with CSRF. Primitive-level crypto (AES-256-GCM random nonces, HKDF/X25519 wrap, Ed25519, PBKDF2 600k, `compare_digest`, `O_EXCL|O_NOFOLLOW` 0600 recovery files, AAD on key envelopes and bundle manifests) is correct; the gap is the backup envelope (#16). No `pickle`/`eval`/`shell=True`; the only `exec` runs AST-verified adapter code. All SQL is parameterised; f-string fragments interpolate only constants or `?` placeholders. FTS5 injection is not possible (tested `NOT`, `OR`, `near`, `_`). The SDK blocks redirects, verifies TLS, retries GET only. `cryptography>=50.0.1` resolves (`uv.lock:127-150`); version strings are consistent across `pyproject`, `CHANGELOG`, `README`, `SECURITY`, CI.

## Suggested fix order

1. #1 and #2 (security, reproduced) — patch and release as 1.6.1 with regression tests.
2. #3, #4 together (the replay contract), plus the projection-based "unchanged" check so #26-class drift cannot reintroduce it.
3. #5, #6, #7 (service-boundary authz gaps; each is a few lines).
4. #8-#12 (core correctness, all reproduced).
5. #13-#31 by area; #19 (default `BEGIN IMMEDIATE`) and #25 (token cache) are the two that most affect day-to-day use.

## Reproduction scripts

`repro_http.py` (issue #10, #2, #4, #5, #6, #7) and `repro_federation.py` (#1) were run against the `v1.6.0` tree with disposable databases. They are not committed; they are suitable seeds for regression tests in `tests/test_service_security.py` and `tests/test_federation_security.py`.
