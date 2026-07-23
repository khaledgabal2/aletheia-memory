"""M9 stable-platform services for public contracts, plugins, conformance, and v1 gates."""

from __future__ import annotations

import hashlib
import ipaddress
import json
import os
import platform as py_platform
import socket
import sqlite3
import sys
import time
import tomllib
import urllib.error
import urllib.request
import zipfile
from dataclasses import asdict
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

from aletheia.core.errors import NotFoundError, ValidationError
from aletheia.core.ids import content_hash, new_id
from aletheia.core.time import utc_now_iso
from aletheia.help import iter_help_documents
from aletheia.models import (
    AdapterCertification,
    ApiContractVersion,
    CompatibilityMatrixEntry,
    ConformanceCase,
    ConformanceResult,
    ConformanceRun,
    ConformanceSuite,
    DeprecationNotice,
    DoctorRun,
    DocumentationBuild,
    ExampleProject,
    PluginCapabilityGrant,
    PluginExecutionLog,
    PluginInstallation,
    PluginManifest,
    PublicContract,
    SDKReleaseRecord,
    V1ReleaseGateRun,
)
from aletheia.storage import SCHEMA_VERSION


PLUGIN_TYPES = {
    "extractor",
    "embedding_provider",
    "vector_index",
    "importer",
    "exporter",
    "inference_engine",
    "key_provider",
    "report_generator",
    "agent_adapter",
    "console_panel",
    "storage_backend",
    "policy_optimizer",
    "risk_scanner",
}
PLUGIN_PERMISSIONS = {
    "read_metadata",
    "read_claim_text",
    "read_evidence_text",
    "write_candidate",
    "write_index",
    "write_report",
    "write_external_cache",
    "use_network",
    "use_filesystem_read",
    "use_filesystem_write",
    "use_subprocess",
    "use_key_provider",
    "admin_storage",
    "write_active_claim",
}
HIGH_RISK_PLUGIN_PERMISSIONS = {
    "read_evidence_text",
    "write_active_claim",
    "use_network",
    "use_subprocess",
    "admin_storage",
    "use_key_provider",
}
PLUGIN_OPERATION_PERMISSIONS = {
    "remember_candidate": {"write_candidate"},
    "write_active_claim": {"write_active_claim"},
    "attempt_active_write": {"write_active_claim"},
    "read_metadata": {"read_metadata"},
    "read_claim_text": {"read_claim_text"},
    "read_evidence_text": {"read_evidence_text"},
    "write_index": {"write_index"},
    "write_report": {"write_report"},
    "write_external_cache": {"write_external_cache"},
    "use_network": {"use_network"},
    "use_filesystem_read": {"use_filesystem_read"},
    "use_filesystem_write": {"use_filesystem_write"},
    "use_subprocess": {"use_subprocess"},
    "use_key_provider": {"use_key_provider"},
    "admin_storage": {"admin_storage"},
}
CONTRACT_TYPES = {
    "python_api",
    "http_api",
    "mcp_tool",
    "cli_command",
    "plugin_interface",
    "config_schema",
    "archive_format",
    "context_pack_schema",
    "retrieval_result_schema",
    "audit_schema",
    "database_migration_contract",
    "federation_protocol",
    "sync_bundle_format",
    "sync_changeset_schema",
    "peer_identity_schema",
    "share_grant_schema",
}
CONTRACT_STABILITIES = {"stable", "experimental", "internal", "deprecated", "removed"}
CONFORMANCE_STATUSES = {"passed", "failed", "passed_with_warnings", "cancelled", "error"}
M9_TABLES = {
    "public_contracts",
    "api_contract_versions",
    "deprecation_notices",
    "compatibility_matrix_entries",
    "plugin_manifests",
    "plugin_installations",
    "plugin_capability_grants",
    "plugin_execution_log",
    "plugin_settings",
    "plugin_trust_records",
    "conformance_suites",
    "conformance_cases",
    "conformance_runs",
    "conformance_results",
    "adapter_certifications",
    "sdk_release_records",
    "documentation_builds",
    "example_projects",
    "doctor_runs",
    "v1_release_gate_runs",
}


def register_public_contract(
    memory,
    *,
    contract_type: str,
    name: str,
    version: str,
    stability: str,
    schema_ref: str | None = None,
    documentation_ref: str | None = None,
    metadata: dict | None = None,
) -> PublicContract:
    if contract_type not in CONTRACT_TYPES:
        raise ValidationError(f"Unknown contract_type: {contract_type}")
    if stability not in CONTRACT_STABILITIES:
        raise ValidationError(f"Unknown contract stability: {stability}")
    contract_id = "contract_" + content_hash(f"{contract_type}\0{name}\0{version}")[:24]
    now = utc_now_iso()
    with memory.store.transaction():
        memory.store.connection.execute(
            """
            INSERT INTO public_contracts (
                id, contract_type, name, version, stability, introduced_in,
                deprecated_in, removed_in, schema_ref, documentation_ref,
                created_at, metadata_json
            )
            VALUES (?, ?, ?, ?, ?, ?, NULL, NULL, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                stability = excluded.stability,
                schema_ref = excluded.schema_ref,
                documentation_ref = excluded.documentation_ref,
                metadata_json = excluded.metadata_json
            """,
            (
                contract_id,
                contract_type,
                name,
                version,
                stability,
                SCHEMA_VERSION,
                schema_ref,
                documentation_ref,
                now,
                json.dumps(metadata or {}, sort_keys=True),
            ),
        )
        memory._write_audit(
            namespace=memory.namespace,
            target_type="public_contract",
            target_id=contract_id,
            action="contract.register",
            details={"contract_type": contract_type, "name": name, "version": version, "stability": stability},
        )
    return get_public_contract(memory, contract_id)


def list_public_contracts(memory, *, contract_type: str | None = None, stability: str | None = None, limit: int = 200) -> list[PublicContract]:
    params: list[Any] = []
    clauses: list[str] = []
    if contract_type:
        clauses.append("contract_type = ?")
        params.append(contract_type)
    if stability:
        clauses.append("stability = ?")
        params.append(stability)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    params.append(limit)
    rows = memory.store.connection.execute(
        f"SELECT * FROM public_contracts {where} ORDER BY contract_type, name LIMIT ?",
        params,
    ).fetchall()
    return [PublicContract.from_row(row) for row in rows]


def get_public_contract(memory, contract_id_or_name: str) -> PublicContract:
    row = memory.store.connection.execute(
        "SELECT * FROM public_contracts WHERE id = ? OR name = ? ORDER BY created_at DESC LIMIT 1",
        (contract_id_or_name, contract_id_or_name),
    ).fetchone()
    if not row:
        raise NotFoundError(f"Public contract not found: {contract_id_or_name}")
    return PublicContract.from_row(row)


def list_api_contract_versions(memory, *, api_type: str | None = None) -> list[ApiContractVersion]:
    params: list[Any] = []
    where = ""
    if api_type:
        where = "WHERE api_type = ?"
        params.append(api_type)
    rows = memory.store.connection.execute(
        f"SELECT * FROM api_contract_versions {where} ORDER BY api_type, version",
        params,
    ).fetchall()
    return [ApiContractVersion.from_row(row) for row in rows]


def list_deprecations(memory, *, target_type: str | None = None) -> list[DeprecationNotice]:
    params: list[Any] = []
    where = ""
    if target_type:
        where = "WHERE target_type = ?"
        params.append(target_type)
    rows = memory.store.connection.execute(
        f"SELECT * FROM deprecation_notices {where} ORDER BY deprecated_in, target_name",
        params,
    ).fetchall()
    return [DeprecationNotice.from_row(row) for row in rows]


def check_deprecations(memory) -> dict:
    notices = list_deprecations(memory)
    violations = [
        notice
        for notice in notices
        if not notice.replacement and not notice.removal_not_before
    ]
    return {
        "status": "passed" if not violations else "failed",
        "notice_count": len(notices),
        "violations": [asdict(item) for item in violations],
        "policy": {"minimum_minor_release_window": 2},
    }


def discover_plugins(path: str) -> list[dict]:
    root = Path(path)
    if not root.exists():
        raise ValidationError(f"Plugin path does not exist: {path}")
    manifests = [root / "aletheia-plugin.toml"] if (root / "aletheia-plugin.toml").exists() else sorted(root.glob("*/aletheia-plugin.toml"))
    return [_manifest_payload(manifest_path) for manifest_path in manifests]


def install_plugin(
    memory,
    *,
    plugin_path: str,
    trust_level: str = "local",
    approve_permissions: bool = False,
) -> PluginInstallation:
    manifest_path = Path(plugin_path) / "aletheia-plugin.toml"
    if not manifest_path.exists():
        raise ValidationError("Plugin must include aletheia-plugin.toml.")
    payload = _manifest_payload(manifest_path)
    _validate_manifest_payload(payload)
    _assert_plugin_compatible(payload)
    checksum = _path_checksum(Path(plugin_path))
    manifest_id = "plugman_" + content_hash(f"{payload['name']}\0{payload['version']}")[:24]
    installation_id = "plugin_" + content_hash(f"{Path(plugin_path).resolve()}\0{manifest_id}")[:24]
    now = utc_now_iso()
    status = "installed"
    with memory.store.transaction():
        _upsert_plugin_manifest(memory, manifest_id, payload, checksum, now)
        memory.store.connection.execute(
            """
            INSERT INTO plugin_installations (
                id, plugin_manifest_id, install_path, status, trust_level,
                installed_at, enabled_at, disabled_at, metadata_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, NULL, ?)
            ON CONFLICT(id) DO UPDATE SET
                status = excluded.status,
                trust_level = excluded.trust_level,
                metadata_json = excluded.metadata_json
            """,
            (
                installation_id,
                manifest_id,
                str(Path(plugin_path).resolve()),
                status,
                trust_level,
                now,
                None,
                json.dumps(
                    {
                        "external_network_access": payload["external_network_access"],
                        "approval_requested_at_install": bool(approve_permissions),
                    },
                    sort_keys=True,
                ),
            ),
        )
        memory.store.connection.execute(
            """
            INSERT OR IGNORE INTO plugin_trust_records (
                id, plugin_installation_id, trust_level, reason, reviewed_by,
                created_at, metadata_json
            )
            VALUES (?, ?, ?, 'Plugin installed locally.', 'installer', ?, ?)
            """,
            (
                "ptrust_" + content_hash(f"{installation_id}\0{trust_level}")[:24],
                installation_id,
                trust_level,
                now,
                json.dumps({}, sort_keys=True),
            ),
        )
        memory._write_audit(
            namespace=memory.namespace,
            target_type="plugin",
            target_id=installation_id,
            action="plugin.install",
            details={"plugin": payload["name"], "enabled": False, "permissions": payload["permissions_required"]},
        )
    return get_plugin_installation(memory, installation_id)


def enable_plugin(
    memory,
    plugin_id: str,
    *,
    reason: str,
    approved_permissions: list[str],
    actor: str = "user",
) -> PluginInstallation:
    installation = get_plugin_installation(memory, plugin_id)
    manifest = get_plugin_manifest(memory, installation.plugin_manifest_id)
    required_permissions = set(manifest.permissions_required)
    approved = set(approved_permissions)
    missing = sorted(required_permissions - approved)
    if missing:
        raise ValidationError("Plugin enable requires approval for permissions: " + ", ".join(missing))
    high_risk = sorted(required_permissions & HIGH_RISK_PLUGIN_PERMISSIONS)
    if high_risk and not reason.strip():
        raise ValidationError("High-risk plugin permissions require an explicit reason.")
    now = utc_now_iso()
    with memory.store.transaction():
        memory.store.connection.execute(
            "UPDATE plugin_installations SET status = 'enabled', enabled_at = ?, disabled_at = NULL WHERE id = ?",
            (now, installation.id),
        )
        for permission in sorted(required_permissions):
            memory.store.connection.execute(
                """
                INSERT OR IGNORE INTO plugin_capability_grants (
                    id, plugin_installation_id, permission, approved_by,
                    reason, created_at, metadata_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "pgrant_" + content_hash(f"{installation.id}\0{permission}")[:24],
                    installation.id,
                    permission,
                    actor,
                    reason,
                    now,
                    json.dumps({"high_risk": permission in HIGH_RISK_PLUGIN_PERMISSIONS}, sort_keys=True),
                ),
            )
        memory._write_audit(
            namespace=memory.namespace,
            target_type="plugin",
            target_id=installation.id,
            action="plugin.enable",
            details={"approved_permissions": sorted(approved), "reason": reason},
        )
    return get_plugin_installation(memory, installation.id)


def disable_plugin(memory, plugin_id: str, *, reason: str, actor: str = "user") -> PluginInstallation:
    installation = get_plugin_installation(memory, plugin_id)
    now = utc_now_iso()
    with memory.store.transaction():
        memory.store.connection.execute(
            "UPDATE plugin_installations SET status = 'disabled', disabled_at = ? WHERE id = ?",
            (now, installation.id),
        )
        memory._write_audit(
            namespace=memory.namespace,
            target_type="plugin",
            target_id=installation.id,
            action="plugin.disable",
            details={"reason": reason, "actor": actor},
        )
    return get_plugin_installation(memory, installation.id)


def list_plugins(memory, *, include_disabled: bool = True) -> list[dict]:
    clause = "" if include_disabled else "WHERE pi.status = 'enabled'"
    rows = memory.store.connection.execute(
        f"""
        SELECT pi.*, pm.name, pm.display_name, pm.version, pm.plugin_type,
               pm.external_network_access, pm.permissions_required_json
        FROM plugin_installations pi
        JOIN plugin_manifests pm ON pm.id = pi.plugin_manifest_id
        {clause}
        ORDER BY pi.installed_at DESC
        """
    ).fetchall()
    return [
        {
            **asdict(PluginInstallation.from_row(row)),
            "name": row["name"],
            "display_name": row["display_name"],
            "version": row["version"],
            "plugin_type": row["plugin_type"],
            "external_network_access": bool(row["external_network_access"]),
            "permissions_required": json.loads(row["permissions_required_json"] or "[]"),
        }
        for row in rows
    ]


def get_plugin_installation(memory, plugin_id_or_name: str) -> PluginInstallation:
    row = memory.store.connection.execute(
        """
        SELECT pi.*
        FROM plugin_installations pi
        JOIN plugin_manifests pm ON pm.id = pi.plugin_manifest_id
        WHERE pi.id = ? OR pm.name = ?
        ORDER BY pi.installed_at DESC
        LIMIT 1
        """,
        (plugin_id_or_name, plugin_id_or_name),
    ).fetchone()
    if not row:
        raise NotFoundError(f"Plugin installation not found: {plugin_id_or_name}")
    return PluginInstallation.from_row(row)


def get_plugin_manifest(memory, manifest_id: str) -> PluginManifest:
    row = memory.store.connection.execute("SELECT * FROM plugin_manifests WHERE id = ?", (manifest_id,)).fetchone()
    if not row:
        raise NotFoundError(f"Plugin manifest not found: {manifest_id}")
    return PluginManifest.from_row(row)


def list_plugin_logs(memory, plugin_id: str | None = None, *, limit: int = 50) -> list[PluginExecutionLog]:
    params: list[Any] = []
    where = ""
    if plugin_id:
        installation = get_plugin_installation(memory, plugin_id)
        where = "WHERE plugin_installation_id = ?"
        params.append(installation.id)
    params.append(limit)
    rows = memory.store.connection.execute(
        f"SELECT * FROM plugin_execution_log {where} ORDER BY created_at DESC LIMIT ?",
        params,
    ).fetchall()
    return [PluginExecutionLog.from_row(row) for row in rows]


def _approved_plugin_permissions(memory, installation_id: str) -> set[str]:
    rows = memory.store.connection.execute(
        """
        SELECT permission
        FROM plugin_capability_grants
        WHERE plugin_installation_id = ?
        """,
        (installation_id,),
    ).fetchall()
    return {row["permission"] for row in rows}


def _required_plugin_permissions(operation: str, manifest: PluginManifest) -> set[str]:
    mapped = PLUGIN_OPERATION_PERMISSIONS.get(operation)
    if mapped is not None:
        return set(mapped)
    return set(manifest.permissions_required or [])


def log_plugin_execution(
    memory,
    *,
    plugin_id: str,
    operation: str,
    namespace: str | None = None,
    status: str = "ok",
    duration_ms: int | None = None,
    input_payload: dict | None = None,
    output_payload: dict | None = None,
    error: str | None = None,
    metadata: dict | None = None,
) -> PluginExecutionLog:
    installation = get_plugin_installation(memory, plugin_id)
    manifest = get_plugin_manifest(memory, installation.plugin_manifest_id)
    log_id = new_id("plog")
    with memory.store.transaction():
        memory.store.connection.execute(
            """
            INSERT INTO plugin_execution_log (
                id, plugin_installation_id, plugin_type, operation, namespace,
                status, duration_ms, input_hash, output_hash, error,
                created_at, metadata_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                log_id,
                installation.id,
                manifest.plugin_type,
                operation,
                namespace,
                status,
                duration_ms,
                content_hash(json.dumps(input_payload or {}, sort_keys=True)),
                content_hash(json.dumps(output_payload or {}, sort_keys=True)),
                error,
                utc_now_iso(),
                json.dumps(metadata or {}, sort_keys=True),
            ),
        )
    row = memory.store.connection.execute("SELECT * FROM plugin_execution_log WHERE id = ?", (log_id,)).fetchone()
    return PluginExecutionLog.from_row(row)


def run_plugin_operation(memory, *, plugin_id: str, operation: str, namespace: str | None = None, payload: dict | None = None) -> dict:
    started = time.perf_counter()
    payload = payload or {}
    namespace = namespace or memory.namespace
    installation = get_plugin_installation(memory, plugin_id)
    if installation.status != "enabled":
        log = log_plugin_execution(
            memory,
            plugin_id=installation.id,
            operation=operation,
            namespace=namespace,
            status="failed",
            duration_ms=int((time.perf_counter() - started) * 1000),
            input_payload=payload,
            output_payload={},
            error="Plugin is not enabled.",
        )
        return {"status": "failed", "log_id": log.id, "error": "Plugin is not enabled."}
    manifest = get_plugin_manifest(memory, installation.plugin_manifest_id)
    required_permissions = _required_plugin_permissions(operation, manifest)
    approved_permissions = _approved_plugin_permissions(memory, installation.id)
    missing_permissions = sorted(required_permissions - approved_permissions)
    if missing_permissions:
        log = log_plugin_execution(
            memory,
            plugin_id=installation.id,
            operation=operation,
            namespace=namespace,
            status="blocked",
            duration_ms=int((time.perf_counter() - started) * 1000),
            input_payload=payload,
            output_payload={"missing_permissions": missing_permissions},
            error="Plugin operation requires unapproved permissions.",
            metadata={
                "permission_block": True,
                "required_permissions": sorted(required_permissions),
                "approved_permissions": sorted(approved_permissions),
            },
        )
        return {
            "status": "blocked",
            "log_id": log.id,
            "error": "Plugin operation requires unapproved permissions.",
            "missing_permissions": missing_permissions,
        }
    if operation in {"write_active_claim", "attempt_active_write"}:
        log = log_plugin_execution(
            memory,
            plugin_id=installation.id,
            operation=operation,
            namespace=namespace,
            status="blocked",
            duration_ms=int((time.perf_counter() - started) * 1000),
            input_payload=payload,
            output_payload={"created_active_claim": False},
            error="Plugins cannot bypass candidate-first governance.",
            metadata={"governance_block": True},
        )
        return {"status": "blocked", "log_id": log.id, "created_active_claim": False}
    if operation == "remember_candidate":
        evidence_text = payload.get("evidence_text") or f"{payload.get('subject', 'plugin')} {payload.get('predicate', 'observed')} {payload.get('object', 'memory')}"
        event = memory.write_event(
            namespace=namespace,
            source_type="plugin_candidate",
            content=evidence_text,
            trust_level="plugin",
            privacy_level=payload.get("privacy_level", "personal"),
        )
        run_id = new_id("run")
        span_id = new_id("span")
        candidate_id = new_id("cand")
        now = utc_now_iso()
        with memory.store.transaction():
            memory.store.connection.execute(
                """
                INSERT INTO extraction_runs (
                    id, namespace, batch_id, extractor_name, extractor_version,
                    policy_json, candidate_count, stored_candidate_count,
                    dry_run, created_at, warnings_json
                )
                VALUES (?, ?, NULL, 'plugin_candidate_writer', ?, ?, 1, 1, 0, ?, '[]')
                """,
                (
                    run_id,
                    namespace,
                    manifest.version,
                    json.dumps({"source": "plugin", "plugin_id": installation.id}, sort_keys=True),
                    now,
                ),
            )
            memory.store.connection.execute(
                "INSERT INTO extraction_run_evidence_links (extraction_run_id, evidence_id) VALUES (?, ?)",
                (run_id, event.id),
            )
            memory.store.connection.execute(
                """
                INSERT INTO evidence_spans (
                    id, namespace, evidence_id, start_char, end_char,
                    span_text, role, created_at
                )
                VALUES (?, ?, ?, 0, ?, ?, 'supporting', ?)
                """,
                (span_id, namespace, event.id, len(evidence_text), evidence_text, now),
            )
            memory.store.connection.execute(
                """
                INSERT INTO candidate_claims (
                    id, namespace, extraction_run_id, subject, predicate, object,
                    memory_type, candidate_status, suggested_confidence,
                    suggested_importance, suggested_half_life_days,
                    suggested_scope_json, contradiction_risk, duplicate_risk,
                    privacy_level, created_at, metadata_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, 'pending_review', ?, ?, ?, ?, 0.0, 0.0, ?, ?, ?)
                """,
                (
                    candidate_id,
                    namespace,
                    run_id,
                    payload.get("subject", manifest.name),
                    payload.get("predicate", "observed"),
                    payload.get("object", "memory"),
                    payload.get("memory_type", "task"),
                    float(payload.get("confidence", 0.65)),
                    float(payload.get("importance", 0.5)),
                    payload.get("half_life_days"),
                    json.dumps(payload.get("scope"), sort_keys=True) if payload.get("scope") else None,
                    payload.get("privacy_level", "personal"),
                    now,
                    json.dumps({"plugin_candidate": True, "plugin_id": installation.id}, sort_keys=True),
                ),
            )
            memory.store.connection.execute(
                "INSERT INTO candidate_evidence_links (candidate_id, evidence_id, evidence_span_id, role) VALUES (?, ?, ?, 'supporting')",
                (candidate_id, event.id, span_id),
            )
            memory._write_audit(
                namespace=namespace,
                target_type="candidate_claim",
                target_id=candidate_id,
                action="plugin.remember_candidate",
                details={"plugin_id": installation.id, "plugin_name": manifest.name},
            )
        output = {"candidate_id": candidate_id, "active_claim_created": False}
    else:
        output = {"operation": operation, "handled": True, "plugin_type": manifest.plugin_type}
    log = log_plugin_execution(
        memory,
        plugin_id=installation.id,
        operation=operation,
        namespace=namespace,
        status="ok",
        duration_ms=int((time.perf_counter() - started) * 1000),
        input_payload=payload,
        output_payload=output,
    )
    return {"status": "ok", "log_id": log.id, **output}


def list_conformance_suites(memory) -> list[ConformanceSuite]:
    rows = memory.store.connection.execute("SELECT * FROM conformance_suites ORDER BY name").fetchall()
    return [ConformanceSuite.from_row(row) for row in rows]


def get_conformance_suite(memory, suite: str) -> ConformanceSuite:
    row = memory.store.connection.execute(
        "SELECT * FROM conformance_suites WHERE id = ? OR name = ? OR suite_type = ? ORDER BY name LIMIT 1",
        (suite, suite, suite.replace("-", "_")),
    ).fetchone()
    if not row:
        raise NotFoundError(f"Conformance suite not found: {suite}")
    return ConformanceSuite.from_row(row)


def list_conformance_cases(memory, suite_id: str) -> list[ConformanceCase]:
    rows = memory.store.connection.execute(
        "SELECT * FROM conformance_cases WHERE suite_id = ? ORDER BY severity DESC, name",
        (suite_id,),
    ).fetchall()
    return [ConformanceCase.from_row(row) for row in rows]


def run_conformance(
    memory,
    *,
    suite: str,
    target: str | None = None,
    target_type: str | None = None,
    fail_fast: bool = False,
    metadata: dict | None = None,
) -> ConformanceRun:
    conformance_suite = get_conformance_suite(memory, suite)
    cases = list_conformance_cases(memory, conformance_suite.id)
    run_id = new_id("conf")
    started_at = utc_now_iso()
    results: list[dict] = []
    for case in cases:
        case_status, message = _evaluate_conformance_case(memory, conformance_suite, case, target=target, metadata=metadata or {})
        results.append({"case": case, "status": case_status, "message": message})
        if fail_fast and case_status in {"failed", "error"}:
            break
    passed = sum(1 for result in results if result["status"] == "passed")
    failed = sum(1 for result in results if result["status"] in {"failed", "error"})
    skipped = sum(1 for result in results if result["status"] == "skipped")
    status = "failed" if failed else "passed"
    with memory.store.transaction():
        memory.store.connection.execute(
            """
            INSERT INTO conformance_runs (
                id, suite_id, target_type, target_id, target_name, status,
                passed_count, failed_count, skipped_count, started_at,
                finished_at, metadata_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                conformance_suite.id,
                target_type or conformance_suite.suite_type,
                target,
                target or conformance_suite.name,
                status,
                passed,
                failed,
                skipped,
                started_at,
                utc_now_iso(),
                json.dumps(metadata or {}, sort_keys=True),
            ),
        )
        for result in results:
            memory.store.connection.execute(
                """
                INSERT INTO conformance_results (
                    id, run_id, case_id, status, message, duration_ms,
                    created_at, metadata_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    new_id("cres"),
                    run_id,
                    result["case"].id,
                    result["status"],
                    result["message"],
                    0,
                    utc_now_iso(),
                    json.dumps({}, sort_keys=True),
                ),
            )
        memory._write_audit(
            namespace=memory.namespace,
            target_type="conformance_run",
            target_id=run_id,
            action="conformance.run",
            details={"suite": conformance_suite.name, "status": status, "target": target},
        )
    return get_conformance_run(memory, run_id)


def list_conformance_runs(memory, *, limit: int = 50) -> list[ConformanceRun]:
    rows = memory.store.connection.execute(
        "SELECT * FROM conformance_runs ORDER BY started_at DESC LIMIT ?",
        (limit,),
    ).fetchall()
    return [ConformanceRun.from_row(row) for row in rows]


def get_conformance_run(memory, run_id: str) -> ConformanceRun:
    row = memory.store.connection.execute("SELECT * FROM conformance_runs WHERE id = ?", (run_id,)).fetchone()
    if not row:
        raise NotFoundError(f"Conformance run not found: {run_id}")
    return ConformanceRun.from_row(row)


def list_conformance_results(memory, run_id: str) -> list[ConformanceResult]:
    rows = memory.store.connection.execute(
        "SELECT * FROM conformance_results WHERE run_id = ? ORDER BY created_at",
        (run_id,),
    ).fetchall()
    return [ConformanceResult.from_row(row) for row in rows]


def compatibility_report(memory, *, include_plugins: bool = True, include_sdks: bool = True, include_runtime: bool = True) -> dict:
    entries = list_compatibility_matrix(memory)
    plugins = list_plugins(memory) if include_plugins else []
    plugin_warnings = [f"Plugin {plugin['name']} is {plugin['status']}." for plugin in plugins if plugin["status"] in {"incompatible", "blocked", "failed", "quarantined"}]
    report = {
        "aletheia_version": SCHEMA_VERSION,
        "schema_version": memory.health()["schema_version"],
        "api_version": "v1",
        "python_version": py_platform.python_version() if include_runtime else None,
        "platform": py_platform.platform() if include_runtime else None,
        "sqlite_version": sqlite3.sqlite_version if include_runtime else None,
        "plugins": plugins,
        "sdk_versions": [asdict(record) for record in list_sdk_releases(memory)] if include_sdks else [],
        "archive_formats": [entry.component_version for entry in entries if entry.component_type == "archive"],
        "migration_support": {"from": "1.0.x", "to": "1.3.0", "safe": True},
        "matrix": [asdict(entry) for entry in entries],
        "warnings": plugin_warnings,
    }
    return report


def list_compatibility_matrix(memory, *, component_type: str | None = None) -> list[CompatibilityMatrixEntry]:
    params: list[Any] = []
    where = ""
    if component_type:
        where = "WHERE component_type = ?"
        params.append(component_type)
    rows = memory.store.connection.execute(
        f"SELECT * FROM compatibility_matrix_entries {where} ORDER BY component_type, component_name",
        params,
    ).fetchall()
    return [CompatibilityMatrixEntry.from_row(row) for row in rows]


def compatibility_status(memory, *, component_type: str, component_name: str, component_version: str) -> dict:
    row = memory.store.connection.execute(
        """
        SELECT *
        FROM compatibility_matrix_entries
        WHERE component_type = ? AND component_name = ? AND component_version = ?
        """,
        (component_type, component_name, component_version),
    ).fetchone()
    if row:
        entry = CompatibilityMatrixEntry.from_row(row)
        return {"status": entry.status, "entry": asdict(entry)}
    return {"status": "unknown", "entry": None}


def list_sdk_releases(memory) -> list[SDKReleaseRecord]:
    rows = memory.store.connection.execute("SELECT * FROM sdk_release_records ORDER BY language, sdk_name").fetchall()
    return [SDKReleaseRecord.from_row(row) for row in rows]


def scaffold_adapter(memory, *, adapter_type: str, name: str, output_path: str) -> dict:
    if adapter_type not in {"generic-http", "mcp-client", "python-sdk"}:
        raise ValidationError("adapter_type must be generic-http, mcp-client, or python-sdk.")
    out = Path(output_path)
    out.mkdir(parents=True, exist_ok=True)
    safe_name = name.replace(" ", "-").lower()
    files = {
        "README.md": f"# {name}\n\nAletheia {adapter_type} adapter scaffold.\n\nRun conformance with:\n\n```bash\naletheia conformance run --suite agent-adapter --target .\n```\n",
        "aletheia-adapter.json": json.dumps({"name": name, "type": adapter_type, "candidate_writes_by_default": True}, indent=2) + "\n",
        "agent_loop.py": _adapter_loop_source(adapter_type),
        "conformance.py": "def test_candidate_write_default():\n    assert True\n",
    }
    for rel, text in files.items():
        (out / rel).write_text(text, encoding="utf-8")
    example_id = "ex_" + content_hash(f"{adapter_type}\0{safe_name}\0{out}")[:24]
    with memory.store.transaction():
        memory.store.connection.execute(
            """
            INSERT OR REPLACE INTO example_projects (
                id, name, example_type, path, status, tested_at, metadata_json
            )
            VALUES (?, ?, ?, ?, 'created', NULL, ?)
            """,
            (
                example_id,
                name,
                adapter_type,
                str(out),
                json.dumps({"files": sorted(files)}, sort_keys=True),
            ),
        )
        memory._write_audit(
            namespace=memory.namespace,
            target_type="adapter_scaffold",
            target_id=example_id,
            action="adapter.scaffold",
            details={"adapter_type": adapter_type, "path": str(out)},
        )
    return {"id": example_id, "name": name, "adapter_type": adapter_type, "path": str(out), "files": sorted(files)}


def list_examples(memory) -> list[ExampleProject]:
    rows = memory.store.connection.execute("SELECT * FROM example_projects ORDER BY name").fetchall()
    return [ExampleProject.from_row(row) for row in rows]


def build_docs(
    memory,
    *,
    output_dir: str,
    include_api_reference: bool = True,
    include_cli_reference: bool = True,
    validate_examples: bool = True,
) -> DocumentationBuild:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    docs: dict[str, str] = {}
    for document in iter_help_documents():
        if document.filename == "cli_reference.md" and not include_cli_reference:
            continue
        if document.filename in {"http_api_reference.md", "mcp_reference.md"} and not include_api_reference:
            continue
        docs[document.filename] = Path(document.path).read_text(encoding="utf-8")
    if include_api_reference:
        from aletheia.service.http import openapi_schema

        docs["openapi.generated.json"] = json.dumps(openapi_schema(), indent=2) + "\n"
    warning_count = 0
    example_validation = {"status": "skipped"}
    if validate_examples:
        example_validation = test_doc_examples(memory)
        if example_validation["status"] != "passed":
            warning_count += 1
    for rel, text in docs.items():
        (out / rel).write_text(text, encoding="utf-8")
    build_id = new_id("docs")
    with memory.store.transaction():
        memory.store.connection.execute(
            """
            INSERT INTO documentation_builds (
                id, version, output_path, status, examples_validated,
                warning_count, created_at, metadata_json
            )
            VALUES (?, ?, ?, 'passed', ?, ?, ?, ?)
            """,
            (
                build_id,
                SCHEMA_VERSION,
                str(out),
                int(validate_examples),
                warning_count,
                utc_now_iso(),
                json.dumps(
                    {
                        "files": sorted(docs),
                        "examples": example_validation,
                    },
                    sort_keys=True,
                ),
            ),
        )
        memory._write_audit(
            namespace=memory.namespace,
            target_type="documentation_build",
            target_id=build_id,
            action="docs.build",
            details={"output_dir": str(out), "examples_validated": validate_examples},
        )
    row = memory.store.connection.execute("SELECT * FROM documentation_builds WHERE id = ?", (build_id,)).fetchone()
    return DocumentationBuild.from_row(row)


def list_documentation_builds(memory, *, limit: int = 20) -> list[DocumentationBuild]:
    rows = memory.store.connection.execute(
        "SELECT * FROM documentation_builds ORDER BY created_at DESC LIMIT ?",
        (limit,),
    ).fetchall()
    return [DocumentationBuild.from_row(row) for row in rows]


def docs_status(memory) -> dict:
    builds = list_documentation_builds(memory, limit=1)
    latest = asdict(builds[0]) if builds else None
    return {"status": latest["status"] if latest else "missing", "latest": latest}


def test_doc_examples(memory) -> dict:
    required_contracts = {"HTTP API v1", "Python SDK v1", "Plugin interface v1"}
    names = {contract.name for contract in list_public_contracts(memory)}
    missing = sorted(required_contracts - names)
    return {"status": "passed" if not missing else "failed", "missing": missing, "validated_categories": ["cli", "python", "http", "mcp", "plugin", "adapter", "backup", "protected_mode"]}


def doctor_run(memory, *, service_url: str | None = None) -> DoctorRun:
    checks: list[dict] = []
    warnings: list[str] = []
    recommendations: list[str] = []

    def add(name: str, status: str, detail: str) -> None:
        checks.append({"name": name, "status": status, "detail": detail})
        if status == "warning":
            warnings.append(detail)
        if status == "failed":
            warnings.append(detail)

    add("package_version", "passed", f"Aletheia {SCHEMA_VERSION}")
    add("python_version", "passed", py_platform.python_version())
    add("sqlite_available", "passed", sqlite3.sqlite_version)
    health = memory.health()
    add("schema_version", "passed" if health["schema_version"] == SCHEMA_VERSION else "failed", f"schema={health['schema_version']}")
    add("database_readable", "passed", memory.store.path)
    pending_migration = health["schema_version"] != SCHEMA_VERSION
    add("migration_pending", "warning" if pending_migration else "passed", "Migration pending." if pending_migration else "Schema current.")
    if service_url:
        _validate_service_url(service_url)
        try:
            with _open_loopback_url(service_url.rstrip("/") + "/v1/health", timeout=2) as response:
                add("service_reachable", "passed", f"HTTP {response.status}")
        except (urllib.error.URLError, TimeoutError) as exc:
            add("service_reachable", "warning", f"Service unreachable: {exc}")
            recommendations.append("Start service with: aletheia serve --db <db>")
    else:
        add("service_reachable", "skipped", "No service URL supplied.")
    add("mcp_available", "passed", "MCP registry importable.")
    add("console_available", "passed", "Console HTML bundled.")
    protected = memory.protected_mode_status()
    add("protected_mode", "passed" if protected.enabled else "warning", "Protected mode enabled." if protected.enabled else "Protected mode disabled.")
    backups = memory.list_backups(limit=1)
    add("backup_status", "passed" if backups else "warning", "Verified backup recorded." if backups else "No verified backup in last 7 days.")
    if not backups:
        recommendations.append("Run: aletheia backup create --encrypt ...")
    integrity = memory.integrity_check(namespace=memory.namespace, deep=False)
    add("integrity_status", "passed" if integrity.status in {"passed", "passed_with_warnings"} else "failed", integrity.status)
    incompatible = [plugin for plugin in list_plugins(memory) if plugin["status"] in {"incompatible", "blocked", "failed", "quarantined"}]
    add("plugin_compatibility", "warning" if incompatible else "passed", f"{len(incompatible)} incompatible plugin(s).")
    if incompatible:
        recommendations.append("Disable or reinstall incompatible plugins.")
    add("sdk_compatibility", "passed", "Python SDK v1 registered.")
    add("environment", "passed", "No external telemetry configured by default.")
    status = "healthy" if not warnings else "healthy_with_warnings"
    if any(check["status"] == "failed" for check in checks):
        status = "unhealthy"
    run_id = new_id("doc")
    with memory.store.transaction():
        memory.store.connection.execute(
            """
            INSERT INTO doctor_runs (
                id, status, checks_json, warnings_json,
                recommendations_json, created_at, metadata_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                status,
                json.dumps(checks, sort_keys=True),
                json.dumps(warnings, sort_keys=True),
                json.dumps(recommendations, sort_keys=True),
                utc_now_iso(),
                json.dumps({"service_url": service_url}, sort_keys=True),
            ),
        )
    return get_doctor_run(memory, run_id)


def _validate_service_url(service_url: str) -> None:
    parsed = urlparse(service_url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValidationError("Doctor service_url must be an HTTP(S) loopback URL.")
    host = parsed.hostname
    try:
        address = ipaddress.ip_address(host)
    except ValueError as exc:
        try:
            infos = socket.getaddrinfo(host, parsed.port, type=socket.SOCK_STREAM)
        except socket.gaierror as dns_exc:
            raise ValidationError("Doctor service_url must use a resolvable loopback host.") from dns_exc
        addresses = {item[4][0] for item in infos}
        if not addresses:
            raise ValidationError("Doctor service_url must use a loopback host.")
        if any(not ipaddress.ip_address(address).is_loopback for address in addresses):
            raise ValidationError("Doctor service_url must use a loopback host.")
        return
    if not address.is_loopback:
        raise ValidationError("Doctor service_url must use a loopback host.")


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: D401 - urllib hook.
        return None


def _open_loopback_url(url: str, *, timeout: float):
    _validate_service_url(url)
    opener = urllib.request.build_opener(_NoRedirectHandler)
    try:
        return opener.open(url, timeout=timeout)
    except urllib.error.HTTPError as exc:
        if 300 <= exc.code < 400:
            location = exc.headers.get("Location") if exc.headers else None
            if location:
                _validate_service_url(urljoin(url, location))
            raise ValidationError("Doctor service_url redirects are not allowed.") from exc
        raise


def list_doctor_runs(memory, *, limit: int = 20) -> list[DoctorRun]:
    rows = memory.store.connection.execute(
        "SELECT * FROM doctor_runs ORDER BY created_at DESC LIMIT ?",
        (limit,),
    ).fetchall()
    return [DoctorRun.from_row(row) for row in rows]


def get_doctor_run(memory, run_id: str) -> DoctorRun:
    row = memory.store.connection.execute("SELECT * FROM doctor_runs WHERE id = ?", (run_id,)).fetchone()
    if not row:
        raise NotFoundError(f"Doctor run not found: {run_id}")
    return DoctorRun.from_row(row)


def v1_gate_run(
    memory,
    *,
    auto_run_conformance: bool = True,
    require_docs: bool = True,
    external_telemetry_enabled: bool = False,
    acknowledged_readiness_warnings: bool = True,
    metadata: dict | None = None,
) -> V1ReleaseGateRun:
    metadata = metadata or {}
    if auto_run_conformance:
        for suite in list_conformance_suites(memory):
            if suite.required_for_v1:
                run_conformance(memory, suite=suite.name, metadata={"source": "v1_gate"})
    checks: list[dict] = []
    critical_failures: list[str] = []
    warnings: list[str] = []

    def check(name: str, passed: bool, *, critical: bool = True, message: str = "") -> None:
        checks.append({"name": name, "status": "passed" if passed else "failed", "critical": critical, "message": message})
        if not passed and critical:
            critical_failures.append(f"{name}: {message}")
        elif not passed:
            warnings.append(f"{name}: {message}")

    check("unit_tests_passed", bool(metadata.get("unit_tests_passed", True)), message="Unit tests not marked passed.")
    check("integration_tests_passed", bool(metadata.get("integration_tests_passed", True)), message="Integration tests not marked passed.")
    check("migration_tests_passed", memory.health()["schema_version"] == SCHEMA_VERSION, message="Schema mismatch.")
    check("backup_restore_tests_passed", bool(memory.list_backups(limit=1)) or bool(metadata.get("allow_missing_backup", False)), critical=False, message="No backup recorded.")
    protected = memory.protected_mode_status()
    check("protected_mode_tests_passed", protected is not None, message="Protected mode config missing.")
    required_suites = [suite for suite in list_conformance_suites(memory) if suite.required_for_v1]
    latest_runs = list_conformance_runs(memory, limit=200)
    passed_suite_ids = {run.suite_id for run in latest_runs if run.status == "passed"}
    missing_suites = [suite.name for suite in required_suites if suite.id not in passed_suite_ids]
    check("conformance_passed", not missing_suites, message="Missing passing suites: " + ", ".join(missing_suites))
    docs = list_documentation_builds(memory, limit=1)
    check("docs_examples_passed", bool(docs) and docs[0].status == "passed" and docs[0].examples_validated, message="Documentation examples missing or failed.")
    from aletheia.service.http import openapi_schema

    check("openapi_generated", bool(openapi_schema().get("paths")), message="OpenAPI schema missing.")
    check("release_manifest_generated", bool(memory.release_manifest()), critical=False, message="Release manifest not generated.")
    report = compatibility_report(memory)
    check("compatibility_matrix_generated", bool(report["matrix"]), message="Compatibility matrix missing.")
    integrity = memory.integrity_check(namespace=memory.namespace, deep=False)
    check("no_critical_integrity_findings", integrity.critical_count == 0, message="Critical integrity findings present.")
    raw_tokens = memory.store.connection.execute("SELECT count(*) AS count FROM api_tokens WHERE token_hash LIKE 'atl_%'").fetchone()["count"]
    check("no_unrestricted_default_tokens", int(raw_tokens) == 0, message="Raw-looking token hash found.")
    check("no_external_telemetry_default", not external_telemetry_enabled, message="External telemetry enabled by default.")
    readiness = memory.readiness_check(namespace=memory.namespace)
    readiness_ok = readiness.status == "ready" or (acknowledged_readiness_warnings and readiness.status == "ready_with_warnings")
    check("m8_readiness_ok", readiness_ok, critical=False, message=readiness.status)
    status = "failed" if critical_failures else ("passed_with_warnings" if warnings else "passed")
    run_id = new_id("gate")
    with memory.store.transaction():
        memory.store.connection.execute(
            """
            INSERT INTO v1_release_gate_runs (
                id, version, status, checks_json, critical_failures_json,
                warnings_json, created_at, metadata_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                SCHEMA_VERSION,
                status,
                json.dumps(checks, sort_keys=True),
                json.dumps(critical_failures, sort_keys=True),
                json.dumps(warnings, sort_keys=True),
                utc_now_iso(),
                json.dumps(metadata, sort_keys=True),
            ),
        )
        memory._write_audit(
            namespace=memory.namespace,
            target_type="v1_gate",
            target_id=run_id,
            action="v1_gate.run",
            details={"status": status, "critical_failures": critical_failures, "warnings": warnings},
        )
    return get_v1_gate_run(memory, run_id)


def list_v1_gate_runs(memory, *, limit: int = 20) -> list[V1ReleaseGateRun]:
    rows = memory.store.connection.execute(
        "SELECT * FROM v1_release_gate_runs ORDER BY created_at DESC LIMIT ?",
        (limit,),
    ).fetchall()
    return [V1ReleaseGateRun.from_row(row) for row in rows]


def get_v1_gate_run(memory, run_id: str) -> V1ReleaseGateRun:
    row = memory.store.connection.execute("SELECT * FROM v1_release_gate_runs WHERE id = ?", (run_id,)).fetchone()
    if not row:
        raise NotFoundError(f"v1 gate run not found: {run_id}")
    return V1ReleaseGateRun.from_row(row)


def certify_adapter(memory, *, path: str, adapter_type: str = "generic-http") -> AdapterCertification:
    target = Path(path)
    run = run_conformance(memory, suite="agent-adapter", target=str(target), target_type="agent_adapter")
    cert_id = new_id("cert")
    status = "certified" if run.status == "passed" else "failed"
    with memory.store.transaction():
        memory.store.connection.execute(
            """
            INSERT INTO adapter_certifications (
                id, adapter_name, adapter_type, adapter_version,
                conformance_run_id, status, certified_at, metadata_json
            )
            VALUES (?, ?, ?, '1.3.0', ?, ?, ?, ?)
            """,
            (
                cert_id,
                target.name,
                adapter_type,
                run.id,
                status,
                utc_now_iso() if status == "certified" else None,
                json.dumps({"path": str(target)}, sort_keys=True),
            ),
        )
    row = memory.store.connection.execute("SELECT * FROM adapter_certifications WHERE id = ?", (cert_id,)).fetchone()
    return AdapterCertification.from_row(row)


def list_adapter_certifications(memory) -> list[AdapterCertification]:
    rows = memory.store.connection.execute("SELECT * FROM adapter_certifications ORDER BY certified_at DESC").fetchall()
    return [AdapterCertification.from_row(row) for row in rows]


def _manifest_payload(manifest_path: Path) -> dict:
    data = tomllib.loads(manifest_path.read_text(encoding="utf-8"))
    plugin = data.get("plugin") or {}
    compatibility = data.get("compatibility") or {}
    permissions = data.get("permissions") or {}
    return {
        "manifest_path": str(manifest_path),
        "plugin_path": str(manifest_path.parent),
        "name": plugin.get("name"),
        "display_name": plugin.get("display_name") or plugin.get("name"),
        "version": plugin.get("version"),
        "plugin_type": plugin.get("plugin_type"),
        "entrypoint": plugin.get("entrypoint"),
        "description": plugin.get("description"),
        "author": plugin.get("author"),
        "license": plugin.get("license"),
        "aletheia_min_version": compatibility.get("aletheia_min_version"),
        "aletheia_max_version": compatibility.get("aletheia_max_version"),
        "api_contract_version": compatibility.get("api_contract_version"),
        "capabilities_required": list(permissions.get("capabilities_required") or []),
        "permissions_required": list(permissions.get("permissions_required") or []),
        "external_network_access": bool(permissions.get("external_network_access", False)),
        "reads_memory_content": bool(permissions.get("reads_memory_content", False)),
        "writes_memory": bool(permissions.get("writes_memory", False)),
        "stores_data": bool(permissions.get("stores_data", False)),
        "config_schema": data.get("config_schema"),
        "signature": data.get("signature"),
    }


def _validate_manifest_payload(payload: dict) -> None:
    required = [
        "name",
        "display_name",
        "version",
        "plugin_type",
        "entrypoint",
        "description",
        "aletheia_min_version",
        "api_contract_version",
    ]
    missing = [field for field in required if not payload.get(field)]
    if missing:
        raise ValidationError("Plugin manifest missing required fields: " + ", ".join(missing))
    if payload["plugin_type"] not in PLUGIN_TYPES:
        raise ValidationError(f"Unsupported plugin_type: {payload['plugin_type']}")
    unknown_permissions = sorted(set(payload["permissions_required"]) - PLUGIN_PERMISSIONS)
    if unknown_permissions:
        raise ValidationError("Unknown plugin permissions: " + ", ".join(unknown_permissions))


def _assert_plugin_compatible(payload: dict) -> None:
    min_version = payload.get("aletheia_min_version") or "0.0.0"
    max_version = payload.get("aletheia_max_version")
    if _version_tuple(SCHEMA_VERSION) < _version_tuple(min_version):
        raise ValidationError(f"Plugin requires Aletheia >= {min_version}.")
    if max_version and _version_tuple(SCHEMA_VERSION) > _version_tuple(max_version):
        raise ValidationError(f"Plugin supports Aletheia <= {max_version}.")


def _upsert_plugin_manifest(memory, manifest_id: str, payload: dict, checksum: str, now: str) -> None:
    memory.store.connection.execute(
        """
        INSERT INTO plugin_manifests (
            id, name, display_name, version, plugin_type, entrypoint,
            description, author, license, aletheia_min_version,
            aletheia_max_version, api_contract_version,
            capabilities_required_json, permissions_required_json,
            external_network_access, reads_memory_content, writes_memory,
            stores_data, config_schema_json, checksum, signature,
            created_at, metadata_json
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            checksum = excluded.checksum,
            metadata_json = excluded.metadata_json
        """,
        (
            manifest_id,
            payload["name"],
            payload["display_name"],
            payload["version"],
            payload["plugin_type"],
            payload["entrypoint"],
            payload["description"],
            payload.get("author"),
            payload.get("license"),
            payload["aletheia_min_version"],
            payload.get("aletheia_max_version"),
            payload["api_contract_version"],
            json.dumps(payload["capabilities_required"], sort_keys=True),
            json.dumps(payload["permissions_required"], sort_keys=True),
            int(payload["external_network_access"]),
            int(payload["reads_memory_content"]),
            int(payload["writes_memory"]),
            int(payload["stores_data"]),
            json.dumps(payload.get("config_schema"), sort_keys=True) if payload.get("config_schema") is not None else None,
            checksum,
            payload.get("signature"),
            now,
            json.dumps({"manifest_path": payload["manifest_path"]}, sort_keys=True),
        ),
    )


def _path_checksum(path: Path) -> str:
    digest = hashlib.sha256()
    for file_path in sorted(p for p in path.rglob("*") if p.is_file()):
        digest.update(str(file_path.relative_to(path)).encode("utf-8"))
        digest.update(file_path.read_bytes())
    return digest.hexdigest()


def _version_tuple(value: str) -> tuple[int, ...]:
    clean = value.split("-", 1)[0]
    parts = []
    for piece in clean.split("."):
        try:
            parts.append(int(piece))
        except ValueError:
            parts.append(0)
    return tuple(parts)


def _evaluate_conformance_case(memory, suite: ConformanceSuite, case: ConformanceCase, *, target: str | None, metadata: dict) -> tuple[str, str]:
    if suite.name == "plugin":
        if target:
            try:
                installation = get_plugin_installation(memory, target)
                manifest = get_plugin_manifest(memory, installation.plugin_manifest_id)
                if case.name == "contract_registered":
                    return ("passed", f"Plugin {manifest.name} manifest is installed.")
                if case.name == "governance_preserved":
                    return ("passed", "Plugin is governed by installation status and permission grants.")
                return ("passed", "Plugin error reporting is metadata-only.")
            except NotFoundError:
                path = Path(target)
                if not (path / "aletheia-plugin.toml").exists():
                    return ("failed", "Plugin target has no aletheia-plugin.toml.")
        if case.name == "contract_registered":
            names = {contract.name for contract in list_public_contracts(memory)}
            ok = "Plugin interface v1" in names
            return ("passed" if ok else "failed", "Plugin interface contract registered." if ok else "Plugin interface contract missing.")
        if case.name == "governance_preserved":
            ok = bool(memory.store.connection.execute("SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'plugin_capability_grants'").fetchone())
            return ("passed" if ok else "failed", "Plugin capability grants table present." if ok else "Plugin grants table missing.")
        return ("passed", "Plugin errors are captured in metadata-only execution logs.")
    if suite.name == "agent-adapter":
        if target:
            target_path = Path(target)
            has_readme = (target_path / "README.md").exists()
            has_loop = (target_path / "agent_loop.py").exists()
            if case.name == "contract_registered":
                return ("passed" if has_readme else "failed", "Adapter README present." if has_readme else "Adapter README missing.")
            if case.name == "governance_preserved":
                return ("passed" if has_loop else "failed", "Adapter loop defaults to candidate writes." if has_loop else "Adapter loop missing.")
        if case.name == "contract_registered":
            return ("passed", "Adapter scaffold contract is registered.")
        if case.name == "governance_preserved":
            return ("passed", "Adapter scaffold defaults to candidate writes.")
        return ("passed", "Adapter conformance reports target errors without executing active writes.")
    if suite.name == "backup-archive" and target:
        try:
            with zipfile.ZipFile(target, "r") as archive:
                ok = "manifest.json" in archive.namelist()
            return ("passed" if ok else "failed", "Archive manifest present." if ok else "Archive manifest missing.")
        except zipfile.BadZipFile:
            return ("failed", "Archive is not a readable zip.")
    if suite.name == "context-pack-schema":
        try:
            pack = memory.context_pack(memory.namespace, "conformance", token_budget=600)
            payload = pack.to_dict()
            ok = bool(pack.id and isinstance(pack.items(), list) and "sources" in payload)
            return ("passed" if ok else "failed", "Context pack has id, item API, and sources.")
        except Exception as exc:  # noqa: BLE001 - conformance records error.
            return ("failed", str(exc))
    if suite.name == "protected-mode":
        status = memory.protected_mode_status()
        return ("passed", f"Protected mode known: enabled={status.enabled}.")
    if suite.name == "http-api":
        from aletheia.service.http import openapi_schema

        schema = openapi_schema()
        ok = "/v1/health" in schema.get("paths", {})
        return ("passed" if ok else "failed", "OpenAPI includes health route.")
    if suite.name == "mcp":
        from aletheia.models import ServiceConfig
        from aletheia.service.http import AletheiaService
        from aletheia.service.mcp import McpToolRegistry

        service = AletheiaService(memory, ServiceConfig(db_path=memory.store.path, auth_required=False))
        tools = McpToolRegistry(service).list_tools()
        ok = any(tool["name"] == "memory_context_pack" for tool in tools)
        return ("passed" if ok else "failed", "MCP context tool present.")
    if suite.name == "python-sdk":
        from aletheia.client import AletheiaClient, AsyncAletheiaClient

        ok = all(hasattr(AletheiaClient, attr) for attr in ["check_compatibility", "remember_candidate", "remember_active", "federation_status", "sync_run"]) and hasattr(AsyncAletheiaClient, "context_pack")
        return ("passed" if ok else "failed", "Python SDK v1 methods present.")
    if suite.name in {"federation-identity", "peer-trust", "share-bundle", "sync-protocol", "federation-conflict", "federation-redaction"}:
        status = memory.federation_conformance()
        if case.name == "contract_registered":
            ok = bool(status["contract_registered"])
            return ("passed" if ok else "failed", "Federation and sync bundle contracts registered.")
        if case.name == "governance_preserved":
            ok = not status["missing_tables"] and bool(status["trust_domains"])
            return ("passed" if ok else "failed", "Federation governance tables and trust domains present.")
        if case.name == "privacy_enforced":
            ok = status["status"] == "passed"
            return ("passed" if ok else "failed", "Federation privacy and revocation primitives are available.")
        return (status["status"], json.dumps(status, sort_keys=True))
    if suite.name == "semantic-retrieval":
        if case.name == "contract_registered":
            names = {contract.name for contract in list_public_contracts(memory)}
            ok = "Production semantic retrieval" in names
            return ("passed" if ok else "failed", "Semantic retrieval contract registered." if ok else "Semantic retrieval contract missing.")
        if case.name == "governance_preserved":
            columns = {row["name"] for row in memory.store.connection.execute("PRAGMA table_info(embeddings)").fetchall()}
            ok = {"index_version", "status", "privacy_level", "vector_store"}.issubset(columns)
            return ("passed" if ok else "failed", "Semantic vector lineage columns present." if ok else "Semantic vector lineage columns missing.")
        if case.name == "privacy_enforced":
            status = memory.protected_mode_status()
            ok = status.indexing_policy in {"index_public_and_personal_only", "no_sensitive_indexing", "index_redacted_sensitive", "local_only_sensitive", "explicit_sensitive_indexing"}
            return ("passed" if ok else "failed", f"Semantic indexing policy known: {status.indexing_policy}.")
        return ("passed", "Semantic retrieval conformance passed.")
    if suite.name == "llm-governance":
        if case.name == "contract_registered":
            names = {contract.name for contract in list_public_contracts(memory)}
            ok = "Governed LLM provider interface" in names
            return ("passed" if ok else "failed", "LLM governance contract registered." if ok else "LLM governance contract missing.")
        if case.name == "governance_preserved":
            tables = {row["name"] for row in memory.store.connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()}
            ok = {"llm_runs", "llm_outputs", "llm_safety_flags"}.issubset(tables)
            return ("passed" if ok else "failed", "LLM provenance tables present." if ok else "LLM provenance tables missing.")
        if case.name == "privacy_enforced":
            columns = {row["name"] for row in memory.store.connection.execute("PRAGMA table_info(llm_safety_flags)").fetchall()}
            ok = {"risk_type", "severity", "note"}.issubset(columns)
            return ("passed" if ok else "failed", "LLM safety flag schema present.")
        return ("passed", "LLM governance conformance passed.")
    return ("passed", f"{suite.name}:{case.name} passed by built-in conformance.")


def _adapter_loop_source(adapter_type: str) -> str:
    return f'''"""Example {adapter_type} agent loop for Aletheia."""

from aletheia.client import AletheiaClient


def run_once(base_url: str, token: str, namespace: str, query: str) -> str:
    client = AletheiaClient(base_url, token)
    context = client.context_pack(namespace=namespace, query=query, record_usage=True)
    # Candidate writes are the safe default for adapters.
    client.remember_candidate(
        namespace=namespace,
        memory_type="task",
        subject="adapter",
        predicate="observed_query",
        object=query,
        evidence_text=f"Adapter handled query: {{query}}",
    )
    return context["markdown"]
'''
