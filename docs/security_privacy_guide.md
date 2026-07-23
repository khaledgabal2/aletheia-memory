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

Deployment limits:

- The v1.3.0 production baseline on `main` is Aletheia-generic. Product-specific integrations, including sample adapter compatibility code, must stay on a branch or fork.
- Non-loopback HTTP deployments must run with `auth_required=True`, scoped API tokens, namespace grants, and an external TLS/reverse-proxy boundary.
- Protected mode requires configured key material through `ALETHEIA_PROTECTED_KEY` or `ALETHEIA_KEY_<key_id>` before sensitive content can be written.
- Full physical backups can include raw SQLite and auth metadata; use encrypted backups for protected deployments and logical redacted backups for support or sharing.
- Federation sync bundles carrying non-public data must be encrypted and signed.

Run diagnostics:

```bash
aletheia doctor --db ./aletheia.db
aletheia v1-gate run --db ./aletheia.db
```

Read `docs/encryption_layer.md` for the full encryption-layer model, including
algorithms, key records, rotation, backup encryption, indexing effects,
redaction/forget interactions, and current limits.
