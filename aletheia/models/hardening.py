"""M8 production hardening, protection, backup, and release models."""

from __future__ import annotations

import json
from dataclasses import dataclass, field


def _json(value: str | None, default):
    if value is None:
        return default
    return json.loads(value)


@dataclass(frozen=True)
class BackupManifest:
    id: str
    namespace: str | None
    backup_type: str
    format_version: str
    schema_version: str
    archive_path: str
    encrypted: bool
    encryption_key_id: str | None
    privacy_mode: str
    includes_auth_metadata: bool
    includes_raw_content: bool
    item_counts: dict = field(default_factory=dict)
    checksums: dict = field(default_factory=dict)
    created_by: str | None = None
    created_at: str = ""
    metadata: dict = field(default_factory=dict)

    @classmethod
    def from_row(cls, row) -> "BackupManifest":
        return cls(
            id=row["id"],
            namespace=row["namespace"],
            backup_type=row["backup_type"],
            format_version=row["format_version"],
            schema_version=row["schema_version"],
            archive_path=row["archive_path"],
            encrypted=bool(row["encrypted"]),
            encryption_key_id=row["encryption_key_id"],
            privacy_mode=row["privacy_mode"],
            includes_auth_metadata=bool(row["includes_auth_metadata"]),
            includes_raw_content=bool(row["includes_raw_content"]),
            item_counts=_json(row["item_counts_json"], {}),
            checksums=_json(row["checksums_json"], {}),
            created_by=row["created_by"],
            created_at=row["created_at"],
            metadata=_json(row["metadata_json"], {}),
        )


@dataclass(frozen=True)
class BackupVerificationRun:
    id: str
    backup_id: str | None
    backup_path: str
    status: str
    deep: bool
    finding_count: int
    started_at: str
    finished_at: str | None
    warnings: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    @classmethod
    def from_row(cls, row) -> "BackupVerificationRun":
        return cls(
            id=row["id"],
            backup_id=row["backup_id"],
            backup_path=row["backup_path"],
            status=row["status"],
            deep=bool(row["deep"]),
            finding_count=row["finding_count"],
            started_at=row["started_at"],
            finished_at=row["finished_at"],
            warnings=_json(row["warnings_json"], []),
            metadata=_json(row["metadata_json"], {}),
        )


@dataclass(frozen=True)
class RestoreRun:
    id: str
    backup_manifest_id: str | None
    backup_path: str
    target_db_path: str
    mode: str
    dry_run: bool
    verified_before_restore: bool
    restored_item_counts: dict
    status: str
    started_at: str
    finished_at: str | None
    warnings: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    @classmethod
    def from_row(cls, row) -> "RestoreRun":
        return cls(
            id=row["id"],
            backup_manifest_id=row["backup_manifest_id"],
            backup_path=row["backup_path"],
            target_db_path=row["target_db_path"],
            mode=row["mode"],
            dry_run=bool(row["dry_run"]),
            verified_before_restore=bool(row["verified_before_restore"]),
            restored_item_counts=_json(row["restored_item_counts_json"], {}),
            status=row["status"],
            started_at=row["started_at"],
            finished_at=row["finished_at"],
            warnings=_json(row["warnings_json"], []),
            metadata=_json(row["metadata_json"], {}),
        )


@dataclass(frozen=True)
class EncryptionKeyRecord:
    id: str
    provider: str
    label: str
    status: str
    algorithm: str | None
    kdf: str | None
    key_version: int
    created_at: str
    rotated_at: str | None
    metadata: dict = field(default_factory=dict)

    @classmethod
    def from_row(cls, row) -> "EncryptionKeyRecord":
        return cls(
            id=row["id"],
            provider=row["provider"],
            label=row["label"],
            status=row["status"],
            algorithm=row["algorithm"],
            kdf=row["kdf"],
            key_version=row["key_version"],
            created_at=row["created_at"],
            rotated_at=row["rotated_at"],
            metadata=_json(row["metadata_json"], {}),
        )


@dataclass(frozen=True)
class KeyRotationEvent:
    id: str
    old_key_id: str
    new_key_id: str
    target: str
    dry_run: bool
    affected_count: int
    status: str
    created_at: str
    metadata: dict = field(default_factory=dict)

    @classmethod
    def from_row(cls, row) -> "KeyRotationEvent":
        return cls(
            id=row["id"],
            old_key_id=row["old_key_id"],
            new_key_id=row["new_key_id"],
            target=row["target"],
            dry_run=bool(row["dry_run"]),
            affected_count=row["affected_count"],
            status=row["status"],
            created_at=row["created_at"],
            metadata=_json(row["metadata_json"], {}),
        )


@dataclass(frozen=True)
class ProtectedModeConfig:
    id: str
    enabled: bool
    content_encryption_enabled: bool
    backup_encryption_required: bool
    indexing_policy: str
    request_logging_policy: str
    created_at: str
    updated_at: str
    metadata: dict = field(default_factory=dict)

    @classmethod
    def from_row(cls, row) -> "ProtectedModeConfig":
        return cls(
            id=row["id"],
            enabled=bool(row["enabled"]),
            content_encryption_enabled=bool(row["content_encryption_enabled"]),
            backup_encryption_required=bool(row["backup_encryption_required"]),
            indexing_policy=row["indexing_policy"],
            request_logging_policy=row["request_logging_policy"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            metadata=_json(row["metadata_json"], {}),
        )


@dataclass(frozen=True)
class RedactionEvent:
    id: str
    namespace: str
    target_id: str
    target_type: str
    replacement_text: str | None
    reason: str
    actor: str
    dry_run: bool
    affected_counts: dict
    created_at: str
    metadata: dict = field(default_factory=dict)

    @classmethod
    def from_row(cls, row) -> "RedactionEvent":
        return cls(
            id=row["id"],
            namespace=row["namespace"],
            target_id=row["target_id"],
            target_type=row["target_type"],
            replacement_text=row["replacement_text"],
            reason=row["reason"],
            actor=row["actor"],
            dry_run=bool(row["dry_run"]),
            affected_counts=_json(row["affected_counts_json"], {}),
            created_at=row["created_at"],
            metadata=_json(row["metadata_json"], {}),
        )


@dataclass(frozen=True)
class DeletionTombstone:
    id: str
    namespace: str
    target_id: str
    target_type: str
    deletion_mode: str
    reason: str
    deleted_by: str
    affected_derived_count: int
    backup_warning: str | None
    created_at: str
    metadata: dict = field(default_factory=dict)

    @classmethod
    def from_row(cls, row) -> "DeletionTombstone":
        return cls(
            id=row["id"],
            namespace=row["namespace"],
            target_id=row["target_id"],
            target_type=row["target_type"],
            deletion_mode=row["deletion_mode"],
            reason=row["reason"],
            deleted_by=row["deleted_by"],
            affected_derived_count=row["affected_derived_count"],
            backup_warning=row["backup_warning"],
            created_at=row["created_at"],
            metadata=_json(row["metadata_json"], {}),
        )


@dataclass(frozen=True)
class RetentionPolicy:
    id: str
    namespace: str | None
    memory_type: str | None
    privacy_level: str | None
    source_type: str | None
    action: str
    after_days: int
    enabled: bool
    reason: str
    created_at: str
    updated_at: str
    metadata: dict = field(default_factory=dict)

    @classmethod
    def from_row(cls, row) -> "RetentionPolicy":
        return cls(
            id=row["id"],
            namespace=row["namespace"],
            memory_type=row["memory_type"],
            privacy_level=row["privacy_level"],
            source_type=row["source_type"],
            action=row["action"],
            after_days=row["after_days"],
            enabled=bool(row["enabled"]),
            reason=row["reason"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            metadata=_json(row["metadata_json"], {}),
        )


@dataclass(frozen=True)
class SimpleRun:
    id: str
    status: str
    started_at: str
    finished_at: str | None
    metadata: dict = field(default_factory=dict)


@dataclass(frozen=True)
class IntegrityCheckRun:
    id: str
    namespace: str | None
    scope: str
    status: str
    finding_count: int
    critical_count: int
    started_at: str
    finished_at: str | None
    metadata: dict = field(default_factory=dict)

    @classmethod
    def from_row(cls, row) -> "IntegrityCheckRun":
        return cls(
            id=row["id"],
            namespace=row["namespace"],
            scope=row["scope"],
            status=row["status"],
            finding_count=row["finding_count"],
            critical_count=row["critical_count"],
            started_at=row["started_at"],
            finished_at=row["finished_at"],
            metadata=_json(row["metadata_json"], {}),
        )


@dataclass(frozen=True)
class IntegrityFinding:
    id: str
    run_id: str
    severity: str
    finding_type: str
    target_id: str | None
    target_type: str | None
    message: str
    repairable: bool
    recommended_action: str | None
    created_at: str
    metadata: dict = field(default_factory=dict)

    @classmethod
    def from_row(cls, row) -> "IntegrityFinding":
        return cls(
            id=row["id"],
            run_id=row["run_id"],
            severity=row["severity"],
            finding_type=row["finding_type"],
            target_id=row["target_id"],
            target_type=row["target_type"],
            message=row["message"],
            repairable=bool(row["repairable"]),
            recommended_action=row["recommended_action"],
            created_at=row["created_at"],
            metadata=_json(row["metadata_json"], {}),
        )


@dataclass(frozen=True)
class MigrationPlan:
    id: str
    from_version: str
    to_version: str
    steps: list[dict]
    irreversible: bool
    backup_required: bool
    warnings: list[str]
    created_at: str
    metadata: dict = field(default_factory=dict)

    @classmethod
    def from_row(cls, row) -> "MigrationPlan":
        return cls(
            id=row["id"],
            from_version=row["from_version"],
            to_version=row["to_version"],
            steps=_json(row["steps_json"], []),
            irreversible=bool(row["irreversible"]),
            backup_required=bool(row["backup_required"]),
            warnings=_json(row["warnings_json"], []),
            created_at=row["created_at"],
            metadata=_json(row["metadata_json"], {}),
        )


@dataclass(frozen=True)
class ExportManifest:
    id: str
    namespace: str | None
    export_type: str
    format: str
    file_path: str
    encrypted: bool
    privacy_mode: str
    item_counts: dict
    created_at: str
    metadata: dict = field(default_factory=dict)

    @classmethod
    def from_row(cls, row) -> "ExportManifest":
        return cls(
            id=row["id"],
            namespace=row["namespace"],
            export_type=row["export_type"],
            format=row["format"],
            file_path=row["file_path"],
            encrypted=bool(row["encrypted"]),
            privacy_mode=row["privacy_mode"],
            item_counts=_json(row["item_counts_json"], {}),
            created_at=row["created_at"],
            metadata=_json(row["metadata_json"], {}),
        )


@dataclass(frozen=True)
class ImportRun:
    id: str
    source_path: str
    target_namespace: str | None
    dry_run: bool
    imported_counts: dict
    skipped_counts: dict
    conflict_count: int
    status: str
    started_at: str
    finished_at: str | None
    warnings: list[str]
    metadata: dict = field(default_factory=dict)

    @classmethod
    def from_row(cls, row) -> "ImportRun":
        return cls(
            id=row["id"],
            source_path=row["source_path"],
            target_namespace=row["target_namespace"],
            dry_run=bool(row["dry_run"]),
            imported_counts=_json(row["imported_counts_json"], {}),
            skipped_counts=_json(row["skipped_counts_json"], {}),
            conflict_count=row["conflict_count"],
            status=row["status"],
            started_at=row["started_at"],
            finished_at=row["finished_at"],
            warnings=_json(row["warnings_json"], []),
            metadata=_json(row["metadata_json"], {}),
        )


@dataclass(frozen=True)
class SupportBundle:
    id: str
    file_path: str
    privacy_mode: str
    encrypted: bool
    includes_raw_content: bool
    created_at: str
    metadata: dict = field(default_factory=dict)

    @classmethod
    def from_row(cls, row) -> "SupportBundle":
        return cls(
            id=row["id"],
            file_path=row["file_path"],
            privacy_mode=row["privacy_mode"],
            encrypted=bool(row["encrypted"]),
            includes_raw_content=bool(row["includes_raw_content"]),
            created_at=row["created_at"],
            metadata=_json(row["metadata_json"], {}),
        )


@dataclass(frozen=True)
class BenchmarkRun:
    id: str
    profile: str
    started_at: str
    finished_at: str | None
    status: str
    metadata: dict = field(default_factory=dict)

    @classmethod
    def from_row(cls, row) -> "BenchmarkRun":
        return cls(
            id=row["id"],
            profile=row["profile"],
            started_at=row["started_at"],
            finished_at=row["finished_at"],
            status=row["status"],
            metadata=_json(row["metadata_json"], {}),
        )


@dataclass(frozen=True)
class BenchmarkResult:
    id: str
    benchmark_run_id: str
    operation: str
    item_count: int | None
    duration_ms: int
    p50_ms: float | None
    p95_ms: float | None
    p99_ms: float | None
    memory_mb: float | None
    created_at: str
    metadata: dict = field(default_factory=dict)

    @classmethod
    def from_row(cls, row) -> "BenchmarkResult":
        return cls(
            id=row["id"],
            benchmark_run_id=row["benchmark_run_id"],
            operation=row["operation"],
            item_count=row["item_count"],
            duration_ms=row["duration_ms"],
            p50_ms=row["p50_ms"],
            p95_ms=row["p95_ms"],
            p99_ms=row["p99_ms"],
            memory_mb=row["memory_mb"],
            created_at=row["created_at"],
            metadata=_json(row["metadata_json"], {}),
        )


@dataclass(frozen=True)
class ReleaseManifest:
    id: str
    version: str
    git_commit: str | None
    build_time: str
    python_versions: list[str]
    platform_targets: list[str]
    package_files: list[dict]
    dependency_lock_hash: str | None
    migration_range: str
    test_summary: dict
    benchmark_summary: dict
    created_at: str
    metadata: dict = field(default_factory=dict)

    @classmethod
    def from_row(cls, row) -> "ReleaseManifest":
        return cls(
            id=row["id"],
            version=row["version"],
            git_commit=row["git_commit"],
            build_time=row["build_time"],
            python_versions=_json(row["python_versions_json"], []),
            platform_targets=_json(row["platform_targets_json"], []),
            package_files=_json(row["package_files_json"], []),
            dependency_lock_hash=row["dependency_lock_hash"],
            migration_range=row["migration_range"],
            test_summary=_json(row["test_summary_json"], {}),
            benchmark_summary=_json(row["benchmark_summary_json"], {}),
            created_at=row["created_at"],
            metadata=_json(row["metadata_json"], {}),
        )


@dataclass(frozen=True)
class ProductionReadinessCheck:
    id: str
    namespace: str | None
    profile: str
    status: str
    checks: dict
    warnings: list[str]
    recommendations: list[str]
    created_at: str
    metadata: dict = field(default_factory=dict)

    @classmethod
    def from_row(cls, row) -> "ProductionReadinessCheck":
        return cls(
            id=row["id"],
            namespace=row["namespace"],
            profile=row["profile"],
            status=row["status"],
            checks=_json(row["checks_json"], {}),
            warnings=_json(row["warnings_json"], []),
            recommendations=_json(row["recommendations_json"], []),
            created_at=row["created_at"],
            metadata=_json(row["metadata_json"], {}),
        )
