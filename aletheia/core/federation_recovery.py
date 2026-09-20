"""Operator-authorized federation key replacement and offline data recovery.

Recovery archives contain only a retired X25519 decryption key. They cannot
restore signing authority, and recovered bundles are never imported here.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import x25519

from aletheia.core import federation as fed
from aletheia.core.crypto import decrypt_bytes_with_passphrase, encrypt_bytes_with_passphrase, sha256_hex
from aletheia.core.errors import ValidationError
from aletheia.core.time import utc_now_iso


KEY_ARCHIVE_FORMAT = "aletheia-federation-decryption-recovery"
REVIEW_FORMAT = "aletheia-federation-recovery-review"


def _recovery_passphrase(value: str | None) -> str:
    secret = value if value is not None else os.environ.get("ALETHEIA_FEDERATION_RECOVERY_KEY")
    if not isinstance(secret, str) or not secret.strip():
        raise ValidationError("Configure ALETHEIA_FEDERATION_RECOVERY_KEY or provide a recovery passphrase.")
    return secret


def _confirm_fingerprint(expected: str | None, actual: str) -> None:
    if not isinstance(expected, str) or expected != actual:
        raise ValidationError("Expected fingerprint does not match; inspect and independently confirm the current identity.")


def _write_encrypted_document(path: Path, document: dict, secret: str, format_name: str) -> None:
    ciphertext, metadata = encrypt_bytes_with_passphrase(
        json.dumps(document, sort_keys=True).encode("utf-8"), secret,
        associated_data=format_name.encode("ascii"),
    )
    envelope = {"format": format_name, "version": 1, "metadata": metadata, "ciphertext": fed._b64(ciphertext)}
    # No replacement, symlink following, or plaintext staging file. A leftover
    # encrypted archive on a later database failure is deliberately retained.
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(envelope, stream, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        if os.name == "posix":
            directory = os.open(path.parent, os.O_RDONLY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
    except OSError as exc:
        raise ValidationError("Cannot persist recovery output; choose a new file in a writable private directory.") from exc
    if _read_encrypted_document(path, secret, format_name) != document:
        raise ValidationError("Encrypted recovery file verification failed.")


def _read_encrypted_document(path: Path, secret: str, format_name: str) -> dict:
    try:
        envelope = json.loads(path.read_text(encoding="utf-8"))
        if envelope["format"] != format_name or envelope["version"] != 1:
            raise ValidationError("Unsupported federation recovery archive format.")
        if not isinstance(envelope["metadata"], dict) or not isinstance(envelope["ciphertext"], str):
            raise ValidationError("Invalid federation recovery encryption metadata.")
        data = decrypt_bytes_with_passphrase(
            fed._unb64(envelope["ciphertext"]), secret, envelope["metadata"],
            associated_data=format_name.encode("ascii"),
        )
        document = json.loads(data)
        if not isinstance(document, dict):
            raise ValidationError("Invalid federation recovery document.")
        return document
    except (OSError, KeyError, TypeError, ValueError) as exc:
        raise ValidationError("Invalid federation recovery archive.") from exc


def rotate_federation_key(memory, *, reason: str, actor: str = "user", expected_fingerprint: str | None = None,
                          recovery_path: str | None = None, recovery_passphrase: str | None = None):
    fed._require_reason(reason)
    if not recovery_path:
        raise ValidationError("A new encrypted recovery_path is required before rotating federation keys.")
    secret = _recovery_passphrase(recovery_passphrase)
    path = Path(recovery_path).expanduser()
    with memory.store.transaction(immediate=True):
        identity = fed.active_federation_identity(memory)
        _confirm_fingerprint(expected_fingerprint, identity.key_fingerprint)
        old_private = fed._private_key_doc(identity)
        archived = {
            "instance_id": identity.instance_id,
            "public_key": identity.public_key,
            "key_fingerprint": identity.key_fingerprint,
            "encryption_private_key": old_private["encryption"]["private_key"],
            "created_at": utc_now_iso(),
        }
        _archive_decryption_key(archived)  # Check that the retained key matches its public identity.
        public_key, private_ref, fingerprint = fed._new_key_material(
            identity.display_name, identity.key_algorithm,
            protected=bool(identity.metadata.get("protected_private_key", True)),
        )
        _write_encrypted_document(path, archived, secret, KEY_ARCHIVE_FORMAT)
        now = utc_now_iso()
        metadata = dict(identity.metadata)
        old_keys = list(metadata.get("old_public_keys") or [])
        old_keys.append({"public_key": identity.public_key, "key_fingerprint": identity.key_fingerprint,
                         "rotated_at": now, "reason": reason})
        metadata.update({"old_public_keys": old_keys, "private_key_ref": private_ref,
                         "private_key_exported": False, "last_rotation_reason": reason})
        memory.store.connection.execute(
            "UPDATE federation_identities SET public_key = ?, key_fingerprint = ?, rotated_at = ?, metadata_json = ? WHERE id = ?",
            (public_key, fingerprint, now, json.dumps(metadata, sort_keys=True), identity.id),
        )
        # A compromise recovery never silently renews prior grants, including
        # grants imported from peers. Historical recovery is a separate path.
        for share in fed.list_share_grants(memory):
            if share.status != "revoked":
                fed._revoke_share_grant(memory, share.id, reason=reason, actor=actor)
        audit_metadata = {"old_fingerprint": identity.key_fingerprint, "new_fingerprint": fingerprint,
                          "recovery_archive_sha256": sha256_hex(path.read_bytes())}
        fed._write_revocation_record(memory, revocation_type="key_revocation", target_id=identity.id,
                                     target_type="federation_identity", peer_id=None, reason=reason,
                                     actor=actor, metadata=audit_metadata)
        fed._write_federation_audit(memory, event_type="identity.key_rotated", target_id=identity.id,
                                    target_type="federation_identity", actor=actor, reason=reason, metadata=audit_metadata)
    return fed.get_federation_identity(memory, identity.id)


def _key_components(public_key: str) -> tuple[bytes, bytes]:
    doc = fed._public_key_doc(public_key)
    return tuple(fed._unb64(doc[role]["public_key"]) for role in ("signing", "encryption"))


def replace_peer_key(memory, peer_id: str, *, peer_identity: dict, expected_fingerprint: str,
                     confirmed_fingerprint: str, reason: str, actor: str = "user"):
    fed._require_reason(reason)
    fed._validate_peer_identity_payload(peer_identity)
    _confirm_fingerprint(confirmed_fingerprint, peer_identity["key_fingerprint"])
    with memory.store.transaction(immediate=True):
        peer = fed.get_peer(memory, peer_id)
        _confirm_fingerprint(expected_fingerprint, peer.key_fingerprint)
        if peer_identity["instance_id"] != peer.peer_instance_id:
            raise ValidationError("Replacement identity must use the pinned peer instance ID.")
        new_components = _key_components(peer_identity["public_key"])
        if any(old == new for old, new in zip(_key_components(peer.public_key), new_components)):
            raise ValidationError("Recovery must replace both signing and encryption keys.")
        # Keep retirement history in the durable revocation records, not
        # peer metadata that ordinary add_peer refreshes can replace.
        rows = memory.store.connection.execute(
            "SELECT metadata_json FROM revocation_records WHERE target_id = ? AND target_type = 'peer_device' AND revocation_type = 'key_revocation'",
            (peer.id,),
        ).fetchall()
        for row in rows:
            previous = json.loads(row["metadata_json"])
            if previous.get("old_fingerprint") == peer_identity["key_fingerprint"]:
                raise ValidationError("Cannot restore a retired or revoked peer key.")
            if previous.get("old_public_key") and any(
                old == new for old, new in zip(_key_components(previous["old_public_key"]), new_components)
            ):
                raise ValidationError("Cannot reuse retired signing or encryption key material.")
        fed.revoke_peer(memory, peer.id, reason=reason, actor=actor, revoke_shares=True)
        # Whitelist public input; do not echo arbitrary imported metadata into
        # API responses, including old private-key records from legacy exports.
        public_identity = {key: peer_identity[key] for key in
                           ("instance_id", "display_name", "public_key", "key_fingerprint", "key_algorithm")}
        memory.store.connection.execute(
            """UPDATE peer_devices SET display_name = ?, public_key = ?, key_fingerprint = ?,
               trust_status = 'unknown', trust_domain_id = NULL, trusted_at = NULL, revoked_at = NULL,
               metadata_json = ? WHERE id = ?""",
            (peer_identity["display_name"], peer_identity["public_key"], peer_identity["key_fingerprint"],
             json.dumps({"source_identity": public_identity, "reason": reason}, sort_keys=True), peer.id),
        )
        metadata = {"old_fingerprint": peer.key_fingerprint, "old_public_key": peer.public_key,
                    "new_fingerprint": peer_identity["key_fingerprint"], "trust_reset": True}
        fed._write_revocation_record(memory, revocation_type="key_revocation", target_id=peer.id,
                                     target_type="peer_device", peer_id=peer.id, reason=reason, actor=actor, metadata=metadata)
        fed._write_federation_audit(memory, event_type="peer.key_replaced", peer_id=peer.id,
                                    target_id=peer.id, target_type="peer_device", actor=actor, reason=reason, metadata=metadata)
    return fed.get_peer(memory, peer.id)


def _archive_decryption_key(archived: dict) -> x25519.X25519PrivateKey:
    try:
        public_key = archived["public_key"]
        if sha256_hex(public_key)[:32] != archived["key_fingerprint"]:
            raise ValidationError("Recovery key fingerprint is invalid.")
        key = x25519.X25519PrivateKey.from_private_bytes(fed._unb64(archived["encryption_private_key"]))
        derived = key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
        if derived != _key_components(public_key)[1]:
            raise ValidationError("Recovery decryption key does not match its public identity.")
        return key
    except (KeyError, TypeError, ValueError) as exc:
        raise ValidationError("Invalid recovery decryption key.") from exc


def recover_share_bundle_for_review(memory, *, input_path: str, recovery_path: str, expected_fingerprint: str,
                                    output_path: str, reason: str, actor: str = "user",
                                    recovery_passphrase: str | None = None) -> dict:
    fed._require_reason(reason)
    secret = _recovery_passphrase(recovery_passphrase)
    archived = _read_encrypted_document(Path(recovery_path).expanduser(), secret, KEY_ARCHIVE_FORMAT)
    _confirm_fingerprint(expected_fingerprint, archived.get("key_fingerprint"))
    identity = fed.active_federation_identity(memory)
    if archived.get("instance_id") != identity.instance_id:
        raise ValidationError("Recovery key belongs to another local identity.")
    key = _archive_decryption_key(archived)
    manifest, payload = fed._read_bundle(memory, input_path, recovery_key=(expected_fingerprint, key))
    # Recovery verifies cryptographic integrity, not current authorization or
    # historical authenticity after a compromise. It writes no database state.
    # Keep this a distinct encrypted format, never a re-importable sync bundle.
    fields = {
        "claims": ("id", "namespace", "subject", "predicate", "object", "memory_type", "status", "confidence_base",
                   "importance", "half_life_days", "evidence_ids", "created_at"),
        "evidence": ("id", "namespace", "source_type", "source_uri", "content", "content_hash", "created_at",
                     "observed_at", "trust_level", "privacy_level"),
        "tombstones": ("id", "namespace", "object_id", "object_type", "tombstone_type", "reason", "created_at"),
    }
    recovered = {
        "requires_review": True,
        "recovered_at": utc_now_iso(),
        "actor": actor,
        "reason": reason,
        "recipient_fingerprint": expected_fingerprint,
        "source_bundle_sha256": sha256_hex(Path(input_path).read_bytes()),
        "origin_instance_id": manifest["origin_instance_id"],
        "signer_fingerprint": payload["peer_identity"]["key_fingerprint"],
        "payloads": {kind: [{field: item[field] for field in allowed if field in item}
                            for item in payload.get("payloads", {}).get(kind, [])]
                     for kind, allowed in fields.items()},
    }
    path = Path(output_path).expanduser()
    _write_encrypted_document(path, recovered, secret, REVIEW_FORMAT)
    return {"output_path": str(path), "requires_review": True,
            "item_counts": {kind: len(items) for kind, items in recovered["payloads"].items()}}


def read_federation_recovery_review(*, input_path: str, recovery_passphrase: str | None = None) -> dict:
    """Embedded-only explicit decryption for review; never used by import."""
    return _read_encrypted_document(Path(input_path).expanduser(), _recovery_passphrase(recovery_passphrase), REVIEW_FORMAT)
