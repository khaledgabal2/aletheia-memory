# v1.3.0 Remediation — Post-Mortem & Follow-Up TODO (for Codex)

Independent verification of Phases 1–3 (main baseline, non-sample adapter). Verdicts are from
reading the shipped code directly, not the closure checklist. Test suite was **not**
re-run during this pass (the environment had Python 3.10; the code requires 3.13),
so the "149 tests pass" claim is taken on trust — code-level review is the basis below.

## Codex follow-up closure evidence (2026-07-02)

- [x] H11 runtime plugin grants: `run_plugin_operation` now maps operations to required
  grants and blocks unapproved runtime operations with an audited `blocked` log.
  Evidence: `tests/test_m9_stable_platform.py::test_m9_plugin_lifecycle_and_active_write_governance`.
- [x] H17 FTS repair atomicity: namespace FTS rebuild now refuses unscoped repair and
  wraps delete + reindex in `memory.store.transaction()`.
  Evidence: `tests/test_m8_production_hardening.py::test_fts_repair_is_scoped_to_finding_namespace`
  and `::test_fts_repair_rolls_back_and_refuses_unscoped_delete`.
- [x] H2 doctor URL SSRF/redirect bypass: doctor health checks now disable redirects,
  validate redirect targets before rejection, require HTTP(S), and resolve `localhost`
  through loopback checks.
  Evidence: `tests/test_m9_stable_platform.py::test_doctor_service_url_rejects_redirects_and_spoofed_localhost`.
- [x] Rate-limit header spoofing: anonymous rate-limit identity ignores
  `X-Forwarded-For`/`X-Real-IP` unless `trust_proxy_headers` is explicitly enabled.
  Evidence: `tests/test_m6_memory_service.py::test_rate_limit_applies_per_token_and_can_be_disabled`.
- [x] Retention per-evidence matching: retention now matches effective claim privacy
  and requires all linked evidence sources to satisfy a source filter.
  Evidence: `tests/test_m8_production_hardening.py::test_retention_filters_use_effective_claim_privacy_and_source_set`.
- [x] H14 raw transaction residue: remaining reviewed `with ...store.connection:`
  contexts in CLI/hardening paths were converted to `store.transaction()`.
  Evidence: pattern sweep across `aletheia/cli/main.py`, `aletheia/core/hardening.py`,
  `aletheia/core/platform.py`, `aletheia/core/federation.py`, and
  `aletheia/core/memory.py`.
- [x] Semantic vector search boundedness: semantic/hybrid retrieval now scores only
  vectors for the bounded governed candidate claim IDs instead of every indexed vector
  in the namespace.
  Evidence: `tests/test_m3_intelligent_ingestion.py::test_semantic_and_hybrid_retrieval_respect_governance_filters`.
- [x] Governed-query filter de-duplication: lexical and semantic/hybrid retrieval now
  share the same status/type/project/session/category SQL clause builder, including
  namespace-scoped category labels.
  Evidence: `tests/test_m1_reliable_recall.py` and
  `tests/test_m3_intelligent_ingestion.py::test_semantic_and_hybrid_retrieval_respect_governance_filters`.
- [x] C2 federation trust anchor + encrypted identity private keys: newly protected
  federation identities store encrypted private refs, protected identity creation
  requires a configured federation/protected key, and trusted-device bundle imports
  require a previously added and trusted peer.
  Evidence: `tests/test_m10_federated_memory.py::test_federation_identity_private_key_ref_is_encrypted_and_requires_key`
  and `::test_trusted_device_import_requires_pretrusted_peer`.

Verification run: `uv run pytest tests/test_m6_memory_service.py tests/test_m8_production_hardening.py tests/test_m9_stable_platform.py`
passed 40 tests; `uv run pytest tests/test_m1_reliable_recall.py tests/test_m3_intelligent_ingestion.py`
passed 20 tests; `uv run pytest tests/test_m10_federated_memory.py` passed 12 tests;
`uv run pytest` passed 140 tests on Python 3.13.13.

## Scorecard

- Solidly fixed (18): C1, C3, C4, H1, H3, H4, H5, H6, H7, H8, H9, H13, H15, H16, H19, H20, and the mediums (mass-assignment, read-before-authz, LLM trust boundary, C5 read-only retrieve, job-race atomic claim, migration version gate, storage path/key).
- Partial — reopen (4): **C2, H2, H11, H17**.
- New/residual issues found (6): semantic scan unbounded, rate-limit header spoofing, retention per-evidence matching, H14 raw-context residue, federation private keys at rest, duplicated governed-query logic.

---

## Post-Mortem: what the checklist got wrong

The remediation was largely real and high quality. Three recurring patterns explain
every gap below, and are the thing to fix in *process*, not just code:

1. **"Closed" was scoped to "the test passes," not "the finding is eliminated."**
   H11's original finding was *runtime grant enforcement*; the fix delivered
   install/enable separation and a test for that, and the row was closed — but the
   operation path is still ungated. H17 was closed on namespace scoping while the
   "in a transaction" half of the same finding was never implemented. Closure
   evidence should restate the *full* original finding and show each clause met.

2. **Fixes stopped at the first code path; siblings were missed.** H2 fixed
   filesystem paths thoroughly but left the SSRF/redirect path. H14 converted the
   named write paths but left raw `with store.connection:` in three places. When a
   finding names one instance, grep for the pattern class before closing.

3. **Scale/correctness behavior wasn't checked beyond the fixture.** The bounded-query
   fix (H18) is real for lexical but the semantic vector path still scan-and-scores the
   whole table; retention honors filters but matches per-evidence-row. Small test data
   hides both. Closure for perf/data findings needs a bounded-cost assertion or a
   large-N check, and a "what does this do at 1M rows / multi-evidence claims" note.

No regressions were introduced in the solidly-fixed set. Crypto choices (AES-GCM,
X25519, Ed25519, PBKDF2 + `compare_digest`) are correct and centralized in
`core/crypto.py` — good call.

---

## TODO — Reopen (must fix before the baseline is "closed")

### 1. H11 — enforce plugin permission grants at operation time  `[High]`
- File: `aletheia/core/platform.py:519` `run_plugin_operation`.
- Problem: only checks `installation.status == "enabled"` and blocks active writes.
  No check that the operation's required permission is in the approved grants, so
  enable-time approval/denial has zero runtime effect.
- Fix: map each operation to its required permission(s); verify against the plugin's
  approved `plugin_permission_grants` before dispatch; deny + audit on miss.
- Done when: a test enables a plugin *without* a given permission and the corresponding
  operation is rejected (not just active-write ops).

### 2. H17 — make FTS repair atomic and remove the unscoped delete  `[High]`
- File: `aletheia/core/hardening.py:1216` (`fts_drift` branch).
- Problem: DELETE + reindex use bare `connection.execute` — not wrapped in
  `memory.store.transaction()` (the closure note claims it is). A crash mid-reindex
  leaves the namespace unsearchable. The `else: DELETE FROM claims_fts` (all
  namespaces) fallback also still fires when a finding has no resolvable namespace.
- Fix: wrap the whole delete+reindex in `with memory.store.transaction():`; when no
  namespace resolves, refuse the repair rather than nuking all namespaces.
- Done when: a two-namespace test proves repair of ns A leaves ns B's FTS intact, and
  an induced failure mid-reindex rolls back.

### 3. C2 — establish a federation trust anchor + protect keys at rest  `[High]`
- File: `aletheia/core/federation.py` (`_validate_peer_identity_payload`, `_new_key_material`).
- Problem A: signatures are cryptographically real, but a self-minted identity passes
  validation (only self-checks `fingerprint == sha256(pubkey)[:32]`). A signature
  proves key possession, not legitimacy — trust rests entirely on `trust_policy`.
- Problem B: identity private keys are serialized with `NoEncryption()` into the DB, so
  DB read access = impersonation + inbound-bundle decryption.
- Fix: verify imported peer keys against a pinned/out-of-band fingerprint (TOFU with
  explicit pin, or an operator-confirmed trust step) before `trusted_device`
  elevation; encrypt private key material at rest under the configured protected key.
- Done when: importing a bundle whose identity key doesn't match a pinned fingerprint
  is rejected; private-key column is ciphertext.

### 4. H2 — close the SSRF redirect/localhost bypass  `[Medium-High]`
- File: `aletheia/service/http.py` / `aletheia/core/platform.py` `_validate_service_url`.
- Problem: URL is validated once, but `urllib.request.urlopen` follows redirects, so a
  loopback URL that 302s to `169.254.169.254`/internal hosts is never re-checked; the
  `localhost` literal early-return also skips the IP resolution check.
- Fix: use an opener with redirects disabled (or re-validate every hop), resolve and
  check the literal `localhost` too, and reject non-HTTP(S) schemes.
- Done when: a redirect-to-internal target and a `localhost`→non-loopback DNS entry are
  both denied.

---

## TODO — New / residual issues

### 5. Semantic vector search is unbounded  `[Medium, scale]`
- File: `aletheia/semantic.py:369` `SQLiteVectorStore.search`.
- Loads and cosine-scores every embedding in the namespace, then slices `[:limit]`.
  Fine on test data, O(N) memory+CPU per semantic/hybrid retrieve and context_pack at
  scale. Add a candidate pre-filter/LIMIT (or ANN index) and assert bounded cost.

### 6. Rate-limit bucket is spoofable for anonymous clients  `[Medium, security]`
- File: `aletheia/service/http.py:2486` `_rate_limit_identity`.
- Anonymous identity comes straight from client-supplied `X-Forwarded-For`/`X-Real-IP`;
  rotate the header, evade the limit. Only trust these behind a configured proxy;
  otherwise key on the socket peer address.

### 7. Retention privacy/source filter matches per-evidence-row  `[Medium, privacy]`
- File: `aletheia/core/hardening.py:962` `run_retention` (LEFT JOIN evidence + DISTINCT).
- A claim matches a `privacy_level='public'` policy if *any one* linked evidence row is
  public — so a public-data policy can act on a claim that also carries private
  evidence. Match on the claim's effective (most-restrictive) privacy, not any row.

### 8. H14 residue — sweep remaining raw connection context managers  `[Low]`
- `aletheia/cli/main.py:4048`, `:4078`, `aletheia/core/hardening.py:430` still use raw
  `with ...store.connection:`. Single-statement so low risk, but they bypass the new
  `transaction()` discipline. Convert for consistency.

### 9. De-duplicate the governed-query filter logic  `[Low, latent divergence]`
- `SQLiteFTSRetriever.retrieve` (`retrieval/lexical.py:123`) and `_governed_claim_rows`
  (`core/memory.py:12103`) independently rebuild the same status/type/project/session/
  category clauses and already differ (category namespace scoping present in one,
  absent in the other), so lexical vs semantic/hybrid can return different candidate
  sets. Extract one shared clause builder.

---

## Process changes to carry into the next phase

- Closure evidence must quote the **full original finding** and show each clause met,
  not just cite a passing test.
- For any finding that names a code location, grep the **pattern class** repo-wide and
  list every instance before marking closed.
- Perf/data findings need a bounded-cost or large-N check, plus a one-line "behavior at
  scale / with adversarial input" note.
- Re-run the suite on the supported interpreter (3.13) as part of closure; record the
  Python version alongside the pass count.
- Workstream 6 (splitting the 13k-line `core/memory.py` and 4.4k-line `cli/main.py`)
  is still open by design — the H13 duplicate-method bug and the #9 divergence are both
  symptoms of the monolith; prioritize the CI check for duplicate method names now even
  before the split.
