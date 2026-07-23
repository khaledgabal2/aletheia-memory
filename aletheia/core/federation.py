"""M10 local-first federation, sharing, and secure sync services."""

from __future__ import annotations

import base64
import json
import os
import zipfile
from dataclasses import asdict
from pathlib import Path
from typing import Any

from aletheia.core.crypto import (
    aes_gcm_decrypt,
    aes_gcm_encrypt,
    constant_time_equal,
    decrypt_bytes_with_passphrase,
    encrypt_bytes_with_passphrase,
    generate_aes_key,
    random_bytes,
    sha256_hex,
)
from aletheia.core.errors import NotFoundError, ValidationError
from aletheia.core.ids import content_hash, new_id
from aletheia.core.time import parse_iso, utc_now, utc_now_iso
from aletheia.models import (
    AgentGroup,
    AgentGroupMember,
    ConsentRecord,
    FederationAuditEvent,
    FederationIdentity,
    ImportTrustPolicy,
    PeerDevice,
    RemoteMemorySource,
    ReplicationCursor,
    RevocationRecord,
    ShareGrant,
    ShareRecipient,
    SyncChangeItem,
    SyncChangeSet,
    SyncCollection,
    SyncConflict,
    SyncConflictResolution,
    SyncRun,
    SyncTombstone,
    TrustDomain,
    Workspace,
    WorkspaceMember,
)
from aletheia.storage import SCHEMA_VERSION

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ed25519, x25519
from cryptography.hazmat.primitives.kdf.hkdf import HKDF


PRIVACY_ORDER = {"public": 0, "personal": 1, "private": 2, "sensitive": 2, "secret": 3}
IDENTITY_STATUSES = {"active", "rotated", "revoked", "disabled"}
PEER_TRUST_STATUSES = {"unknown", "untrusted", "trusted_device", "trusted_user", "trusted_team", "revoked", "blocked"}
GRANT_TYPES = {"read_only", "read_write_candidate", "read_write_active", "feedback_only", "sync_bidirectional", "export_only"}
SHARE_PERMISSIONS = {
    "read_claims",
    "read_evidence",
    "read_reflections",
    "read_inferences",
    "read_audit",
    "write_candidate",
    "write_feedback",
    "write_active",
    "sync_pull",
    "sync_push",
    "receive_redactions",
    # CLI-friendly aliases from the primary objective.
    "read",
    "candidate_write",
    "feedback",
}
SHARE_STATUSES = {"active", "paused", "revoked", "expired", "disabled"}
COLLECTION_DIRECTIONS = {"push", "pull", "bidirectional"}
COLLECTION_TRANSPORTS = {"file_bundle", "local_http", "manual_import", "plugin_transport"}
COLLECTION_STATUSES = {"active", "paused", "revoked", "failed", "disabled"}
SYNC_STATUSES = {"planned", "running", "completed", "completed_with_conflicts", "failed", "cancelled", "blocked"}
IMPORT_MODES = {"candidate_only", "remote_claim_only", "active_if_trusted", "active_for_project_state", "manual_review", "reject_by_default"}
CONFLICT_TYPES = {
    "claim_value_conflict",
    "status_conflict",
    "scope_conflict",
    "privacy_label_conflict",
    "delete_update_conflict",
    "redaction_update_conflict",
    "confidence_conflict",
    "policy_conflict",
    "duplicate_remote_object",
    "missing_dependency",
    "unsupported_object_type",
}
CONFLICT_RESOLUTION_STRATEGIES = {
    "keep_local",
    "accept_remote_as_candidate",
    "accept_remote_active",
    "merge_as_conflict_family",
    "scope_both",
    "time_scope",
    "reject_remote",
    "defer",
    "manual_merge",
}
WORKSPACE_MEMBER_TYPES = {"local_user", "peer_device", "agent", "api_client"}
WORKSPACE_ROLES = {"owner", "admin", "curator", "contributor", "reader", "agent"}
AGENT_GROUP_ROLES = {"owner", "admin", "member", "agent"}
FEDERATION_PUBLIC_KEY_PREFIX = "fedpub_v2_"
FEDERATION_PRIVATE_KEY_PREFIX = "local_v2_"
FEDERATION_ENCRYPTED_PRIVATE_KEY_PREFIX = "local_enc_v2_"
FEDERATION_PRIVATE_KEY_AAD = b"aletheia-federation-private-key-v2"
BUNDLE_CRYPTO_VERSION = "2.0"
SIGNING_ALGORITHM = "ed25519"
ENCRYPTION_ALGORITHM = "AES-256-GCM-X25519"


def create_federation_identity(memory, *, display_name: str, key_algorithm: str = "default", protected: bool = True) -> FederationIdentity:
    existing = active_federation_identity(memory, none_if_missing=True)
    if existing:
        raise ValidationError("Active federation identity already exists; rotate the key instead.")
    public_key, private_ref, fingerprint = _new_key_material(display_name, key_algorithm, protected=protected)
    instance_id = "inst_" + content_hash(f"{display_name}\0{public_key}")[:24]
    identity_id = "fid_" + content_hash(instance_id)[:24]
    now = utc_now_iso()
    with memory.store.transaction():
        memory.store.connection.execute(
            """
            INSERT INTO federation_identities (
                id, instance_id, display_name, public_key, key_fingerprint,
                key_algorithm, status, created_at, rotated_at, metadata_json
            )
            VALUES (?, ?, ?, ?, ?, ?, 'active', ?, NULL, ?)
            """,
            (
                identity_id,
                instance_id,
                display_name,
                public_key,
                fingerprint,
                key_algorithm,
                now,
                json.dumps(
                    {
                        "protected_private_key": bool(protected),
                        "private_key_ref": private_ref,
                        "private_key_exported": False,
                    },
                    sort_keys=True,
                ),
            ),
        )
        _write_federation_audit(memory, event_type="identity.created", target_id=identity_id, target_type="federation_identity", actor="user")
    return get_federation_identity(memory, identity_id)


def active_federation_identity(memory, *, none_if_missing: bool = False) -> FederationIdentity | None:
    row = memory.store.connection.execute(
        "SELECT * FROM federation_identities WHERE status = 'active' ORDER BY created_at DESC LIMIT 1"
    ).fetchone()
    if not row:
        if none_if_missing:
            return None
        raise NotFoundError("No active federation identity exists.")
    return FederationIdentity.from_row(row)


def get_federation_identity(memory, identity_id: str) -> FederationIdentity:
    row = memory.store.connection.execute(
        "SELECT * FROM federation_identities WHERE id = ? OR instance_id = ?",
        (identity_id, identity_id),
    ).fetchone()
    if not row:
        raise NotFoundError(f"Federation identity not found: {identity_id}")
    return FederationIdentity.from_row(row)


def list_federation_identities(memory) -> list[FederationIdentity]:
    rows = memory.store.connection.execute("SELECT * FROM federation_identities ORDER BY created_at DESC").fetchall()
    return [FederationIdentity.from_row(row) for row in rows]


def export_federation_identity(memory, *, output_path: str | None = None) -> dict:
    identity = active_federation_identity(memory)
    payload = _public_identity_payload(identity)
    if output_path:
        Path(output_path).write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    _write_federation_audit(memory, event_type="identity.exported", target_id=identity.id, target_type="federation_identity", metadata={"output_path": output_path})
    return payload


def rotate_federation_key(memory, *, reason: str, actor: str = "user") -> FederationIdentity:
    _require_reason(reason)
    identity = active_federation_identity(memory)
    public_key, private_ref, fingerprint = _new_key_material(
        identity.display_name,
        identity.key_algorithm,
        protected=bool(identity.metadata.get("protected_private_key", True)),
    )
    metadata = dict(identity.metadata)
    old_keys = list(metadata.get("old_public_keys") or [])
    old_keys.append(
        {
            "public_key": identity.public_key,
            "key_fingerprint": identity.key_fingerprint,
            "rotated_at": utc_now_iso(),
            "reason": reason,
        }
    )
    metadata.update(
        {
            "old_public_keys": old_keys,
            "private_key_ref": private_ref,
            "private_key_exported": False,
            "last_rotation_reason": reason,
        }
    )
    now = utc_now_iso()
    with memory.store.transaction():
        memory.store.connection.execute(
            """
            UPDATE federation_identities
            SET public_key = ?, key_fingerprint = ?, rotated_at = ?, metadata_json = ?
            WHERE id = ?
            """,
            (public_key, fingerprint, now, json.dumps(metadata, sort_keys=True), identity.id),
        )
        _write_revocation_record(
            memory,
            revocation_type="key_revocation",
            target_id=identity.id,
            target_type="federation_identity",
            peer_id=None,
            reason=reason,
            actor=actor,
            metadata={"old_fingerprint": identity.key_fingerprint, "new_fingerprint": fingerprint},
        )
        _write_federation_audit(memory, event_type="identity.key_rotated", target_id=identity.id, target_type="federation_identity", actor=actor, reason=reason)
    return get_federation_identity(memory, identity.id)


def federation_status(memory) -> dict:
    identity = active_federation_identity(memory, none_if_missing=True)
    return {
        "schema_version": SCHEMA_VERSION,
        "identity": asdict(identity) if identity else None,
        "peer_count": len(list_peers(memory, include_revoked=True)),
        "trusted_peer_count": len([peer for peer in list_peers(memory) if peer.trust_status in {"trusted_device", "trusted_user", "trusted_team"}]),
        "active_share_count": len(list_share_grants(memory, status="active")),
        "open_conflict_count": len(list_sync_conflicts(memory, status="unresolved")),
        "last_sync": _last_sync_time(memory),
    }


def add_peer(
    memory,
    *,
    peer_identity_file: str | None = None,
    peer_identity: dict | None = None,
    display_name: str | None = None,
    trust_status: str = "unknown",
    reason: str,
) -> PeerDevice:
    _require_reason(reason)
    if trust_status not in PEER_TRUST_STATUSES:
        raise ValidationError(f"Unknown peer trust status: {trust_status}")
    payload = dict(peer_identity or {})
    if peer_identity_file:
        payload = json.loads(Path(peer_identity_file).read_text(encoding="utf-8"))
    _validate_peer_identity_payload(payload)
    peer_instance_id = payload["instance_id"]
    public_key = payload["public_key"]
    fingerprint = payload["key_fingerprint"]
    peer_id = "peer_" + content_hash(peer_instance_id)[:24]
    now = utc_now_iso()
    with memory.store.transaction():
        existing_row = memory.store.connection.execute(
            "SELECT * FROM peer_devices WHERE peer_instance_id = ?",
            (peer_instance_id,),
        ).fetchone()
        if existing_row:
            existing = PeerDevice.from_row(existing_row)
            if existing.public_key != public_key or existing.key_fingerprint != fingerprint:
                raise ValidationError(
                    "Peer identity key changed; revoke and re-add the peer or use a signed key rotation flow."
                )
        memory.store.connection.execute(
            """
            INSERT INTO peer_devices (
                id, peer_instance_id, display_name, public_key, key_fingerprint,
                trust_status, trust_domain_id, added_at, trusted_at, revoked_at,
                metadata_json
            )
            VALUES (?, ?, ?, ?, ?, ?, NULL, ?, ?, NULL, ?)
            ON CONFLICT(peer_instance_id) DO UPDATE SET
                display_name = excluded.display_name,
                public_key = excluded.public_key,
                key_fingerprint = excluded.key_fingerprint,
                metadata_json = excluded.metadata_json
            """,
            (
                peer_id,
                peer_instance_id,
                display_name or payload.get("display_name") or peer_instance_id,
                public_key,
                fingerprint,
                trust_status,
                now,
                now if trust_status.startswith("trusted_") else None,
                json.dumps({"source_identity": payload, "reason": reason}, sort_keys=True),
            ),
        )
        _write_federation_audit(memory, event_type="peer.added", peer_id=peer_id, target_id=peer_id, target_type="peer_device", reason=reason)
    return get_peer(memory, peer_id)


def get_peer(memory, peer_id: str) -> PeerDevice:
    row = memory.store.connection.execute(
        "SELECT * FROM peer_devices WHERE id = ? OR peer_instance_id = ? OR display_name = ?",
        (peer_id, peer_id, peer_id),
    ).fetchone()
    if not row:
        raise NotFoundError(f"Peer not found: {peer_id}")
    return PeerDevice.from_row(row)


def list_peers(memory, *, include_revoked: bool = False) -> list[PeerDevice]:
    where = "" if include_revoked else "WHERE trust_status != 'revoked'"
    rows = memory.store.connection.execute(f"SELECT * FROM peer_devices {where} ORDER BY added_at DESC").fetchall()
    return [PeerDevice.from_row(row) for row in rows]


def trust_peer(memory, peer_id: str, *, trust_status: str, trust_domain_id: str | None = None, reason: str, actor: str = "user") -> PeerDevice:
    _require_reason(reason)
    if trust_status not in PEER_TRUST_STATUSES - {"revoked"}:
        raise ValidationError(f"Unsupported trust status: {trust_status}")
    peer = get_peer(memory, peer_id)
    if peer.trust_status == "revoked":
        raise ValidationError("Revoked peers cannot be trusted again; add the peer identity again.")
    if trust_domain_id:
        get_trust_domain(memory, trust_domain_id)
    elif trust_status == "trusted_device":
        trust_domain_id = "trust_personal_trusted_devices"
    elif trust_status == "trusted_team":
        trust_domain_id = "trust_team_shared_project"
    elif trust_status in {"unknown", "untrusted", "blocked"}:
        trust_domain_id = "trust_untrusted_imports"
    now = utc_now_iso()
    with memory.store.transaction():
        memory.store.connection.execute(
            "UPDATE peer_devices SET trust_status = ?, trust_domain_id = ?, trusted_at = ? WHERE id = ?",
            (trust_status, trust_domain_id, now if trust_status.startswith("trusted_") else None, peer.id),
        )
        _write_federation_audit(memory, event_type="peer.trusted", peer_id=peer.id, target_id=peer.id, target_type="peer_device", actor=actor, reason=reason, metadata={"trust_status": trust_status, "trust_domain_id": trust_domain_id})
    if trust_status in {"trusted_team"}:
        memory.create_review_task(
            memory.namespace,
            task_type="access_review",
            title=f"Review high-trust peer {peer.display_name}",
            description="A peer was granted high-trust federation access.",
            target_id=peer.id,
            target_type="peer_device",
            severity="high",
            recommended_action="Confirm the trust domain and share grants are intentional.",
            metadata={"trust_status": trust_status},
        )
    return get_peer(memory, peer.id)


def revoke_peer(memory, peer_id: str, *, reason: str, actor: str = "user", revoke_shares: bool = True) -> RevocationRecord:
    _require_reason(reason)
    peer = get_peer(memory, peer_id)
    now = utc_now_iso()
    with memory.store.transaction():
        memory.store.connection.execute(
            "UPDATE peer_devices SET trust_status = 'revoked', revoked_at = ? WHERE id = ?",
            (now, peer.id),
        )
        if revoke_shares:
            rows = memory.store.connection.execute(
                "SELECT DISTINCT share_grant_id FROM share_recipients WHERE peer_id = ? AND status != 'revoked'",
                (peer.id,),
            ).fetchall()
            for row in rows:
                _revoke_share_grant(memory, row["share_grant_id"], reason=reason, actor=actor, peer_id=peer.id)
        record = _write_revocation_record(
            memory,
            revocation_type="peer_revocation",
            target_id=peer.id,
            target_type="peer_device",
            peer_id=peer.id,
            reason=reason,
            actor=actor,
            metadata={"remote_erasure_limit": "Revocation prevents future sync but cannot guarantee remote deletion without peer cooperation."},
        )
        _write_federation_audit(memory, event_type="peer.revoked", peer_id=peer.id, target_id=peer.id, target_type="peer_device", actor=actor, reason=reason)
    return record


def list_trust_domains(memory) -> list[TrustDomain]:
    rows = memory.store.connection.execute("SELECT * FROM trust_domains ORDER BY name").fetchall()
    return [TrustDomain.from_row(row) for row in rows]


def get_trust_domain(memory, trust_domain_id_or_name: str) -> TrustDomain:
    row = memory.store.connection.execute(
        "SELECT * FROM trust_domains WHERE id = ? OR name = ?",
        (trust_domain_id_or_name, trust_domain_id_or_name),
    ).fetchone()
    if not row:
        raise NotFoundError(f"Trust domain not found: {trust_domain_id_or_name}")
    return TrustDomain.from_row(row)


def create_share_grant(
    memory,
    *,
    name: str,
    namespace: str,
    recipient_peer_ids: list[str],
    grant_type: str = "read_write_candidate",
    permissions: list[str],
    privacy_ceiling: str = "personal",
    memory_types: list[str] | None = None,
    statuses: list[str] | None = None,
    project_id: str | None = None,
    include_evidence: bool = True,
    include_reflections: bool = True,
    include_inferences: bool = False,
    include_audit: bool = False,
    expires_at: str | None = None,
    reason: str,
    allow_secret: bool = False,
) -> ShareGrant:
    _require_reason(reason)
    _validate_share(namespace=namespace, grant_type=grant_type, permissions=permissions, privacy_ceiling=privacy_ceiling, allow_secret=allow_secret)
    if not recipient_peer_ids:
        raise ValidationError("At least one recipient peer is required.")
    peers = [get_peer(memory, peer_id) for peer_id in recipient_peer_ids]
    revoked = [peer.id for peer in peers if peer.trust_status == "revoked"]
    if revoked:
        raise ValidationError("Cannot create share for revoked peers: " + ", ".join(revoked))
    now = utc_now_iso()
    share_id = new_id("share")
    collection_id = "sync_" + content_hash(share_id)[:24]
    normalized_permissions = _normalize_permissions(permissions)
    with memory.store.transaction():
        memory.store.connection.execute(
            """
            INSERT INTO share_grants (
                id, name, namespace, project_id, grant_type, permissions_json,
                memory_types_json, statuses_json, privacy_ceiling,
                include_evidence, include_reflections, include_inferences,
                include_audit, candidate_write_allowed, active_write_allowed,
                expires_at, status, created_at, revoked_at, reason, metadata_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active', ?, NULL, ?, ?)
            """,
            (
                share_id,
                name,
                namespace,
                project_id,
                grant_type,
                json.dumps(normalized_permissions, sort_keys=True),
                json.dumps(memory_types, sort_keys=True) if memory_types else None,
                json.dumps(statuses, sort_keys=True) if statuses else None,
                privacy_ceiling,
                int(include_evidence),
                int(include_reflections),
                int(include_inferences),
                int(include_audit),
                int("write_candidate" in normalized_permissions or grant_type in {"read_write_candidate", "sync_bidirectional"}),
                int("write_active" in normalized_permissions or grant_type == "read_write_active"),
                expires_at,
                now,
                reason,
                json.dumps({"allow_secret": allow_secret}, sort_keys=True),
            ),
        )
        memory.store.connection.execute(
            """
            INSERT INTO sync_collections (
                id, share_grant_id, namespace, project_id, name, direction,
                transport, status, created_at, updated_at, metadata_json
            )
            VALUES (?, ?, ?, ?, ?, ?, 'file_bundle', 'active', ?, ?, ?)
            """,
            (
                collection_id,
                share_id,
                namespace,
                project_id,
                name,
                "bidirectional" if grant_type == "sync_bidirectional" else "push",
                now,
                now,
                json.dumps({"created_from_share": True}, sort_keys=True),
            ),
        )
        for peer in peers:
            memory.store.connection.execute(
                """
                INSERT INTO share_recipients (
                    id, share_grant_id, peer_id, recipient_public_key, status,
                    created_at, accepted_at, revoked_at, metadata_json
                )
                VALUES (?, ?, ?, ?, 'active', ?, ?, NULL, ?)
                """,
                (
                    "sr_" + content_hash(f"{share_id}\0{peer.id}")[:24],
                    share_id,
                    peer.id,
                    peer.public_key,
                    now,
                    now,
                    json.dumps({"peer_fingerprint": peer.key_fingerprint}, sort_keys=True),
                ),
            )
            _write_consent_record(
                memory,
                namespace=namespace,
                consent_type="share_namespace",
                target_id=share_id,
                target_type="share_grant",
                granted_by="user",
                granted_to_peer_id=peer.id,
                reason=reason,
                expires_at=expires_at,
            )
        _write_federation_audit(memory, event_type="share.created", namespace=namespace, share_grant_id=share_id, target_id=share_id, target_type="share_grant", reason=reason)
    return get_share_grant(memory, share_id)


def get_share_grant(memory, share_id: str) -> ShareGrant:
    row = memory.store.connection.execute("SELECT * FROM share_grants WHERE id = ? OR name = ?", (share_id, share_id)).fetchone()
    if not row:
        raise NotFoundError(f"Share grant not found: {share_id}")
    return ShareGrant.from_row(row)


def list_share_grants(memory, *, namespace: str | None = None, status: str | None = None) -> list[ShareGrant]:
    clauses: list[str] = []
    params: list[Any] = []
    if namespace:
        clauses.append("namespace = ?")
        params.append(namespace)
    if status:
        clauses.append("status = ?")
        params.append(status)
    where = "WHERE " + " AND ".join(clauses) if clauses else ""
    rows = memory.store.connection.execute(f"SELECT * FROM share_grants {where} ORDER BY created_at DESC", params).fetchall()
    return [ShareGrant.from_row(row) for row in rows]


def list_share_recipients(memory, share_grant_id: str) -> list[ShareRecipient]:
    rows = memory.store.connection.execute(
        "SELECT * FROM share_recipients WHERE share_grant_id = ? ORDER BY created_at",
        (share_grant_id,),
    ).fetchall()
    return [ShareRecipient.from_row(row) for row in rows]


def revoke_share_grant(memory, share_id: str, *, reason: str, actor: str = "user") -> RevocationRecord:
    return _revoke_share_grant(memory, share_id, reason=reason, actor=actor)


def _revoke_share_grant(memory, share_id: str, *, reason: str, actor: str, peer_id: str | None = None) -> RevocationRecord:
    _require_reason(reason)
    share = get_share_grant(memory, share_id)
    now = utc_now_iso()
    with memory.store.transaction():
        memory.store.connection.execute("UPDATE share_grants SET status = 'revoked', revoked_at = ? WHERE id = ?", (now, share.id))
        memory.store.connection.execute("UPDATE sync_collections SET status = 'revoked', updated_at = ? WHERE share_grant_id = ?", (now, share.id))
        if peer_id:
            memory.store.connection.execute("UPDATE share_recipients SET status = 'revoked', revoked_at = ? WHERE share_grant_id = ? AND peer_id = ?", (now, share.id, peer_id))
        else:
            memory.store.connection.execute("UPDATE share_recipients SET status = 'revoked', revoked_at = ? WHERE share_grant_id = ?", (now, share.id))
        record = _write_revocation_record(
            memory,
            revocation_type="share_revocation",
            target_id=share.id,
            target_type="share_grant",
            peer_id=peer_id,
            reason=reason,
            actor=actor,
            metadata={"remote_erasure_limit": "Revocation blocks future sync but cannot forcibly erase data already received by peers."},
        )
        _write_federation_audit(memory, event_type="share.revoked", namespace=share.namespace, peer_id=peer_id, share_grant_id=share.id, target_id=share.id, target_type="share_grant", actor=actor, reason=reason)
    return record


def _require_active_share(memory, share: ShareGrant, *, action: str) -> None:
    if share.status != "active":
        raise ValidationError(f"Cannot {action} revoked or inactive share grant.")
    expires_at = parse_iso(share.expires_at) if share.expires_at else None
    if expires_at and expires_at <= utc_now():
        now = utc_now_iso()
        with memory.store.transaction():
            memory.store.connection.execute(
                "UPDATE share_grants SET status = 'expired', revoked_at = ? WHERE id = ? AND status = 'active'",
                (now, share.id),
            )
            memory.store.connection.execute(
                "UPDATE sync_collections SET status = 'paused', updated_at = ? WHERE share_grant_id = ? AND status = 'active'",
                (now, share.id),
            )
        raise ValidationError(f"Cannot {action} expired share grant.")


def get_sync_collection(memory, collection_id_or_share: str) -> SyncCollection:
    row = memory.store.connection.execute(
        "SELECT * FROM sync_collections WHERE id = ? OR share_grant_id = ? OR name = ?",
        (collection_id_or_share, collection_id_or_share, collection_id_or_share),
    ).fetchone()
    if not row:
        raise NotFoundError(f"Sync collection not found: {collection_id_or_share}")
    return SyncCollection.from_row(row)


def list_sync_collections(memory, *, status: str | None = None) -> list[SyncCollection]:
    params: list[Any] = []
    where = ""
    if status:
        where = "WHERE status = ?"
        params.append(status)
    rows = memory.store.connection.execute(f"SELECT * FROM sync_collections {where} ORDER BY created_at DESC", params).fetchall()
    return [SyncCollection.from_row(row) for row in rows]


def export_share_bundle(
    memory,
    *,
    share_id: str,
    output_path: str,
    encrypt: bool = True,
    redacted: bool = False,
    actor: str = "user",
) -> SyncRun:
    share = get_share_grant(memory, share_id)
    _require_active_share(memory, share, action="export")
    if _protected_requires_encryption(memory) and not encrypt:
        raise ValidationError("Protected-mode databases require encrypted sync packages.")
    if not encrypt and share.privacy_ceiling != "public" and not redacted:
        raise ValidationError("Unencrypted sync exports require public or redacted mode.")
    collection = get_sync_collection(memory, share.id)
    recipients = list_share_recipients(memory, share.id)
    if not recipients:
        raise ValidationError("Share has no recipients.")
    identity = active_federation_identity(memory)
    payload = _build_share_payload(memory, identity=identity, share=share, collection=collection, redacted=redacted)
    changeset, items = _record_changeset(memory, identity=identity, collection=collection, target_peer_id=recipients[0].peer_id, encrypted=encrypt, payload=payload)
    payload["changesets"] = [{**asdict(changeset), "items": [asdict(item) for item in items]}]
    manifest = {
        "format": "aletsync",
        "format_version": "1.0",
        "origin_instance_id": identity.instance_id,
        "share_grant_id": share.id,
        "collection_id": collection.id,
        "created_at": utc_now_iso(),
        "encrypted": bool(encrypt),
        "signed": True,
        "item_counts": payload["item_counts"],
        "privacy_ceiling": share.privacy_ceiling,
        "schema_version": SCHEMA_VERSION,
    }
    _write_bundle(
        output_path,
        manifest=manifest,
        payload=payload,
        encrypt=encrypt,
        signer=identity,
        recipients=recipients,
    )
    run = _insert_sync_run(
        memory,
        collection_id=collection.id,
        peer_id=recipients[0].peer_id,
        direction="push",
        transport="file_bundle",
        status="completed",
        sent_count=sum(payload["item_counts"].values()),
        received_count=0,
        applied_count=0,
        conflict_count=0,
        redaction_count=payload["item_counts"].get("tombstones", 0),
        warnings=payload.get("warnings", []),
        metadata={"output_path": output_path, "changeset_id": changeset.id, "encrypted": encrypt},
    )
    _update_cursor(memory, collection.id, recipients[0].peer_id, changeset.id)
    _write_federation_audit(memory, event_type="share.exported", namespace=share.namespace, peer_id=recipients[0].peer_id, share_grant_id=share.id, sync_run_id=run.id, target_id=share.id, target_type="share_grant", actor=actor, metadata={"output_path": output_path, "encrypted": encrypt})
    return run


def import_share_bundle(memory, *, input_path: str, trust_policy: str = "candidate_only", actor: str = "user", dry_run: bool = False) -> SyncRun:
    manifest, payload = _read_bundle(memory, input_path)
    if manifest.get("format") != "aletsync":
        raise ValidationError("Not an Aletheia sync bundle.")
    origin_identity = payload["peer_identity"]
    share_payload = payload["share_grant"]
    collection_payload = payload["collection"]
    local_share_id = share_payload["id"]
    local_collection_id = collection_payload["id"]
    if dry_run:
        return SyncRun(
            id=new_id("sync"),
            collection_id=local_collection_id,
            peer_id="peer_" + content_hash(origin_identity["instance_id"])[:24],
            direction="pull",
            transport="file_bundle",
            status="planned",
            started_at=utc_now_iso(),
            finished_at=None,
            sent_count=0,
            received_count=sum(payload.get("item_counts", {}).values()),
            applied_count=0,
            conflict_count=0,
            redaction_count=payload.get("item_counts", {}).get("tombstones", 0),
            warnings=["dry_run_no_mutation"],
            metadata={"input_path": input_path, "dry_run": True},
        )
    peer = _peer_for_import(memory, origin_identity, trust_policy=trust_policy, reason=f"Imported bundle {Path(input_path).name}")
    _ensure_imported_share_and_collection(memory, share_payload, collection_payload, peer)
    run_id = new_id("sync")
    started_at = utc_now_iso()
    applied = 0
    conflicts = 0
    redactions = 0
    warnings: list[str] = []
    remote_to_local_evidence: dict[str, str] = {}
    with memory.store.transaction():
        memory.store.connection.execute(
            """
            INSERT INTO sync_runs (
                id, collection_id, peer_id, direction, transport, status,
                started_at, finished_at, sent_count, received_count,
                applied_count, conflict_count, redaction_count,
                warnings_json, metadata_json
            )
            VALUES (?, ?, ?, 'pull', 'file_bundle', 'running', ?, NULL, 0, ?, 0, 0, 0, '[]', ?)
            """,
            (
                run_id,
                local_collection_id,
                peer.id,
                started_at,
                sum(payload.get("item_counts", {}).values()),
                json.dumps({"input_path": input_path, "manifest": manifest}, sort_keys=True),
            ),
        )
    policy = _policy_for_import(memory, peer, trust_policy=trust_policy, namespace=share_payload["namespace"])
    for evidence in payload.get("payloads", {}).get("evidence", []):
        local_event = _import_evidence(memory, evidence, peer=peer, share_id=local_share_id, sync_run_id=run_id, trust_domain_id=policy.trust_domain_id)
        remote_to_local_evidence[evidence["id"]] = local_event.id
        applied += 1
    for claim in payload.get("payloads", {}).get("claims", []):
        local_evidence_ids = [remote_to_local_evidence[eid] for eid in claim.get("evidence_ids", []) if eid in remote_to_local_evidence]
        result = _import_claim(memory, claim, peer=peer, share_id=local_share_id, collection_id=local_collection_id, sync_run_id=run_id, policy=policy, evidence_ids=local_evidence_ids)
        applied += int(result["applied"])
        conflicts += int(result["conflict"])
    for tombstone in payload.get("payloads", {}).get("tombstones", []):
        if _apply_remote_tombstone(memory, tombstone, peer=peer, share_id=local_share_id, sync_run_id=run_id):
            applied += 1
            redactions += 1
    status = "completed_with_conflicts" if conflicts else "completed"
    with memory.store.transaction():
        memory.store.connection.execute(
            """
            UPDATE sync_runs
            SET status = ?, finished_at = ?, applied_count = ?,
                conflict_count = ?, redaction_count = ?, warnings_json = ?
            WHERE id = ?
            """,
            (status, utc_now_iso(), applied, conflicts, redactions, json.dumps(warnings, sort_keys=True), run_id),
        )
    _update_cursor(memory, local_collection_id, peer.id, payload.get("changesets", [{}])[-1].get("id"))
    _write_federation_audit(memory, event_type="share.imported", namespace=share_payload["namespace"], peer_id=peer.id, share_grant_id=local_share_id, sync_run_id=run_id, target_id=local_share_id, target_type="share_grant", actor=actor, metadata={"input_path": input_path, "trust_policy": trust_policy, "status": status})
    return get_sync_run(memory, run_id)


def sync(
    memory,
    *,
    collection_id: str,
    peer_id: str | None = None,
    direction: str = "bidirectional",
    transport: str = "file_bundle",
    input_path: str | None = None,
    output_path: str | None = None,
    dry_run: bool = False,
) -> SyncRun:
    collection = get_sync_collection(memory, collection_id)
    share = get_share_grant(memory, collection.share_grant_id)
    _require_active_share(memory, share, action="sync")
    if collection.status != "active":
        raise ValidationError("Cannot sync revoked or inactive collection.")
    peer = get_peer(memory, peer_id) if peer_id else _default_peer_for_share(memory, share.id)
    if peer.trust_status in {"revoked", "blocked"}:
        raise ValidationError("Peer is revoked or blocked.")
    if dry_run:
        count = len(_eligible_claim_rows(memory, share))
        return _insert_sync_run(
            memory,
            collection_id=collection.id,
            peer_id=peer.id,
            direction=direction,
            transport=transport,
            status="planned",
            sent_count=count if direction in {"push", "bidirectional"} else 0,
            received_count=0,
            applied_count=0,
            conflict_count=0,
            redaction_count=0,
            warnings=["dry_run_no_mutation"],
            metadata={"dry_run": True},
        )
    if output_path:
        return export_share_bundle(memory, share_id=share.id, output_path=output_path, encrypt=True)
    if input_path:
        return import_share_bundle(memory, input_path=input_path)
    return _insert_sync_run(
        memory,
        collection_id=collection.id,
        peer_id=peer.id,
        direction=direction,
        transport=transport,
        status="completed",
        sent_count=0,
        received_count=0,
        applied_count=0,
        conflict_count=0,
        redaction_count=0,
        warnings=["no_input_or_output_path_for_file_bundle_sync"],
        metadata={},
    )


def get_sync_run(memory, sync_run_id: str) -> SyncRun:
    row = memory.store.connection.execute("SELECT * FROM sync_runs WHERE id = ?", (sync_run_id,)).fetchone()
    if not row:
        raise NotFoundError(f"Sync run not found: {sync_run_id}")
    return SyncRun.from_row(row)


def list_sync_runs(memory, *, limit: int = 50) -> list[SyncRun]:
    rows = memory.store.connection.execute("SELECT * FROM sync_runs ORDER BY started_at DESC LIMIT ?", (limit,)).fetchall()
    return [SyncRun.from_row(row) for row in rows]


def list_replication_cursors(memory) -> list[ReplicationCursor]:
    rows = memory.store.connection.execute("SELECT * FROM replication_cursors ORDER BY last_synced_at DESC").fetchall()
    return [ReplicationCursor.from_row(row) for row in rows]


def list_remote_sources(memory, *, local_object_id: str | None = None) -> list[RemoteMemorySource]:
    params: list[Any] = []
    where = ""
    if local_object_id:
        where = "WHERE local_object_id = ?"
        params.append(local_object_id)
    rows = memory.store.connection.execute(f"SELECT * FROM remote_memory_sources {where} ORDER BY imported_at DESC", params).fetchall()
    return [RemoteMemorySource.from_row(row) for row in rows]


def list_import_trust_policies(memory) -> list[ImportTrustPolicy]:
    rows = memory.store.connection.execute("SELECT * FROM import_trust_policies ORDER BY name").fetchall()
    return [ImportTrustPolicy.from_row(row) for row in rows]


def list_sync_conflicts(memory, *, status: str | None = None, namespace: str | None = None) -> list[SyncConflict]:
    params: list[Any] = []
    clauses: list[str] = []
    if status:
        clauses.append("status = ?")
        params.append(status)
    if namespace:
        clauses.append("namespace = ?")
        params.append(namespace)
    where = "WHERE " + " AND ".join(clauses) if clauses else ""
    rows = memory.store.connection.execute(f"SELECT * FROM sync_conflicts {where} ORDER BY created_at DESC", params).fetchall()
    return [SyncConflict.from_row(row) for row in rows]


def get_sync_conflict(memory, conflict_id: str) -> SyncConflict:
    row = memory.store.connection.execute("SELECT * FROM sync_conflicts WHERE id = ?", (conflict_id,)).fetchone()
    if not row:
        raise NotFoundError(f"Sync conflict not found: {conflict_id}")
    return SyncConflict.from_row(row)


def resolve_sync_conflict(memory, conflict_id: str, *, strategy: str, reason: str, actor: str = "user") -> SyncConflictResolution:
    _require_reason(reason)
    if strategy not in CONFLICT_RESOLUTION_STRATEGIES:
        raise ValidationError(f"Unknown sync conflict resolution strategy: {strategy}")
    conflict = get_sync_conflict(memory, conflict_id)
    resolution_id = new_id("sres")
    now = utc_now_iso()
    with memory.store.transaction():
        memory.store.connection.execute(
            "UPDATE sync_conflicts SET status = ?, resolved_at = ? WHERE id = ?",
            ("deferred" if strategy == "defer" else "resolved", now, conflict.id),
        )
        memory.store.connection.execute(
            """
            INSERT INTO sync_conflict_resolutions (
                id, sync_conflict_id, strategy, reason, actor, applied_at,
                metadata_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (resolution_id, conflict.id, strategy, reason, actor, now, json.dumps({"remote_object_id": conflict.remote_object_id}, sort_keys=True)),
        )
        _write_federation_audit(memory, event_type="conflict.resolved", namespace=conflict.namespace, sync_run_id=conflict.sync_run_id, target_id=conflict.id, target_type="sync_conflict", actor=actor, reason=reason, metadata={"strategy": strategy})
    row = memory.store.connection.execute("SELECT * FROM sync_conflict_resolutions WHERE id = ?", (resolution_id,)).fetchone()
    return SyncConflictResolution.from_row(row)


def list_sync_conflict_resolutions(memory, conflict_id: str | None = None) -> list[SyncConflictResolution]:
    params: list[Any] = []
    where = ""
    if conflict_id:
        where = "WHERE sync_conflict_id = ?"
        params.append(conflict_id)
    rows = memory.store.connection.execute(f"SELECT * FROM sync_conflict_resolutions {where} ORDER BY applied_at DESC", params).fetchall()
    return [SyncConflictResolution.from_row(row) for row in rows]


def list_revocations(memory) -> list[RevocationRecord]:
    rows = memory.store.connection.execute("SELECT * FROM revocation_records ORDER BY created_at DESC").fetchall()
    return [RevocationRecord.from_row(row) for row in rows]


def propagate_revocations(memory, *, peer_id: str | None = None) -> dict:
    now = utc_now_iso()
    params: list[Any] = []
    where = "WHERE propagated_at IS NULL"
    if peer_id:
        where += " AND (peer_id = ? OR peer_id IS NULL)"
        params.append(peer_id)
    with memory.store.transaction():
        memory.store.connection.execute(f"UPDATE revocation_records SET propagated_at = ? {where}", [now, *params])
    return {"status": "completed", "propagated_at": now, "peer_id": peer_id}


def list_consent_records(memory) -> list[ConsentRecord]:
    rows = memory.store.connection.execute("SELECT * FROM consent_records ORDER BY created_at DESC").fetchall()
    return [ConsentRecord.from_row(row) for row in rows]


def list_federation_audit_events(memory, *, limit: int = 100) -> list[FederationAuditEvent]:
    rows = memory.store.connection.execute("SELECT * FROM federation_audit_events ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
    return [FederationAuditEvent.from_row(row) for row in rows]


def list_sync_tombstones(memory) -> list[SyncTombstone]:
    rows = memory.store.connection.execute("SELECT * FROM sync_tombstones ORDER BY created_at DESC").fetchall()
    return [SyncTombstone.from_row(row) for row in rows]


def create_workspace(memory, *, namespace: str, name: str, description: str | None = None, owner_identity_id: str | None = None, metadata: dict | None = None) -> Workspace:
    identity = get_federation_identity(memory, owner_identity_id) if owner_identity_id else active_federation_identity(memory)
    workspace_id = new_id("ws")
    now = utc_now_iso()
    with memory.store.transaction():
        memory.store.connection.execute(
            """
            INSERT INTO workspaces (
                id, namespace, name, description, owner_identity_id, status,
                created_at, updated_at, metadata_json
            )
            VALUES (?, ?, ?, ?, ?, 'active', ?, ?, ?)
            """,
            (workspace_id, namespace, name, description, identity.id, now, now, json.dumps(metadata or {}, sort_keys=True)),
        )
        add_workspace_member(memory, workspace_id=workspace_id, member_type="local_user", member_id=identity.instance_id, role="owner", metadata={"created_with_workspace": True})
        _write_federation_audit(memory, event_type="workspace.created", namespace=namespace, target_id=workspace_id, target_type="workspace")
    return get_workspace(memory, workspace_id)


def get_workspace(memory, workspace_id: str) -> Workspace:
    row = memory.store.connection.execute("SELECT * FROM workspaces WHERE id = ? OR name = ?", (workspace_id, workspace_id)).fetchone()
    if not row:
        raise NotFoundError(f"Workspace not found: {workspace_id}")
    return Workspace.from_row(row)


def list_workspaces(memory, *, namespace: str | None = None) -> list[Workspace]:
    params: list[Any] = []
    where = ""
    if namespace:
        where = "WHERE namespace = ?"
        params.append(namespace)
    rows = memory.store.connection.execute(f"SELECT * FROM workspaces {where} ORDER BY created_at DESC", params).fetchall()
    return [Workspace.from_row(row) for row in rows]


def add_workspace_member(memory, *, workspace_id: str, member_type: str, member_id: str, role: str, metadata: dict | None = None) -> WorkspaceMember:
    if member_type not in WORKSPACE_MEMBER_TYPES:
        raise ValidationError(f"Unknown workspace member type: {member_type}")
    if role not in WORKSPACE_ROLES:
        raise ValidationError(f"Unknown workspace role: {role}")
    workspace = get_workspace(memory, workspace_id) if not metadata or not metadata.get("created_with_workspace") else None
    member_row_id = "wsm_" + content_hash(f"{workspace_id}\0{member_type}\0{member_id}")[:24]
    now = utc_now_iso()
    with memory.store.transaction():
        memory.store.connection.execute(
            """
            INSERT INTO workspace_members (
                id, workspace_id, member_type, member_id, role, status,
                joined_at, metadata_json
            )
            VALUES (?, ?, ?, ?, ?, 'active', ?, ?)
            ON CONFLICT(workspace_id, member_type, member_id) DO UPDATE SET
                role = excluded.role,
                status = 'active',
                metadata_json = excluded.metadata_json
            """,
            (member_row_id, workspace_id, member_type, member_id, role, now, json.dumps(metadata or {}, sort_keys=True)),
        )
        _write_federation_audit(memory, event_type="workspace.member_added", namespace=workspace.namespace if workspace else None, target_id=workspace_id, target_type="workspace", metadata={"member_type": member_type, "member_id": member_id, "role": role})
    return get_workspace_member(memory, workspace_id, member_type, member_id)


def remove_workspace_member(memory, *, workspace_id: str, member_id: str) -> dict:
    workspace = get_workspace(memory, workspace_id)
    with memory.store.transaction():
        memory.store.connection.execute(
            "UPDATE workspace_members SET status = 'removed' WHERE workspace_id = ? AND member_id = ?",
            (workspace_id, member_id),
        )
        _write_federation_audit(memory, event_type="workspace.member_removed", namespace=workspace.namespace, target_id=workspace_id, target_type="workspace", metadata={"member_id": member_id})
    return {"removed": member_id, "workspace_id": workspace_id}


def get_workspace_member(memory, workspace_id: str, member_type: str, member_id: str) -> WorkspaceMember:
    row = memory.store.connection.execute(
        "SELECT * FROM workspace_members WHERE workspace_id = ? AND member_type = ? AND member_id = ?",
        (workspace_id, member_type, member_id),
    ).fetchone()
    if not row:
        raise NotFoundError(f"Workspace member not found: {member_id}")
    return WorkspaceMember.from_row(row)


def list_workspace_members(memory, workspace_id: str) -> list[WorkspaceMember]:
    rows = memory.store.connection.execute("SELECT * FROM workspace_members WHERE workspace_id = ? ORDER BY joined_at", (workspace_id,)).fetchall()
    return [WorkspaceMember.from_row(row) for row in rows]


def workspace_role_allows(role: str, action: str) -> bool:
    allowed = {
        "owner": {"read", "write", "share", "admin"},
        "admin": {"read", "write", "share", "admin"},
        "curator": {"read", "write", "share"},
        "contributor": {"read", "write"},
        "agent": {"read", "write_candidate"},
        "reader": {"read"},
    }
    return action in allowed.get(role, set())


def create_agent_group(memory, *, namespace: str, name: str, description: str | None = None, default_capabilities: list[str] | None = None, metadata: dict | None = None) -> AgentGroup:
    group_id = new_id("ag")
    now = utc_now_iso()
    caps = default_capabilities or ["memory:read", "memory:context", "memory:write_candidate"]
    with memory.store.transaction():
        memory.store.connection.execute(
            """
            INSERT INTO agent_groups (
                id, namespace, name, description, default_capabilities_json,
                created_at, updated_at, metadata_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (group_id, namespace, name, description, json.dumps(caps, sort_keys=True), now, now, json.dumps(metadata or {}, sort_keys=True)),
        )
        _write_federation_audit(memory, event_type="agent_group.created", namespace=namespace, target_id=group_id, target_type="agent_group")
    return get_agent_group(memory, group_id)


def get_agent_group(memory, group_id: str) -> AgentGroup:
    row = memory.store.connection.execute("SELECT * FROM agent_groups WHERE id = ? OR name = ?", (group_id, group_id)).fetchone()
    if not row:
        raise NotFoundError(f"Agent group not found: {group_id}")
    return AgentGroup.from_row(row)


def list_agent_groups(memory, *, namespace: str | None = None) -> list[AgentGroup]:
    params: list[Any] = []
    where = ""
    if namespace:
        where = "WHERE namespace = ?"
        params.append(namespace)
    rows = memory.store.connection.execute(f"SELECT * FROM agent_groups {where} ORDER BY name", params).fetchall()
    return [AgentGroup.from_row(row) for row in rows]


def add_agent_group_member(memory, *, agent_group_id: str, agent_id: str, role: str = "agent", metadata: dict | None = None) -> AgentGroupMember:
    if role not in AGENT_GROUP_ROLES:
        raise ValidationError(f"Unknown agent group role: {role}")
    group = get_agent_group(memory, agent_group_id)
    member_id = "agm_" + content_hash(f"{agent_group_id}\0{agent_id}")[:24]
    now = utc_now_iso()
    with memory.store.transaction():
        memory.store.connection.execute(
            """
            INSERT INTO agent_group_members (
                id, agent_group_id, agent_id, role, status, joined_at,
                metadata_json
            )
            VALUES (?, ?, ?, ?, 'active', ?, ?)
            ON CONFLICT(agent_group_id, agent_id) DO UPDATE SET
                role = excluded.role,
                status = 'active',
                metadata_json = excluded.metadata_json
            """,
            (member_id, agent_group_id, agent_id, role, now, json.dumps(metadata or {}, sort_keys=True)),
        )
        _write_federation_audit(memory, event_type="agent_group.member_added", namespace=group.namespace, target_id=agent_group_id, target_type="agent_group", metadata={"agent_id": agent_id, "role": role})
    return get_agent_group_member(memory, agent_group_id, agent_id)


def get_agent_group_member(memory, group_id: str, agent_id: str) -> AgentGroupMember:
    row = memory.store.connection.execute("SELECT * FROM agent_group_members WHERE agent_group_id = ? AND agent_id = ?", (group_id, agent_id)).fetchone()
    if not row:
        raise NotFoundError(f"Agent group member not found: {agent_id}")
    return AgentGroupMember.from_row(row)


def list_agent_group_members(memory, group_id: str) -> list[AgentGroupMember]:
    rows = memory.store.connection.execute("SELECT * FROM agent_group_members WHERE agent_group_id = ? ORDER BY joined_at", (group_id,)).fetchall()
    return [AgentGroupMember.from_row(row) for row in rows]


def agent_group_allows(memory, *, agent_group_id: str, capability: str) -> bool:
    group = get_agent_group(memory, agent_group_id)
    return capability in group.default_capabilities or "memory:admin" in group.default_capabilities


def federation_conformance(memory) -> dict:
    tables = {
        "federation_identities",
        "peer_devices",
        "share_grants",
        "sync_collections",
        "sync_runs",
        "sync_conflicts",
        "remote_memory_sources",
        "revocation_records",
        "workspaces",
        "agent_groups",
    }
    existing = {row["name"] for row in memory.store.connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()}
    missing = sorted(tables - existing)
    contracts = {contract.name for contract in memory.list_public_contracts()}
    contract_ok = "Federation protocol v1" in contracts and "Aletheia sync bundle format" in contracts
    no_auto_identity = not list_federation_identities(memory)
    return {
        "status": "passed" if not missing and contract_ok else "failed",
        "missing_tables": missing,
        "contract_registered": contract_ok,
        "no_auto_identity": no_auto_identity,
        "trust_domains": [asdict(domain) for domain in list_trust_domains(memory)],
    }


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _unb64(value: str) -> bytes:
    padded = value + "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(padded.encode("ascii"))


def _b64_json(value: dict) -> str:
    return _b64(json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8"))


def _unb64_json(value: str) -> dict:
    return json.loads(_unb64(value).decode("utf-8"))


def _public_key_doc(public_key: str) -> dict:
    if not public_key.startswith(FEDERATION_PUBLIC_KEY_PREFIX):
        raise ValidationError("Federation identity uses a legacy public key; rotate the identity before secure sync.")
    try:
        doc = _unb64_json(public_key.removeprefix(FEDERATION_PUBLIC_KEY_PREFIX))
        signing = doc["signing"]
        encryption = doc["encryption"]
        if doc.get("version") != 2 or signing.get("algorithm") != SIGNING_ALGORITHM or encryption.get("algorithm") != "x25519":
            raise KeyError
        if len(_unb64(signing["public_key"])) != 32 or len(_unb64(encryption["public_key"])) != 32:
            raise ValueError
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise ValidationError("Federation public key is not valid v2 key material.") from exc
    return doc


def _private_key_doc(identity: FederationIdentity) -> dict:
    ref = str(identity.metadata.get("private_key_ref") or "")
    if ref.startswith(FEDERATION_ENCRYPTED_PRIVATE_KEY_PREFIX):
        try:
            envelope = _unb64_json(ref.removeprefix(FEDERATION_ENCRYPTED_PRIVATE_KEY_PREFIX))
            metadata = envelope["metadata"]
            cipher = _unb64(envelope["ciphertext"])
            plaintext = decrypt_bytes_with_passphrase(
                cipher,
                _federation_private_key_passphrase(),
                metadata,
                associated_data=FEDERATION_PRIVATE_KEY_AAD,
            )
            doc = json.loads(plaintext.decode("utf-8"))
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise ValidationError("Federation private key is not valid encrypted v2 key material.") from exc
        return _validated_private_key_doc(doc)
    if not ref.startswith(FEDERATION_PRIVATE_KEY_PREFIX):
        raise ValidationError("Federation identity uses a legacy private key; rotate the identity before secure sync.")
    try:
        doc = _unb64_json(ref.removeprefix(FEDERATION_PRIVATE_KEY_PREFIX))
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise ValidationError("Federation private key is not valid v2 key material.") from exc
    return _validated_private_key_doc(doc)


def _signing_private_key(identity: FederationIdentity) -> ed25519.Ed25519PrivateKey:
    doc = _private_key_doc(identity)
    return ed25519.Ed25519PrivateKey.from_private_bytes(_unb64(doc["signing"]["private_key"]))


def _signing_public_key(public_key: str) -> ed25519.Ed25519PublicKey:
    doc = _public_key_doc(public_key)
    return ed25519.Ed25519PublicKey.from_public_bytes(_unb64(doc["signing"]["public_key"]))


def _encryption_private_key(identity: FederationIdentity) -> x25519.X25519PrivateKey:
    doc = _private_key_doc(identity)
    return x25519.X25519PrivateKey.from_private_bytes(_unb64(doc["encryption"]["private_key"]))


def _encryption_public_key(public_key: str) -> x25519.X25519PublicKey:
    doc = _public_key_doc(public_key)
    return x25519.X25519PublicKey.from_public_bytes(_unb64(doc["encryption"]["public_key"]))


def _public_identity_payload(identity: FederationIdentity) -> dict:
    return {
        "format": "aletheia-peer-identity",
        "format_version": "1.0",
        "schema_version": SCHEMA_VERSION,
        "instance_id": identity.instance_id,
        "display_name": identity.display_name,
        "public_key": identity.public_key,
        "key_fingerprint": identity.key_fingerprint,
        "key_algorithm": identity.key_algorithm,
        "created_at": identity.created_at,
        "metadata": {"private_key_exported": False, "key_material_version": 2},
    }


def _new_key_material(display_name: str, key_algorithm: str, *, protected: bool = True) -> tuple[str, str, str]:
    signing_private = ed25519.Ed25519PrivateKey.generate()
    encryption_private = x25519.X25519PrivateKey.generate()
    signing_public = signing_private.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    encryption_public = encryption_private.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    public_doc = {
        "version": 2,
        "key_algorithm": key_algorithm,
        "signing": {"algorithm": SIGNING_ALGORITHM, "public_key": _b64(signing_public)},
        "encryption": {"algorithm": "x25519", "public_key": _b64(encryption_public)},
    }
    private_doc = {
        "version": 2,
        "signing": {
            "algorithm": SIGNING_ALGORITHM,
            "private_key": _b64(
                signing_private.private_bytes(
                    encoding=serialization.Encoding.Raw,
                    format=serialization.PrivateFormat.Raw,
                    encryption_algorithm=serialization.NoEncryption(),
                )
            ),
        },
        "encryption": {
            "algorithm": "x25519",
            "private_key": _b64(
                encryption_private.private_bytes(
                    encoding=serialization.Encoding.Raw,
                    format=serialization.PrivateFormat.Raw,
                    encryption_algorithm=serialization.NoEncryption(),
                )
            ),
        },
    }
    public_key = FEDERATION_PUBLIC_KEY_PREFIX + _b64_json(public_doc)
    fingerprint = sha256_hex(public_key)[:32]
    private_ref = _private_key_ref(private_doc, protected=protected)
    return public_key, private_ref, fingerprint


def _private_key_ref(private_doc: dict, *, protected: bool) -> str:
    if not protected:
        return FEDERATION_PRIVATE_KEY_PREFIX + _b64_json(private_doc)
    cipher, metadata = encrypt_bytes_with_passphrase(
        json.dumps(private_doc, sort_keys=True, separators=(",", ":")).encode("utf-8"),
        _federation_private_key_passphrase(),
        key_id=os.environ.get("ALETHEIA_FEDERATION_KEY_ID", "federation-protected-key"),
        associated_data=FEDERATION_PRIVATE_KEY_AAD,
    )
    envelope = {
        "version": 2,
        "ciphertext": _b64(cipher),
        "metadata": metadata,
    }
    return FEDERATION_ENCRYPTED_PRIVATE_KEY_PREFIX + _b64_json(envelope)


def _federation_private_key_passphrase() -> str:
    value = os.environ.get("ALETHEIA_FEDERATION_KEY") or os.environ.get("ALETHEIA_PROTECTED_KEY")
    if not value:
        raise ValidationError(
            "Protected federation key is not configured. Set ALETHEIA_FEDERATION_KEY or "
            "ALETHEIA_PROTECTED_KEY, or create the identity with protected=False."
        )
    return value


def _validated_private_key_doc(doc: dict) -> dict:
    try:
        signing = doc["signing"]
        encryption = doc["encryption"]
        if doc.get("version") != 2 or signing.get("algorithm") != SIGNING_ALGORITHM or encryption.get("algorithm") != "x25519":
            raise KeyError
        if len(_unb64(signing["private_key"])) != 32 or len(_unb64(encryption["private_key"])) != 32:
            raise ValueError
    except (KeyError, TypeError, ValueError) as exc:
        raise ValidationError("Federation private key is not valid v2 key material.") from exc
    return doc


def _validate_peer_identity_payload(payload: dict) -> None:
    required = {"instance_id", "display_name", "public_key", "key_fingerprint", "key_algorithm"}
    missing = sorted(required - set(payload))
    if missing:
        raise ValidationError("Peer identity missing fields: " + ", ".join(missing))
    expected = sha256_hex(payload["public_key"])[:32]
    if payload["key_fingerprint"] != expected:
        raise ValidationError("Peer identity fingerprint does not match public key.")
    _public_key_doc(payload["public_key"])


def _require_reason(reason: str) -> None:
    if not reason or not reason.strip():
        raise ValidationError("A reason is required.")


def _normalize_permissions(permissions: list[str]) -> list[str]:
    aliases = {
        "read": "read_claims",
        "candidate_write": "write_candidate",
        "feedback": "write_feedback",
    }
    normalized = sorted({aliases.get(permission, permission) for permission in permissions})
    unknown = sorted(set(normalized) - SHARE_PERMISSIONS)
    if unknown:
        raise ValidationError("Unknown share permissions: " + ", ".join(unknown))
    return normalized


def _validate_share(*, namespace: str, grant_type: str, permissions: list[str], privacy_ceiling: str, allow_secret: bool) -> None:
    if not namespace:
        raise ValidationError("Share namespace is required.")
    if grant_type not in GRANT_TYPES:
        raise ValidationError(f"Unknown share grant type: {grant_type}")
    _normalize_permissions(permissions)
    if privacy_ceiling not in PRIVACY_ORDER:
        raise ValidationError(f"Unknown privacy ceiling: {privacy_ceiling}")
    if privacy_ceiling == "secret" and not allow_secret:
        raise ValidationError("Secret sharing is blocked by default.")


def _protected_requires_encryption(memory) -> bool:
    try:
        status = memory.protected_mode_status()
        return bool(status.enabled and status.backup_encryption_required)
    except Exception:  # noqa: BLE001 - fallback should be conservative only where possible.
        return False


def _eligible_claim_rows(memory, share: ShareGrant) -> list[Any]:
    params: list[Any] = [share.namespace]
    clauses = ["c.namespace = ?"]
    if share.project_id:
        clauses.append(
            """
            EXISTS (
                SELECT 1 FROM project_claim_links pcl
                WHERE pcl.claim_id = c.id AND pcl.project_id = ?
            )
            """
        )
        params.append(share.project_id)
    if share.memory_types:
        clauses.append(f"c.memory_type IN ({','.join('?' for _ in share.memory_types)})")
        params.extend(share.memory_types)
    if share.statuses:
        clauses.append(f"c.status IN ({','.join('?' for _ in share.statuses)})")
        params.extend(share.statuses)
    else:
        clauses.append("c.status NOT IN ('rejected', 'archived')")
    rows = memory.store.connection.execute(
        f"SELECT c.* FROM claims c WHERE {' AND '.join(clauses)} ORDER BY c.created_at, c.id",
        params,
    ).fetchall()
    return [row for row in rows if _claim_within_privacy(memory, row["id"], share.privacy_ceiling)]


def _claim_within_privacy(memory, claim_id: str, privacy_ceiling: str) -> bool:
    rows = memory.store.connection.execute(
        """
        SELECT ee.privacy_level
        FROM claim_evidence_links cel
        JOIN evidence_events ee ON ee.id = cel.evidence_id
        WHERE cel.claim_id = ?
        """,
        (claim_id,),
    ).fetchall()
    if not rows:
        return PRIVACY_ORDER["personal"] <= PRIVACY_ORDER[privacy_ceiling]
    return all(PRIVACY_ORDER.get(row["privacy_level"], 1) <= PRIVACY_ORDER[privacy_ceiling] for row in rows)


def _build_share_payload(memory, *, identity: FederationIdentity, share: ShareGrant, collection: SyncCollection, redacted: bool) -> dict:
    claims = []
    evidence_by_id: dict[str, dict] = {}
    warnings: list[str] = []
    for row in _eligible_claim_rows(memory, share):
        claim = memory.read_claim(row["id"])
        evidence_ids = list(claim.evidence_ids) if share.include_evidence else []
        claims.append(
            {
                "id": claim.id,
                "namespace": claim.namespace,
                "subject": claim.subject,
                "predicate": claim.predicate,
                "object": claim.object if not redacted else "[REDACTED]",
                "memory_type": claim.memory_type,
                "status": claim.status,
                "confidence_base": claim.confidence_base,
                "importance": claim.importance,
                "half_life_days": claim.half_life_days,
                "evidence_ids": evidence_ids,
                "created_at": claim.created_at,
            }
        )
        for evidence_id in evidence_ids:
            event = memory.read_event(evidence_id)
            if PRIVACY_ORDER.get(event.privacy_level, 1) > PRIVACY_ORDER[share.privacy_ceiling]:
                warnings.append("Some evidence was excluded by privacy ceiling.")
                continue
            evidence_by_id[evidence_id] = {
                "id": event.id,
                "namespace": event.namespace,
                "source_type": event.source_type,
                "source_uri": event.source_uri,
                "content": event.content if not redacted else "[REDACTED]",
                "content_hash": event.content_hash,
                "created_at": event.created_at,
                "observed_at": event.observed_at,
                "trust_level": event.trust_level,
                "privacy_level": event.privacy_level,
            }
    tombstones = _exportable_tombstones(memory, share)
    payloads = {"claims": claims, "evidence": list(evidence_by_id.values()), "tombstones": tombstones}
    return {
        "schema_version": SCHEMA_VERSION,
        "peer_identity": _public_identity_payload(identity),
        "origin_identity": asdict(identity),
        "share_grant": asdict(share),
        "collection": asdict(collection),
        "payloads": payloads,
        "item_counts": {key: len(value) for key, value in payloads.items()},
        "warnings": sorted(set(warnings)),
    }


def _exportable_tombstones(memory, share: ShareGrant) -> list[dict]:
    rows = memory.store.connection.execute(
        "SELECT * FROM deletion_tombstones WHERE namespace = ? ORDER BY created_at",
        (share.namespace,),
    ).fetchall()
    return [
        {
            "id": row["id"],
            "namespace": row["namespace"],
            "object_id": row["target_id"],
            "object_type": row["target_type"],
            "tombstone_type": row["deletion_mode"],
            "reason": row["reason"],
            "created_at": row["created_at"],
        }
        for row in rows
    ]


def _record_changeset(memory, *, identity: FederationIdentity, collection: SyncCollection, target_peer_id: str, encrypted: bool, payload: dict) -> tuple[SyncChangeSet, list[SyncChangeItem]]:
    next_seq = memory.store.connection.execute(
        "SELECT COALESCE(MAX(sequence_number), 0) + 1 AS seq FROM sync_changesets WHERE collection_id = ?",
        (collection.id,),
    ).fetchone()["seq"]
    changeset_id = new_id("chg")
    created_at = utc_now_iso()
    flat_items: list[dict] = []
    for object_type, values in payload["payloads"].items():
        singular = {"claims": "claim", "evidence": "evidence_event", "tombstones": "tombstone"}[object_type]
        operation = "tombstone" if object_type == "tombstones" else "create"
        for value in values:
            flat_items.append({"object_type": singular, "operation": operation, "payload": value})
    signing_payload = json.dumps(payload["payloads"], sort_keys=True, separators=(",", ":")).encode("utf-8")
    payload_hash = sha256_hex(signing_payload)
    signature = _b64(_signing_private_key(identity).sign(signing_payload))
    with memory.store.transaction():
        memory.store.connection.execute(
            """
            INSERT INTO sync_changesets (
                id, collection_id, origin_instance_id, target_peer_id,
                sequence_number, signed, signature, encrypted, created_at,
                item_count, metadata_json
            )
            VALUES (?, ?, ?, ?, ?, 1, ?, ?, ?, ?, ?)
            """,
            (
                changeset_id,
                collection.id,
                identity.instance_id,
                target_peer_id,
                next_seq,
                signature,
                int(encrypted),
                created_at,
                len(flat_items),
                json.dumps(
                    {
                        "payload_hash": payload_hash,
                        "signature_algorithm": SIGNING_ALGORITHM,
                        "signer_key_fingerprint": identity.key_fingerprint,
                    },
                    sort_keys=True,
                ),
            ),
        )
        for item in flat_items:
            value = item["payload"]
            memory.store.connection.execute(
                """
                INSERT INTO sync_change_items (
                    id, changeset_id, object_id, object_type, operation,
                    object_hash, previous_hash, payload_ref, privacy_level,
                    created_at, metadata_json
                )
                VALUES (?, ?, ?, ?, ?, ?, NULL, ?, ?, ?, ?)
                """,
                (
                    new_id("chi"),
                    changeset_id,
                    value.get("id") or value.get("object_id"),
                    item["object_type"],
                    item["operation"],
                    content_hash(json.dumps(value, sort_keys=True)),
                    f"payloads/{item['object_type']}/{value.get('id') or value.get('object_id')}",
                    value.get("privacy_level", "personal"),
                    created_at,
                    json.dumps({"origin_instance_id": identity.instance_id}, sort_keys=True),
                ),
            )
    return get_sync_changeset(memory, changeset_id), list_sync_change_items(memory, changeset_id)


def get_sync_changeset(memory, changeset_id: str) -> SyncChangeSet:
    row = memory.store.connection.execute("SELECT * FROM sync_changesets WHERE id = ?", (changeset_id,)).fetchone()
    if not row:
        raise NotFoundError(f"Sync changeset not found: {changeset_id}")
    return SyncChangeSet.from_row(row)


def list_sync_change_items(memory, changeset_id: str) -> list[SyncChangeItem]:
    rows = memory.store.connection.execute("SELECT * FROM sync_change_items WHERE changeset_id = ? ORDER BY created_at", (changeset_id,)).fetchall()
    return [SyncChangeItem.from_row(row) for row in rows]


def _write_bundle(
    output_path: str,
    *,
    manifest: dict,
    payload: dict,
    encrypt: bool,
    signer: FederationIdentity,
    recipients: list[ShareRecipient],
) -> None:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload_bytes = json.dumps(payload, sort_keys=True).encode("utf-8")
    manifest = {
        **manifest,
        "crypto_version": BUNDLE_CRYPTO_VERSION,
        "signature_algorithm": SIGNING_ALGORITHM,
        "encryption_algorithm": ENCRYPTION_ALGORITHM if encrypt else "none",
    }
    files: dict[str, bytes] = {
        "manifest.json": (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode("utf-8"),
        "origin_identity.json": (json.dumps(_public_identity_payload(signer), indent=2, sort_keys=True) + "\n").encode("utf-8"),
    }
    if encrypt:
        encrypted, metadata = _encrypt_payload(payload_bytes, manifest, recipients)
        files["encrypted_payload.bin"] = encrypted
        files["encryption_metadata.json"] = (json.dumps(metadata, indent=2, sort_keys=True) + "\n").encode("utf-8")
    else:
        files["peer_identity.json"] = (json.dumps(payload["peer_identity"], indent=2, sort_keys=True) + "\n").encode("utf-8")
        files["share_grant.json"] = (json.dumps(payload["share_grant"], indent=2, sort_keys=True) + "\n").encode("utf-8")
        files["payloads/payload.json"] = payload_bytes
    checksums: dict[str, str] = {
        name: sha256_hex(value)
        for name, value in sorted(files.items())
    }
    signature = _signing_private_key(signer).sign(_bundle_signing_payload(manifest, checksums))
    signature_doc = {
        "algorithm": SIGNING_ALGORITHM,
        "key_fingerprint": signer.key_fingerprint,
        "origin_instance_id": signer.instance_id,
        "signature": _b64(signature),
    }
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, value in sorted(files.items()):
            archive.writestr(name, value)
        archive.writestr("checksums.sha256", _checksums_body(checksums))
        archive.writestr("signature.json", json.dumps(signature_doc, indent=2, sort_keys=True) + "\n")


def _read_bundle(memory, input_path: str) -> tuple[dict, dict]:
    with zipfile.ZipFile(input_path, "r") as archive:
        manifest = json.loads(archive.read("manifest.json").decode("utf-8"))
        if manifest.get("crypto_version") != BUNDLE_CRYPTO_VERSION:
            raise ValidationError("Legacy unsigned sync bundles are not accepted.")
        origin_identity = json.loads(archive.read("origin_identity.json").decode("utf-8"))
        _verify_bundle_checksums(archive)
        _verify_bundle_signature(archive, manifest=manifest, origin_identity=origin_identity)
        if manifest.get("encrypted"):
            metadata = json.loads(archive.read("encryption_metadata.json").decode("utf-8"))
            payload = json.loads(_decrypt_payload(memory, archive.read("encrypted_payload.bin"), manifest, metadata).decode("utf-8"))
        else:
            payload = json.loads(archive.read("payloads/payload.json").decode("utf-8"))
    if payload.get("peer_identity", {}).get("instance_id") != origin_identity.get("instance_id"):
        raise ValidationError("Sync bundle origin identity does not match signed identity.")
    if payload.get("peer_identity", {}).get("key_fingerprint") != origin_identity.get("key_fingerprint"):
        raise ValidationError("Sync bundle origin key does not match signed identity.")
    return manifest, payload


def _encrypt_payload(payload: bytes, manifest: dict, recipients: list[ShareRecipient]) -> tuple[bytes, dict]:
    if not recipients:
        raise ValidationError("Encrypted sync bundles require at least one recipient.")
    content_key = generate_aes_key()
    nonce = random_bytes(12)
    aad = _bundle_encryption_aad(manifest)
    cipher = aes_gcm_encrypt(content_key, nonce, payload, aad)
    ephemeral_private = x25519.X25519PrivateKey.generate()
    ephemeral_public = ephemeral_private.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    wrapped_recipients = []
    for recipient in recipients:
        recipient_public = _encryption_public_key(recipient.recipient_public_key)
        salt = random_bytes(16)
        wrap_nonce = random_bytes(12)
        wrap_key = _derive_recipient_wrap_key(ephemeral_private.exchange(recipient_public), salt)
        wrapped_key = aes_gcm_encrypt(wrap_key, wrap_nonce, content_key, recipient.peer_id.encode("utf-8"))
        wrapped_recipients.append(
            {
                "peer_id": recipient.peer_id,
                "key_fingerprint": sha256_hex(recipient.recipient_public_key)[:32],
                "salt": _b64(salt),
                "wrap_nonce": _b64(wrap_nonce),
                "wrapped_key": _b64(wrapped_key),
            }
        )
    return cipher, {
        "algorithm": ENCRYPTION_ALGORITHM,
        "nonce": _b64(nonce),
        "ephemeral_public_key": _b64(ephemeral_public),
        "recipients": wrapped_recipients,
    }


def _decrypt_payload(memory, cipher: bytes, manifest: dict, metadata: dict) -> bytes:
    if metadata.get("algorithm") != ENCRYPTION_ALGORITHM:
        raise ValidationError("Unsupported sync bundle encryption algorithm.")
    identity = active_federation_identity(memory)
    identity_private = _encryption_private_key(identity)
    ephemeral_public = x25519.X25519PublicKey.from_public_bytes(_unb64(metadata["ephemeral_public_key"]))
    shared = identity_private.exchange(ephemeral_public)
    aad = _bundle_encryption_aad(manifest)
    for recipient in metadata.get("recipients", []):
        if recipient.get("key_fingerprint") != identity.key_fingerprint:
            continue
        wrap_key = _derive_recipient_wrap_key(shared, _unb64(recipient["salt"]))
        try:
            content_key = aes_gcm_decrypt(
                wrap_key,
                _unb64(recipient["wrap_nonce"]),
                _unb64(recipient["wrapped_key"]),
                recipient["peer_id"].encode("utf-8"),
            )
            return aes_gcm_decrypt(content_key, _unb64(metadata["nonce"]), cipher, aad)
        except Exception as exc:  # noqa: BLE001 - normalize crypto failures at bundle boundary.
            raise ValidationError("Encrypted sync bundle authentication failed.") from exc
    raise ValidationError("Encrypted sync bundle is not addressed to the active local identity.")


def _derive_recipient_wrap_key(shared_secret: bytes, salt: bytes) -> bytes:
    return HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        info=b"aletheia-sync-bundle-key-wrap-v2",
    ).derive(shared_secret)


def _bundle_encryption_aad(manifest: dict) -> bytes:
    return json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _bundle_signing_payload(manifest: dict, checksums: dict[str, str]) -> bytes:
    return json.dumps(
        {"manifest": manifest, "checksums": checksums},
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _checksums_body(checksums: dict[str, str]) -> str:
    return "\n".join(f"{digest}  {name}" for name, digest in sorted(checksums.items())) + "\n"


def _read_checksums(body: str) -> dict[str, str]:
    checksums: dict[str, str] = {}
    for line in body.splitlines():
        if not line.strip():
            continue
        digest, name = line.split("  ", 1)
        checksums[name] = digest
    return checksums


def _verify_bundle_checksums(archive: zipfile.ZipFile) -> dict[str, str]:
    expected = _read_checksums(archive.read("checksums.sha256").decode("utf-8"))
    for name, digest in expected.items():
        actual = sha256_hex(archive.read(name))
        if not constant_time_equal(actual, digest):
            raise ValidationError(f"Sync bundle checksum mismatch: {name}")
    return expected


def _verify_bundle_signature(archive: zipfile.ZipFile, *, manifest: dict, origin_identity: dict) -> None:
    signature_doc = json.loads(archive.read("signature.json").decode("utf-8"))
    if signature_doc.get("algorithm") != SIGNING_ALGORITHM:
        raise ValidationError("Unsupported sync bundle signature algorithm.")
    if signature_doc.get("key_fingerprint") != origin_identity.get("key_fingerprint"):
        raise ValidationError("Sync bundle signature key does not match origin identity.")
    expected_fingerprint = sha256_hex(origin_identity["public_key"])[:32]
    if expected_fingerprint != origin_identity.get("key_fingerprint"):
        raise ValidationError("Sync bundle origin identity fingerprint is invalid.")
    checksums = _read_checksums(archive.read("checksums.sha256").decode("utf-8"))
    try:
        _signing_public_key(origin_identity["public_key"]).verify(
            _unb64(signature_doc["signature"]),
            _bundle_signing_payload(manifest, checksums),
        )
    except (InvalidSignature, KeyError, ValueError) as exc:
        raise ValidationError("Sync bundle signature verification failed.") from exc


def _peer_for_import(memory, identity_payload: dict, *, trust_policy: str, reason: str) -> PeerDevice:
    try:
        peer = get_peer(memory, identity_payload["instance_id"])
    except NotFoundError:
        if trust_policy == "trusted_device":
            raise ValidationError("Trusted-device imports require a previously added and trusted peer.")
        peer = add_peer(memory, peer_identity=identity_payload, trust_status="unknown", reason=reason)
    if trust_policy == "trusted_device" and peer.trust_status != "trusted_device":
        raise ValidationError("Trusted-device imports require a previously trusted peer.")
    return peer


def _ensure_imported_share_and_collection(memory, share_payload: dict, collection_payload: dict, peer: PeerDevice) -> None:
    now = utc_now_iso()
    with memory.store.transaction():
        memory.store.connection.execute(
            """
            INSERT OR IGNORE INTO share_grants (
                id, name, namespace, project_id, grant_type, permissions_json,
                memory_types_json, statuses_json, privacy_ceiling,
                include_evidence, include_reflections, include_inferences,
                include_audit, candidate_write_allowed, active_write_allowed,
                expires_at, status, created_at, revoked_at, reason, metadata_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                share_payload["id"],
                share_payload["name"],
                share_payload["namespace"],
                share_payload.get("project_id"),
                share_payload["grant_type"],
                json.dumps(share_payload["permissions"], sort_keys=True),
                json.dumps(share_payload.get("memory_types"), sort_keys=True) if share_payload.get("memory_types") else None,
                json.dumps(share_payload.get("statuses"), sort_keys=True) if share_payload.get("statuses") else None,
                share_payload["privacy_ceiling"],
                int(share_payload.get("include_evidence", True)),
                int(share_payload.get("include_reflections", True)),
                int(share_payload.get("include_inferences", False)),
                int(share_payload.get("include_audit", False)),
                int(share_payload.get("candidate_write_allowed", True)),
                int(share_payload.get("active_write_allowed", False)),
                share_payload.get("expires_at"),
                share_payload.get("status", "active"),
                share_payload.get("created_at", now),
                share_payload.get("revoked_at"),
                share_payload.get("reason", "Imported share grant."),
                json.dumps({"imported": True, "origin_share": share_payload["id"]}, sort_keys=True),
            ),
        )
        memory.store.connection.execute(
            """
            INSERT OR IGNORE INTO share_recipients (
                id, share_grant_id, peer_id, recipient_public_key, status,
                created_at, accepted_at, revoked_at, metadata_json
            )
            VALUES (?, ?, ?, ?, 'active', ?, ?, NULL, ?)
            """,
            (
                "sr_" + content_hash(f"{share_payload['id']}\0{peer.id}")[:24],
                share_payload["id"],
                peer.id,
                peer.public_key,
                now,
                now,
                json.dumps({"imported": True}, sort_keys=True),
            ),
        )
        memory.store.connection.execute(
            """
            INSERT OR IGNORE INTO sync_collections (
                id, share_grant_id, namespace, project_id, name, direction,
                transport, status, created_at, updated_at, metadata_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                collection_payload["id"],
                collection_payload["share_grant_id"],
                collection_payload["namespace"],
                collection_payload.get("project_id"),
                collection_payload["name"],
                collection_payload["direction"],
                collection_payload["transport"],
                collection_payload["status"],
                collection_payload.get("created_at", now),
                now,
                json.dumps({"imported": True}, sort_keys=True),
            ),
        )


def _policy_for_import(memory, peer: PeerDevice, *, trust_policy: str, namespace: str) -> ImportTrustPolicy:
    if trust_policy == "trusted_device":
        policy_id = "itp_trusted_device"
    elif peer.trust_domain_id == "trust_personal_trusted_devices":
        policy_id = "itp_trusted_device"
    elif peer.trust_domain_id == "trust_team_shared_project":
        policy_id = "itp_team_shared_project"
    else:
        policy_id = "itp_candidate_only"
    row = memory.store.connection.execute("SELECT * FROM import_trust_policies WHERE id = ?", (policy_id,)).fetchone()
    if not row:
        raise NotFoundError(f"Import trust policy not found: {policy_id}")
    return ImportTrustPolicy.from_row(row)


def _import_evidence(memory, evidence: dict, *, peer: PeerDevice, share_id: str, sync_run_id: str, trust_domain_id: str | None):
    event = memory.write_event(
        namespace=evidence["namespace"],
        source_type="remote_sync:" + evidence.get("source_type", "unknown"),
        source_uri=evidence.get("source_uri"),
        content=evidence.get("content", ""),
        trust_level="remote:" + peer.trust_status,
        privacy_level=evidence.get("privacy_level", "personal"),
    )
    _write_remote_source(
        memory,
        local_object_id=event.id,
        local_object_type="evidence_event",
        remote_object_id=evidence["id"],
        remote_object_type="evidence_event",
        origin_instance_id=peer.peer_instance_id,
        peer_id=peer.id,
        share_grant_id=share_id,
        sync_run_id=sync_run_id,
        trust_domain_id=trust_domain_id,
        metadata={"remote_content_hash": evidence.get("content_hash")},
    )
    return event


def _import_claim(memory, claim: dict, *, peer: PeerDevice, share_id: str, collection_id: str, sync_run_id: str, policy: ImportTrustPolicy, evidence_ids: list[str]) -> dict:
    conflict = _local_claim_conflict(memory, claim)
    if conflict:
        conflict_id = _create_sync_conflict(
            memory,
            namespace=claim["namespace"],
            collection_id=collection_id,
            sync_run_id=sync_run_id,
            conflict_type="claim_value_conflict",
            local_object_id=conflict["id"],
            local_object_type="claim",
            remote_object_id=claim["id"],
            remote_object_type="claim",
            origin_instance_id=peer.peer_instance_id,
            metadata={"local_object": conflict["object"], "remote_object": claim["object"], "remote_claim": claim},
        )
        _create_conflict_review_task(memory, namespace=claim["namespace"], conflict_id=conflict_id)
        local_id = _store_remote_candidate(memory, claim, evidence_ids=evidence_ids, peer=peer, sync_run_id=sync_run_id)
        _write_remote_source(memory, local_object_id=local_id, local_object_type="candidate_claim", remote_object_id=claim["id"], remote_object_type="claim", origin_instance_id=peer.peer_instance_id, peer_id=peer.id, share_grant_id=share_id, sync_run_id=sync_run_id, trust_domain_id=policy.trust_domain_id, metadata={"conflict_id": conflict_id})
        return {"applied": 1, "conflict": 1}
    if _claim_imports_active(claim, policy, peer):
        status = "active" if claim.get("status") == "core" else claim.get("status", "active")
        if status == "core":
            status = "active"
        active = memory.write_claim(
            namespace=claim["namespace"],
            subject=claim["subject"],
            predicate=claim["predicate"],
            object=claim["object"],
            memory_type=claim["memory_type"],
            evidence_ids=evidence_ids or [memory.write_event(namespace=claim["namespace"], source_type="remote_sync", content=_claim_text(claim), trust_level="remote:" + peer.trust_status).id],
            confidence=claim.get("confidence_base", 0.65),
            status=status,
            half_life_days=claim.get("half_life_days"),
            importance=claim.get("importance", 0.5),
        )
        _write_remote_source(memory, local_object_id=active.id, local_object_type="claim", remote_object_id=claim["id"], remote_object_type="claim", origin_instance_id=peer.peer_instance_id, peer_id=peer.id, share_grant_id=share_id, sync_run_id=sync_run_id, trust_domain_id=policy.trust_domain_id, metadata={"import_mode": policy.import_mode})
    else:
        local_id = _store_remote_candidate(memory, claim, evidence_ids=evidence_ids, peer=peer, sync_run_id=sync_run_id)
        _write_remote_source(memory, local_object_id=local_id, local_object_type="candidate_claim", remote_object_id=claim["id"], remote_object_type="claim", origin_instance_id=peer.peer_instance_id, peer_id=peer.id, share_grant_id=share_id, sync_run_id=sync_run_id, trust_domain_id=policy.trust_domain_id, metadata={"import_mode": policy.import_mode})
        memory.create_review_task(
            claim["namespace"],
            task_type="candidate_review",
            title="Review remote candidate memory",
            description=f"Remote peer {peer.display_name} suggested a memory.",
            target_id=local_id,
            target_type="candidate_claim",
            severity="medium",
            recommended_action="Review before promotion.",
            metadata={"peer_id": peer.id, "remote_claim_id": claim["id"], "sync_run_id": sync_run_id},
        )
    return {"applied": 1, "conflict": 0}


def _claim_imports_active(claim: dict, policy: ImportTrustPolicy, peer: PeerDevice) -> bool:
    if not policy.allow_active_claims:
        return False
    if peer.trust_status not in {"trusted_device", "trusted_user", "trusted_team"}:
        return False
    if claim.get("status") == "core":
        return policy.import_mode in {"active_if_trusted", "active_for_project_state"}
    if policy.import_mode == "active_for_project_state":
        return claim.get("memory_type") in {"project", "decision", "procedure"}
    return policy.import_mode == "active_if_trusted"


def _store_remote_candidate(memory, claim: dict, *, evidence_ids: list[str], peer: PeerDevice, sync_run_id: str) -> str:
    namespace = claim["namespace"]
    if not evidence_ids:
        evidence_ids = [
            memory.write_event(
                namespace=namespace,
                source_type="remote_sync",
                content=_claim_text(claim),
                trust_level="remote:" + peer.trust_status,
                privacy_level="personal",
            ).id
        ]
    run_id = new_id("run")
    candidate_id = new_id("cand")
    now = utc_now_iso()
    evidence_text = _claim_text(claim)
    with memory.store.transaction():
        memory.store.connection.execute(
            """
            INSERT INTO extraction_runs (
                id, namespace, batch_id, extractor_name, extractor_version,
                policy_json, candidate_count, stored_candidate_count,
                dry_run, created_at, warnings_json
            )
            VALUES (?, ?, NULL, 'remote_sync_candidate_writer', '1.3.0', ?, 1, 1, 0, ?, '[]')
            """,
            (run_id, namespace, json.dumps({"sync_run_id": sync_run_id, "peer_id": peer.id}, sort_keys=True), now),
        )
        span_links: list[tuple[str, str]] = []
        for evidence_id in evidence_ids:
            span_id = new_id("span")
            memory.store.connection.execute("INSERT INTO extraction_run_evidence_links (extraction_run_id, evidence_id) VALUES (?, ?)", (run_id, evidence_id))
            memory.store.connection.execute(
                """
                INSERT INTO evidence_spans (
                    id, namespace, evidence_id, start_char, end_char,
                    span_text, role, created_at
                )
                VALUES (?, ?, ?, 0, ?, ?, 'supporting', ?)
                """,
                (span_id, namespace, evidence_id, len(evidence_text), evidence_text, now),
            )
            span_links.append((evidence_id, span_id))
        memory.store.connection.execute(
            """
            INSERT INTO candidate_claims (
                id, namespace, extraction_run_id, subject, predicate, object,
                memory_type, candidate_status, suggested_confidence,
                suggested_importance, suggested_half_life_days,
                suggested_scope_json, contradiction_risk, duplicate_risk,
                privacy_level, created_at, metadata_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, 'pending_review', ?, ?, ?, NULL, 0.0, 0.0, 'personal', ?, ?)
            """,
            (
                candidate_id,
                namespace,
                run_id,
                claim["subject"],
                claim["predicate"],
                claim["object"],
                claim["memory_type"],
                float(claim.get("confidence_base", 0.65)),
                float(claim.get("importance", 0.5)),
                claim.get("half_life_days"),
                now,
                json.dumps({"remote_candidate": True, "peer_id": peer.id, "sync_run_id": sync_run_id}, sort_keys=True),
            ),
        )
        for evidence_id, span_id in span_links:
            memory.store.connection.execute(
                """
                INSERT INTO candidate_evidence_links (
                    candidate_id, evidence_id, evidence_span_id, role
                )
                VALUES (?, ?, ?, 'supporting')
                """,
                (candidate_id, evidence_id, span_id),
            )
        memory._write_audit(namespace=namespace, target_type="candidate_claim", target_id=candidate_id, action="remote_sync.remember_candidate", details={"peer_id": peer.id, "remote_claim_id": claim["id"]})
    return candidate_id


def _local_claim_conflict(memory, claim: dict) -> dict | None:
    row = memory.store.connection.execute(
        """
        SELECT id, object, status
        FROM claims
        WHERE namespace = ?
          AND subject = ?
          AND predicate = ?
          AND status NOT IN ('rejected', 'archived', 'superseded')
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (claim["namespace"], claim["subject"], claim["predicate"]),
    ).fetchone()
    if row and row["object"] != claim["object"]:
        return dict(row)
    return None


def _create_sync_conflict(memory, **kwargs) -> str:
    conflict_id = new_id("sconf")
    with memory.store.transaction():
        memory.store.connection.execute(
            """
            INSERT INTO sync_conflicts (
                id, namespace, collection_id, sync_run_id, conflict_type,
                local_object_id, local_object_type, remote_object_id,
                remote_object_type, origin_instance_id, status, severity,
                created_at, resolved_at, metadata_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'unresolved', ?, ?, NULL, ?)
            """,
            (
                conflict_id,
                kwargs["namespace"],
                kwargs["collection_id"],
                kwargs["sync_run_id"],
                kwargs["conflict_type"],
                kwargs.get("local_object_id"),
                kwargs.get("local_object_type"),
                kwargs.get("remote_object_id"),
                kwargs.get("remote_object_type"),
                kwargs["origin_instance_id"],
                kwargs.get("severity", "high"),
                utc_now_iso(),
                json.dumps(kwargs.get("metadata") or {}, sort_keys=True),
            ),
        )
        _write_federation_audit(memory, event_type="conflict.detected", namespace=kwargs["namespace"], sync_run_id=kwargs["sync_run_id"], target_id=conflict_id, target_type="sync_conflict", metadata={"conflict_type": kwargs["conflict_type"]})
    return conflict_id


def _create_conflict_review_task(memory, *, namespace: str, conflict_id: str) -> None:
    memory.create_review_task(
        namespace,
        task_type="conflict_resolution",
        title="Resolve remote sync conflict",
        description="A remote sync change conflicts with local memory and was not applied silently.",
        target_id=conflict_id,
        target_type="sync_conflict",
        priority=0.8,
        severity="high",
        recommended_action="Resolve with keep_local, accept_remote_as_candidate, or another approved strategy.",
        metadata={"source": "federation"},
    )


def _apply_remote_tombstone(memory, tombstone: dict, *, peer: PeerDevice, share_id: str, sync_run_id: str) -> bool:
    local_sources = memory.store.connection.execute(
        "SELECT * FROM remote_memory_sources WHERE remote_object_id = ? AND peer_id = ?",
        (tombstone["object_id"], peer.id),
    ).fetchall()
    now = utc_now_iso()
    with memory.store.transaction():
        memory.store.connection.execute(
            """
            INSERT OR IGNORE INTO sync_tombstones (
                id, namespace, origin_instance_id, object_id, object_type,
                tombstone_type, reason, created_at, metadata_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "stomb_" + content_hash(f"{peer.peer_instance_id}\0{tombstone['object_id']}\0{tombstone['tombstone_type']}")[:24],
                tombstone["namespace"],
                peer.peer_instance_id,
                tombstone["object_id"],
                tombstone["object_type"],
                tombstone["tombstone_type"],
                tombstone["reason"],
                now,
                json.dumps({"peer_id": peer.id, "sync_run_id": sync_run_id, "share_grant_id": share_id}, sort_keys=True),
            ),
        )
        for source in local_sources:
            if source["local_object_type"] == "evidence_event":
                memory.store.connection.execute(
                    "UPDATE evidence_events SET content = '[REDACTED]', content_hash = ? WHERE id = ?",
                    (content_hash("[REDACTED]"), source["local_object_id"]),
                )
            elif source["local_object_type"] == "claim":
                memory.store.connection.execute("UPDATE claims SET status = 'archived' WHERE id = ?", (source["local_object_id"],))
                memory.store.connection.execute("DELETE FROM claims_fts WHERE claim_id = ?", (source["local_object_id"],))
            elif source["local_object_type"] == "candidate_claim":
                memory.store.connection.execute(
                    "UPDATE candidate_claims SET candidate_status = 'rejected' WHERE id = ?",
                    (source["local_object_id"],),
                )
                linked = memory.store.connection.execute(
                    "SELECT evidence_id FROM candidate_evidence_links WHERE candidate_id = ?",
                    (source["local_object_id"],),
                ).fetchall()
                for row in linked:
                    memory.store.connection.execute(
                        "UPDATE evidence_events SET content = '[REDACTED]', content_hash = ? WHERE id = ?",
                        (content_hash("[REDACTED]"), row["evidence_id"]),
                    )
        _write_federation_audit(memory, event_type="redaction.propagated", namespace=tombstone["namespace"], peer_id=peer.id, share_grant_id=share_id, sync_run_id=sync_run_id, target_id=tombstone["object_id"], target_type=tombstone["object_type"], reason=tombstone["reason"])
    return True


def _write_remote_source(memory, **kwargs) -> None:
    memory.store.connection.execute(
        """
        INSERT OR IGNORE INTO remote_memory_sources (
            id, local_object_id, local_object_type, remote_object_id,
            remote_object_type, origin_instance_id, peer_id, share_grant_id,
            sync_run_id, trust_domain_id, imported_at, metadata_json
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "rms_" + content_hash(f"{kwargs['local_object_id']}\0{kwargs['remote_object_id']}\0{kwargs['peer_id']}")[:24],
            kwargs["local_object_id"],
            kwargs["local_object_type"],
            kwargs["remote_object_id"],
            kwargs["remote_object_type"],
            kwargs["origin_instance_id"],
            kwargs["peer_id"],
            kwargs["share_grant_id"],
            kwargs["sync_run_id"],
            kwargs.get("trust_domain_id"),
            utc_now_iso(),
            json.dumps(kwargs.get("metadata") or {}, sort_keys=True),
        ),
    )


def _insert_sync_run(memory, *, collection_id: str, peer_id: str | None, direction: str, transport: str, status: str, sent_count: int, received_count: int, applied_count: int, conflict_count: int, redaction_count: int, warnings: list[str], metadata: dict) -> SyncRun:
    run_id = new_id("sync")
    now = utc_now_iso()
    with memory.store.transaction():
        memory.store.connection.execute(
            """
            INSERT INTO sync_runs (
                id, collection_id, peer_id, direction, transport, status,
                started_at, finished_at, sent_count, received_count,
                applied_count, conflict_count, redaction_count,
                warnings_json, metadata_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                collection_id,
                peer_id,
                direction,
                transport,
                status,
                now,
                now if status != "running" else None,
                sent_count,
                received_count,
                applied_count,
                conflict_count,
                redaction_count,
                json.dumps(warnings, sort_keys=True),
                json.dumps(metadata, sort_keys=True),
            ),
        )
    return get_sync_run(memory, run_id)


def _update_cursor(memory, collection_id: str, peer_id: str, last_change_id: str | None) -> None:
    if not last_change_id:
        return
    now = utc_now_iso()
    with memory.store.transaction():
        memory.store.connection.execute(
            """
            INSERT INTO replication_cursors (
                id, collection_id, peer_id, last_change_id, last_synced_at,
                status, metadata_json
            )
            VALUES (?, ?, ?, ?, ?, 'active', '{}')
            ON CONFLICT(collection_id, peer_id) DO UPDATE SET
                last_change_id = excluded.last_change_id,
                last_synced_at = excluded.last_synced_at,
                status = 'active'
            """,
            ("rcur_" + content_hash(f"{collection_id}\0{peer_id}")[:24], collection_id, peer_id, last_change_id, now),
        )


def _default_peer_for_share(memory, share_id: str) -> PeerDevice:
    row = memory.store.connection.execute(
        "SELECT peer_id FROM share_recipients WHERE share_grant_id = ? AND status != 'revoked' ORDER BY created_at LIMIT 1",
        (share_id,),
    ).fetchone()
    if not row:
        raise NotFoundError("Share has no active peer recipients.")
    return get_peer(memory, row["peer_id"])


def _last_sync_time(memory) -> str | None:
    row = memory.store.connection.execute("SELECT finished_at FROM sync_runs WHERE finished_at IS NOT NULL ORDER BY finished_at DESC LIMIT 1").fetchone()
    return row["finished_at"] if row else None


def _claim_text(claim: dict) -> str:
    return f"{claim['subject']} {claim['predicate']} {claim['object']}"


def _write_federation_audit(
    memory,
    *,
    event_type: str,
    namespace: str | None = None,
    peer_id: str | None = None,
    share_grant_id: str | None = None,
    sync_run_id: str | None = None,
    target_id: str | None = None,
    target_type: str | None = None,
    actor: str | None = None,
    reason: str | None = None,
    metadata: dict | None = None,
) -> FederationAuditEvent:
    event_id = new_id("faud")
    with memory.store.transaction():
        memory.store.connection.execute(
            """
            INSERT INTO federation_audit_events (
                id, event_type, namespace, peer_id, share_grant_id,
                sync_run_id, target_id, target_type, actor, reason,
                created_at, metadata_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event_id,
                event_type,
                namespace,
                peer_id,
                share_grant_id,
                sync_run_id,
                target_id,
                target_type,
                actor,
                reason,
                utc_now_iso(),
                json.dumps(metadata or {}, sort_keys=True),
            ),
        )
        if target_id and target_type:
            memory._write_audit(
                namespace=namespace or memory.namespace,
                target_type=target_type,
                target_id=target_id,
                action="federation." + event_type,
                details={"peer_id": peer_id, "share_grant_id": share_grant_id, "sync_run_id": sync_run_id, "reason": reason},
            )
    row = memory.store.connection.execute("SELECT * FROM federation_audit_events WHERE id = ?", (event_id,)).fetchone()
    return FederationAuditEvent.from_row(row)


def _write_consent_record(memory, *, namespace: str, consent_type: str, target_id: str, target_type: str, granted_by: str, granted_to_peer_id: str | None, reason: str, expires_at: str | None) -> ConsentRecord:
    record_id = new_id("cons")
    with memory.store.transaction():
        memory.store.connection.execute(
            """
            INSERT INTO consent_records (
                id, namespace, consent_type, target_id, target_type,
                granted_by, granted_to_peer_id, reason, created_at,
                expires_at, revoked_at, metadata_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, '{}')
            """,
            (record_id, namespace, consent_type, target_id, target_type, granted_by, granted_to_peer_id, reason, utc_now_iso(), expires_at),
        )
    row = memory.store.connection.execute("SELECT * FROM consent_records WHERE id = ?", (record_id,)).fetchone()
    return ConsentRecord.from_row(row)


def _write_revocation_record(memory, *, revocation_type: str, target_id: str, target_type: str, peer_id: str | None, reason: str, actor: str, metadata: dict | None = None) -> RevocationRecord:
    record_id = new_id("revoc")
    memory.store.connection.execute(
        """
        INSERT INTO revocation_records (
            id, revocation_type, target_id, target_type, peer_id, reason,
            actor, created_at, propagated_at, metadata_json
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL, ?)
        """,
        (
            record_id,
            revocation_type,
            target_id,
            target_type,
            peer_id,
            reason,
            actor,
            utc_now_iso(),
            json.dumps(metadata or {}, sort_keys=True),
        ),
    )
    row = memory.store.connection.execute("SELECT * FROM revocation_records WHERE id = ?", (record_id,)).fetchone()
    return RevocationRecord.from_row(row)
