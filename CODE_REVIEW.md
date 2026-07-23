# Code Review: Aletheia

**Scope:** Full `aletheia` package (~27k LOC across core, service, storage, retrieval, models, CLI, and the uncommitted sample adapter integration) plus the test suite.
**Date:** 2026-07-02
**Reviewer focus:** correctness, security, architecture, performance.

---

## Summary

Aletheia is an ambitious "governed LLM memory" library with a genuinely thoughtful design: a candidate/promotion trust boundary, parameterized SQL throughout, privacy ceilings, audit trails, and behavioral tests that verify governance actually holds. The bones are good.

But it is **not production-ready**, and the gap is concentrated in two areas. First, the security substance behind the security *vocabulary* is largely missing — federation "encryption" and "signatures" are cosmetic, protected content falls back to a hardcoded key, and tokens use unsalted SHA-256 with non-constant-time comparison. Second, the codebase is carrying serious structural debt (a 13k-line `Memory` god-class, a 4.4k-line CLI, a 3.1k-line HTTP handler) that has already produced concrete bugs — a silently shadowed duplicate method, divergent validation paths, and pervasive nested-transaction hazards.

The uncommitted sample adapter integration should **not be committed as-is**: it leaks claim data before authorization, bypasses the governance pipeline with raw SQL, and has zero tests.

**Verdict: Request Changes.** Address the Critical and High security items before any non-loopback deployment; the sample adapter work needs a hardening pass before commit.

---

## Critical Issues

| # | File:Line | Issue | Category |
|---|-----------|-------|----------|
| C1 | core/federation.py:1400–1415 | Bundle "encryption" derives its key from `manifest.json`, which is shipped in plaintext inside the same zip; the cipher is repeating-key XOR. Provides zero confidentiality — anyone with the bundle can decrypt. | 🔴 Security/Crypto |
| C2 | core/federation.py:1122, 1305, 1386 | No real cryptography in the federation trust model. "Public keys" are `"fedpub_" + sha256(...)` (no keypair), signatures are unkeyed content hashes anyone can recompute, identity fingerprints are self-verifying. Every peer, bundle, and changeset is forgeable. | 🔴 Security/Crypto |
| C3 | core/hardening.py:1859 | Protected/secret content encryption falls back to a compiled-in constant passphrase `"aletheia-local-protected-content-key"` when no env key is set (the default). All "encrypted" sensitive content is encrypted under a publicly known key, silently. | 🔴 Security/Secrets |
| C4 | service/auth.py:72–81 (via mcp.py:315, platform.py:1359) | When `auth_required=False` (the default for MCP and embedded modes), `AuthContext` with `token=None` returns **all** capabilities, `namespace_grants=["*"]`, and `privacy_ceiling="secret"`. Any local caller that reaches the MCP stdio or an unauthenticated HTTP service gets unrestricted admin + secret access. | 🔴 Security/AuthZ |
| C5 | core/memory.py:6536 | `retrieve()` defaults `recompute_confidence=True`, which loads *every claim in the namespace* and runs ~6 queries + 1 UPDATE + 2 INSERTs per claim on the **read path**. Reads are O(N) queries and O(N) writes, and telemetry tables grow quadratically. `context_pack`/`resolve_claim` inherit it. | 🔴 Performance |

*All five verified directly against source.*

---

## High-Severity Issues

### Security

| # | File:Line | Issue |
|---|-----------|-------|
| H1 | service/auth.py:268, 318 | API tokens stored as **unsalted SHA-256** and compared with `!=` (not constant-time). Use `hmac.compare_digest` and a slow keyed KDF (argon2/scrypt or HMAC-with-server-secret). Same non-constant-time `!=` on console session/CSRF/login tokens (http.py:2000, 2149). |
| H2 | service/http.py:1696–1852, 2983 | Admin endpoints take caller-controlled filesystem paths with no sandboxing: backup/restore/export `output_path`/`target_db_path`, import `input_path`, and `install_plugin(plugin_path)`. Arbitrary local file read/write + code loading for any admin-token holder. `/v1/doctor/run` takes a `service_url` (SSRF-adjacent). |
| H3 | service/http.py:2792 | Request body fully buffered (`self.rfile.read(Content-Length)`) *before* the `max_request_bytes` check runs — trivial memory-exhaustion DoS. Malformed `Content-Length` also raises an uncaught `ValueError`. |
| H4 | service/http.py:406, errors.py | Catch-all returns raw `str(exc)` in the JSON error body — leaks SQLite errors, file paths, KeyErrors to clients. |
| H5 | core/hardening.py:110–119 | `create_backup` embeds a full physical DB snapshot (incl. raw evidence and the `api_tokens` table) regardless of `privacy_mode`; the manifest then falsely records `includes_raw_content: false` for redacted/metadata-only backups. |
| H6 | core/federation.py:274–292 | `add_peer` upserts a peer's `public_key`/`fingerprint` without resetting `trust_status` — TOFU key-substitution. Re-importing a bundle that reuses a trusted peer's `instance_id` with a new key silently swaps the key while keeping trust. |
| H7 | core/federation.py:651–676 | `import_share_bundle` dry-run mutates: `_peer_for_import` (which calls `add_peer`, possibly `trust_peer`) runs *before* the `if dry_run:` return, so a "dry run" of an untrusted bundle inserts/trusts a peer. **Verified.** |
| H8 | core/federation.py:602–648 | Share-grant `expires_at` is stored and there's an `"expired"` status, but nothing ever checks it — expired grants export/sync forever. |
| H9 | core/memory.py:12272 (via write_claim) | Writing a contradicting claim sets *every* claim in the family to `disputed`, including `core` claims — and `disputed` is excluded from default retrieval. Cheap memory-poisoning / denial vector against established core memories. |
| H10 | integrations/sample_adapter.py:472 + service/http.py:777–798 | `_sample_adapter_remember` runs `find_duplicate_sample_adapter_claim` / `find_structured_conflict` (returning claim IDs and evidence) **before** the capability check, and with no privacy filtering (unlike `_sample_adapter_forget`). A read oracle over claims the token cannot see. |
| H11 | platform.py:279–303 | `install_plugin(approve_permissions=True)` sets `status="enabled"` directly, bypassing `enable_plugin`'s per-permission approval and high-risk gating. No grants are ever checked at operation time — the permission model is recorded but never enforced. |
| H12 | integrations/sample_adapter.py:388–469 | `create_sample_adapter_candidate` hand-writes INSERTs into 5 tables, hardcodes `contradiction_risk`/`duplicate_risk` to `0.0`, and calls private `memory._write_audit`. sample adapter candidates skip the risk scoring used for review triage and will break on any schema migration. |

### Correctness / Architecture

| # | File:Line | Issue |
|---|-----------|-------|
| H13 | core/memory.py:10387 & 10740 | `_active_ranking_policy_version_id` is **defined twice**; the parameterless version at 10740 silently shadows the parameterized one at 10387, making non-default ranking policies unreachable. A direct symptom of the 13k-line file. **Verified — delete the second def.** |
| H14 | core/memory.py:7668, 2901 | Nested `with self.store.connection:` blocks. Python's sqlite3 context manager does not nest — the inner `__exit__` **commits the outer transaction mid-flight**, so a later failure leaves a half-applied conflict resolution durably persisted. Pervasive pattern (also federation.py:354, hardening.py:798). |
| H15 | core/memory.py:1742, 8888 / 2137 | Candidate/inference "edit" review bypasses promotion gates: `_apply_candidate_edits` writes `candidate_status`/`privacy_level`/`suggested_confidence` verbatim with no enum/clamp validation, so `{"candidate_status": "promoted"}` promotes without any gate. Contrast `_apply_inference_edits`, which validates. |
| H16 | core/memory.py:8043 | `curate()` auto-promotes to core with `force=True`, explicitly overriding every promotion gate (unresolved conflicts, low confidence). The unattended pipeline bypasses exactly the protections a "governed" store exists for. |
| H17 | core/hardening.py:1085–1103 | `repair_integrity` for `fts_drift` does `DELETE FROM claims_fts` (all namespaces) then re-indexes only the current namespace (capped at 100k) — destroys every other namespace's FTS index, outside any transaction. |
| H18 | retrieval/lexical.py:205–218 + core/memory.py:11706 | Retrieval has no SQL `LIMIT` and fires ~3–7 follow-up queries **per candidate row** before truncating to `limit`; a blank query full-scans all claims. Degrades linearly with corpus size. |
| H19 | cli/main.py:47, 856 | `--db` defined on both parent and leaf subparsers; argparse clobbers the parsed value with the leaf default, so `migrate --db custom.db apply` migrates `./aletheia.db` instead — destructive write to the wrong database. |
| H20 | models/integrity.py:110 | `ConflictResolution.status` is a property hardcoded to `return "resolved"` — every instance lies. **Verified.** |
| H21 | tests / git status | The uncommitted sample adapter work (816-line integration, new endpoints, CLI block) has **zero tests**; `tests/fixtures/sample_adapter/` is an empty skeleton. |

---

## Selected Medium Issues

A representative set (full list of ~40 mediums available on request):

- **Mass-assignment via `**payload`** (service/http.py:833–954): ~15 handlers splat the raw request body into kernel methods (`scope_claim(**payload)`, `create_project(**payload)`, `resolve_conflict(**payload)`…), letting clients inject keywords that bypass the top-level namespace/authz checks. Whitelist fields per endpoint.
- **Read-before-authz** (service/http.py:822): `_claim_endpoint` reads the claim before checking capability/namespace — leaks existence (404 vs 403) and enables enumeration.
- **Rate limiting exempts unauthenticated traffic** (service/http.py:357): only runs when `client_id` is set, so login/health/no-auth endpoints are unthrottled. The routing lock also serializes the whole "threading" server.
- **LLM-controlled provenance/privacy** (extraction.py:198–221): model output `metadata.update()` can overwrite trusted keys (`llm_output`, `provider`); model can set candidate `privacy_level` below the source event's; evidence span offsets/text are never bounds-checked against the source, and `suggested_confidence` is unclamped.
- **Job runner race** (core/memory.py:4758): jobs are SELECTed then marked `running` in a separate transaction — two processes on one DB run the same job twice. Claim atomically with `UPDATE … WHERE status='pending'` + rowcount.
- **Migrations rerun every open** (storage/sqlite.py:61–89): `SCHEMA_VERSION` is written but never read; the full schema + 10 backfill scans re-execute on every `Memory.open()`, non-atomically, with no forward-compat guard. Startup cost grows with DB size.
- **Retention half-implemented** (hardening.py:914): `run_retention` ignores `privacy_level`/`source_type` filters; 4 of 6 retention actions match rows but silently do nothing.
- **Home-rolled crypto duplicated** across federation.py and hardening.py with *different* weak schemes — should be one vetted AEAD utility.
- **"merged" that doesn't merge** (integrations/sample_adapter.py:472): duplicate remember returns `kind="merged"` but appends no evidence and drops the observation; the check also costs ~60 queries per call.
- **Path/thread/nullable-key issues** (storage/sqlite.py:47, 50, 159): `expanduser()` applied to mkdir but not the connect string; shared connection with `check_same_thread=False` and no lock; nullable `index_version` in a UNIQUE upsert key causes silent duplicates.

---

## What Looks Good

- **Governance-first design is real, not just claimed.** LLM output can only ever become a *candidate*; promotion to active/core goes through explicit gates. The trust boundary is the right architecture, and the tests verify it (e.g., negative tests proving external providers are never called on private data).
- **SQL injection: none found.** Every caller-supplied value uses `?` placeholders; f-strings near SQL interpolate only hardcoded identifiers. FTS input is sanitized to `[A-Za-z0-9_]+`. No `pickle`/`eval`; deserialization is `json.loads` only.
- **No mutable-default-argument bugs** in the ~90 model dataclasses — `default_factory` is used correctly throughout.
- **Tests are behavioral and isolated.** Specific assertions on status transitions and HTTP error codes, `tmp_path` isolation everywhere, no sleeps or ordering dependencies.
- **CLI is architecturally thin** — mostly `memory.<method>()` + `json.dumps`, no shell/subprocess/eval.

---

## Recommended Priorities

1. **Before any non-loopback deployment (blockers):** C1–C4 (crypto + default god-context), H1–H4 (token hashing, path sandboxing, body limits, error leakage).
2. **Correctness landmines:** H13 (duplicate method), H14 (nested transactions — fix structurally with a transaction/unit-of-work helper), H15–H16 (governance bypasses).
3. **Before committing sample adapter:** H10, H12, H21 (authz ordering + privacy filter, governance-respecting candidate creation, tests).
4. **Structural debt (schedule, don't rush):** split `core/memory.py` by lifecycle stage behind a `Repository` that owns transactions; this also fixes H14 at the root. Split the CLI and HTTP handler along the milestone seams already implied by the code.
5. **Performance:** move confidence recompute off the read path (C5); batch the N+1 hydration and retrieval scoring (H18); gate migrations behind the version check.

---

*Findings were produced by five parallel focused reviews (core memory; federation/hardening/platform; service/security; storage/retrieval; CLI/models/tests) and the highest-severity items were re-verified against source.*
