"""M10 federation, sharing, sync, and multi-agent governance models."""

from __future__ import annotations

import json
from dataclasses import dataclass, field


def _json(value: str | None, default):
    if value is None:
        return default
    return json.loads(value)


@dataclass(frozen=True)
class FederationIdentity:
    id: str
    instance_id: str
    display_name: str
    public_key: str
    key_fingerprint: str
    key_algorithm: str
    status: str
    created_at: str
    rotated_at: str | None
    metadata: dict = field(default_factory=dict)

    @classmethod
    def from_row(cls, row) -> "FederationIdentity":
        return cls(
            id=row["id"],
            instance_id=row["instance_id"],
            display_name=row["display_name"],
            public_key=row["public_key"],
            key_fingerprint=row["key_fingerprint"],
            key_algorithm=row["key_algorithm"],
            status=row["status"],
            created_at=row["created_at"],
            rotated_at=row["rotated_at"],
            metadata=_json(row["metadata_json"], {}),
        )


@dataclass(frozen=True)
class PeerDevice:
    id: str
    peer_instance_id: str
    display_name: str
    public_key: str
    key_fingerprint: str
    trust_status: str
    trust_domain_id: str | None
    added_at: str
    trusted_at: str | None
    revoked_at: str | None
    metadata: dict = field(default_factory=dict)

    @classmethod
    def from_row(cls, row) -> "PeerDevice":
        return cls(
            id=row["id"],
            peer_instance_id=row["peer_instance_id"],
            display_name=row["display_name"],
            public_key=row["public_key"],
            key_fingerprint=row["key_fingerprint"],
            trust_status=row["trust_status"],
            trust_domain_id=row["trust_domain_id"],
            added_at=row["added_at"],
            trusted_at=row["trusted_at"],
            revoked_at=row["revoked_at"],
            metadata=_json(row["metadata_json"], {}),
        )


@dataclass(frozen=True)
class TrustDomain:
    id: str
    name: str
    description: str | None
    default_import_policy: str
    allowed_memory_types: list[str]
    max_privacy_level: str
    allow_active_import: bool
    allow_candidate_import: bool
    allow_feedback_import: bool
    allow_remote_redaction: bool
    created_at: str
    updated_at: str
    metadata: dict = field(default_factory=dict)

    @classmethod
    def from_row(cls, row) -> "TrustDomain":
        return cls(
            id=row["id"],
            name=row["name"],
            description=row["description"],
            default_import_policy=row["default_import_policy"],
            allowed_memory_types=_json(row["allowed_memory_types_json"], []),
            max_privacy_level=row["max_privacy_level"],
            allow_active_import=bool(row["allow_active_import"]),
            allow_candidate_import=bool(row["allow_candidate_import"]),
            allow_feedback_import=bool(row["allow_feedback_import"]),
            allow_remote_redaction=bool(row["allow_remote_redaction"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            metadata=_json(row["metadata_json"], {}),
        )


@dataclass(frozen=True)
class ShareGrant:
    id: str
    name: str
    namespace: str
    project_id: str | None
    grant_type: str
    permissions: list[str]
    memory_types: list[str] | None
    statuses: list[str] | None
    privacy_ceiling: str
    include_evidence: bool
    include_reflections: bool
    include_inferences: bool
    include_audit: bool
    candidate_write_allowed: bool
    active_write_allowed: bool
    expires_at: str | None
    status: str
    created_at: str
    revoked_at: str | None
    reason: str
    metadata: dict = field(default_factory=dict)

    @classmethod
    def from_row(cls, row) -> "ShareGrant":
        return cls(
            id=row["id"],
            name=row["name"],
            namespace=row["namespace"],
            project_id=row["project_id"],
            grant_type=row["grant_type"],
            permissions=_json(row["permissions_json"], []),
            memory_types=_json(row["memory_types_json"], None),
            statuses=_json(row["statuses_json"], None),
            privacy_ceiling=row["privacy_ceiling"],
            include_evidence=bool(row["include_evidence"]),
            include_reflections=bool(row["include_reflections"]),
            include_inferences=bool(row["include_inferences"]),
            include_audit=bool(row["include_audit"]),
            candidate_write_allowed=bool(row["candidate_write_allowed"]),
            active_write_allowed=bool(row["active_write_allowed"]),
            expires_at=row["expires_at"],
            status=row["status"],
            created_at=row["created_at"],
            revoked_at=row["revoked_at"],
            reason=row["reason"],
            metadata=_json(row["metadata_json"], {}),
        )


@dataclass(frozen=True)
class ShareRecipient:
    id: str
    share_grant_id: str
    peer_id: str
    recipient_public_key: str
    status: str
    created_at: str
    accepted_at: str | None
    revoked_at: str | None
    metadata: dict = field(default_factory=dict)

    @classmethod
    def from_row(cls, row) -> "ShareRecipient":
        return cls(
            id=row["id"],
            share_grant_id=row["share_grant_id"],
            peer_id=row["peer_id"],
            recipient_public_key=row["recipient_public_key"],
            status=row["status"],
            created_at=row["created_at"],
            accepted_at=row["accepted_at"],
            revoked_at=row["revoked_at"],
            metadata=_json(row["metadata_json"], {}),
        )


@dataclass(frozen=True)
class SyncCollection:
    id: str
    share_grant_id: str
    namespace: str
    project_id: str | None
    name: str
    direction: str
    transport: str
    status: str
    created_at: str
    updated_at: str
    metadata: dict = field(default_factory=dict)

    @classmethod
    def from_row(cls, row) -> "SyncCollection":
        return cls(
            id=row["id"],
            share_grant_id=row["share_grant_id"],
            namespace=row["namespace"],
            project_id=row["project_id"],
            name=row["name"],
            direction=row["direction"],
            transport=row["transport"],
            status=row["status"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            metadata=_json(row["metadata_json"], {}),
        )


@dataclass(frozen=True)
class SyncChangeSet:
    id: str
    collection_id: str
    origin_instance_id: str
    target_peer_id: str | None
    sequence_number: int
    signed: bool
    signature: str | None
    encrypted: bool
    created_at: str
    item_count: int
    metadata: dict = field(default_factory=dict)

    @classmethod
    def from_row(cls, row) -> "SyncChangeSet":
        return cls(
            id=row["id"],
            collection_id=row["collection_id"],
            origin_instance_id=row["origin_instance_id"],
            target_peer_id=row["target_peer_id"],
            sequence_number=row["sequence_number"],
            signed=bool(row["signed"]),
            signature=row["signature"],
            encrypted=bool(row["encrypted"]),
            created_at=row["created_at"],
            item_count=row["item_count"],
            metadata=_json(row["metadata_json"], {}),
        )


@dataclass(frozen=True)
class SyncChangeItem:
    id: str
    changeset_id: str
    object_id: str
    object_type: str
    operation: str
    object_hash: str
    previous_hash: str | None
    payload_ref: str | None
    privacy_level: str
    created_at: str
    metadata: dict = field(default_factory=dict)

    @classmethod
    def from_row(cls, row) -> "SyncChangeItem":
        return cls(
            id=row["id"],
            changeset_id=row["changeset_id"],
            object_id=row["object_id"],
            object_type=row["object_type"],
            operation=row["operation"],
            object_hash=row["object_hash"],
            previous_hash=row["previous_hash"],
            payload_ref=row["payload_ref"],
            privacy_level=row["privacy_level"],
            created_at=row["created_at"],
            metadata=_json(row["metadata_json"], {}),
        )


@dataclass(frozen=True)
class SyncRun:
    id: str
    collection_id: str
    peer_id: str | None
    direction: str
    transport: str
    status: str
    started_at: str
    finished_at: str | None
    sent_count: int
    received_count: int
    applied_count: int
    conflict_count: int
    redaction_count: int
    warnings: list[str]
    metadata: dict = field(default_factory=dict)

    @classmethod
    def from_row(cls, row) -> "SyncRun":
        return cls(
            id=row["id"],
            collection_id=row["collection_id"],
            peer_id=row["peer_id"],
            direction=row["direction"],
            transport=row["transport"],
            status=row["status"],
            started_at=row["started_at"],
            finished_at=row["finished_at"],
            sent_count=row["sent_count"],
            received_count=row["received_count"],
            applied_count=row["applied_count"],
            conflict_count=row["conflict_count"],
            redaction_count=row["redaction_count"],
            warnings=_json(row["warnings_json"], []),
            metadata=_json(row["metadata_json"], {}),
        )


@dataclass(frozen=True)
class ReplicationCursor:
    id: str
    collection_id: str
    peer_id: str
    last_change_id: str | None
    last_synced_at: str | None
    status: str
    metadata: dict = field(default_factory=dict)

    @classmethod
    def from_row(cls, row) -> "ReplicationCursor":
        return cls(
            id=row["id"],
            collection_id=row["collection_id"],
            peer_id=row["peer_id"],
            last_change_id=row["last_change_id"],
            last_synced_at=row["last_synced_at"],
            status=row["status"],
            metadata=_json(row["metadata_json"], {}),
        )


@dataclass(frozen=True)
class RemoteMemorySource:
    id: str
    local_object_id: str
    local_object_type: str
    remote_object_id: str
    remote_object_type: str
    origin_instance_id: str
    peer_id: str
    share_grant_id: str
    sync_run_id: str
    trust_domain_id: str | None
    imported_at: str
    metadata: dict = field(default_factory=dict)

    @classmethod
    def from_row(cls, row) -> "RemoteMemorySource":
        return cls(
            id=row["id"],
            local_object_id=row["local_object_id"],
            local_object_type=row["local_object_type"],
            remote_object_id=row["remote_object_id"],
            remote_object_type=row["remote_object_type"],
            origin_instance_id=row["origin_instance_id"],
            peer_id=row["peer_id"],
            share_grant_id=row["share_grant_id"],
            sync_run_id=row["sync_run_id"],
            trust_domain_id=row["trust_domain_id"],
            imported_at=row["imported_at"],
            metadata=_json(row["metadata_json"], {}),
        )


@dataclass(frozen=True)
class ImportTrustPolicy:
    id: str
    name: str
    trust_domain_id: str | None
    peer_id: str | None
    namespace: str | None
    import_mode: str
    allow_active_claims: bool
    allow_candidates: bool
    allow_evidence: bool
    allow_reflections: bool
    allow_inferences: bool
    require_review_for_conflicts: bool
    created_at: str
    updated_at: str
    metadata: dict = field(default_factory=dict)

    @classmethod
    def from_row(cls, row) -> "ImportTrustPolicy":
        return cls(
            id=row["id"],
            name=row["name"],
            trust_domain_id=row["trust_domain_id"],
            peer_id=row["peer_id"],
            namespace=row["namespace"],
            import_mode=row["import_mode"],
            allow_active_claims=bool(row["allow_active_claims"]),
            allow_candidates=bool(row["allow_candidates"]),
            allow_evidence=bool(row["allow_evidence"]),
            allow_reflections=bool(row["allow_reflections"]),
            allow_inferences=bool(row["allow_inferences"]),
            require_review_for_conflicts=bool(row["require_review_for_conflicts"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            metadata=_json(row["metadata_json"], {}),
        )


@dataclass(frozen=True)
class SyncConflict:
    id: str
    namespace: str
    collection_id: str
    sync_run_id: str
    conflict_type: str
    local_object_id: str | None
    local_object_type: str | None
    remote_object_id: str | None
    remote_object_type: str | None
    origin_instance_id: str
    status: str
    severity: str
    created_at: str
    resolved_at: str | None
    metadata: dict = field(default_factory=dict)

    @classmethod
    def from_row(cls, row) -> "SyncConflict":
        return cls(
            id=row["id"],
            namespace=row["namespace"],
            collection_id=row["collection_id"],
            sync_run_id=row["sync_run_id"],
            conflict_type=row["conflict_type"],
            local_object_id=row["local_object_id"],
            local_object_type=row["local_object_type"],
            remote_object_id=row["remote_object_id"],
            remote_object_type=row["remote_object_type"],
            origin_instance_id=row["origin_instance_id"],
            status=row["status"],
            severity=row["severity"],
            created_at=row["created_at"],
            resolved_at=row["resolved_at"],
            metadata=_json(row["metadata_json"], {}),
        )


@dataclass(frozen=True)
class SyncConflictResolution:
    id: str
    sync_conflict_id: str
    strategy: str
    reason: str
    actor: str
    applied_at: str
    metadata: dict = field(default_factory=dict)

    @classmethod
    def from_row(cls, row) -> "SyncConflictResolution":
        return cls(
            id=row["id"],
            sync_conflict_id=row["sync_conflict_id"],
            strategy=row["strategy"],
            reason=row["reason"],
            actor=row["actor"],
            applied_at=row["applied_at"],
            metadata=_json(row["metadata_json"], {}),
        )


@dataclass(frozen=True)
class FederationAuditEvent:
    id: str
    event_type: str
    namespace: str | None
    peer_id: str | None
    share_grant_id: str | None
    sync_run_id: str | None
    target_id: str | None
    target_type: str | None
    actor: str | None
    reason: str | None
    created_at: str
    metadata: dict = field(default_factory=dict)

    @classmethod
    def from_row(cls, row) -> "FederationAuditEvent":
        return cls(
            id=row["id"],
            event_type=row["event_type"],
            namespace=row["namespace"],
            peer_id=row["peer_id"],
            share_grant_id=row["share_grant_id"],
            sync_run_id=row["sync_run_id"],
            target_id=row["target_id"],
            target_type=row["target_type"],
            actor=row["actor"],
            reason=row["reason"],
            created_at=row["created_at"],
            metadata=_json(row["metadata_json"], {}),
        )


@dataclass(frozen=True)
class ConsentRecord:
    id: str
    namespace: str
    consent_type: str
    target_id: str
    target_type: str
    granted_by: str
    granted_to_peer_id: str | None
    reason: str
    created_at: str
    expires_at: str | None
    revoked_at: str | None
    metadata: dict = field(default_factory=dict)

    @classmethod
    def from_row(cls, row) -> "ConsentRecord":
        return cls(
            id=row["id"],
            namespace=row["namespace"],
            consent_type=row["consent_type"],
            target_id=row["target_id"],
            target_type=row["target_type"],
            granted_by=row["granted_by"],
            granted_to_peer_id=row["granted_to_peer_id"],
            reason=row["reason"],
            created_at=row["created_at"],
            expires_at=row["expires_at"],
            revoked_at=row["revoked_at"],
            metadata=_json(row["metadata_json"], {}),
        )


@dataclass(frozen=True)
class RevocationRecord:
    id: str
    revocation_type: str
    target_id: str
    target_type: str
    peer_id: str | None
    reason: str
    actor: str
    created_at: str
    propagated_at: str | None
    metadata: dict = field(default_factory=dict)

    @classmethod
    def from_row(cls, row) -> "RevocationRecord":
        return cls(
            id=row["id"],
            revocation_type=row["revocation_type"],
            target_id=row["target_id"],
            target_type=row["target_type"],
            peer_id=row["peer_id"],
            reason=row["reason"],
            actor=row["actor"],
            created_at=row["created_at"],
            propagated_at=row["propagated_at"],
            metadata=_json(row["metadata_json"], {}),
        )


@dataclass(frozen=True)
class SyncTombstone:
    id: str
    namespace: str
    origin_instance_id: str
    object_id: str
    object_type: str
    tombstone_type: str
    reason: str
    created_at: str
    metadata: dict = field(default_factory=dict)

    @classmethod
    def from_row(cls, row) -> "SyncTombstone":
        return cls(
            id=row["id"],
            namespace=row["namespace"],
            origin_instance_id=row["origin_instance_id"],
            object_id=row["object_id"],
            object_type=row["object_type"],
            tombstone_type=row["tombstone_type"],
            reason=row["reason"],
            created_at=row["created_at"],
            metadata=_json(row["metadata_json"], {}),
        )


@dataclass(frozen=True)
class Workspace:
    id: str
    namespace: str
    name: str
    description: str | None
    owner_identity_id: str
    status: str
    created_at: str
    updated_at: str
    metadata: dict = field(default_factory=dict)

    @classmethod
    def from_row(cls, row) -> "Workspace":
        return cls(
            id=row["id"],
            namespace=row["namespace"],
            name=row["name"],
            description=row["description"],
            owner_identity_id=row["owner_identity_id"],
            status=row["status"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            metadata=_json(row["metadata_json"], {}),
        )


@dataclass(frozen=True)
class WorkspaceMember:
    id: str
    workspace_id: str
    member_type: str
    member_id: str
    role: str
    status: str
    joined_at: str
    metadata: dict = field(default_factory=dict)

    @classmethod
    def from_row(cls, row) -> "WorkspaceMember":
        return cls(
            id=row["id"],
            workspace_id=row["workspace_id"],
            member_type=row["member_type"],
            member_id=row["member_id"],
            role=row["role"],
            status=row["status"],
            joined_at=row["joined_at"],
            metadata=_json(row["metadata_json"], {}),
        )


@dataclass(frozen=True)
class AgentGroup:
    id: str
    namespace: str
    name: str
    description: str | None
    default_capabilities: list[str]
    created_at: str
    updated_at: str
    metadata: dict = field(default_factory=dict)

    @classmethod
    def from_row(cls, row) -> "AgentGroup":
        return cls(
            id=row["id"],
            namespace=row["namespace"],
            name=row["name"],
            description=row["description"],
            default_capabilities=_json(row["default_capabilities_json"], []),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            metadata=_json(row["metadata_json"], {}),
        )


@dataclass(frozen=True)
class AgentGroupMember:
    id: str
    agent_group_id: str
    agent_id: str
    role: str
    status: str
    joined_at: str
    metadata: dict = field(default_factory=dict)

    @classmethod
    def from_row(cls, row) -> "AgentGroupMember":
        return cls(
            id=row["id"],
            agent_group_id=row["agent_group_id"],
            agent_id=row["agent_id"],
            role=row["role"],
            status=row["status"],
            joined_at=row["joined_at"],
            metadata=_json(row["metadata_json"], {}),
        )
