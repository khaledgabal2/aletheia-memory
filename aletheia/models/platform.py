"""M9 stable platform, plugin, conformance, and v1 release models."""

from __future__ import annotations

import json
from dataclasses import dataclass, field


def _json(value: str | None, default):
    if value is None:
        return default
    return json.loads(value)


@dataclass(frozen=True)
class PublicContract:
    id: str
    contract_type: str
    name: str
    version: str
    stability: str
    introduced_in: str
    deprecated_in: str | None
    removed_in: str | None
    schema_ref: str | None
    documentation_ref: str | None
    created_at: str
    metadata: dict = field(default_factory=dict)

    @classmethod
    def from_row(cls, row) -> "PublicContract":
        return cls(
            id=row["id"],
            contract_type=row["contract_type"],
            name=row["name"],
            version=row["version"],
            stability=row["stability"],
            introduced_in=row["introduced_in"],
            deprecated_in=row["deprecated_in"],
            removed_in=row["removed_in"],
            schema_ref=row["schema_ref"],
            documentation_ref=row["documentation_ref"],
            created_at=row["created_at"],
            metadata=_json(row["metadata_json"], {}),
        )


@dataclass(frozen=True)
class ApiContractVersion:
    id: str
    api_type: str
    version: str
    status: str
    schema_hash: str | None
    introduced_in: str
    deprecated_in: str | None
    created_at: str
    metadata: dict = field(default_factory=dict)

    @classmethod
    def from_row(cls, row) -> "ApiContractVersion":
        return cls(
            id=row["id"],
            api_type=row["api_type"],
            version=row["version"],
            status=row["status"],
            schema_hash=row["schema_hash"],
            introduced_in=row["introduced_in"],
            deprecated_in=row["deprecated_in"],
            created_at=row["created_at"],
            metadata=_json(row["metadata_json"], {}),
        )


@dataclass(frozen=True)
class DeprecationNotice:
    id: str
    target_type: str
    target_name: str
    deprecated_in: str
    removal_not_before: str | None
    replacement: str | None
    message: str
    created_at: str
    metadata: dict = field(default_factory=dict)

    @classmethod
    def from_row(cls, row) -> "DeprecationNotice":
        return cls(
            id=row["id"],
            target_type=row["target_type"],
            target_name=row["target_name"],
            deprecated_in=row["deprecated_in"],
            removal_not_before=row["removal_not_before"],
            replacement=row["replacement"],
            message=row["message"],
            created_at=row["created_at"],
            metadata=_json(row["metadata_json"], {}),
        )


@dataclass(frozen=True)
class CompatibilityMatrixEntry:
    id: str
    component_type: str
    component_name: str
    component_version: str
    aletheia_min_version: str
    aletheia_max_version: str | None
    status: str
    tested_at: str | None
    notes: str | None
    metadata: dict = field(default_factory=dict)

    @classmethod
    def from_row(cls, row) -> "CompatibilityMatrixEntry":
        return cls(
            id=row["id"],
            component_type=row["component_type"],
            component_name=row["component_name"],
            component_version=row["component_version"],
            aletheia_min_version=row["aletheia_min_version"],
            aletheia_max_version=row["aletheia_max_version"],
            status=row["status"],
            tested_at=row["tested_at"],
            notes=row["notes"],
            metadata=_json(row["metadata_json"], {}),
        )


@dataclass(frozen=True)
class PluginManifest:
    id: str
    name: str
    display_name: str
    version: str
    plugin_type: str
    entrypoint: str
    description: str
    author: str | None
    license: str | None
    aletheia_min_version: str
    aletheia_max_version: str | None
    api_contract_version: str
    capabilities_required: list[str]
    permissions_required: list[str]
    external_network_access: bool
    reads_memory_content: bool
    writes_memory: bool
    stores_data: bool
    config_schema: dict | None
    checksum: str | None
    signature: str | None
    created_at: str
    metadata: dict = field(default_factory=dict)

    @classmethod
    def from_row(cls, row) -> "PluginManifest":
        return cls(
            id=row["id"],
            name=row["name"],
            display_name=row["display_name"],
            version=row["version"],
            plugin_type=row["plugin_type"],
            entrypoint=row["entrypoint"],
            description=row["description"],
            author=row["author"],
            license=row["license"],
            aletheia_min_version=row["aletheia_min_version"],
            aletheia_max_version=row["aletheia_max_version"],
            api_contract_version=row["api_contract_version"],
            capabilities_required=_json(row["capabilities_required_json"], []),
            permissions_required=_json(row["permissions_required_json"], []),
            external_network_access=bool(row["external_network_access"]),
            reads_memory_content=bool(row["reads_memory_content"]),
            writes_memory=bool(row["writes_memory"]),
            stores_data=bool(row["stores_data"]),
            config_schema=_json(row["config_schema_json"], None),
            checksum=row["checksum"],
            signature=row["signature"],
            created_at=row["created_at"],
            metadata=_json(row["metadata_json"], {}),
        )


@dataclass(frozen=True)
class PluginInstallation:
    id: str
    plugin_manifest_id: str
    install_path: str
    status: str
    trust_level: str
    installed_at: str
    enabled_at: str | None
    disabled_at: str | None
    metadata: dict = field(default_factory=dict)

    @classmethod
    def from_row(cls, row) -> "PluginInstallation":
        return cls(
            id=row["id"],
            plugin_manifest_id=row["plugin_manifest_id"],
            install_path=row["install_path"],
            status=row["status"],
            trust_level=row["trust_level"],
            installed_at=row["installed_at"],
            enabled_at=row["enabled_at"],
            disabled_at=row["disabled_at"],
            metadata=_json(row["metadata_json"], {}),
        )


@dataclass(frozen=True)
class PluginCapabilityGrant:
    id: str
    plugin_installation_id: str
    permission: str
    approved_by: str
    reason: str
    created_at: str
    metadata: dict = field(default_factory=dict)

    @classmethod
    def from_row(cls, row) -> "PluginCapabilityGrant":
        return cls(
            id=row["id"],
            plugin_installation_id=row["plugin_installation_id"],
            permission=row["permission"],
            approved_by=row["approved_by"],
            reason=row["reason"],
            created_at=row["created_at"],
            metadata=_json(row["metadata_json"], {}),
        )


@dataclass(frozen=True)
class PluginExecutionLog:
    id: str
    plugin_installation_id: str
    plugin_type: str
    operation: str
    namespace: str | None
    status: str
    duration_ms: int | None
    input_hash: str | None
    output_hash: str | None
    error: str | None
    created_at: str
    metadata: dict = field(default_factory=dict)

    @classmethod
    def from_row(cls, row) -> "PluginExecutionLog":
        return cls(
            id=row["id"],
            plugin_installation_id=row["plugin_installation_id"],
            plugin_type=row["plugin_type"],
            operation=row["operation"],
            namespace=row["namespace"],
            status=row["status"],
            duration_ms=row["duration_ms"],
            input_hash=row["input_hash"],
            output_hash=row["output_hash"],
            error=row["error"],
            created_at=row["created_at"],
            metadata=_json(row["metadata_json"], {}),
        )


@dataclass(frozen=True)
class PluginTrustRecord:
    id: str
    plugin_installation_id: str
    trust_level: str
    reason: str
    reviewed_by: str
    created_at: str
    metadata: dict = field(default_factory=dict)

    @classmethod
    def from_row(cls, row) -> "PluginTrustRecord":
        return cls(
            id=row["id"],
            plugin_installation_id=row["plugin_installation_id"],
            trust_level=row["trust_level"],
            reason=row["reason"],
            reviewed_by=row["reviewed_by"],
            created_at=row["created_at"],
            metadata=_json(row["metadata_json"], {}),
        )


@dataclass(frozen=True)
class ConformanceSuite:
    id: str
    name: str
    suite_type: str
    version: str
    description: str
    required_for_v1: bool
    created_at: str
    metadata: dict = field(default_factory=dict)

    @classmethod
    def from_row(cls, row) -> "ConformanceSuite":
        return cls(
            id=row["id"],
            name=row["name"],
            suite_type=row["suite_type"],
            version=row["version"],
            description=row["description"],
            required_for_v1=bool(row["required_for_v1"]),
            created_at=row["created_at"],
            metadata=_json(row["metadata_json"], {}),
        )


@dataclass(frozen=True)
class ConformanceCase:
    id: str
    suite_id: str
    name: str
    description: str
    severity: str
    required: bool
    test_ref: str
    created_at: str
    metadata: dict = field(default_factory=dict)

    @classmethod
    def from_row(cls, row) -> "ConformanceCase":
        return cls(
            id=row["id"],
            suite_id=row["suite_id"],
            name=row["name"],
            description=row["description"],
            severity=row["severity"],
            required=bool(row["required"]),
            test_ref=row["test_ref"],
            created_at=row["created_at"],
            metadata=_json(row["metadata_json"], {}),
        )


@dataclass(frozen=True)
class ConformanceRun:
    id: str
    suite_id: str
    target_type: str
    target_id: str | None
    target_name: str
    status: str
    passed_count: int
    failed_count: int
    skipped_count: int
    started_at: str
    finished_at: str | None
    metadata: dict = field(default_factory=dict)

    @classmethod
    def from_row(cls, row) -> "ConformanceRun":
        return cls(
            id=row["id"],
            suite_id=row["suite_id"],
            target_type=row["target_type"],
            target_id=row["target_id"],
            target_name=row["target_name"],
            status=row["status"],
            passed_count=row["passed_count"],
            failed_count=row["failed_count"],
            skipped_count=row["skipped_count"],
            started_at=row["started_at"],
            finished_at=row["finished_at"],
            metadata=_json(row["metadata_json"], {}),
        )


@dataclass(frozen=True)
class ConformanceResult:
    id: str
    run_id: str
    case_id: str
    status: str
    message: str | None
    duration_ms: int | None
    created_at: str
    metadata: dict = field(default_factory=dict)

    @classmethod
    def from_row(cls, row) -> "ConformanceResult":
        return cls(
            id=row["id"],
            run_id=row["run_id"],
            case_id=row["case_id"],
            status=row["status"],
            message=row["message"],
            duration_ms=row["duration_ms"],
            created_at=row["created_at"],
            metadata=_json(row["metadata_json"], {}),
        )


@dataclass(frozen=True)
class AdapterCertification:
    id: str
    adapter_name: str
    adapter_type: str
    adapter_version: str
    conformance_run_id: str
    status: str
    certified_at: str | None
    metadata: dict = field(default_factory=dict)

    @classmethod
    def from_row(cls, row) -> "AdapterCertification":
        return cls(
            id=row["id"],
            adapter_name=row["adapter_name"],
            adapter_type=row["adapter_type"],
            adapter_version=row["adapter_version"],
            conformance_run_id=row["conformance_run_id"],
            status=row["status"],
            certified_at=row["certified_at"],
            metadata=_json(row["metadata_json"], {}),
        )


@dataclass(frozen=True)
class SDKReleaseRecord:
    id: str
    sdk_name: str
    sdk_version: str
    language: str
    api_contract_version: str
    status: str
    released_at: str | None
    metadata: dict = field(default_factory=dict)

    @classmethod
    def from_row(cls, row) -> "SDKReleaseRecord":
        return cls(
            id=row["id"],
            sdk_name=row["sdk_name"],
            sdk_version=row["sdk_version"],
            language=row["language"],
            api_contract_version=row["api_contract_version"],
            status=row["status"],
            released_at=row["released_at"],
            metadata=_json(row["metadata_json"], {}),
        )


@dataclass(frozen=True)
class DocumentationBuild:
    id: str
    version: str
    output_path: str
    status: str
    examples_validated: bool
    warning_count: int
    created_at: str
    metadata: dict = field(default_factory=dict)

    @classmethod
    def from_row(cls, row) -> "DocumentationBuild":
        return cls(
            id=row["id"],
            version=row["version"],
            output_path=row["output_path"],
            status=row["status"],
            examples_validated=bool(row["examples_validated"]),
            warning_count=row["warning_count"],
            created_at=row["created_at"],
            metadata=_json(row["metadata_json"], {}),
        )


@dataclass(frozen=True)
class ExampleProject:
    id: str
    name: str
    example_type: str
    path: str
    status: str
    tested_at: str | None
    metadata: dict = field(default_factory=dict)

    @classmethod
    def from_row(cls, row) -> "ExampleProject":
        return cls(
            id=row["id"],
            name=row["name"],
            example_type=row["example_type"],
            path=row["path"],
            status=row["status"],
            tested_at=row["tested_at"],
            metadata=_json(row["metadata_json"], {}),
        )


@dataclass(frozen=True)
class DoctorRun:
    id: str
    status: str
    checks: list[dict]
    warnings: list[str]
    recommendations: list[str]
    created_at: str
    metadata: dict = field(default_factory=dict)

    @classmethod
    def from_row(cls, row) -> "DoctorRun":
        return cls(
            id=row["id"],
            status=row["status"],
            checks=_json(row["checks_json"], []),
            warnings=_json(row["warnings_json"], []),
            recommendations=_json(row["recommendations_json"], []),
            created_at=row["created_at"],
            metadata=_json(row["metadata_json"], {}),
        )


@dataclass(frozen=True)
class V1ReleaseGateRun:
    id: str
    version: str
    status: str
    checks: list[dict]
    critical_failures: list[str]
    warnings: list[str]
    created_at: str
    metadata: dict = field(default_factory=dict)

    @classmethod
    def from_row(cls, row) -> "V1ReleaseGateRun":
        return cls(
            id=row["id"],
            version=row["version"],
            status=row["status"],
            checks=_json(row["checks_json"], []),
            critical_failures=_json(row["critical_failures_json"], []),
            warnings=_json(row["warnings_json"], []),
            created_at=row["created_at"],
            metadata=_json(row["metadata_json"], {}),
        )
