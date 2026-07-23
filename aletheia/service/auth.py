"""Authentication, token, namespace, and privacy enforcement for M6."""

from __future__ import annotations

import json
import secrets
from dataclasses import dataclass

from aletheia.core.crypto import (
    PBKDF2_ITERATIONS,
    PBKDF2_SECRET_HASH_ALGORITHM,
    hash_secret,
    verify_secret_hash,
)
from aletheia.core.ids import content_hash, new_id
from aletheia.core.time import parse_iso, utc_now, utc_now_iso
from aletheia.models import ApiClient, ApiToken
from aletheia.service.errors import forbidden, unauthorized, validation_error


CAPABILITIES = {
    "memory:read",
    "memory:context",
    "memory:write_candidate",
    "memory:write_active",
    "memory:ingest",
    "memory:extract",
    "memory:review",
    "memory:feedback",
    "memory:audit",
    "memory:admin",
    "memory:jobs",
    "memory:evaluate",
    "memory:learn",
    "memory:policy",
    "memory:delete",
    "memory:federation",
    "memory:peers",
    "memory:share",
    "memory:sync",
    "memory:workspace",
    "memory:remote_write",
    "memory:remote_admin",
    "memory:share_sensitive",
    "memory:remote_active_write",
    "memory:revoke_peer",
    "memory:sync_secret",
}

DEFAULT_LOCAL_AGENT_CAPABILITIES = [
    "memory:read",
    "memory:context",
    "memory:write_candidate",
    "memory:feedback",
    "memory:audit",
]
DEFAULT_TOKENLESS_NAMESPACE_GRANTS = ["user/default"]
DEFAULT_TOKENLESS_PRIVACY_CEILING = "personal"
PBKDF2_TOKEN_HASH_ALGORITHM = PBKDF2_SECRET_HASH_ALGORITHM
PBKDF2_TOKEN_HASH_ITERATIONS = PBKDF2_ITERATIONS

CLIENT_TYPES = {"agent", "cli", "mcp", "sdk", "admin", "worker", "test", "unknown"}
PRIVACY_ORDER = {"public": 0, "personal": 1, "private": 2, "sensitive": 2, "secret": 3}


@dataclass(frozen=True)
class AuthContext:
    token: ApiToken | None
    client: ApiClient | None
    auth_required: bool = True
    default_capabilities: tuple[str, ...] = tuple(DEFAULT_LOCAL_AGENT_CAPABILITIES)
    default_namespace_grants: tuple[str, ...] = tuple(DEFAULT_TOKENLESS_NAMESPACE_GRANTS)
    default_privacy_ceiling: str = DEFAULT_TOKENLESS_PRIVACY_CEILING

    @property
    def client_id(self) -> str | None:
        return self.client.id if self.client else None

    @property
    def token_id(self) -> str | None:
        return self.token.id if self.token else None

    @property
    def capabilities(self) -> list[str]:
        return self.token.capabilities if self.token else list(self.default_capabilities)

    @property
    def namespace_grants(self) -> list[str]:
        return self.token.namespace_grants if self.token else list(self.default_namespace_grants)

    @property
    def privacy_ceiling(self) -> str:
        return self.token.privacy_ceiling if self.token else self.default_privacy_ceiling


class AuthService:
    def __init__(self, memory):
        self.memory = memory
        self.connection = memory.store.connection

    def create_client(
        self,
        *,
        name: str,
        client_type: str = "agent",
        metadata: dict | None = None,
    ) -> ApiClient:
        if client_type not in CLIENT_TYPES:
            raise validation_error(f"Unknown client_type: {client_type}")
        client_id = new_id("cli")
        with self.connection:
            self.connection.execute(
                """
                INSERT INTO api_clients (id, name, client_type, status, created_at, metadata_json)
                VALUES (?, ?, ?, 'active', ?, ?)
                """,
                (
                    client_id,
                    name,
                    client_type,
                    utc_now_iso(),
                    json.dumps(metadata or {}, sort_keys=True),
                ),
            )
        return self.get_client(client_id)

    def get_client(self, client_id: str) -> ApiClient:
        row = self.connection.execute("SELECT * FROM api_clients WHERE id = ?", (client_id,)).fetchone()
        if not row:
            raise validation_error(f"API client not found: {client_id}")
        return ApiClient.from_row(row)

    def list_clients(self, *, include_disabled: bool = False) -> list[ApiClient]:
        clause = "" if include_disabled else "WHERE status != 'disabled'"
        rows = self.connection.execute(
            f"SELECT * FROM api_clients {clause} ORDER BY created_at DESC"
        ).fetchall()
        return [ApiClient.from_row(row) for row in rows]

    def disable_client(self, client_id: str) -> ApiClient:
        self.get_client(client_id)
        with self.connection:
            self.connection.execute(
                "UPDATE api_clients SET status = 'disabled' WHERE id = ?",
                (client_id,),
            )
        return self.get_client(client_id)

    def create_token(
        self,
        *,
        client_id: str,
        namespace_grants: list[str],
        capabilities: list[str] | None = None,
        privacy_ceiling: str = "personal",
        expires_at: str | None = None,
        metadata: dict | None = None,
    ) -> tuple[ApiToken, str]:
        client = self.get_client(client_id)
        if client.status != "active":
            raise validation_error("Client must be active to create a token.")
        capabilities = capabilities or DEFAULT_LOCAL_AGENT_CAPABILITIES
        unknown = [capability for capability in capabilities if capability not in CAPABILITIES]
        if unknown:
            raise validation_error(f"Unknown capabilities: {', '.join(unknown)}")
        if privacy_ceiling not in PRIVACY_ORDER:
            raise validation_error(f"Unknown privacy ceiling: {privacy_ceiling}")
        if not namespace_grants:
            raise validation_error("At least one namespace grant is required.")
        raw_token = "atl_" + secrets.token_urlsafe(32)
        token_hash = self.hash_token(raw_token)
        token_id = new_id("tok")
        token_prefix = raw_token[:12]
        now = utc_now_iso()
        with self.connection:
            self.connection.execute(
                """
                INSERT INTO api_tokens (
                    id, client_id, token_prefix, token_hash, status,
                    privacy_ceiling, expires_at, created_at, metadata_json
                )
                VALUES (?, ?, ?, ?, 'active', ?, ?, ?, ?)
                """,
                (
                    token_id,
                    client_id,
                    token_prefix,
                    token_hash,
                    privacy_ceiling,
                    expires_at,
                    now,
                    json.dumps(metadata or {}, sort_keys=True),
                ),
            )
            for capability in sorted(set(capabilities)):
                self.connection.execute(
                    """
                    INSERT OR IGNORE INTO capability_grants (id, token_id, capability, created_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        "cap_" + content_hash(f"{token_id}\0{capability}")[:24],
                        token_id,
                        capability,
                        now,
                    ),
                )
            for namespace in sorted(set(namespace_grants)):
                self.connection.execute(
                    """
                    INSERT OR IGNORE INTO namespace_access_grants (
                        id, token_id, namespace, access_level, created_at
                    )
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        "nsg_" + content_hash(f"{token_id}\0{namespace}")[:24],
                        token_id,
                        namespace,
                        self._access_level_for_capabilities(capabilities),
                        now,
                    ),
                )
        return self.get_token(token_id), raw_token

    def revoke_token(self, token_id: str, *, reason: str | None = None) -> ApiToken:
        self.get_token(token_id)
        with self.connection:
            self.connection.execute(
                """
                UPDATE api_tokens
                SET status = 'revoked', revoked_at = ?, metadata_json = ?
                WHERE id = ?
                """,
                (
                    utc_now_iso(),
                    json.dumps({"revoke_reason": reason} if reason else {}, sort_keys=True),
                    token_id,
                ),
            )
        return self.get_token(token_id)

    def get_token(self, token_id: str) -> ApiToken:
        row = self.connection.execute("SELECT * FROM api_tokens WHERE id = ?", (token_id,)).fetchone()
        if not row:
            raise validation_error(f"API token not found: {token_id}")
        return ApiToken.from_row(
            row,
            capabilities=self._capabilities_for_token(token_id),
            namespace_grants=self._namespaces_for_token(token_id),
        )

    def list_tokens(self, *, include_inactive: bool = False) -> list[ApiToken]:
        clause = "" if include_inactive else "WHERE status = 'active'"
        rows = self.connection.execute(
            f"SELECT * FROM api_tokens {clause} ORDER BY created_at DESC"
        ).fetchall()
        return [
            ApiToken.from_row(
                row,
                capabilities=self._capabilities_for_token(row["id"]),
                namespace_grants=self._namespaces_for_token(row["id"]),
            )
            for row in rows
        ]

    def authenticate(
        self,
        raw_token: str | None,
        *,
        auth_required: bool = True,
        default_capabilities: list[str] | None = None,
        default_namespace_grants: list[str] | None = None,
        default_privacy_ceiling: str = DEFAULT_TOKENLESS_PRIVACY_CEILING,
    ) -> AuthContext:
        if not auth_required:
            return AuthContext(
                token=None,
                client=None,
                auth_required=False,
                default_capabilities=tuple(default_capabilities or DEFAULT_LOCAL_AGENT_CAPABILITIES),
                default_namespace_grants=tuple(default_namespace_grants or DEFAULT_TOKENLESS_NAMESPACE_GRANTS),
                default_privacy_ceiling=default_privacy_ceiling,
            )
        if not raw_token:
            raise unauthorized()
        raw_token = raw_token.removeprefix("Bearer ").strip()
        prefix = raw_token[:12]
        rows = self.connection.execute(
            "SELECT * FROM api_tokens WHERE token_prefix = ?",
            (prefix,),
        ).fetchall()
        for row in rows:
            if not self.verify_secret_hash(raw_token, row["token_hash"]):
                continue
            token = self.get_token(row["id"])
            if token.status != "active":
                raise unauthorized("Token is not active.")
            if token.expires_at and parse_iso(token.expires_at) and parse_iso(token.expires_at) <= utc_now():
                with self.connection:
                    self.connection.execute(
                        "UPDATE api_tokens SET status = 'expired' WHERE id = ?",
                        (token.id,),
                    )
                raise unauthorized("Token is expired.")
            client = self.get_client(token.client_id)
            if client.status != "active":
                raise unauthorized("Client is not active.")
            return AuthContext(token=token, client=client, auth_required=True)
        raise unauthorized("Invalid token.")

    def require_capability(self, context: AuthContext, capability: str) -> None:
        if capability not in CAPABILITIES:
            raise validation_error(f"Unknown capability: {capability}")
        if capability in context.capabilities or "memory:admin" in context.capabilities:
            return
        raise forbidden(f"Capability required: {capability}", {"required_capability": capability})

    def require_namespace(
        self,
        context: AuthContext,
        *,
        namespace: str,
        project_id: str | None = None,
    ) -> None:
        if "*" in context.namespace_grants:
            return
        for grant in context.namespace_grants:
            if grant == namespace or namespace.startswith(grant + "/"):
                return
            marker = "/projects/"
            if marker in grant:
                grant_namespace, grant_project = grant.split(marker, 1)
                if namespace == grant_namespace and project_id == grant_project:
                    return
        raise forbidden("Token does not grant access to this namespace.")

    def privacy_allows(self, context: AuthContext, privacy_level: str | None) -> bool:
        level = privacy_level or "personal"
        return PRIVACY_ORDER.get(level, 1) <= PRIVACY_ORDER.get(context.privacy_ceiling, 1)

    @staticmethod
    def hash_token(raw_token: str) -> str:
        return AuthService.hash_secret(raw_token)

    @staticmethod
    def hash_secret(value: str) -> str:
        return hash_secret(value)

    @staticmethod
    def verify_token_hash(raw_token: str, stored_hash: str) -> bool:
        return AuthService.verify_secret_hash(raw_token, stored_hash)

    @staticmethod
    def verify_secret_hash(value: str, stored_hash: str | None) -> bool:
        return verify_secret_hash(value, stored_hash)

    def _capabilities_for_token(self, token_id: str) -> list[str]:
        rows = self.connection.execute(
            "SELECT capability FROM capability_grants WHERE token_id = ? ORDER BY capability",
            (token_id,),
        ).fetchall()
        return [row["capability"] for row in rows]

    def _namespaces_for_token(self, token_id: str) -> list[str]:
        rows = self.connection.execute(
            "SELECT namespace FROM namespace_access_grants WHERE token_id = ? ORDER BY namespace",
            (token_id,),
        ).fetchall()
        return [row["namespace"] for row in rows]

    @staticmethod
    def _access_level_for_capabilities(capabilities: list[str]) -> str:
        if "memory:admin" in capabilities:
            return "admin"
        if "memory:review" in capabilities:
            return "review"
        if "memory:write_active" in capabilities:
            return "write_active"
        if "memory:write_candidate" in capabilities:
            return "write_candidate"
        if "memory:context" in capabilities:
            return "context"
        return "read"
