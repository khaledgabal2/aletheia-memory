# Security And Privacy Guide

Aletheia is local-first. Evidence, claims, review state, metrics, and service logs live in the configured SQLite database unless explicitly exported.

Core controls:

- Protected mode encrypts sensitive stored content.
- Protected content and encrypted backup payloads use AES-256-GCM with PBKDF2-derived local key material; legacy encrypted content remains readable for compatibility.
- Protected content encryption currently applies to secret-tier evidence content when protected mode is enabled; use `--privacy secret` for evidence that needs this path.
- Raw key material is not stored in key records. Protected content key material is resolved from `ALETHEIA_KEY_<key_id>` or `ALETHEIA_PROTECTED_KEY`.
- Encrypted backups, namespace exports, and support bundles use explicit passphrases or configured backup key material.
- API tokens use scoped capabilities and namespace grants.
- Console sessions require login tokens and CSRF checks for state-changing actions.
- Plugins require explicit permission grants before enablement.
- High-risk plugin permissions require a reason.
- Forget and redact flows preserve auditability through tombstones.
- External telemetry is off by default and is checked by the v1 gate.

HTTP object operations authorize the stored target's namespace/project and
source evidence, including referenced replacement claims and LLM inputs.
Session summaries default to candidate writes. Trace creation filters content
before persistence, and trace reads recheck current access rather than trusting
an old snapshot's visibility. Operational list requests require a namespace
unless the caller has a wildcard namespace grant; admin capability alone does
not grant global namespace access on these routes. For route details and
upgrade behavior, see [HTTP access boundaries](service_access_boundaries.md).

Deployment limits:

- The v1.3.0 production baseline on `main` is Aletheia-generic. Product-specific integrations, including sample adapter compatibility code, must stay on a branch or fork.
- Non-loopback HTTP deployments must run with `auth_required=True`, scoped API tokens, namespace grants, and an external TLS/reverse-proxy boundary.
- Protected mode requires configured key material through `ALETHEIA_PROTECTED_KEY` or `ALETHEIA_KEY_<key_id>` before sensitive content can be written.
- Full physical backups can include raw SQLite and auth metadata; use encrypted backups for protected deployments and logical redacted backups for support or sharing.
- Federation sync bundles carrying non-public data must be encrypted and signed.

Federation sharing boundaries:

- Bundles contain only the public identity schema, including inside encrypted
  payloads. Private signing/encryption key records and local identity metadata
  are never included in new exports.
- Import checks the signing and encryption keys and fingerprint against the
  exact stored peer instance ID. A valid signature from a different key does
  not inherit that peer's trust. Changed keys require separately authorized
  recovery; importing a bundle cannot update the pinned key.
- Revoked or blocked peers cannot import, including through candidate-only or
  dry-run paths. Import also checks signed grant expiry/status and locally
  retained share, collection, and recipient revocation. Failed imports roll
  back their content and federation records together.
- `candidate_only` (the default), `manual_review`, and `remote_claim_only`
  cannot create active claims even for trusted peers. Active imports require
  an explicitly selected active policy and compatible local trust; HTTP
  callers also need `memory:remote_active_write`. Remote core claims never
  become local core claims, and project-state policies remain limited to
  project, decision, and procedure memory.
- `read` is an alias for `read_claims` only. Exporting source evidence requires
  both `read_evidence` and `include_evidence=True`. A feedback-only grant
  exports no memory content. Redaction notices require `read_claims` and
  `receive_redactions`; write permissions do not imply read access.

Upgrade considerations: existing shares that intentionally include source
evidence must explicitly grant `read_evidence`. Dry-run imports now enforce
the same trust and revocation rules as real imports, while leaving the
database unchanged. If older bundles were distributed, assess the sender's
signing and encryption keys as potentially exposed, coordinate key recovery
with recipients, and retire affected bundles. This code change does not
rotate existing identities or recall already distributed packages.

For operator-approved replacement, use the [federation key recovery procedure](federation_key_recovery.md).
Rotation requires an encrypted decryption-only recovery file and the expected
current fingerprint. Peer replacement requires independently confirmed old and
new fingerprints, resets trust, and revokes existing grants. Both HTTP operations
require `memory:admin`. Historical bundle recovery produces an encrypted review
file and never imports content or restores signing authority.

Run diagnostics:

```bash
aletheia doctor --db ./aletheia.db
aletheia v1-gate run --db ./aletheia.db
```

Read `docs/encryption_layer.md` for the full encryption-layer model, including
algorithms, key records, rotation, backup encryption, indexing effects,
redaction/forget interactions, and current limits.
