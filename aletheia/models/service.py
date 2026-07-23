"""Local service, auth, request-log, console, and adapter models."""

from __future__ import annotations

import json
import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path


def _json(value: str | None, default):
    if value is None:
        return default
    return json.loads(value)


@dataclass(frozen=True)
class ApiClient:
    id: str
    name: str
    client_type: str
    status: str
    created_at: str
    metadata: dict = field(default_factory=dict)

    @classmethod
    def from_row(cls, row) -> "ApiClient":
        return cls(
            id=row["id"],
            name=row["name"],
            client_type=row["client_type"],
            status=row["status"],
            created_at=row["created_at"],
            metadata=_json(row["metadata_json"], {}),
        )


@dataclass(frozen=True)
class ApiToken:
    id: str
    client_id: str
    token_prefix: str
    token_hash: str
    status: str
    privacy_ceiling: str
    expires_at: str | None
    created_at: str
    revoked_at: str | None
    capabilities: list[str] = field(default_factory=list)
    namespace_grants: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    @classmethod
    def from_row(
        cls,
        row,
        *,
        capabilities: list[str] | None = None,
        namespace_grants: list[str] | None = None,
    ) -> "ApiToken":
        return cls(
            id=row["id"],
            client_id=row["client_id"],
            token_prefix=row["token_prefix"],
            token_hash=row["token_hash"],
            status=row["status"],
            privacy_ceiling=row["privacy_ceiling"],
            expires_at=row["expires_at"],
            created_at=row["created_at"],
            revoked_at=row["revoked_at"],
            capabilities=capabilities or [],
            namespace_grants=namespace_grants or [],
            metadata=_json(row["metadata_json"], {}),
        )


@dataclass(frozen=True)
class AgentRegistration:
    id: str
    namespace: str
    name: str
    agent_type: str | None
    client_id: str | None
    default_project_id: str | None
    status: str
    created_at: str
    updated_at: str
    metadata: dict = field(default_factory=dict)

    @classmethod
    def from_row(cls, row) -> "AgentRegistration":
        return cls(
            id=row["id"],
            namespace=row["namespace"],
            name=row["name"],
            agent_type=row["agent_type"],
            client_id=row["client_id"],
            default_project_id=row["default_project_id"],
            status=row["status"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            metadata=_json(row["metadata_json"], {}),
        )


@dataclass(frozen=True)
class ServiceRequestLog:
    id: str
    request_id: str
    client_id: str | None
    agent_id: str | None
    namespace: str | None
    method: str
    path: str
    status_code: int
    duration_ms: int | None
    request_hash: str | None
    response_hash: str | None
    log_mode: str
    created_at: str
    metadata: dict = field(default_factory=dict)

    @classmethod
    def from_row(cls, row) -> "ServiceRequestLog":
        return cls(
            id=row["id"],
            request_id=row["request_id"],
            client_id=row["client_id"],
            agent_id=row["agent_id"],
            namespace=row["namespace"],
            method=row["method"],
            path=row["path"],
            status_code=row["status_code"],
            duration_ms=row["duration_ms"],
            request_hash=row["request_hash"],
            response_hash=row["response_hash"],
            log_mode=row["log_mode"],
            created_at=row["created_at"],
            metadata=_json(row["metadata_json"], {}),
        )


@dataclass(frozen=True)
class McpToolInvocationLog:
    id: str
    request_id: str
    client_id: str | None
    tool_name: str
    namespace: str | None
    status: str
    duration_ms: int | None
    input_hash: str | None
    output_hash: str | None
    created_at: str
    metadata: dict = field(default_factory=dict)

    @classmethod
    def from_row(cls, row) -> "McpToolInvocationLog":
        return cls(
            id=row["id"],
            request_id=row["request_id"],
            client_id=row["client_id"],
            tool_name=row["tool_name"],
            namespace=row["namespace"],
            status=row["status"],
            duration_ms=row["duration_ms"],
            input_hash=row["input_hash"],
            output_hash=row["output_hash"],
            created_at=row["created_at"],
            metadata=_json(row["metadata_json"], {}),
        )


@dataclass(frozen=True)
class ServiceConfig:
    db_path: str = "./aletheia.db"
    host: str = "127.0.0.1"
    port: int = 8765
    api_prefix: str = "/v1"
    auto_migrate: bool = False
    auth_required: bool = True
    allow_remote: bool = False
    default_privacy_ceiling: str = "personal"
    request_log_mode: str = "metadata_only"
    mcp_default_namespace: str = "user/default"
    mcp_default_mode: str = "read_write_candidate"
    worker_enabled: bool = False
    max_jobs_per_tick: int = 10
    max_request_bytes: int = 1_048_576
    default_page_size: int = 50
    max_page_size: int = 200
    rate_limit_per_minute: int = 120
    rate_limit_enabled: bool = True
    trust_proxy_headers: bool = False
    console_enabled: bool = False
    console_session_ttl_minutes: int = 60

    @classmethod
    def load(
        cls,
        config_path: str | None = None,
        *,
        overrides: dict | None = None,
    ) -> "ServiceConfig":
        path = config_path or os.environ.get("ALETHEIA_CONFIG")
        data: dict = {}
        if path:
            data = tomllib.loads(Path(path).read_text(encoding="utf-8"))

        server = data.get("server", {})
        auth = data.get("auth", {})
        security = data.get("security", {})
        mcp = data.get("mcp", {})
        jobs = data.get("jobs", {})
        limits = data.get("limits", {})

        values = {
            "db_path": server.get("db", "./aletheia.db"),
            "host": server.get("host", "127.0.0.1"),
            "port": int(server.get("port", 8765)),
            "api_prefix": server.get("api_prefix", "/v1"),
            "auto_migrate": _bool(server.get("auto_migrate", False)),
            "auth_required": _bool(auth.get("required", True)),
            "allow_remote": _bool(security.get("allow_remote", False)),
            "default_privacy_ceiling": security.get("default_privacy_ceiling", "personal"),
            "request_log_mode": security.get("request_log_mode", "metadata_only"),
            "mcp_default_namespace": mcp.get("default_namespace", "user/default"),
            "mcp_default_mode": mcp.get("default_mode", "read_write_candidate"),
            "worker_enabled": _bool(jobs.get("worker_enabled", False)),
            "max_jobs_per_tick": int(jobs.get("max_jobs_per_tick", 10)),
            "max_request_bytes": int(limits.get("max_request_bytes", 1_048_576)),
            "default_page_size": int(limits.get("default_page_size", 50)),
            "max_page_size": int(limits.get("max_page_size", 200)),
            "rate_limit_per_minute": int(limits.get("rate_limit_per_minute", 120)),
            "rate_limit_enabled": _bool(limits.get("rate_limit_enabled", True)),
            "trust_proxy_headers": _bool(security.get("trust_proxy_headers", False)),
            "console_enabled": _bool(data.get("console", {}).get("enabled", False)),
            "console_session_ttl_minutes": int(data.get("console", {}).get("session_ttl_minutes", 60)),
        }

        env_map = {
            "ALETHEIA_DB": ("db_path", str),
            "ALETHEIA_HOST": ("host", str),
            "ALETHEIA_PORT": ("port", int),
            "ALETHEIA_AUTH_REQUIRED": ("auth_required", _bool),
        }
        for env_name, (key, parser) in env_map.items():
            if env_name in os.environ:
                values[key] = parser(os.environ[env_name])

        for key, value in (overrides or {}).items():
            if value is not None:
                values[key] = value
        return cls(**values)

    def redacted(self) -> dict:
        return {
            "server": {
                "host": self.host,
                "port": self.port,
                "db": self.db_path,
                "api_prefix": self.api_prefix,
                "auto_migrate": self.auto_migrate,
            },
            "auth": {"required": self.auth_required},
            "security": {
                "allow_remote": self.allow_remote,
                "default_privacy_ceiling": self.default_privacy_ceiling,
                "request_log_mode": self.request_log_mode,
                "trust_proxy_headers": self.trust_proxy_headers,
            },
            "mcp": {
                "default_namespace": self.mcp_default_namespace,
                "default_mode": self.mcp_default_mode,
            },
            "jobs": {
                "worker_enabled": self.worker_enabled,
                "max_jobs_per_tick": self.max_jobs_per_tick,
            },
            "limits": {
                "max_request_bytes": self.max_request_bytes,
                "default_page_size": self.default_page_size,
                "max_page_size": self.max_page_size,
                "rate_limit_per_minute": self.rate_limit_per_minute,
                "rate_limit_enabled": self.rate_limit_enabled,
            },
            "console": {
                "enabled": self.console_enabled,
                "session_ttl_minutes": self.console_session_ttl_minutes,
            },
        }


@dataclass(frozen=True)
class ServiceHealth:
    status: str
    schema_version: str
    service_version: str
    database: str = "connected"
    auth_required: bool = True
    warnings: list[str] = field(default_factory=list)


def _bool(value) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)
