# Backup And Restore Guide

Backups are part of the encryption layer. In protected mode, backups must be
encrypted. Encrypted backup payloads use AES-256-GCM with PBKDF2-HMAC-SHA256
key derivation and authenticated verification.

Create and verify a local encrypted archive:

```bash
aletheia backup create --db ./aletheia.db --output ./aletheia.alet --encrypt --passphrase "change-me"
aletheia backup verify ./aletheia.alet --db ./aletheia.db --passphrase "change-me"
```

Dry-run restore before applying:

```bash
aletheia restore dry-run ./aletheia.alet --target ./restored.db --db ./aletheia.db --passphrase "change-me"
```

The v1 release gate checks that backup and restore machinery is available. A clean development database may pass with an acknowledged missing-backup warning, but production readiness should include a verified backup.

Passphrase resolution order:

- Explicit `--passphrase`.
- `ALETHEIA_KEY_<key_id>` when a key ID is provided.
- `ALETHEIA_BACKUP_PASSPHRASE`.

Important limits:

- Full physical backups can include raw SQLite files and auth metadata.
- Use logical redacted exports for support or sharing.
- Redaction and forget operations cannot remove data from old backups,
  filesystem snapshots, OS caches, or external copies.

Read `docs/encryption_layer.md` for the full protected-content and archive
encryption model.
