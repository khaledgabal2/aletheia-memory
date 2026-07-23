"""M8 production-hardening services for backup, restore, protection, and diagnostics."""

from __future__ import annotations

import io
import json
import os
import platform
import shutil
import sqlite3
import statistics
import sys
import tempfile
import zipfile
from dataclasses import asdict
from pathlib import Path
from time import perf_counter
from typing import Any

from aletheia.core.crypto import (
    AES_GCM_PASSPHRASE_ALGORITHM,
    LEGACY_XOR_HMAC_ALGORITHM,
    PBKDF2_KEY_DERIVATION,
    b64url_decode,
    b64url_encode,
    decrypt_bytes_with_passphrase,
    decrypt_legacy_xor_hmac_bytes,
    decrypt_legacy_xor_hmac_content,
    encrypt_bytes_with_passphrase,
    random_bytes,
    sha256_hex,
)
from aletheia.core.errors import NotFoundError, ValidationError
from aletheia.core.ids import content_hash, new_id
from aletheia.core.time import utc_now_iso
from aletheia.models import (
    BackupManifest,
    BackupVerificationRun,
    BenchmarkResult,
    BenchmarkRun,
    DeletionTombstone,
    EncryptionKeyRecord,
    ExportManifest,
    ImportRun,
    IntegrityCheckRun,
    IntegrityFinding,
    KeyRotationEvent,
    MigrationPlan,
    ProductionReadinessCheck,
    ProtectedModeConfig,
    RedactionEvent,
    ReleaseManifest,
    RestoreRun,
    RetentionPolicy,
    SimpleRun,
    SupportBundle,
)
from aletheia.storage import SCHEMA_VERSION


BACKUP_FORMAT_VERSION = "1"
ENCRYPTION_PREFIX = "enc:"
CONTENT_ENCRYPTION_VERSION = "v2"
LEGACY_CONTENT_ENCRYPTION_VERSION = "v1"
SECRET_PRIVACY_LEVELS = {"private", "sensitive", "secret"}
PRIVACY_ORDER = {"public": 0, "personal": 1, "private": 2, "sensitive": 2, "secret": 3}
RETENTION_ACTIONS = {"archive", "redact_content", "tombstone", "hard_delete", "queue_review", "lower_salience"}
FINDING_SEVERITY_RANK = {"info": 0, "low": 1, "medium": 2, "high": 3, "critical": 4}
M8_TABLES = {
    "backup_manifests",
    "backup_items",
    "backup_verification_runs",
    "restore_runs",
    "encryption_key_records",
    "key_rotation_events",
    "protected_mode_config",
    "redaction_events",
    "deletion_tombstones",
    "retention_policies",
    "retention_runs",
    "integrity_check_runs",
    "integrity_findings",
    "index_consistency_runs",
    "migration_plans",
    "migration_runs",
    "compaction_runs",
    "export_manifests",
    "import_runs",
    "support_bundles",
    "benchmark_runs",
    "benchmark_results",
    "release_manifests",
    "production_readiness_checks",
}


def create_backup(
    memory,
    *,
    output_path: str,
    backup_type: str = "physical",
    namespace: str | None = None,
    encrypt: bool = True,
    privacy_mode: str = "full",
    include_auth_metadata: bool = True,
    include_indexes: bool = False,
    passphrase: str | None = None,
    key_id: str | None = None,
    verify_after: bool = True,
    created_by: str = "user",
) -> BackupManifest:
    if backup_type not in {"physical", "logical", "hybrid"}:
        raise ValidationError("backup_type must be physical, logical, or hybrid.")
    if privacy_mode not in {"full", "redacted", "metadata_only", "namespace_filtered"}:
        raise ValidationError("Unknown backup privacy_mode.")
    if privacy_mode != "full" and backup_type in {"physical", "hybrid"}:
        raise ValidationError("Physical backup snapshots require privacy_mode='full'; use backup_type='logical' for redacted backups.")
    protected = protected_mode_status(memory)
    if protected.backup_encryption_required and not encrypt:
        raise ValidationError("Protected mode requires encrypted backups.")
    effective_include_auth_metadata = bool(include_auth_metadata and privacy_mode == "full" and backup_type in {"physical", "hybrid"})
    archive_path = Path(output_path)
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_id = new_id("bkp")
    created_at = utc_now_iso()
    with tempfile.TemporaryDirectory(prefix="aletheia-backup-") as temp:
        temp_dir = Path(temp)
        payload_files: dict[str, bytes] = {
            "config_redacted.json": _json_bytes(_redacted_config(memory)),
            "release_info.json": _json_bytes(_release_info()),
            "indexes_metadata/manifest.json": _json_bytes(_index_metadata(memory, namespace)),
        }
        if backup_type in {"physical", "hybrid"}:
            snapshot_path = temp_dir / "database.sqlite"
            _sqlite_snapshot(memory, snapshot_path)
            payload_files["database.sqlite"] = snapshot_path.read_bytes()
        if backup_type in {"logical", "hybrid"}:
            payload_files.update(_logical_payload(memory, namespace, privacy_mode))
        item_counts = _item_counts(memory, namespace)
        if not effective_include_auth_metadata:
            item_counts.pop("api_tokens", None)
        manifest = {
            "id": manifest_id,
            "namespace": namespace,
            "backup_type": backup_type,
            "format_version": BACKUP_FORMAT_VERSION,
            "schema_version": SCHEMA_VERSION,
            "created_at": created_at,
            "created_by": created_by,
            "encrypted": encrypt,
            "encryption_key_id": key_id,
            "db_path": memory.store.path,
            "archive_path": str(archive_path),
            "item_counts": item_counts,
            "checksums": {},
            "privacy_mode": privacy_mode,
            "includes_auth_metadata": effective_include_auth_metadata,
            "includes_raw_content": privacy_mode == "full",
            "metadata": {
                "include_indexes": include_indexes,
                "protected_mode": asdict(protected),
            },
        }
        if encrypt:
            passphrase = _resolve_passphrase(passphrase, key_id)
            if not passphrase:
                raise ValidationError("Encrypted backup requires passphrase or key material.")
            inner_checksums = _checksums(payload_files)
            inner_bytes = _zip_bytes({**payload_files, "checksums.sha256": _checksums_text(inner_checksums)})
            encrypted_payload, enc_meta = _encrypt_bytes(inner_bytes, passphrase, key_id=key_id)
            manifest["checksums"] = {"encrypted_payload.bin": _sha256(encrypted_payload)}
            archive_files = {
                "manifest.json": _json_bytes(manifest),
                "encryption_metadata.json": _json_bytes(enc_meta),
                "encrypted_payload.bin": encrypted_payload,
                "checksums.sha256": _checksums_text(manifest["checksums"]),
            }
        else:
            checksums = _checksums(payload_files)
            manifest["checksums"] = checksums
            archive_files = {
                "manifest.json": _json_bytes(manifest),
                **payload_files,
                "checksums.sha256": _checksums_text(checksums),
            }
        _write_zip(archive_path, archive_files)
    with memory.store.transaction():
        memory.store.connection.execute(
            """
            INSERT INTO backup_manifests (
                id, namespace, backup_type, format_version, schema_version,
                archive_path, encrypted, encryption_key_id, privacy_mode,
                includes_auth_metadata, includes_raw_content, item_counts_json,
                checksums_json, created_by, created_at, metadata_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                manifest_id,
                namespace,
                backup_type,
                BACKUP_FORMAT_VERSION,
                SCHEMA_VERSION,
                str(archive_path),
                int(encrypt),
                key_id,
                privacy_mode,
                int(effective_include_auth_metadata),
                int(privacy_mode == "full"),
                json.dumps(item_counts, sort_keys=True),
                json.dumps(manifest["checksums"], sort_keys=True),
                created_by,
                created_at,
                json.dumps(manifest["metadata"], sort_keys=True),
            ),
        )
        for item_name, checksum in manifest["checksums"].items():
            memory.store.connection.execute(
                """
                INSERT INTO backup_items (
                    id, backup_id, item_type, item_id, checksum,
                    size_bytes, created_at, metadata_json
                )
                VALUES (?, ?, ?, NULL, ?, NULL, ?, ?)
                """,
                (
                    new_id("bitem"),
                    manifest_id,
                    item_name,
                    checksum,
                    created_at,
                    json.dumps({}, sort_keys=True),
                ),
            )
        memory._write_audit(
            namespace=namespace or memory.namespace,
            target_type="backup",
            target_id=manifest_id,
            action="backup.create",
            details={
                "archive_path": str(archive_path),
                "encrypted": encrypt,
                "backup_type": backup_type,
                "privacy_mode": privacy_mode,
            },
        )
    if verify_after:
        run = verify_backup(memory, backup_path=str(archive_path), passphrase=passphrase, key_id=key_id, deep=True)
        if run.status != "passed":
            raise ValidationError("Backup verification failed: " + "; ".join(run.warnings))
    return get_backup(memory, manifest_id)


def verify_backup(
    memory,
    *,
    backup_path: str,
    passphrase: str | None = None,
    key_id: str | None = None,
    deep: bool = True,
) -> BackupVerificationRun:
    started_at = utc_now_iso()
    status, warnings, manifest, payload = verify_backup_file(
        backup_path=backup_path,
        passphrase=passphrase,
        key_id=key_id,
        deep=deep,
    )
    finished_at = utc_now_iso()
    backup_id = manifest.get("id") if manifest else None
    run_id = new_id("bver")
    with memory.store.transaction():
        memory.store.connection.execute(
            """
            INSERT INTO backup_verification_runs (
                id, backup_id, backup_path, status, deep, finding_count,
                started_at, finished_at, warnings_json, metadata_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                backup_id,
                backup_path,
                status,
                int(deep),
                len(warnings),
                started_at,
                finished_at,
                json.dumps(warnings, sort_keys=True),
                json.dumps({"manifest_schema_version": manifest.get("schema_version") if manifest else None}, sort_keys=True),
            ),
        )
        memory._write_audit(
            namespace=manifest.get("namespace") or memory.namespace if manifest else memory.namespace,
            target_type="backup",
            target_id=backup_id or backup_path,
            action="backup.verify",
            details={"status": status, "warnings": warnings, "payload_files": sorted(payload)},
        )
    return _backup_verification_run(memory, run_id)


def verify_backup_file(
    *,
    backup_path: str,
    passphrase: str | None = None,
    key_id: str | None = None,
    deep: bool = True,
) -> tuple[str, list[str], dict, dict[str, bytes]]:
    warnings: list[str] = []
    path = Path(backup_path)
    if not path.exists():
        return "failed", [f"Backup not found: {backup_path}"], {}, {}
    try:
        with zipfile.ZipFile(path, "r") as archive:
            names = set(archive.namelist())
            if "manifest.json" not in names or "checksums.sha256" not in names:
                return "failed", ["Backup is missing manifest or checksums."], {}, {}
            manifest = json.loads(archive.read("manifest.json").decode("utf-8"))
            checksums = _parse_checksums(archive.read("checksums.sha256").decode("utf-8"))
            if manifest.get("encrypted"):
                if "encrypted_payload.bin" not in names or "encryption_metadata.json" not in names:
                    return "failed", ["Encrypted backup is missing payload or encryption metadata."], manifest, {}
                encrypted_payload = archive.read("encrypted_payload.bin")
                expected = checksums.get("encrypted_payload.bin") or manifest.get("checksums", {}).get("encrypted_payload.bin")
                if expected and _sha256(encrypted_payload) != expected:
                    return "failed", ["Checksum mismatch for encrypted payload."], manifest, {}
                passphrase = _resolve_passphrase(passphrase, key_id or manifest.get("encryption_key_id"))
                if not passphrase:
                    return "failed", ["Encrypted backup requires passphrase or key material."], manifest, {}
                enc_meta = json.loads(archive.read("encryption_metadata.json").decode("utf-8"))
                try:
                    inner_bytes = _decrypt_bytes(encrypted_payload, passphrase, enc_meta)
                except ValidationError as exc:
                    return "failed", [str(exc)], manifest, {}
                payload = _read_zip_bytes(inner_bytes)
                inner_checksums = _parse_checksums(payload.get("checksums.sha256", b"").decode("utf-8"))
                mismatch = _checksum_mismatches(payload, inner_checksums)
                if mismatch:
                    return "failed", mismatch, manifest, payload
                if deep and manifest.get("backup_type") in {"physical", "hybrid"} and "database.sqlite" not in payload:
                    warnings.append("Backup has no database.sqlite payload.")
                return "passed", warnings, manifest, payload
            payload = {name: archive.read(name) for name in names if name not in {"manifest.json", "checksums.sha256"}}
            mismatch = _checksum_mismatches(payload, checksums)
            if mismatch:
                return "failed", mismatch, manifest, payload
            if deep and manifest.get("backup_type") in {"physical", "hybrid"} and "database.sqlite" not in payload:
                warnings.append("Backup has no database.sqlite payload.")
            return ("passed_with_warnings" if warnings else "passed"), warnings, manifest, payload
    except zipfile.BadZipFile:
        return "failed", ["Backup archive is not readable."], {}, {}


def restore_backup(
    *,
    backup_path: str,
    target_db_path: str,
    mode: str = "new_database",
    namespace: str | None = None,
    passphrase: str | None = None,
    key_id: str | None = None,
    dry_run: bool = True,
    verify_before: bool = True,
    run_integrity_after: bool = True,
) -> RestoreRun:
    started_at = utc_now_iso()
    warnings: list[str] = []
    status = "planned" if dry_run else "running"
    manifest: dict[str, Any] = {}
    payload: dict[str, bytes] = {}
    verified = False
    if verify_before:
        verification_status, verify_warnings, manifest, payload = verify_backup_file(
            backup_path=backup_path,
            passphrase=passphrase,
            key_id=key_id,
            deep=True,
        )
        warnings.extend(verify_warnings)
        verified = verification_status == "passed"
        if not verified and not dry_run:
            raise ValidationError("Restore refused because backup verification failed: " + "; ".join(warnings))
    target = Path(target_db_path)
    if dry_run:
        return RestoreRun(
            id=new_id("rest"),
            backup_manifest_id=manifest.get("id"),
            backup_path=backup_path,
            target_db_path=target_db_path,
            mode=mode,
            dry_run=True,
            verified_before_restore=verified,
            restored_item_counts=manifest.get("item_counts", {}),
            status="verified" if verified else "planned",
            started_at=started_at,
            finished_at=utc_now_iso(),
            warnings=warnings,
            metadata={"namespace": namespace},
        )
    if mode == "new_database" and target.exists():
        raise ValidationError("Target database already exists; use overwrite_existing mode explicitly.")
    if mode in {"overwrite_existing", "in_place"} and target.exists():
        pre_restore = target.with_suffix(target.suffix + ".pre-restore")
        shutil.copy2(target, pre_restore)
        warnings.append(f"Existing target backed up to {pre_restore}.")
    if "database.sqlite" not in payload:
        raise ValidationError("Restore requires a database.sqlite payload.")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(payload["database.sqlite"])
    restored_counts = manifest.get("item_counts", {})
    integrity_summary: dict[str, Any] | None = None
    if run_integrity_after:
        from aletheia import Memory

        restored = Memory.open(str(target))
        try:
            integrity = integrity_check(restored, namespace=namespace, scope="post_restore")
            integrity_summary = asdict(integrity)
            if integrity.status == "failed":
                warnings.append("Post-restore integrity check failed.")
        finally:
            restored.close()
    finished_at = utc_now_iso()
    from aletheia import Memory

    restored_memory = Memory.open(str(target))
    try:
        run_id = new_id("rest")
        with restored_memory.store.transaction():
            restored_memory.store.connection.execute(
                """
                INSERT INTO restore_runs (
                    id, backup_manifest_id, backup_path, target_db_path, mode,
                    dry_run, verified_before_restore, restored_item_counts_json,
                    status, started_at, finished_at, warnings_json, metadata_json
                )
                VALUES (?, ?, ?, ?, ?, 0, ?, ?, 'completed', ?, ?, ?, ?)
                """,
                (
                    run_id,
                    manifest.get("id"),
                    backup_path,
                    target_db_path,
                    mode,
                    int(verified),
                    json.dumps(restored_counts, sort_keys=True),
                    started_at,
                    finished_at,
                    json.dumps(warnings, sort_keys=True),
                    json.dumps({"integrity": integrity_summary, "namespace": namespace}, sort_keys=True),
                ),
            )
        row = restored_memory.store.connection.execute("SELECT * FROM restore_runs WHERE id = ?", (run_id,)).fetchone()
        return RestoreRun.from_row(row)
    finally:
        restored_memory.close()


def get_backup(memory, backup_id: str) -> BackupManifest:
    row = memory.store.connection.execute("SELECT * FROM backup_manifests WHERE id = ?", (backup_id,)).fetchone()
    if not row:
        raise NotFoundError(f"Backup not found: {backup_id}")
    return BackupManifest.from_row(row)


def list_backups(memory, *, limit: int = 50) -> list[BackupManifest]:
    rows = memory.store.connection.execute(
        "SELECT * FROM backup_manifests ORDER BY created_at DESC LIMIT ?",
        (limit,),
    ).fetchall()
    return [BackupManifest.from_row(row) for row in rows]


def protected_mode_status(memory) -> ProtectedModeConfig:
    row = memory.store.connection.execute(
        "SELECT * FROM protected_mode_config WHERE id = 'protected_default'"
    ).fetchone()
    if row:
        return ProtectedModeConfig.from_row(row)
    now = utc_now_iso()
    with memory.store.transaction():
        memory.store.connection.execute(
            """
            INSERT INTO protected_mode_config (
                id, enabled, content_encryption_enabled,
                backup_encryption_required, indexing_policy,
                request_logging_policy, created_at, updated_at, metadata_json
            )
            VALUES ('protected_default', 0, 0, 0, 'index_public_and_personal_only', 'metadata_only', ?, ?, '{}')
            """,
            (now, now),
        )
    return protected_mode_status(memory)


def enable_protected_mode(memory, *, protected: bool = True, actor: str = "user") -> ProtectedModeConfig:
    now = utc_now_iso()
    if protected and not list_keys(memory):
        create_key(memory, provider="passphrase", label="local-protected-key", metadata={"created_for": "protected_mode"})
    with memory.store.transaction():
        memory.store.connection.execute(
            """
            INSERT INTO protected_mode_config (
                id, enabled, content_encryption_enabled,
                backup_encryption_required, indexing_policy,
                request_logging_policy, created_at, updated_at, metadata_json
            )
            VALUES (
                'protected_default', ?, ?, ?, 'index_public_and_personal_only',
                'metadata_only', ?, ?, ?
            )
            ON CONFLICT(id) DO UPDATE SET
                enabled = excluded.enabled,
                content_encryption_enabled = excluded.content_encryption_enabled,
                backup_encryption_required = excluded.backup_encryption_required,
                indexing_policy = excluded.indexing_policy,
                request_logging_policy = excluded.request_logging_policy,
                updated_at = excluded.updated_at,
                metadata_json = excluded.metadata_json
            """,
            (
                int(protected),
                int(protected),
                int(protected),
                now,
                now,
                json.dumps({"actor": actor, "secret_safe_indexing": True}, sort_keys=True),
            ),
        )
        memory._write_audit(
            namespace=memory.namespace,
            target_type="protected_mode",
            target_id="protected_default",
            action="protected_mode.enable" if protected else "protected_mode.disable",
            details={"actor": actor},
        )
    return protected_mode_status(memory)


def create_key(memory, *, provider: str, label: str, metadata: dict | None = None) -> EncryptionKeyRecord:
    if provider not in {"passphrase", "environment", "file", "os_keyring"}:
        raise ValidationError("Unsupported key provider.")
    key_id = new_id("key")
    now = utc_now_iso()
    salt = b64url_encode(random_bytes(16))
    with memory.store.transaction():
        memory.store.connection.execute(
            """
            INSERT INTO encryption_key_records (
                id, provider, label, status, algorithm, kdf, key_version,
                created_at, rotated_at, metadata_json
            )
            VALUES (?, ?, ?, 'active', ?, ?, 1, ?, NULL, ?)
            """,
            (
                key_id,
                provider,
                label,
                AES_GCM_PASSPHRASE_ALGORITHM,
                PBKDF2_KEY_DERIVATION,
                now,
                json.dumps({"salt": salt, **(metadata or {})}, sort_keys=True),
            ),
        )
        memory._write_audit(
            namespace=memory.namespace,
            target_type="encryption_key",
            target_id=key_id,
            action="key.create",
            details={"provider": provider, "label": label, "raw_key_stored": False},
        )
    return get_key(memory, key_id)


def get_key(memory, key_id: str) -> EncryptionKeyRecord:
    row = memory.store.connection.execute("SELECT * FROM encryption_key_records WHERE id = ?", (key_id,)).fetchone()
    if not row:
        raise NotFoundError(f"Encryption key not found: {key_id}")
    return EncryptionKeyRecord.from_row(row)


def list_keys(memory, *, include_inactive: bool = False) -> list[EncryptionKeyRecord]:
    where = "" if include_inactive else "WHERE status = 'active'"
    rows = memory.store.connection.execute(
        f"SELECT * FROM encryption_key_records {where} ORDER BY created_at DESC"
    ).fetchall()
    return [EncryptionKeyRecord.from_row(row) for row in rows]


def rotate_key(
    memory,
    *,
    old_key_id: str,
    new_key_label: str,
    target: str = "content",
    dry_run: bool = True,
    force: bool = False,
) -> KeyRotationEvent:
    old = get_key(memory, old_key_id)
    affected = _encrypted_content_count(memory, old_key_id) if target == "content" else 0
    if not dry_run and not force and not list_backups(memory, limit=1):
        raise ValidationError("Key rotation recommends a verified backup first; pass force to override.")
    new_key = create_key(memory, provider=old.provider, label=new_key_label, metadata={"rotated_from": old_key_id})
    now = utc_now_iso()
    status = "planned" if dry_run else "completed"
    with memory.store.transaction():
        if not dry_run:
            memory.store.connection.execute(
                "UPDATE encryption_key_records SET status = 'rotated', rotated_at = ? WHERE id = ?",
                (now, old_key_id),
            )
        memory.store.connection.execute(
            """
            INSERT INTO key_rotation_events (
                id, old_key_id, new_key_id, target, dry_run, affected_count,
                status, created_at, metadata_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                new_id("krot"),
                old_key_id,
                new_key.id,
                target,
                int(dry_run),
                affected,
                status,
                now,
                json.dumps({"force": force}, sort_keys=True),
            ),
        )
        memory._write_audit(
            namespace=memory.namespace,
            target_type="encryption_key",
            target_id=old_key_id,
            action="key.rotate",
            details={"new_key_id": new_key.id, "dry_run": dry_run, "affected_count": affected},
        )
    row = memory.store.connection.execute(
        "SELECT * FROM key_rotation_events WHERE old_key_id = ? ORDER BY created_at DESC LIMIT 1",
        (old_key_id,),
    ).fetchone()
    return KeyRotationEvent.from_row(row)


def protect_content_for_storage(memory, content: str, *, privacy_level: str) -> str:
    status = protected_mode_status(memory)
    if not status.enabled or not status.content_encryption_enabled:
        return content
    if privacy_level not in SECRET_PRIVACY_LEVELS:
        return content
    key = _active_content_key(memory)
    return encrypt_content(content, key_id=key.id, passphrase=_content_passphrase(key.id))


def reveal_content_from_storage(memory, content: str) -> str:
    if not content.startswith(ENCRYPTION_PREFIX):
        return content
    try:
        _prefix, version, key_id, *parts = content.split(":")
    except ValueError as exc:
        raise ValidationError("Encrypted content marker is malformed.") from exc
    if version == CONTENT_ENCRYPTION_VERSION:
        if len(parts) != 3:
            raise ValidationError("Encrypted content marker is malformed.")
        salt_b64, nonce_b64, cipher_b64 = parts
        cipher = b64url_decode(cipher_b64)
        return decrypt_bytes_with_passphrase(
            cipher,
            _content_passphrase(key_id),
            {
                "algorithm": AES_GCM_PASSPHRASE_ALGORITHM,
                "kdf": PBKDF2_KEY_DERIVATION,
                "salt": salt_b64,
                "nonce": nonce_b64,
            },
        ).decode("utf-8")
    if version == LEGACY_CONTENT_ENCRYPTION_VERSION:
        if len(parts) != 3:
            raise ValidationError("Encrypted content marker is malformed.")
        nonce_b64, cipher_b64, mac_b64 = parts
        return decrypt_legacy_xor_hmac_content(
            cipher=b64url_decode(cipher_b64),
            passphrase=_content_passphrase(key_id),
            salt=b64url_decode(nonce_b64),
            mac=b64url_decode(mac_b64),
        ).decode("utf-8")
    raise ValidationError("Unsupported encrypted content version.")


def encrypt_content(content: str, *, key_id: str, passphrase: str) -> str:
    cipher, metadata = encrypt_bytes_with_passphrase(content.encode("utf-8"), passphrase, key_id=key_id)
    return ":".join(
        [
            "enc",
            CONTENT_ENCRYPTION_VERSION,
            key_id,
            metadata["salt"],
            metadata["nonce"],
            b64url_encode(cipher),
        ]
    )


def should_skip_claim_index(memory, *, namespace: str, claim_id: str | None, evidence_ids: list[str] | None = None) -> bool:
    status = protected_mode_status(memory)
    if not status.enabled or status.indexing_policy == "explicit_sensitive_indexing":
        return False
    evidence_ids = list(evidence_ids or [])
    if claim_id and not evidence_ids:
        evidence_ids = [
            row["evidence_id"]
            for row in memory.store.connection.execute(
                "SELECT evidence_id FROM claim_evidence_links WHERE claim_id = ?",
                (claim_id,),
            ).fetchall()
        ]
    if not evidence_ids:
        return False
    rows = memory.store.connection.execute(
        f"SELECT privacy_level FROM evidence_events WHERE id IN ({','.join('?' for _ in evidence_ids)})",
        evidence_ids,
    ).fetchall()
    return any(row["privacy_level"] in SECRET_PRIVACY_LEVELS for row in rows)


def redact(
    memory,
    *,
    target_id: str,
    target_type: str,
    reason: str,
    replacement_text: str = "[REDACTED]",
    actor: str = "user",
    dry_run: bool = True,
) -> RedactionEvent:
    if target_type not in {"evidence", "source_document", "claim"}:
        raise ValidationError("target_type must be evidence, source_document, or claim.")
    namespace, affected = _redaction_impact(memory, target_id, target_type)
    event_id = new_id("red")
    now = utc_now_iso()
    with memory.store.transaction():
        if not dry_run:
            if target_type == "evidence":
                memory.store.connection.execute(
                    "UPDATE evidence_events SET content = ?, content_hash = ? WHERE id = ?",
                    (replacement_text, content_hash(replacement_text), target_id),
                )
                for claim_id in affected["claims"]:
                    memory.store.connection.execute("DELETE FROM claims_fts WHERE claim_id = ?", (claim_id,))
                    memory.store.connection.execute(
                        "UPDATE claims SET status = 'archived' WHERE id = ? AND status IN ('active', 'core')",
                        (claim_id,),
                    )
                    memory._write_status_history(
                        namespace=namespace,
                        claim_id=claim_id,
                        old_status="active",
                        new_status="archived",
                        reason="evidence.redacted",
                        actor=actor,
                    )
                _invalidate_derived(memory, namespace, affected["claims"], reason)
                _stale_semantic_for_targets(memory, namespace=namespace, target_ids=affected["claims"], reason="evidence.redacted")
            elif target_type == "claim":
                memory.store.connection.execute(
                    "UPDATE claims SET object = ?, status = 'archived' WHERE id = ?",
                    (replacement_text, target_id),
                )
                memory.store.connection.execute("DELETE FROM claims_fts WHERE claim_id = ?", (target_id,))
                _invalidate_derived(memory, namespace, [target_id], reason)
                _stale_semantic_for_targets(memory, namespace=namespace, target_ids=[target_id], reason="claim.redacted")
            _write_tombstone(
                memory,
                namespace=namespace,
                target_id=target_id,
                target_type=target_type,
                deletion_mode="redact_content",
                reason=reason,
                actor=actor,
                affected_derived_count=affected["derived_count"],
            )
        memory.store.connection.execute(
            """
            INSERT INTO redaction_events (
                id, namespace, target_id, target_type, replacement_text,
                reason, actor, dry_run, affected_counts_json, created_at,
                metadata_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event_id,
                namespace,
                target_id,
                target_type,
                replacement_text,
                reason,
                actor,
                int(dry_run),
                json.dumps(affected, sort_keys=True),
                now,
                json.dumps({"backup_warning": _backup_warning()}, sort_keys=True),
            ),
        )
        memory._write_audit(
            namespace=namespace,
            target_type=target_type,
            target_id=target_id,
            action="redaction.preview" if dry_run else "redaction.apply",
            details={"reason": reason, "affected": affected, "actor": actor},
        )
    row = memory.store.connection.execute("SELECT * FROM redaction_events WHERE id = ?", (event_id,)).fetchone()
    return RedactionEvent.from_row(row)


def forget(
    memory,
    *,
    selector: dict,
    mode: str = "tombstone",
    reason: str,
    actor: str = "user",
    dry_run: bool = True,
    confirmation: str | None = None,
) -> SimpleRun:
    if mode not in {"redact_content", "tombstone", "hard_delete", "namespace_forget", "derived_invalidate"}:
        raise ValidationError("Unknown forget mode.")
    if not dry_run and mode in {"hard_delete", "namespace_forget"} and confirmation != "forget memory":
        raise ValidationError("Destructive forget requires confirmation text: forget memory")
    targets = _forget_targets(memory, selector)
    namespace = selector.get("namespace") or memory.namespace
    started_at = utc_now_iso()
    run_id = new_id("frun")
    with memory.store.transaction():
        if not dry_run:
            for target in targets:
                if target["target_type"] == "evidence":
                    redact(
                        memory,
                        target_id=target["target_id"],
                        target_type="evidence",
                        reason=reason,
                        actor=actor,
                        dry_run=False,
                    )
                else:
                    memory.store.connection.execute(
                        "UPDATE claims SET status = 'archived' WHERE id = ?",
                        (target["target_id"],),
                    )
                    memory.store.connection.execute("DELETE FROM claims_fts WHERE claim_id = ?", (target["target_id"],))
                    _stale_semantic_for_targets(memory, namespace=target["namespace"], target_ids=[target["target_id"]], reason="forget.applied")
                    _write_tombstone(
                        memory,
                        namespace=target["namespace"],
                        target_id=target["target_id"],
                        target_type=target["target_type"],
                        deletion_mode=mode,
                        reason=reason,
                        actor=actor,
                        affected_derived_count=0,
                    )
        memory._write_audit(
            namespace=namespace,
            target_type="forget_run",
            target_id=run_id,
            action="forget.preview" if dry_run else "forget.apply",
            details={"selector": selector, "mode": mode, "matched_count": len(targets), "backup_warning": _backup_warning()},
        )
    return SimpleRun(
        id=run_id,
        status="planned" if dry_run else "completed",
        started_at=started_at,
        finished_at=utc_now_iso(),
        metadata={
            "selector": selector,
            "mode": mode,
            "matched_count": len(targets),
            "affected": targets,
            "warnings": [_backup_warning()],
        },
    )


def list_tombstones(memory, *, namespace: str | None = None, limit: int = 50) -> list[DeletionTombstone]:
    params: list[Any] = []
    where = ""
    if namespace:
        where = "WHERE namespace = ?"
        params.append(namespace)
    params.append(limit)
    rows = memory.store.connection.execute(
        f"SELECT * FROM deletion_tombstones {where} ORDER BY created_at DESC LIMIT ?",
        params,
    ).fetchall()
    return [DeletionTombstone.from_row(row) for row in rows]


def create_retention_policy(
    memory,
    *,
    namespace: str | None = None,
    memory_type: str | None = None,
    privacy_level: str | None = None,
    source_type: str | None = None,
    action: str = "queue_review",
    after_days: int = 365,
    reason: str,
) -> RetentionPolicy:
    if action not in RETENTION_ACTIONS:
        raise ValidationError("Unknown retention action.")
    policy_id = new_id("retp")
    now = utc_now_iso()
    with memory.store.transaction():
        memory.store.connection.execute(
            """
            INSERT INTO retention_policies (
                id, namespace, memory_type, privacy_level, source_type,
                action, after_days, enabled, reason, created_at, updated_at,
                metadata_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?, '{}')
            """,
            (policy_id, namespace, memory_type, privacy_level, source_type, action, after_days, reason, now, now),
        )
        memory._write_audit(
            namespace=namespace or memory.namespace,
            target_type="retention_policy",
            target_id=policy_id,
            action="retention.policy_create",
            details={"action": action, "after_days": after_days, "reason": reason},
        )
    row = memory.store.connection.execute("SELECT * FROM retention_policies WHERE id = ?", (policy_id,)).fetchone()
    return RetentionPolicy.from_row(row)


def list_retention_policies(memory, *, namespace: str | None = None) -> list[RetentionPolicy]:
    params: list[Any] = []
    where = ""
    if namespace is not None:
        where = "WHERE namespace = ? OR namespace IS NULL"
        params.append(namespace)
    rows = memory.store.connection.execute(
        f"SELECT * FROM retention_policies {where} ORDER BY created_at DESC",
        params,
    ).fetchall()
    return [RetentionPolicy.from_row(row) for row in rows]


def run_retention(memory, *, namespace: str | None = None, dry_run: bool = True) -> SimpleRun:
    namespace = namespace or memory.namespace
    started_at = utc_now_iso()
    run_id = new_id("retrun")
    policies = list_retention_policies(memory, namespace=namespace)
    matched: list[dict] = []
    warnings: list[str] = []
    for policy in policies:
        if not policy.enabled:
            continue
        rows = memory.store.connection.execute(
            """
            SELECT DISTINCT c.id, c.namespace, c.memory_type, c.status
            FROM claims c
            LEFT JOIN claim_evidence_links cel ON cel.claim_id = c.id
            LEFT JOIN evidence_events e ON e.id = cel.evidence_id
            WHERE c.namespace = ?
              AND c.status NOT IN ('rejected', 'archived')
              AND (? <= 0 OR julianday(?) - julianday(c.created_at) >= ?)
              AND (? IS NULL OR c.memory_type = ?)
            GROUP BY c.id, c.namespace, c.memory_type, c.status
            HAVING (
                ? IS NULL
                OR COALESCE(MAX(CASE e.privacy_level
                    WHEN 'public' THEN 0
                    WHEN 'personal' THEN 1
                    WHEN 'private' THEN 2
                    WHEN 'sensitive' THEN 2
                    WHEN 'secret' THEN 3
                    ELSE 1
                END), 1) = ?
            )
              AND (
                ? IS NULL
                OR (
                    COUNT(e.id) > 0
                    AND SUM(CASE WHEN e.source_type = ? THEN 1 ELSE 0 END) = COUNT(e.id)
                )
              )
            """,
            (
                namespace,
                policy.after_days,
                started_at,
                policy.after_days,
                policy.memory_type,
                policy.memory_type,
                policy.privacy_level,
                PRIVACY_ORDER.get(policy.privacy_level or "personal", 1),
                policy.source_type,
                policy.source_type,
            ),
        ).fetchall()
        for row in rows:
            matched.append(
                {
                    "policy_id": policy.id,
                    "claim_id": row["id"],
                    "action": policy.action,
                    "filters": {
                        "memory_type": policy.memory_type,
                        "privacy_level": policy.privacy_level,
                        "source_type": policy.source_type,
                        "after_days": policy.after_days,
                    },
                }
            )
    applied = 0
    with memory.store.transaction():
        if not dry_run:
            for item in matched:
                applied_action = _apply_retention_action(
                    memory,
                    namespace=namespace,
                    policy_id=item["policy_id"],
                    claim_id=item["claim_id"],
                    action=item["action"],
                )
                if applied_action:
                    applied += 1
                else:
                    warnings.append(
                        f"Retention action {item['action']} did not apply to claim {item['claim_id']}."
                    )
        memory.store.connection.execute(
            """
            INSERT INTO retention_runs (
                id, namespace, dry_run, matched_count, applied_count, status,
                started_at, finished_at, warnings_json, metadata_json
            )
            VALUES (?, ?, ?, ?, ?, 'completed', ?, ?, ?, ?)
            """,
            (
                run_id,
                namespace,
                int(dry_run),
                len(matched),
                applied,
                started_at,
                utc_now_iso(),
                json.dumps(warnings, sort_keys=True),
                json.dumps({"matches": matched}, sort_keys=True),
            ),
        )
        memory._write_audit(
            namespace=namespace,
            target_type="retention_run",
            target_id=run_id,
            action="retention.run",
            details={"dry_run": dry_run, "matched_count": len(matched), "applied_count": applied},
        )
    return SimpleRun(
        id=run_id,
        status="completed",
        started_at=started_at,
        finished_at=utc_now_iso(),
        metadata={
            "matched_count": len(matched),
            "applied_count": applied,
            "matches": matched,
            "warnings": warnings,
        },
    )


def _apply_retention_action(
    memory,
    *,
    namespace: str,
    policy_id: str,
    claim_id: str,
    action: str,
) -> bool:
    reason = f"retention policy {policy_id}"
    if action == "archive":
        cursor = memory.store.connection.execute(
            "UPDATE claims SET status = 'archived' WHERE id = ? AND status NOT IN ('rejected', 'archived')",
            (claim_id,),
        )
        if not cursor.rowcount:
            return False
        memory.store.connection.execute("DELETE FROM claims_fts WHERE claim_id = ?", (claim_id,))
        _stale_semantic_for_targets(memory, namespace=namespace, target_ids=[claim_id], reason="retention.archive")
        return True
    if action == "queue_review":
        memory.create_review_task(
            namespace,
            task_type="stale_core_memory",
            title=f"Retention review for {claim_id}",
            description="Retention policy matched this memory.",
            target_id=claim_id,
            target_type="claim",
            recommended_action="Review retention action.",
            metadata={"policy_id": policy_id},
        )
        return True
    if action == "lower_salience":
        cursor = memory.store.connection.execute(
            """
            UPDATE claims
            SET importance = CASE WHEN importance > 0.2 THEN 0.2 ELSE importance END
            WHERE id = ?
              AND status NOT IN ('rejected', 'archived')
            """,
            (claim_id,),
        )
        return cursor.rowcount == 1
    if action == "redact_content":
        redact(
            memory,
            target_id=claim_id,
            target_type="claim",
            reason=reason,
            actor="retention",
            dry_run=False,
        )
        return True
    if action == "tombstone":
        return _tombstone_claim(memory, namespace=namespace, claim_id=claim_id, reason=reason)
    if action == "hard_delete":
        return _hard_delete_claim(memory, namespace=namespace, claim_id=claim_id, reason=reason)
    raise ValidationError("Unknown retention action.")


def integrity_check(memory, *, namespace: str | None = None, scope: str = "standard", deep: bool = False) -> IntegrityCheckRun:
    run_id = new_id("int")
    started_at = utc_now_iso()
    findings = _integrity_findings(memory, namespace=namespace, deep=deep)
    critical_count = sum(1 for finding in findings if finding["severity"] == "critical")
    status = "failed" if critical_count else ("passed_with_warnings" if findings else "passed")
    with memory.store.transaction():
        memory.store.connection.execute(
            """
            INSERT INTO integrity_check_runs (
                id, namespace, scope, status, finding_count, critical_count,
                started_at, finished_at, metadata_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                namespace,
                scope,
                status,
                len(findings),
                critical_count,
                started_at,
                utc_now_iso(),
                json.dumps({"deep": deep}, sort_keys=True),
            ),
        )
        for finding in findings:
            memory.store.connection.execute(
                """
                INSERT INTO integrity_findings (
                    id, run_id, severity, finding_type, target_id, target_type,
                    message, repairable, recommended_action, created_at,
                    metadata_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    new_id("intfind"),
                    run_id,
                    finding["severity"],
                    finding["finding_type"],
                    finding.get("target_id"),
                    finding.get("target_type"),
                    finding["message"],
                    int(finding.get("repairable", False)),
                    finding.get("recommended_action"),
                    utc_now_iso(),
                    json.dumps(finding.get("metadata", {}), sort_keys=True),
                ),
            )
        memory._write_audit(
            namespace=namespace or memory.namespace,
            target_type="integrity_check",
            target_id=run_id,
            action="integrity.check",
            details={"status": status, "finding_count": len(findings), "critical_count": critical_count},
        )
    row = memory.store.connection.execute("SELECT * FROM integrity_check_runs WHERE id = ?", (run_id,)).fetchone()
    return IntegrityCheckRun.from_row(row)


def list_integrity_runs(memory, *, namespace: str | None = None, limit: int = 50) -> list[IntegrityCheckRun]:
    params: list[Any] = []
    where = ""
    if namespace:
        where = "WHERE namespace = ?"
        params.append(namespace)
    params.append(limit)
    rows = memory.store.connection.execute(
        f"SELECT * FROM integrity_check_runs {where} ORDER BY started_at DESC LIMIT ?",
        params,
    ).fetchall()
    return [IntegrityCheckRun.from_row(row) for row in rows]


def list_integrity_findings(memory, *, run_id: str | None = None, limit: int = 100) -> list[IntegrityFinding]:
    params: list[Any] = []
    where = ""
    if run_id:
        where = "WHERE run_id = ?"
        params.append(run_id)
    params.append(limit)
    rows = memory.store.connection.execute(
        f"SELECT * FROM integrity_findings {where} ORDER BY created_at DESC LIMIT ?",
        params,
    ).fetchall()
    return [IntegrityFinding.from_row(row) for row in rows]


def repair_integrity(memory, *, finding_id: str, dry_run: bool = True) -> SimpleRun:
    finding = memory.store.connection.execute("SELECT * FROM integrity_findings WHERE id = ?", (finding_id,)).fetchone()
    if not finding:
        raise NotFoundError(f"Integrity finding not found: {finding_id}")
    if not finding["repairable"]:
        raise ValidationError("Finding is not repairable.")
    started_at = utc_now_iso()
    if not dry_run and finding["finding_type"] == "fts_drift":
        metadata = json.loads(finding["metadata_json"] or "{}")
        namespace = metadata.get("namespace") or (
            finding["target_id"] if finding["target_type"] == "namespace" else None
        )
        if not namespace:
            raise ValidationError("FTS repair requires a resolvable namespace.")
        with memory.store.transaction():
            memory.store.connection.execute("DELETE FROM claims_fts WHERE namespace = ?", (namespace,))
            rows = memory.store.connection.execute(
                """
                SELECT id, namespace, subject, predicate, object, memory_type
                FROM claims
                WHERE status IN ('active', 'core')
                  AND namespace = ?
                ORDER BY namespace, id
                """,
                (namespace,),
            ).fetchall()
            for claim in rows:
                memory._index_claim(
                    claim_id=claim["id"],
                    namespace=claim["namespace"],
                    subject=claim["subject"],
                    predicate=claim["predicate"],
                    object=claim["object"],
                    memory_type=claim["memory_type"],
                )
    return SimpleRun(
        id=new_id("irep"),
        status="planned" if dry_run else "completed",
        started_at=started_at,
        finished_at=utc_now_iso(),
        metadata={"finding_id": finding_id, "dry_run": dry_run},
    )


def migration_plan(memory, *, target_version: str = SCHEMA_VERSION) -> MigrationPlan:
    from_version = memory.health()["schema_version"]
    steps = [{"name": f"Add M8 hardening table {table}", "table": table, "reversible": True} for table in sorted(M8_TABLES)]
    plan_id = new_id("mplan")
    now = utc_now_iso()
    warnings = ["Backup recommended before applying migration."]
    with memory.store.transaction():
        memory.store.connection.execute(
            """
            INSERT INTO migration_plans (
                id, from_version, to_version, steps_json, irreversible,
                backup_required, warnings_json, created_at, metadata_json
            )
            VALUES (?, ?, ?, ?, 0, 1, ?, ?, ?)
            """,
            (
                plan_id,
                from_version,
                target_version,
                json.dumps(steps, sort_keys=True),
                json.dumps(warnings, sort_keys=True),
                now,
                json.dumps({"estimated_affected_tables": sorted(M8_TABLES)}, sort_keys=True),
            ),
        )
    row = memory.store.connection.execute("SELECT * FROM migration_plans WHERE id = ?", (plan_id,)).fetchone()
    return MigrationPlan.from_row(row)


def migration_apply(
    memory,
    *,
    target_version: str = SCHEMA_VERSION,
    dry_run: bool = False,
    backup_before: bool = False,
    verify_after: bool = False,
    backup_output: str | None = None,
    passphrase: str | None = None,
) -> SimpleRun:
    plan = migration_plan(memory, target_version=target_version)
    started_at = utc_now_iso()
    backup_id = None
    if not dry_run and backup_before:
        backup = create_backup(
            memory,
            output_path=backup_output or str(Path(memory.store.path).with_suffix(".pre-migrate.alet")),
            encrypt=True,
            passphrase=passphrase,
            created_by="migration",
        )
        backup_id = backup.id
    if not dry_run:
        memory.store.migrate()
    integrity = integrity_check(memory, scope="post_migration") if verify_after and not dry_run else None
    run_id = new_id("mrun")
    with memory.store.transaction():
        memory.store.connection.execute(
            """
            INSERT INTO migration_runs (
                id, plan_id, from_version, to_version, dry_run,
                backup_manifest_id, status, started_at, finished_at,
                warnings_json, metadata_json
            )
            VALUES (?, ?, ?, ?, ?, ?, 'completed', ?, ?, ?, ?)
            """,
            (
                run_id,
                plan.id,
                plan.from_version,
                target_version,
                int(dry_run),
                backup_id,
                started_at,
                utc_now_iso(),
                json.dumps(plan.warnings, sort_keys=True),
                json.dumps({"verify_after": asdict(integrity) if integrity else None}, sort_keys=True),
            ),
        )
    return SimpleRun(
        id=run_id,
        status="completed",
        started_at=started_at,
        finished_at=utc_now_iso(),
        metadata={"plan_id": plan.id, "dry_run": dry_run, "backup_manifest_id": backup_id},
    )


def compact_database(memory, *, dry_run: bool = True, backup_before: bool = False, passphrase: str | None = None) -> SimpleRun:
    path = Path(memory.store.path)
    size_before = path.stat().st_size if path.exists() else None
    started_at = utc_now_iso()
    backup_id = None
    if not dry_run and backup_before and path.exists():
        backup = create_backup(
            memory,
            output_path=str(path.with_suffix(".pre-compact.alet")),
            encrypt=True,
            passphrase=passphrase,
            created_by="compact",
        )
        backup_id = backup.id
    if not dry_run:
        memory.store.connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        memory.store.connection.execute("VACUUM")
    size_after = path.stat().st_size if path.exists() else size_before
    run_id = new_id("comp")
    with memory.store.transaction():
        memory.store.connection.execute(
            """
            INSERT INTO compaction_runs (
                id, namespace, dry_run, backup_manifest_id, size_before_bytes,
                size_after_bytes, status, started_at, finished_at,
                warnings_json, metadata_json
            )
            VALUES (?, NULL, ?, ?, ?, ?, 'completed', ?, ?, ?, ?)
            """,
            (
                run_id,
                int(dry_run),
                backup_id,
                size_before,
                size_after,
                started_at,
                utc_now_iso(),
                json.dumps(["Backup recommended before compaction."] if dry_run else [], sort_keys=True),
                json.dumps({"operations": ["vacuum", "wal_checkpoint", "prune_expired_metadata"]}, sort_keys=True),
            ),
        )
    return SimpleRun(
        id=run_id,
        status="completed",
        started_at=started_at,
        finished_at=utc_now_iso(),
        metadata={"dry_run": dry_run, "size_before_bytes": size_before, "size_after_bytes": size_after, "backup_manifest_id": backup_id},
    )


def export_archive(
    memory,
    *,
    output_path: str,
    namespace: str | None = None,
    export_type: str = "namespace_archive",
    format: str = "alet",
    encrypt: bool = False,
    privacy_mode: str = "redacted",
    passphrase: str | None = None,
) -> ExportManifest:
    if format == "alet":
        backup = create_backup(
            memory,
            output_path=output_path,
            backup_type="logical",
            namespace=namespace,
            encrypt=encrypt,
            privacy_mode=privacy_mode,
            passphrase=passphrase,
            created_by="export",
        )
        item_counts = backup.item_counts
    elif format == "jsonl":
        rows = _logical_payload(memory, namespace, privacy_mode)
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        Path(output_path).write_bytes(b"\n".join(rows.values()))
        item_counts = _item_counts(memory, namespace)
    else:
        raise ValidationError("export format must be alet or jsonl.")
    export_id = new_id("exp")
    now = utc_now_iso()
    with memory.store.transaction():
        memory.store.connection.execute(
            """
            INSERT INTO export_manifests (
                id, namespace, export_type, format, file_path, encrypted,
                privacy_mode, item_counts_json, created_at, metadata_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                export_id,
                namespace,
                export_type,
                format,
                output_path,
                int(encrypt),
                privacy_mode,
                json.dumps(item_counts, sort_keys=True),
                now,
                json.dumps({}, sort_keys=True),
            ),
        )
        memory._write_audit(
            namespace=namespace or memory.namespace,
            target_type="export",
            target_id=export_id,
            action="export.create",
            details={"output_path": output_path, "privacy_mode": privacy_mode},
        )
    row = memory.store.connection.execute("SELECT * FROM export_manifests WHERE id = ?", (export_id,)).fetchone()
    return ExportManifest.from_row(row)


def import_archive(
    memory,
    *,
    input_path: str,
    namespace: str | None = None,
    dry_run: bool = True,
    passphrase: str | None = None,
) -> ImportRun:
    started_at = utc_now_iso()
    status, warnings, manifest, payload = verify_backup_file(backup_path=input_path, passphrase=passphrase, deep=True)
    if status == "failed":
        raise ValidationError("Import source verification failed: " + "; ".join(warnings))
    imported = {"evidence": 0, "claims": 0}
    skipped = {"duplicate_evidence": 0, "duplicate_claims": 0}
    conflict_count = 0
    if "database.sqlite" in payload:
        with tempfile.TemporaryDirectory(prefix="aletheia-import-") as temp:
            source_db = Path(temp) / "source.sqlite"
            source_db.write_bytes(payload["database.sqlite"])
            source = sqlite3.connect(source_db)
            source.row_factory = sqlite3.Row
            try:
                evidence_rows = source.execute("SELECT * FROM evidence_events").fetchall()
                claim_rows = source.execute("SELECT * FROM claims").fetchall()
                for row in evidence_rows:
                    target_ns = namespace or row["namespace"]
                    duplicate = memory.store.connection.execute(
                        "SELECT 1 FROM evidence_events WHERE namespace = ? AND content_hash = ?",
                        (target_ns, row["content_hash"]),
                    ).fetchone()
                    if duplicate:
                        skipped["duplicate_evidence"] += 1
                        continue
                    imported["evidence"] += 1
                    if not dry_run:
                        memory.store.connection.execute(
                            """
                            INSERT OR IGNORE INTO evidence_events (
                                id, namespace, session_id, source_type, source_uri,
                                content, content_hash, created_at, observed_at,
                                trust_level, privacy_level, retention_policy
                            )
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                row["id"],
                                target_ns,
                                row["session_id"],
                                row["source_type"],
                                row["source_uri"],
                                row["content"],
                                row["content_hash"],
                                row["created_at"],
                                row["observed_at"],
                                row["trust_level"],
                                row["privacy_level"],
                                row["retention_policy"],
                            ),
                        )
                for row in claim_rows:
                    target_ns = namespace or row["namespace"]
                    duplicate = memory.store.connection.execute("SELECT 1 FROM claims WHERE id = ?", (row["id"],)).fetchone()
                    if duplicate:
                        skipped["duplicate_claims"] += 1
                        continue
                    imported["claims"] += 1
                    if not dry_run:
                        evidence_ids = [
                            link["evidence_id"]
                            for link in source.execute(
                                "SELECT evidence_id FROM claim_evidence_links WHERE claim_id = ?",
                                (row["id"],),
                            ).fetchall()
                        ]
                        candidate = memory.remember(
                            namespace=target_ns,
                            memory_type=row["memory_type"],
                            subject=row["subject"],
                            predicate=row["predicate"],
                            object=row["object"],
                            source_type="imported_memory",
                            confidence=row["confidence_base"],
                            status="candidate" if row["status"] not in {"rejected", "archived"} else row["status"],
                        )
                        memory._write_audit(
                            namespace=target_ns,
                            target_type="claim",
                            target_id=candidate.id,
                            action="import.claim_as_candidate",
                            details={"source_claim_id": row["id"], "source_evidence_ids": evidence_ids},
                        )
            finally:
                source.close()
    elif "logical/evidence_events.jsonl" in payload or "logical/claims.jsonl" in payload:
        evidence_rows = _jsonl_rows(payload.get("logical/evidence_events.jsonl", b""))
        claim_rows = _jsonl_rows(payload.get("logical/claims.jsonl", b""))
        for row in evidence_rows:
            target_ns = namespace or row.get("namespace") or memory.namespace
            duplicate = memory.store.connection.execute(
                "SELECT 1 FROM evidence_events WHERE namespace = ? AND content_hash = ?",
                (target_ns, row.get("content_hash")),
            ).fetchone()
            if duplicate:
                skipped["duplicate_evidence"] += 1
                continue
            imported["evidence"] += 1
            if not dry_run:
                memory.store.connection.execute(
                    """
                    INSERT OR IGNORE INTO evidence_events (
                        id, namespace, session_id, source_type, source_uri,
                        content, content_hash, created_at, observed_at,
                        trust_level, privacy_level, retention_policy
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        row["id"],
                        target_ns,
                        row.get("session_id"),
                        row.get("source_type", "imported"),
                        row.get("source_uri"),
                        row.get("content", ""),
                        row.get("content_hash") or content_hash(row.get("content", "")),
                        row.get("created_at") or started_at,
                        row.get("observed_at"),
                        row.get("trust_level", "unverified"),
                        row.get("privacy_level", "personal"),
                        row.get("retention_policy"),
                    ),
                )
        for row in claim_rows:
            target_ns = namespace or row.get("namespace") or memory.namespace
            duplicate = memory.store.connection.execute("SELECT 1 FROM claims WHERE id = ?", (row.get("id"),)).fetchone()
            if duplicate:
                skipped["duplicate_claims"] += 1
                continue
            imported["claims"] += 1
            if not dry_run:
                candidate = memory.remember(
                    namespace=target_ns,
                    memory_type=row.get("memory_type", "imported"),
                    subject=row.get("subject", ""),
                    predicate=row.get("predicate", ""),
                    object=row.get("object", ""),
                    source_type="imported_memory",
                    confidence=float(row.get("confidence_base", 0.5)),
                    status="candidate" if row.get("status") not in {"rejected", "archived"} else row.get("status"),
                )
                memory._write_audit(
                    namespace=target_ns,
                    target_type="claim",
                    target_id=candidate.id,
                    action="import.claim_as_candidate",
                    details={"source_claim_id": row.get("id"), "source": "logical_backup"},
                )
    run_id = new_id("imp")
    with memory.store.transaction():
        memory.store.connection.execute(
            """
            INSERT INTO import_runs (
                id, source_path, target_namespace, dry_run, imported_counts_json,
                skipped_counts_json, conflict_count, status, started_at,
                finished_at, warnings_json, metadata_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, 'completed', ?, ?, ?, ?)
            """,
            (
                run_id,
                input_path,
                namespace,
                int(dry_run),
                json.dumps(imported, sort_keys=True),
                json.dumps(skipped, sort_keys=True),
                conflict_count,
                started_at,
                utc_now_iso(),
                json.dumps(warnings, sort_keys=True),
                json.dumps({"manifest_id": manifest.get("id")}, sort_keys=True),
            ),
        )
        memory._write_audit(
            namespace=namespace or memory.namespace,
            target_type="import",
            target_id=run_id,
            action="import.dry_run" if dry_run else "import.apply",
            details={"source_path": input_path, "imported": imported, "skipped": skipped},
        )
    row = memory.store.connection.execute("SELECT * FROM import_runs WHERE id = ?", (run_id,)).fetchone()
    return ImportRun.from_row(row)


def support_bundle(
    memory,
    *,
    output_path: str,
    encrypt: bool = False,
    include_raw_content: bool = False,
    passphrase: str | None = None,
) -> SupportBundle:
    privacy_mode = "full" if include_raw_content else "redacted"
    diagnostics = {
        "version": _release_info(),
        "health": memory.health(),
        "platform": platform.platform(),
        "table_counts": _table_counts(memory),
        "redacted_config": _redacted_config(memory),
        "integrity_runs": [asdict(run) for run in list_integrity_runs(memory, limit=5)],
        "recent_service_requests": _redacted_service_requests(memory),
        "backups": [asdict(item) for item in list_backups(memory, limit=5)],
    }
    if include_raw_content:
        diagnostics["sample_claims"] = [asdict(claim) for claim in memory.list_claims(namespace=memory.namespace, limit=10)]
        diagnostics["sample_evidence"] = [asdict(event) for event in memory.list_events(namespace=memory.namespace, limit=10)]
    payload = _zip_bytes({"diagnostics.json": _json_bytes(diagnostics)})
    if encrypt:
        passphrase = _resolve_passphrase(passphrase, None)
        if not passphrase:
            raise ValidationError("Encrypted support bundle requires passphrase.")
        payload, enc_meta = _encrypt_bytes(payload, passphrase, key_id=None)
        files = {"encrypted_payload.bin": payload, "encryption_metadata.json": _json_bytes(enc_meta)}
    else:
        files = _read_zip_bytes(payload)
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    _write_zip(path, files)
    bundle_id = new_id("sup")
    now = utc_now_iso()
    with memory.store.transaction():
        memory.store.connection.execute(
            """
            INSERT INTO support_bundles (
                id, file_path, privacy_mode, encrypted, includes_raw_content,
                created_at, metadata_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                bundle_id,
                str(path),
                privacy_mode,
                int(encrypt),
                int(include_raw_content),
                now,
                json.dumps({"contents": sorted(files)}, sort_keys=True),
            ),
        )
    row = memory.store.connection.execute("SELECT * FROM support_bundles WHERE id = ?", (bundle_id,)).fetchone()
    return SupportBundle.from_row(row)


def benchmark_run(memory, *, profile: str = "tiny") -> BenchmarkRun:
    if profile not in {"tiny", "small", "medium", "large"}:
        raise ValidationError("Unknown benchmark profile.")
    counts = {"tiny": 5, "small": 15, "medium": 40, "large": 100}
    item_count = counts[profile]
    run_id = new_id("bench")
    started_at = utc_now_iso()
    protected = protected_mode_status(memory)
    backup_passphrase = _content_passphrase(_active_content_key(memory).id) if protected.backup_encryption_required else None
    with memory.store.transaction():
        memory.store.connection.execute(
            "INSERT INTO benchmark_runs (id, profile, started_at, finished_at, status, metadata_json) VALUES (?, ?, ?, NULL, 'running', '{}')",
            (run_id, profile, started_at),
        )
    operations = [
        ("write_event", lambda: memory.write_event(namespace=memory.namespace, source_type="benchmark", content=f"benchmark event {new_id('x')}")),
        ("remember", lambda: memory.remember(namespace=memory.namespace, memory_type="task", subject="benchmark", predicate="has_item", object=new_id("obj"))),
        ("retrieve_lexical", lambda: memory.retrieve(memory.namespace, "benchmark", mode="lexical", limit=5)),
        ("retrieve_hybrid", lambda: memory.retrieve(memory.namespace, "benchmark", mode="hybrid", limit=5)),
        ("context_pack", lambda: memory.context_pack(memory.namespace, "benchmark", token_budget=600)),
        ("integrity_check", lambda: integrity_check(memory, namespace=memory.namespace)),
        ("backup_create", lambda: create_backup(
            memory,
            output_path=str(Path(tempfile.gettempdir()) / f"{run_id}.alet"),
            encrypt=protected.backup_encryption_required,
            passphrase=backup_passphrase,
            verify_after=False,
            created_by="benchmark",
        )),
        ("backup_verify", lambda: verify_backup(
            memory,
            backup_path=str(Path(tempfile.gettempdir()) / f"{run_id}.alet"),
            passphrase=backup_passphrase,
            deep=False,
        )),
    ]
    for name, fn in operations:
        samples: list[int] = []
        loops = 1 if name.startswith("backup") or name == "integrity_check" else min(item_count, 5)
        for _ in range(loops):
            start = perf_counter()
            fn()
            samples.append(int((perf_counter() - start) * 1000))
        _record_benchmark_result(memory, run_id, name, loops, samples)
    with memory.store.transaction():
        memory.store.connection.execute(
            "UPDATE benchmark_runs SET status = 'completed', finished_at = ?, metadata_json = ? WHERE id = ?",
            (utc_now_iso(), json.dumps({"profile_item_count": item_count}, sort_keys=True), run_id),
        )
    row = memory.store.connection.execute("SELECT * FROM benchmark_runs WHERE id = ?", (run_id,)).fetchone()
    return BenchmarkRun.from_row(row)


def list_benchmarks(memory, *, limit: int = 20) -> list[BenchmarkRun]:
    rows = memory.store.connection.execute(
        "SELECT * FROM benchmark_runs ORDER BY started_at DESC LIMIT ?",
        (limit,),
    ).fetchall()
    return [BenchmarkRun.from_row(row) for row in rows]


def list_benchmark_results(memory, benchmark_run_id: str) -> list[BenchmarkResult]:
    rows = memory.store.connection.execute(
        "SELECT * FROM benchmark_results WHERE benchmark_run_id = ? ORDER BY operation",
        (benchmark_run_id,),
    ).fetchall()
    return [BenchmarkResult.from_row(row) for row in rows]


def release_manifest(memory, *, output_path: str | None = None) -> ReleaseManifest:
    manifest_id = new_id("rel")
    now = utc_now_iso()
    package_files = [{"path": "pyproject.toml", "sha256": _file_hash(Path("pyproject.toml"))}]
    lock_hash = _file_hash(Path("uv.lock")) if Path("uv.lock").exists() else None
    latest_benchmark = list_benchmarks(memory, limit=1)
    with memory.store.transaction():
        memory.store.connection.execute(
            """
            INSERT INTO release_manifests (
                id, version, git_commit, build_time, python_versions_json,
                platform_targets_json, package_files_json, dependency_lock_hash,
                migration_range, test_summary_json, benchmark_summary_json,
                created_at, metadata_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, '1.0.x -> 1.3.0', ?, ?, ?, ?)
            """,
            (
                manifest_id,
                SCHEMA_VERSION,
                os.environ.get("GIT_COMMIT"),
                now,
                json.dumps([platform.python_version()], sort_keys=True),
                json.dumps([platform.system().lower()], sort_keys=True),
                json.dumps(package_files, sort_keys=True),
                lock_hash,
                json.dumps({"unit": "run pytest", "live": "run live scorecards"}, sort_keys=True),
                json.dumps({"latest_benchmark_id": latest_benchmark[0].id if latest_benchmark else None}, sort_keys=True),
                now,
                json.dumps({"openapi_generated": True, "cli_help_generated": True, "package_build_check": "metadata"}, sort_keys=True),
            ),
        )
    row = memory.store.connection.execute("SELECT * FROM release_manifests WHERE id = ?", (manifest_id,)).fetchone()
    model = ReleaseManifest.from_row(row)
    if output_path:
        Path(output_path).write_text(json.dumps(asdict(model), indent=2) + "\n", encoding="utf-8")
    return model


def readiness_check(memory, *, namespace: str | None = None, profile: str = "local_production") -> ProductionReadinessCheck:
    namespace = namespace or memory.namespace
    protected = protected_mode_status(memory)
    content_key_configured = _protected_content_key_configured(memory, protected)
    backups = list_backups(memory, limit=1)
    latest_integrity = list_integrity_runs(memory, namespace=namespace, limit=1)
    failed_jobs = memory.list_jobs(namespace=namespace, status="failed", limit=10)
    critical_conflicts = memory.list_conflict_families(namespace=namespace, status="unresolved", limit=10)
    checks = {
        "schema_current": memory.health()["schema_version"] == SCHEMA_VERSION,
        "verified_backup_exists": bool(backups),
        "integrity_recent": bool(latest_integrity) and latest_integrity[0].status in {"passed", "passed_with_warnings"},
        "protected_mode_known": protected is not None,
        "protected_mode_enabled": protected.enabled,
        "secret_safe_indexing_policy": protected.indexing_policy,
        "critical_conflicts_absent": len(critical_conflicts) == 0,
        "failed_jobs_absent": len(failed_jobs) == 0,
        "request_logging_privacy_safe": protected.request_logging_policy == "metadata_only",
        "support_bundle_redaction_available": True,
        "protected_content_key_configured": content_key_configured,
    }
    warnings: list[str] = []
    recommendations: list[str] = []
    if not checks["verified_backup_exists"]:
        warnings.append("No verified backup is recorded.")
        recommendations.append("Run aletheia backup create --encrypt.")
    if not checks["protected_mode_enabled"]:
        warnings.append("Protected mode is disabled.")
        recommendations.append("Run aletheia encrypt enable --protected for sensitive deployments.")
    elif not checks["protected_content_key_configured"]:
        warnings.append("Protected content key is not configured.")
        recommendations.append("Set ALETHEIA_PROTECTED_KEY or ALETHEIA_KEY_<key_id> before storing protected content.")
    if not checks["integrity_recent"]:
        warnings.append("No recent passing integrity check is recorded.")
        recommendations.append("Run aletheia integrity check --deep.")
    if failed_jobs:
        warnings.append(f"{len(failed_jobs)} failed job(s) need review.")
    if critical_conflicts:
        warnings.append(f"{len(critical_conflicts)} unresolved conflict(s) need review.")
    status = "ready" if not warnings else "ready_with_warnings"
    if not checks["schema_current"]:
        status = "not_ready"
    check_id = new_id("ready")
    now = utc_now_iso()
    with memory.store.transaction():
        memory.store.connection.execute(
            """
            INSERT INTO production_readiness_checks (
                id, namespace, profile, status, checks_json, warnings_json,
                recommendations_json, created_at, metadata_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                check_id,
                namespace,
                profile,
                status,
                json.dumps(checks, sort_keys=True),
                json.dumps(warnings, sort_keys=True),
                json.dumps(recommendations, sort_keys=True),
                now,
                json.dumps({}, sort_keys=True),
            ),
        )
    row = memory.store.connection.execute("SELECT * FROM production_readiness_checks WHERE id = ?", (check_id,)).fetchone()
    return ProductionReadinessCheck.from_row(row)


def _protected_content_key_configured(memory, protected: ProtectedModeConfig) -> bool:
    if not protected.content_encryption_enabled:
        return True
    keys = list_keys(memory)
    if not keys:
        return False
    key_id = keys[0].id
    return bool(os.environ.get(f"ALETHEIA_KEY_{key_id}") or os.environ.get("ALETHEIA_PROTECTED_KEY"))


def _sqlite_snapshot(memory, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    target = sqlite3.connect(destination)
    try:
        memory.store.connection.backup(target)
    finally:
        target.close()


def _logical_payload(memory, namespace: str | None, privacy_mode: str) -> dict[str, bytes]:
    payload: dict[str, bytes] = {}
    for table in [
        "evidence_events",
        "claims",
        "claim_evidence_links",
        "candidate_claims",
        "reflections",
        "derivation_edges",
        "audit_log",
        "review_tasks",
    ]:
        rows = _table_rows(memory, table, namespace=namespace, privacy_mode=privacy_mode)
        payload[f"logical/{table}.jsonl"] = "\n".join(json.dumps(row, sort_keys=True) for row in rows).encode("utf-8")
    return payload


def _jsonl_rows(payload: bytes) -> list[dict]:
    if not payload:
        return []
    return [json.loads(line) for line in payload.decode("utf-8").splitlines() if line.strip()]


def _table_rows(memory, table: str, *, namespace: str | None, privacy_mode: str) -> list[dict]:
    cols = {row["name"] for row in memory.store.connection.execute(f"PRAGMA table_info({table})").fetchall()}
    params: list[Any] = []
    where = ""
    if namespace and "namespace" in cols:
        where = "WHERE namespace = ?"
        params.append(namespace)
    rows = [dict(row) for row in memory.store.connection.execute(f"SELECT * FROM {table} {where}", params).fetchall()]
    if privacy_mode in {"redacted", "metadata_only"}:
        for row in rows:
            for key in ["content", "object", "source_uri", "span_text", "message", "description"]:
                if key in row and row[key] is not None:
                    row[key] = "[REDACTED]"
            for key in list(row):
                if (key.endswith("_json") or key == "details") and row[key]:
                    try:
                        row[key] = json.dumps(_redact_json_value(json.loads(row[key])), sort_keys=True)
                    except (TypeError, ValueError, json.JSONDecodeError):
                        row[key] = "{}"
    return rows


def _redact_json_value(value):
    if isinstance(value, dict):
        return {key: _redact_json_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_redact_json_value(item) for item in value]
    if isinstance(value, str):
        return "[REDACTED]"
    return value


def _item_counts(memory, namespace: str | None = None) -> dict[str, int]:
    counts = {}
    for table in ["evidence_events", "claims", "candidate_claims", "reflections", "audit_log", "review_tasks", "api_tokens"]:
        cols = {row["name"] for row in memory.store.connection.execute(f"PRAGMA table_info({table})").fetchall()}
        if namespace and "namespace" in cols:
            counts[table] = int(memory.store.connection.execute(f"SELECT count(*) AS count FROM {table} WHERE namespace = ?", (namespace,)).fetchone()["count"])
        else:
            counts[table] = int(memory.store.connection.execute(f"SELECT count(*) AS count FROM {table}").fetchone()["count"])
    return counts


def _table_counts(memory) -> dict[str, int]:
    rows = memory.store.connection.execute("SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name").fetchall()
    counts = {}
    for row in rows:
        name = row["name"]
        if name.startswith("sqlite_"):
            continue
        try:
            counts[name] = int(memory.store.connection.execute(f"SELECT count(*) AS count FROM {name}").fetchone()["count"])
        except sqlite3.Error:
            continue
    return counts


def _index_metadata(memory, namespace: str | None) -> dict:
    return {
        "claims_fts_count": int(memory.store.connection.execute("SELECT count(*) AS count FROM claims_fts").fetchone()["count"]),
        "embeddings_count": int(memory.store.connection.execute("SELECT count(*) AS count FROM embeddings").fetchone()["count"]),
        "namespace": namespace,
    }


def _checksums(files: dict[str, bytes]) -> dict[str, str]:
    return {name: _sha256(data) for name, data in sorted(files.items())}


def _checksums_text(checksums: dict[str, str]) -> bytes:
    return "\n".join(f"{digest}  {name}" for name, digest in sorted(checksums.items())).encode("utf-8")


def _parse_checksums(text: str) -> dict[str, str]:
    checksums = {}
    for line in text.splitlines():
        if not line.strip():
            continue
        digest, _, name = line.partition("  ")
        checksums[name.strip()] = digest.strip()
    return checksums


def _checksum_mismatches(files: dict[str, bytes], checksums: dict[str, str]) -> list[str]:
    warnings = []
    for name, digest in checksums.items():
        if name == "checksums.sha256":
            continue
        if name not in files:
            warnings.append(f"Missing payload file: {name}")
        elif _sha256(files[name]) != digest:
            warnings.append(f"Checksum mismatch for {name}")
    return warnings


def _sha256(data: bytes) -> str:
    return sha256_hex(data)


def _file_hash(path: Path) -> str | None:
    if not path.exists():
        return None
    return _sha256(path.read_bytes())


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _zip_bytes(files: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, data in files.items():
            archive.writestr(name, data)
    return buffer.getvalue()


def _read_zip_bytes(data: bytes) -> dict[str, bytes]:
    with zipfile.ZipFile(io.BytesIO(data), "r") as archive:
        return {name: archive.read(name) for name in archive.namelist()}


def _write_zip(path: Path, files: dict[str, bytes]) -> None:
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, data in files.items():
            archive.writestr(name, data)


def _encrypt_bytes(data: bytes, passphrase: str, *, key_id: str | None) -> tuple[bytes, dict]:
    return encrypt_bytes_with_passphrase(data, passphrase, key_id=key_id)


def _decrypt_bytes(cipher: bytes, passphrase: str, metadata: dict) -> bytes:
    if metadata.get("algorithm") == LEGACY_XOR_HMAC_ALGORITHM:
        return decrypt_legacy_xor_hmac_bytes(cipher, passphrase, metadata)
    return decrypt_bytes_with_passphrase(cipher, passphrase, metadata)


def _resolve_passphrase(passphrase: str | None, key_id: str | None) -> str | None:
    if passphrase:
        return passphrase
    if key_id:
        return os.environ.get(f"ALETHEIA_KEY_{key_id}") or os.environ.get("ALETHEIA_BACKUP_PASSPHRASE")
    return os.environ.get("ALETHEIA_BACKUP_PASSPHRASE")


def _content_passphrase(key_id: str) -> str:
    value = os.environ.get(f"ALETHEIA_KEY_{key_id}") or os.environ.get("ALETHEIA_PROTECTED_KEY")
    if not value:
        raise ValidationError(
            f"Protected content key is not configured. Set ALETHEIA_KEY_{key_id} or ALETHEIA_PROTECTED_KEY."
        )
    return value


def _active_content_key(memory) -> EncryptionKeyRecord:
    keys = list_keys(memory)
    if keys:
        return keys[0]
    return create_key(memory, provider="passphrase", label="local-protected-key")


def _encrypted_content_count(memory, key_id: str) -> int:
    return int(memory.store.connection.execute(
        """
        SELECT count(*) AS count
        FROM evidence_events
        WHERE content LIKE ? OR content LIKE ?
        """,
        (
            f"enc:{LEGACY_CONTENT_ENCRYPTION_VERSION}:{key_id}:%",
            f"enc:{CONTENT_ENCRYPTION_VERSION}:{key_id}:%",
        ),
    ).fetchone()["count"])


def _redacted_config(memory) -> dict:
    return {
        "db_path": memory.store.path,
        "schema_version": memory.health()["schema_version"],
        "secrets": "<redacted>",
    }


def _release_info() -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "python": platform.python_version(),
        "platform": platform.platform(),
    }


def _backup_verification_run(memory, run_id: str) -> BackupVerificationRun:
    row = memory.store.connection.execute("SELECT * FROM backup_verification_runs WHERE id = ?", (run_id,)).fetchone()
    return BackupVerificationRun.from_row(row)


def _redaction_impact(memory, target_id: str, target_type: str) -> tuple[str, dict]:
    if target_type == "evidence":
        event = memory.read_event(target_id)
        claim_ids = [row["claim_id"] for row in memory.store.connection.execute("SELECT claim_id FROM claim_evidence_links WHERE evidence_id = ?", (target_id,)).fetchall()]
        derived_count = _derived_count(memory, claim_ids)
        return event.namespace, {"evidence": [target_id], "claims": claim_ids, "derived_count": derived_count}
    if target_type == "claim":
        claim = memory.read_claim(target_id)
        return claim.namespace, {"evidence": claim.evidence_ids, "claims": [target_id], "derived_count": _derived_count(memory, [target_id])}
    raise ValidationError("Unsupported redaction target.")


def _derived_count(memory, claim_ids: list[str]) -> int:
    if not claim_ids:
        return 0
    return int(memory.store.connection.execute(
        f"SELECT count(*) AS count FROM derivation_edges WHERE source_id IN ({','.join('?' for _ in claim_ids)})",
        claim_ids,
    ).fetchone()["count"])


def _invalidate_derived(memory, namespace: str, claim_ids: list[str], reason: str) -> None:
    for claim_id in claim_ids:
        for row in memory.store.connection.execute(
            "SELECT target_id, target_type FROM derivation_edges WHERE source_id = ? AND source_type = 'claim'",
            (claim_id,),
        ).fetchall():
            if row["target_type"] == "reflection":
                memory.store.connection.execute("UPDATE reflections SET status = 'stale' WHERE id = ?", (row["target_id"],))
            memory._write_audit(
                namespace=namespace,
                target_type=row["target_type"],
                target_id=row["target_id"],
                action="derived.invalidate",
                details={"source_id": claim_id, "reason": reason},
            )


def _stale_semantic_for_targets(memory, *, namespace: str, target_ids: list[str], reason: str) -> None:
    if not target_ids:
        return
    memory.store.connection.execute(
        f"""
        UPDATE embeddings
        SET status = 'stale', stale_reason = ?
        WHERE namespace = ?
          AND target_id IN ({','.join('?' for _ in target_ids)})
          AND COALESCE(status, 'indexed') = 'indexed'
        """,
        [reason, namespace, *target_ids],
    )
    memory.store.connection.execute(
        f"""
        UPDATE semantic_index_records
        SET status = 'stale', stale_reason = ?
        WHERE namespace = ?
          AND target_id IN ({','.join('?' for _ in target_ids)})
          AND status IN ('indexed', 'skipped')
        """,
        [reason, namespace, *target_ids],
    )


def _write_tombstone(
    memory,
    *,
    namespace: str,
    target_id: str,
    target_type: str,
    deletion_mode: str,
    reason: str,
    actor: str,
    affected_derived_count: int,
) -> None:
    memory.store.connection.execute(
        """
        INSERT INTO deletion_tombstones (
            id, namespace, target_id, target_type, deletion_mode, reason,
            deleted_by, affected_derived_count, backup_warning, created_at,
            metadata_json
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            new_id("del"),
            namespace,
            target_id,
            target_type,
            deletion_mode,
            reason,
            actor,
            affected_derived_count,
            _backup_warning(),
            utc_now_iso(),
            json.dumps({}, sort_keys=True),
        ),
    )


def _tombstone_claim(memory, *, namespace: str, claim_id: str, reason: str) -> bool:
    cursor = memory.store.connection.execute(
        "UPDATE claims SET status = 'archived' WHERE id = ? AND status NOT IN ('rejected', 'archived')",
        (claim_id,),
    )
    if not cursor.rowcount:
        return False
    memory.store.connection.execute("DELETE FROM claims_fts WHERE claim_id = ?", (claim_id,))
    _invalidate_derived(memory, namespace, [claim_id], reason)
    _stale_semantic_for_targets(memory, namespace=namespace, target_ids=[claim_id], reason="retention.tombstone")
    _write_tombstone(
        memory,
        namespace=namespace,
        target_id=claim_id,
        target_type="claim",
        deletion_mode="tombstone",
        reason=reason,
        actor="retention",
        affected_derived_count=_derived_count(memory, [claim_id]),
    )
    return True


def _hard_delete_claim(memory, *, namespace: str, claim_id: str, reason: str) -> bool:
    _invalidate_derived(memory, namespace, [claim_id], reason)
    _stale_semantic_for_targets(memory, namespace=namespace, target_ids=[claim_id], reason="retention.hard_delete")
    _write_tombstone(
        memory,
        namespace=namespace,
        target_id=claim_id,
        target_type="claim",
        deletion_mode="hard_delete",
        reason=reason,
        actor="retention",
        affected_derived_count=_derived_count(memory, [claim_id]),
    )
    memory.store.connection.execute("DELETE FROM claims_fts WHERE claim_id = ?", (claim_id,))
    memory.store.connection.execute("DELETE FROM claim_evidence_links WHERE claim_id = ?", (claim_id,))
    memory.store.connection.execute("DELETE FROM confidence_events WHERE claim_id = ?", (claim_id,))
    memory.store.connection.execute("DELETE FROM confidence_snapshots WHERE claim_id = ?", (claim_id,))
    memory.store.connection.execute("DELETE FROM claim_status_history WHERE claim_id = ?", (claim_id,))
    memory.store.connection.execute("DELETE FROM claim_scopes WHERE claim_id = ?", (claim_id,))
    memory.store.connection.execute("DELETE FROM conflict_claim_links WHERE claim_id = ?", (claim_id,))
    memory.store.connection.execute("DELETE FROM conflict_family_claims WHERE claim_id = ?", (claim_id,))
    memory.store.connection.execute("DELETE FROM curation_decisions WHERE claim_id = ?", (claim_id,))
    memory.store.connection.execute("DELETE FROM curation_queue WHERE claim_id = ?", (claim_id,))
    memory.store.connection.execute("DELETE FROM candidate_claim_links WHERE claim_id = ?", (claim_id,))
    memory.store.connection.execute("DELETE FROM derived_claim_links WHERE claim_id = ?", (claim_id,))
    memory.store.connection.execute("DELETE FROM project_claim_links WHERE claim_id = ?", (claim_id,))
    memory.store.connection.execute("DELETE FROM session_claim_links WHERE claim_id = ?", (claim_id,))
    memory.store.connection.execute("DELETE FROM claim_entity_links WHERE claim_id = ?", (claim_id,))
    memory.store.connection.execute("DELETE FROM feedback WHERE target_type = 'claim' AND target_id = ?", (claim_id,))
    memory.store.connection.execute("DELETE FROM memory_category_labels WHERE target_type = 'claim' AND target_id = ?", (claim_id,))
    memory.store.connection.execute(
        "DELETE FROM claim_relationships WHERE source_claim_id = ? OR target_claim_id = ?",
        (claim_id, claim_id),
    )
    memory.store.connection.execute(
        """
        DELETE FROM derivation_edges
        WHERE (source_type = 'claim' AND source_id = ?)
           OR (target_type = 'claim' AND target_id = ?)
        """,
        (claim_id, claim_id),
    )
    memory.store.connection.execute(
        "DELETE FROM embeddings WHERE target_id = ? AND target_type IN ('claim', 'claims')",
        (claim_id,),
    )
    memory.store.connection.execute(
        "DELETE FROM semantic_index_records WHERE target_id = ? AND target_type IN ('claim', 'claims')",
        (claim_id,),
    )
    cursor = memory.store.connection.execute("DELETE FROM claims WHERE id = ?", (claim_id,))
    return cursor.rowcount == 1


def _backup_warning() -> str:
    return "Deletion/redaction cannot remove data from old backups, filesystem snapshots, OS caches, or external copies."


def _forget_targets(memory, selector: dict) -> list[dict]:
    targets: list[dict] = []
    if selector.get("target_type") == "evidence" and selector.get("target_id"):
        event = memory.read_event(selector["target_id"])
        return [{"namespace": event.namespace, "target_type": "evidence", "target_id": event.id}]
    if selector.get("target_type") == "claim" and selector.get("target_id"):
        claim = memory.read_claim(selector["target_id"])
        return [{"namespace": claim.namespace, "target_type": "claim", "target_id": claim.id}]
    namespace = selector.get("namespace") or memory.namespace
    for row in memory.store.connection.execute("SELECT id, namespace FROM evidence_events WHERE namespace = ?", (namespace,)).fetchall():
        targets.append({"namespace": row["namespace"], "target_type": "evidence", "target_id": row["id"]})
    for row in memory.store.connection.execute("SELECT id, namespace FROM claims WHERE namespace = ?", (namespace,)).fetchall():
        targets.append({"namespace": row["namespace"], "target_type": "claim", "target_id": row["id"]})
    return targets


def _integrity_findings(memory, *, namespace: str | None, deep: bool) -> list[dict]:
    findings: list[dict] = []
    health = memory.health()
    if health["schema_version"] != SCHEMA_VERSION:
        findings.append(_finding("critical", "schema_version", None, None, f"Schema is {health['schema_version']}, expected {SCHEMA_VERSION}.", False, "Run migration."))
    tables = {row["name"] for row in memory.store.connection.execute("SELECT name FROM sqlite_master WHERE type IN ('table', 'virtual table')").fetchall()}
    for table in sorted(M8_TABLES - tables):
        findings.append(_finding("critical", "missing_table", table, "table", f"Required table missing: {table}", False, "Run migration."))
    params: list[Any] = []
    ns_clause = ""
    if namespace:
        ns_clause = "WHERE c.namespace = ?"
        params.append(namespace)
    rows = memory.store.connection.execute(
        f"""
        SELECT c.id
        FROM claims c
        LEFT JOIN claim_evidence_links l ON l.claim_id = c.id
        {ns_clause}
        GROUP BY c.id
        HAVING count(l.evidence_id) = 0
        """,
        params,
    ).fetchall()
    for row in rows:
        findings.append(_finding("high", "claim_missing_evidence", row["id"], "claim", "Claim has no evidence links.", False, "Archive or repair claim evidence links."))
    dangling = memory.store.connection.execute(
        """
        SELECT l.claim_id, l.evidence_id
        FROM claim_evidence_links l
        LEFT JOIN evidence_events e ON e.id = l.evidence_id
        WHERE e.id IS NULL
        """
    ).fetchall()
    for row in dangling:
        findings.append(_finding("critical", "orphan_claim_evidence_link", row["claim_id"], "claim", f"Claim links missing evidence {row['evidence_id']}.", True, "Remove or repair orphaned evidence link."))
    tombstoned_active = memory.store.connection.execute(
        """
        SELECT c.id AS claim_id, t.target_id AS evidence_id
        FROM claims c
        JOIN claim_evidence_links l ON l.claim_id = c.id
        JOIN deletion_tombstones t ON t.target_id = l.evidence_id AND t.target_type = 'evidence'
        WHERE c.status IN ('active', 'core')
        """
    ).fetchall()
    for row in tombstoned_active:
        findings.append(_finding("high", "tombstoned_evidence_active_support", row["claim_id"], "claim", f"Active claim uses tombstoned evidence {row['evidence_id']}.", True, "Archive claim or replace evidence."))
    active_params: list[Any] = []
    active_clause = "status IN ('active', 'core')"
    fts_params: list[Any] = []
    fts_clause = "1 = 1"
    if namespace:
        active_clause += " AND namespace = ?"
        active_params.append(namespace)
        fts_clause += " AND namespace = ?"
        fts_params.append(namespace)
    active_claims = int(
        memory.store.connection.execute(
            f"SELECT count(*) AS count FROM claims WHERE {active_clause}",
            active_params,
        ).fetchone()["count"]
    )
    fts_count = int(
        memory.store.connection.execute(
            f"SELECT count(*) AS count FROM claims_fts WHERE {fts_clause}",
            fts_params,
        ).fetchone()["count"]
    )
    if deep and fts_count > active_claims:
        findings.append(
            _finding(
                "medium",
                "fts_drift",
                namespace,
                "namespace" if namespace else "index",
                "FTS index has more rows than active/core claims.",
                True,
                "Rebuild FTS index.",
                metadata={"namespace": namespace} if namespace else {},
            )
        )
    reflection_rows = memory.store.connection.execute(
        """
        SELECT r.id
        FROM reflections r
        LEFT JOIN reflection_sources s ON s.reflection_id = r.id
        WHERE r.status = 'active'
        GROUP BY r.id
        HAVING count(s.source_id) = 0
        """
    ).fetchall()
    for row in reflection_rows:
        findings.append(_finding("high", "reflection_missing_sources", row["id"], "reflection", "Active reflection has no sources.", False, "Archive or rebuild reflection."))
    raw_token_rows = memory.store.connection.execute("SELECT token_hash FROM api_tokens WHERE token_hash LIKE 'atl_%'").fetchall()
    for _row in raw_token_rows:
        findings.append(_finding("critical", "raw_token_stored", None, "api_token", "A raw-looking token is stored in token_hash.", False, "Revoke and recreate token."))
    return findings


def _finding(
    severity: str,
    finding_type: str,
    target_id: str | None,
    target_type: str | None,
    message: str,
    repairable: bool,
    action: str,
    metadata: dict | None = None,
) -> dict:
    return {
        "severity": severity,
        "finding_type": finding_type,
        "target_id": target_id,
        "target_type": target_type,
        "message": message,
        "repairable": repairable,
        "recommended_action": action,
        "metadata": metadata or {},
    }


def _redacted_service_requests(memory) -> list[dict]:
    rows = memory.store.connection.execute(
        "SELECT request_id, client_id, namespace, method, path, status_code, duration_ms, log_mode, created_at FROM service_request_log ORDER BY created_at DESC LIMIT 50"
    ).fetchall()
    return [dict(row) for row in rows]


def _record_benchmark_result(memory, run_id: str, operation: str, item_count: int, samples: list[int]) -> None:
    samples = samples or [0]
    ordered = sorted(samples)
    p50 = statistics.median(ordered)
    p95 = ordered[min(len(ordered) - 1, int(len(ordered) * 0.95))]
    p99 = ordered[min(len(ordered) - 1, int(len(ordered) * 0.99))]
    with memory.store.transaction():
        memory.store.connection.execute(
            """
            INSERT INTO benchmark_results (
                id, benchmark_run_id, operation, item_count, duration_ms,
                p50_ms, p95_ms, p99_ms, memory_mb, created_at, metadata_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL, ?, ?)
            """,
            (
                new_id("bres"),
                run_id,
                operation,
                item_count,
                sum(samples),
                p50,
                p95,
                p99,
                utc_now_iso(),
                json.dumps({"samples": samples}, sort_keys=True),
            ),
        )
