# Encryption Layer

Aletheia has an explicit local encryption layer for protected memory content
and exported payloads. It is part of the M8 production-hardening surface and is
implemented by `aletheia/core/crypto.py` and `aletheia/core/hardening.py`.

## What The Encryption Layer Protects

The current implementation covers two main paths:

- Protected content encryption for secret-tier stored evidence content.
- Archive encryption for backups, namespace exports, and support bundles.

It also records key metadata, key rotation events, protected-mode state,
backup verification runs, redaction events, forget runs, and audit records.

## Protected Content Encryption

Protected content encryption is controlled by protected mode:

```bash
aletheia encrypt status --db ./aletheia.db
aletheia encrypt enable --db ./aletheia.db --protected
```

When protected mode is enabled, Aletheia sets:

- `enabled = true`
- `content_encryption_enabled = true`
- `backup_encryption_required = true`
- indexing policy `index_public_and_personal_only`
- request logging policy `metadata_only`

Stored evidence content is encrypted only when its privacy level is in the
secret privacy tier. Public, personal, and other non-secret evidence remains
plain unless future policy expands that behavior.

Use secret privacy for evidence that should be protected at rest:

```bash
aletheia ingest text \
  --db ./aletheia.db \
  --namespace user/default \
  --privacy secret \
  --title "Sensitive note" \
  "Sensitive local-only source material."
```

## Algorithms

Current protected content and encrypted archive payloads use:

- AES-256-GCM
- PBKDF2-HMAC-SHA256
- 120,000 PBKDF2 iterations
- random 16-byte salt
- random 12-byte nonce
- authenticated decryption checks

Legacy XOR/HMAC encrypted content remains readable for compatibility, but new
encrypted payloads use AES-GCM.

## Key Material

Aletheia stores key records, not raw key material. Key records live in
`encryption_key_records` and include provider, label, status, algorithm, KDF,
version, timestamps, and metadata.

Protected content decryption resolves key material from environment variables:

```bash
ALETHEIA_KEY_<key_id>
ALETHEIA_PROTECTED_KEY
```

Backup and export decryption resolves passphrases from:

```bash
--passphrase
ALETHEIA_KEY_<key_id>
ALETHEIA_BACKUP_PASSPHRASE
```

For production-like use, configure key material before writing secret evidence:

```bash
export ALETHEIA_PROTECTED_KEY="replace-with-local-secret"
aletheia encrypt enable --db ./aletheia.db --protected
```

Then verify readiness:

```bash
aletheia readiness check --db ./aletheia.db --namespace user/default
```

## Key Records And Rotation

List key records:

```bash
aletheia keys list --db ./aletheia.db
```

Create a key record:

```bash
aletheia keys create \
  --db ./aletheia.db \
  --provider passphrase \
  --label local-protected-key
```

Plan or apply rotation:

```bash
aletheia keys rotate key_... \
  --db ./aletheia.db \
  --label rotated-local-protected-key

aletheia keys rotate key_... \
  --db ./aletheia.db \
  --label rotated-local-protected-key \
  --apply \
  --force
```

Rotation records events in `key_rotation_events`. A verified backup is
recommended before applying rotation.

## Backup And Export Encryption

Protected mode requires encrypted backups. Create and verify one:

```bash
aletheia backup create \
  --db ./aletheia.db \
  --namespace user/default \
  --output ./aletheia.alet \
  --encrypt \
  --passphrase "change-me"

aletheia backup verify ./aletheia.alet \
  --db ./aletheia.db \
  --passphrase "change-me"
```

Encrypted backup archives contain an outer manifest plus encrypted payload and
encryption metadata. Verification checks checksums and authenticated
decryption.

Logical namespace exports can also be encrypted:

```bash
aletheia export namespace \
  --db ./aletheia.db \
  --namespace user/default \
  --output ./namespace.alet \
  --encrypt \
  --passphrase "change-me"
```

Support bundles can be encrypted too:

```bash
aletheia support bundle \
  --db ./aletheia.db \
  --output ./aletheia-support.zip \
  --encrypt \
  --passphrase "change-me"
```

## Indexing And Retrieval Effects

Protected mode uses a secret-safe indexing policy by default. Secret evidence
is not indexed as ordinary searchable content unless policy explicitly allows
it. This reduces accidental exposure through lexical, semantic, hybrid, trace,
or context-pack paths.

If expected secret-backed memories do not appear in retrieval, inspect:

```bash
aletheia encrypt status --db ./aletheia.db
aletheia index status --db ./aletheia.db --namespace user/default
aletheia traces context --db ./aletheia.db --namespace user/default --query "your query"
```

## Redaction And Forget

Redaction and forget flows are adjacent to encryption:

```bash
aletheia redact evidence evt_... \
  --db ./aletheia.db \
  --reason "Remove sensitive source content."

aletheia forget preview \
  --db ./aletheia.db \
  --namespace user/default \
  --claim clm_... \
  --reason "User requested removal."
```

These workflows preserve auditability through tombstones and audit records.
They also mark affected semantic indexes stale when needed.

Important limit: redaction and forget cannot remove data from old backups,
filesystem snapshots, OS caches, or external copies. Rotate or destroy external
copies according to your own retention policy.

## Deployment Checklist

- Set `ALETHEIA_PROTECTED_KEY` or `ALETHEIA_KEY_<key_id>` before storing secret evidence.
- Run `aletheia encrypt enable --protected` for sensitive deployments.
- Use secret privacy labels for evidence that needs protected content encryption.
- Keep HTTP service auth enabled outside single-process local use.
- Use encrypted backups and verify them.
- Keep backup passphrases separate from database files.
- Dry-run restores before applying.
- Review `readiness check` warnings before release.
- Use redacted logical exports for support or sharing.

## Current Limits

The encryption layer is local-first. It does not provide remote key management,
hardware-backed key storage, or transparent full-database encryption by itself.
Use filesystem or disk encryption as an additional control when the full SQLite
file, WAL files, temporary files, or host backups need physical protection.
