from __future__ import annotations

import asyncio
import hashlib
import io
import json
import socket
import sqlite3
import threading
import urllib.error
from dataclasses import asdict

import pytest

from aletheia import Memory
from aletheia.adapters import HttpAgentMemoryAdapter
from aletheia.client import (
    AletheiaClient,
    AletheiaForbiddenError,
    AletheiaValidationError,
    AsyncAletheiaClient,
)
from aletheia.models import ServiceConfig
from aletheia.service.auth import AuthService, DEFAULT_LOCAL_AGENT_CAPABILITIES
from aletheia.service.errors import ServiceError
from aletheia.service.http import AletheiaDaemon, AletheiaService, openapi_schema
from aletheia.service.mcp import McpToolRegistry


NAMESPACE = "user/default"


def _service(
    tmp_path,
    *,
    capabilities: list[str] | None = None,
    namespaces: list[str] | None = None,
    privacy_ceiling: str = "personal",
    rate_limit_per_minute: int = 120,
    auth_required: bool = True,
) -> tuple[AletheiaService, str | None]:
    db_path = str(tmp_path / "aletheia.db")
    memory = Memory.open(db_path, namespace=NAMESPACE)
    config = ServiceConfig(
        db_path=db_path,
        auto_migrate=True,
        auth_required=auth_required,
        rate_limit_per_minute=rate_limit_per_minute,
    )
    service = AletheiaService(memory, config)
    if not auth_required:
        return service, None
    auth = AuthService(memory)
    client = auth.create_client(name="local-agent", client_type="agent")
    _token, raw = auth.create_token(
        client_id=client.id,
        namespace_grants=namespaces or [NAMESPACE],
        capabilities=capabilities or DEFAULT_LOCAL_AGENT_CAPABILITIES,
        privacy_ceiling=privacy_ceiling,
    )
    return service, raw


def _json(payload: dict) -> bytes:
    return json.dumps(payload).encode("utf-8")


def _post(service: AletheiaService, path: str, token: str | None, payload: dict, **headers):
    request_headers = {"X-Request-ID": "req_unit"}
    if token:
        request_headers["Authorization"] = f"Bearer {token}"
    request_headers.update(headers)
    return service.handle_http(method="POST", path=path, headers=request_headers, body=_json(payload))


def _get(service: AletheiaService, path: str, token: str | None = None, **headers):
    request_headers = {"X-Request-ID": "req_unit"}
    if token:
        request_headers["Authorization"] = f"Bearer {token}"
    request_headers.update(headers)
    return service.handle_http(method="GET", path=path, headers=request_headers)


def _remember_payload(**overrides) -> dict:
    payload = {
        "namespace": NAMESPACE,
        "write_mode": "candidate",
        "memory_type": "preference",
        "subject": "user",
        "predicate": "prefers_m6_testing",
        "object": "contract-driven service scorecards",
        "evidence_text": "The user asked for live tests after each milestone.",
    }
    payload.update(overrides)
    return payload


def test_m6_migration_adds_service_tables_without_tokens_or_daemons(tmp_path):
    db_path = str(tmp_path / "migrate.db")
    memory = Memory.open(db_path, namespace=NAMESPACE)
    try:
        claim = memory.remember(
            namespace=NAMESPACE,
            memory_type="preference",
            subject="user",
            predicate="prefers_validation",
            object="live scorecards",
        )
        memory.store.migrate()
        health = memory.health()
        assert health["schema_version"] == "1.3.0"
        names = {
            row["name"]
            for row in memory.store.connection.execute(
                "SELECT name FROM sqlite_master WHERE type IN ('table', 'virtual table')"
            ).fetchall()
        }
        assert {
            "api_clients",
            "api_tokens",
            "agent_registrations",
            "namespace_access_grants",
            "capability_grants",
            "service_request_log",
            "mcp_tool_invocation_log",
            "idempotency_records",
            "rate_limit_records",
            "service_config_history",
            "service_instance_log",
        }.issubset(names)
        assert memory.retrieve(NAMESPACE, "live scorecards")[0].claim_id == claim.id
        assert memory.store.connection.execute("SELECT count(*) AS count FROM api_tokens").fetchone()["count"] == 0
        assert memory.store.connection.execute("SELECT count(*) AS count FROM api_clients").fetchone()["count"] == 0
        assert memory.store.connection.execute("SELECT count(*) AS count FROM service_instance_log").fetchone()["count"] == 0
    finally:
        memory.close()


def test_service_config_loads_toml_and_environment(monkeypatch, tmp_path):
    config_path = tmp_path / "aletheia.toml"
    config_path.write_text(
        """
[server]
host = "127.0.0.1"
port = 8766
db = "from-file.db"
auto_migrate = true
[auth]
required = false
[security]
default_privacy_ceiling = "public"
request_log_mode = "hashes"
[mcp]
default_namespace = "user/file"
default_mode = "read_only"
[jobs]
worker_enabled = true
max_jobs_per_tick = 3
[limits]
rate_limit_per_minute = 9
""",
        encoding="utf-8",
    )
    monkeypatch.setenv("ALETHEIA_DB", "from-env.db")
    monkeypatch.setenv("ALETHEIA_PORT", "8777")
    monkeypatch.setenv("ALETHEIA_AUTH_REQUIRED", "true")

    config = ServiceConfig.load(str(config_path), overrides={"host": "localhost"})

    assert config.db_path == "from-env.db"
    assert config.host == "localhost"
    assert config.port == 8777
    assert config.auth_required is True
    assert config.auto_migrate is True
    assert config.request_log_mode == "hashes"
    assert config.trust_proxy_headers is False
    assert config.mcp_default_namespace == "user/file"
    assert config.worker_enabled is True
    assert config.max_jobs_per_tick == 3
    assert config.rate_limit_per_minute == 9


def test_auth_tokens_are_hashed_and_enforce_revoke_expiry_capability_namespace_and_privacy(tmp_path):
    service, token = _service(tmp_path, namespaces=["user/default/projects/aletheia"], capabilities=["memory:context"])
    assert token is not None
    raw_count = service.memory.store.connection.execute(
        "SELECT count(*) AS count FROM api_tokens WHERE token_hash = ?",
        (token,),
    ).fetchone()["count"]
    assert raw_count == 0
    stored_hash = service.memory.store.connection.execute(
        "SELECT token_hash FROM api_tokens WHERE token_prefix = ?",
        (token[:12],),
    ).fetchone()["token_hash"]
    assert stored_hash.startswith("pbkdf2_sha256$")
    assert AuthService.verify_token_hash(token, stored_hash)

    service.memory.write_claim(
        namespace=NAMESPACE,
        subject="project",
        predicate="has_secret",
        object="ultra-secret-m6-detail",
        memory_type="project",
        evidence_ids=[
            service.memory.write_event(
                namespace=NAMESPACE,
                source_type="manual",
                content="ultra-secret-m6-detail",
                privacy_level="secret",
            ).id
        ],
        project_id="aletheia",
    )
    status, envelope = _post(
        service,
        "/v1/context-pack",
        token,
        {"namespace": NAMESPACE, "project_id": "aletheia", "query": "ultra-secret"},
    )
    assert status == 200
    assert "ultra-secret-m6-detail" not in envelope["data"]["markdown"]

    status, envelope = _post(
        service,
        "/v1/context-pack",
        token,
        {"namespace": NAMESPACE, "project_id": "private_finances", "query": "anything"},
    )
    assert status == 403
    assert envelope["error"]["code"] == "forbidden"

    status, envelope = _post(service, "/v1/remember", token, _remember_payload(project_id="aletheia"))
    assert status == 403
    assert envelope["error"]["details"]["required_capability"] == "memory:write_candidate"

    auth = service.auth
    stored = auth.list_tokens()[0]
    auth.revoke_token(stored.id, reason="rotate")
    status, envelope = _post(
        service,
        "/v1/context-pack",
        token,
        {"namespace": NAMESPACE, "project_id": "aletheia", "query": "anything"},
    )
    assert status == 401
    assert envelope["error"]["code"] == "unauthorized"

    client = auth.list_clients(include_disabled=True)[0]
    expired_token, expired_raw = auth.create_token(
        client_id=client.id,
        namespace_grants=[NAMESPACE],
        capabilities=["memory:context"],
        expires_at="2000-01-01T00:00:00+00:00",
    )
    status, envelope = _post(
        service,
        "/v1/context-pack",
        expired_raw,
        {"namespace": NAMESPACE, "query": "anything"},
    )
    assert status == 401
    assert auth.get_token(expired_token.id).status == "expired"

    legacy_token, legacy_raw = auth.create_token(
        client_id=client.id,
        namespace_grants=[NAMESPACE],
        capabilities=["memory:context"],
    )
    with service.memory.store.connection:
        service.memory.store.connection.execute(
            "UPDATE api_tokens SET token_hash = ? WHERE id = ?",
            (hashlib.sha256(legacy_raw.encode("utf-8")).hexdigest(), legacy_token.id),
        )
    status, envelope = _post(
        service,
        "/v1/context-pack",
        legacy_raw,
        {"namespace": NAMESPACE, "query": "legacy token"},
    )
    assert status == 200


def test_no_auth_context_is_least_privilege_for_local_namespace(tmp_path):
    service, token = _service(tmp_path, auth_required=False)
    assert token is None
    secret_event = service.memory.write_event(
        namespace=NAMESPACE,
        source_type="manual",
        content="no-auth secret detail",
        privacy_level="secret",
    )
    service.memory.write_claim(
        namespace=NAMESPACE,
        subject="no-auth",
        predicate="must_not_read",
        object="no-auth secret detail",
        memory_type="project",
        evidence_ids=[secret_event.id],
    )

    status, envelope = _post(service, "/v1/context-pack", None, {"namespace": NAMESPACE, "query": "secret"})
    assert status == 200
    assert "no-auth secret detail" not in envelope["data"]["markdown"]

    status, envelope = _get(service, f"/v1/health-report?namespace={NAMESPACE}", None)
    assert status == 403
    assert envelope["error"]["details"]["required_capability"] == "memory:admin"

    status, envelope = _post(service, "/v1/search", None, {"namespace": "user/other", "query": "anything"})
    assert status == 403
    assert envelope["error"]["code"] == "forbidden"


def test_claim_get_requires_capability_before_existence_lookup(tmp_path):
    service, token = _service(tmp_path, capabilities=["memory:context"])
    claim = service.memory.remember(
        namespace=NAMESPACE,
        memory_type="project",
        subject="phase2",
        predicate="guards",
        object="read before auth",
    )

    existing_status, existing = _get(service, f"/v1/claims/{claim.id}", token)
    missing_status, missing = _get(service, "/v1/claims/clm_missing", token)

    assert existing_status == 403
    assert missing_status == 403
    assert existing["error"]["details"]["required_capability"] == "memory:read"
    assert missing["error"]["details"]["required_capability"] == "memory:read"


def test_http_claim_scope_whitelists_payload_fields(tmp_path):
    service, token = _service(tmp_path, capabilities=[*DEFAULT_LOCAL_AGENT_CAPABILITIES, "memory:review"])
    claim = service.memory.remember(
        namespace=NAMESPACE,
        memory_type="preference",
        subject="user",
        predicate="prefers_phase2",
        object="explicit route argument maps",
    )

    status, envelope = _post(
        service,
        f"/v1/claims/{claim.id}/scope",
        token,
        {
            "scope_type": "contextual",
            "applies_when": "phase2",
            "reason": "Route should ignore fields outside the scope contract.",
            "claim_id": "clm_attacker",
            "status": "rejected",
        },
    )

    assert status == 200
    assert envelope["data"]["claim_id"] == claim.id
    assert service.memory.read_claim(claim.id).status == "active"


def test_http_boundary_rejects_oversized_and_malformed_lengths_before_body_read(tmp_path):
    db_path = str(tmp_path / "daemon.db")
    daemon = AletheiaDaemon(
        ServiceConfig(
            db_path=db_path,
            auto_migrate=True,
            auth_required=False,
            port=0,
            max_request_bytes=8,
        )
    )
    try:
        host, port = daemon.start()
        thread = threading.Thread(target=daemon.httpd.serve_forever, daemon=True)
        thread.start()

        with socket.create_connection((host, port), timeout=2) as sock:
            sock.sendall(b"POST /v1/remember HTTP/1.1\r\nHost: localhost\r\nContent-Length: 9\r\n\r\n")
            response = b"".join(iter(lambda: sock.recv(4096), b""))
        assert b"413" in response
        assert b"payload_too_large" in response

        with socket.create_connection((host, port), timeout=2) as sock:
            sock.sendall(b"POST /v1/remember HTTP/1.1\r\nHost: localhost\r\nContent-Length: nope\r\n\r\n")
            response = b"".join(iter(lambda: sock.recv(4096), b""))
        assert b"400" in response
        assert b"validation_error" in response
    finally:
        daemon.shutdown()


def test_http_catch_all_does_not_return_internal_exception_text(monkeypatch, tmp_path):
    service, token = _service(tmp_path)
    assert token is not None

    def boom(**_kwargs):
        raise RuntimeError("sqlite path /tmp/secret.db leaked")

    monkeypatch.setattr(service, "_route", boom)
    status, envelope = _post(service, "/v1/context-pack", token, {"namespace": NAMESPACE, "query": "m6"})
    assert status == 500
    assert envelope["error"]["code"] == "internal_error"
    assert envelope["error"]["message"] == "Internal server error."
    assert "secret.db" not in json.dumps(envelope)


def test_http_api_envelopes_idempotency_rate_limit_audit_and_admin_gates(tmp_path):
    service, token = _service(tmp_path, rate_limit_per_minute=20)
    assert token is not None
    for path in ["/v1/health", "/v1/ready", "/v1/version", "/v1/openapi.json"]:
        status, envelope = _get(service, path)
        assert status == 200
        assert "data" in envelope and "request_id" in envelope and "warnings" in envelope

    schema = openapi_schema()
    assert "/v1/context-pack" in schema["paths"]
    assert "/v1/candidates/{candidate_id}/promote" in schema["paths"]
    assert "/v1/eval/sets/{eval_set_id}/run" in schema["paths"]

    status, first = _post(service, "/v1/remember", token, _remember_payload(), **{"Idempotency-Key": "idem-1"})
    assert status == 200
    candidate_id = first["data"]["candidate"]["id"]
    status, replay = _post(service, "/v1/remember", token, _remember_payload(), **{"Idempotency-Key": "idem-1"})
    assert status == 200
    assert replay["data"]["candidate"]["id"] == candidate_id
    status, conflict = _post(
        service,
        "/v1/remember",
        token,
        _remember_payload(object="different"),
        **{"Idempotency-Key": "idem-1"},
    )
    assert status == 409
    assert conflict["error"]["code"] == "idempotency_conflict"

    status, retrieve = _post(service, "/v1/retrieve", token, {"namespace": NAMESPACE, "query": "m6"})
    assert status == 200
    assert retrieve["data"] == []
    status, active = _post(service, "/v1/remember", token, _remember_payload(write_mode="active"))
    assert status == 403

    status, audit = _get(service, f"/v1/audit/candidate/{candidate_id}", token)
    assert status == 200
    assert any(entry["action"] == "service.remember_candidate" for entry in audit["data"]["audit"])
    status, health_report = _get(service, f"/v1/health-report?namespace={NAMESPACE}", token)
    assert status == 403
    assert health_report["error"]["code"] == "forbidden"

    rows = service.service_requests(limit=20)
    assert any(row["request_id"] == "req_unit" for row in rows)
    assert all(row["request_hash"] is None for row in rows)


def test_rate_limit_applies_per_token_and_can_be_disabled(tmp_path):
    service, token = _service(tmp_path, rate_limit_per_minute=1)
    assert token is not None
    assert _post(service, "/v1/context-pack", token, {"namespace": NAMESPACE, "query": "first"})[0] == 200
    status, envelope = _post(service, "/v1/context-pack", token, {"namespace": NAMESPACE, "query": "second"})
    assert status == 429
    assert envelope["error"]["code"] == "rate_limited"

    service.config = ServiceConfig(db_path=service.config.db_path, auto_migrate=True, auth_required=True, rate_limit_enabled=False)
    assert _post(service, "/v1/context-pack", token, {"namespace": NAMESPACE, "query": "third"})[0] == 200

    anonymous, _ = _service(tmp_path / "anonymous", auth_required=False, rate_limit_per_minute=1)
    assert _post(
        anonymous,
        "/v1/context-pack",
        None,
        {"namespace": NAMESPACE, "query": "first"},
        **{"X-Forwarded-For": "203.0.113.10"},
    )[0] == 200
    status, envelope = _post(
        anonymous,
        "/v1/context-pack",
        None,
        {"namespace": NAMESPACE, "query": "second"},
        **{"X-Forwarded-For": "203.0.113.10"},
    )
    assert status == 429
    assert envelope["error"]["code"] == "rate_limited"
    assert _post(
        anonymous,
        "/v1/context-pack",
        None,
        {"namespace": NAMESPACE, "query": "third"},
        **{"X-Forwarded-For": "203.0.113.11"},
    )[0] == 429


def test_mcp_tools_are_candidate_first_logged_and_namespace_capability_aware(tmp_path):
    service, _token = _service(tmp_path, auth_required=False)
    registry = McpToolRegistry(service, namespace=NAMESPACE, mode="read_write_candidate")

    context = registry.invoke("memory_context_pack", {"query": "m6"})
    assert context["context_pack_id"].startswith("ctx_")
    search = registry.invoke("memory_search", {"query": "m6"})
    assert search == []
    candidate = registry.invoke(
        "memory_remember",
        {
            "memory_type": "preference",
            "subject": "user",
            "predicate": "prefers_mcp",
            "object": "candidate-first writes",
            "evidence_text": "MCP remember should be candidate-first.",
        },
    )
    assert candidate["write_mode"] == "candidate"
    assert service.memory.list_claims(namespace=NAMESPACE) == []
    audit = registry.invoke("memory_audit", {"target_type": "candidate", "target_id": candidate["candidate"]["id"]})
    assert audit["audit"]

    with pytest.raises(PermissionError):
        registry.invoke("memory_remember", {**_remember_payload(namespace=NAMESPACE), "write_mode": "active"})
    with pytest.raises(PermissionError):
        registry.invoke("memory_search", {"namespace": "user/other", "query": "m6"})
    assert any(row["tool_name"] == "memory_remember" for row in service.mcp_invocations(limit=20))


class _FakeResponse:
    def __init__(self, envelope: dict):
        self.envelope = envelope

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return json.dumps(self.envelope).encode("utf-8")


def test_python_client_and_adapter_send_headers_preserve_warnings_and_raise_typed_errors(monkeypatch):
    calls: list = []

    def fake_urlopen(request, timeout):
        calls.append((request, timeout, request.data))
        if request.full_url.endswith("/v1/context-pack"):
            return _FakeResponse(
                {
                    "data": {"context_pack_id": "ctx_client", "markdown": "## Memory Context\n", "warnings": []},
                    "request_id": "req_client",
                    "warnings": ["Some memories were omitted due to access policy."],
                    "pagination": None,
                }
        )
        if request.full_url.endswith("/v1/remember"):
            if request.headers.get("Idempotency-key") is not None:
                assert request.headers["Idempotency-key"] == "idem-client"
            return _FakeResponse(
                {
                    "data": {"candidate": {"id": "cand_client"}},
                    "request_id": "req_remember",
                    "warnings": [],
                    "pagination": None,
                }
            )
        if request.full_url.endswith("/v1/outcomes"):
            return _FakeResponse({"data": {"id": "out_client"}, "request_id": "req_out", "warnings": []})
        raise urllib.error.HTTPError(
            request.full_url,
            403,
            "Forbidden",
            hdrs=None,
            fp=io.BytesIO(
                json.dumps(
                    {
                        "error": {
                            "code": "forbidden",
                            "message": "Capability required.",
                            "details": {"required_capability": "memory:admin"},
                        },
                        "request_id": "req_forbidden",
                    }
                ).encode("utf-8")
            ),
        )

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    client = AletheiaClient("http://127.0.0.1:8765", "atl_raw", timeout=3)
    data = client.context_pack(namespace=NAMESPACE, query="m6")
    assert data["context_pack_id"] == "ctx_client"
    assert client.last_warnings == ["Some memories were omitted due to access policy."]
    assert calls[0][0].headers["Authorization"] == "Bearer atl_raw"
    assert calls[0][1] == 3

    remembered = client.remember(idempotency_key="idem-client", **_remember_payload())
    assert remembered["candidate"]["id"] == "cand_client"
    adapter = HttpAgentMemoryAdapter(client)
    assert adapter.before_agent_call(namespace=NAMESPACE, query="m6").startswith("## Memory Context")
    assert adapter.remember_candidate(
        namespace=NAMESPACE,
        subject="user",
        predicate="likes",
        object="adapters",
        memory_type="preference",
        evidence_text="Adapter test.",
    ) == "cand_client"
    adapter.after_agent_call(namespace=NAMESPACE, task_id="task-1", outcome="success", notes="done")

    with pytest.raises(AletheiaForbiddenError) as forbidden:
        client.audit("claim", "clm_missing")
    assert forbidden.value.details["required_capability"] == "memory:admin"

    def validation_urlopen(request, timeout):
        raise urllib.error.HTTPError(
            request.full_url,
            400,
            "Bad Request",
            hdrs=None,
            fp=io.BytesIO(
                json.dumps(
                    {
                        "error": {"code": "validation_error", "message": "Bad payload.", "details": {}},
                        "request_id": "req_bad",
                    }
                ).encode("utf-8")
            ),
        )

    monkeypatch.setattr("urllib.request.urlopen", validation_urlopen)
    with pytest.raises(AletheiaValidationError):
        client.context_pack(namespace=NAMESPACE, query="bad")


def test_async_client_wraps_sync_client(monkeypatch):
    def fake_urlopen(request, timeout):
        return _FakeResponse({"data": {"status": "ok"}, "request_id": "req_async", "warnings": []})

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    client = AsyncAletheiaClient("http://127.0.0.1:8765", "atl_raw")
    assert asyncio.run(client.health()) == {"status": "ok"}
    assert client.last_request_id == "req_async"


def test_worker_runs_success_failure_and_respects_max_jobs(tmp_path):
    service, token = _service(tmp_path, capabilities=[*DEFAULT_LOCAL_AGENT_CAPABILITIES, "memory:jobs"])
    assert token is not None
    first_payload = {"namespace": NAMESPACE, "job_type": "memory_health_check", "payload": {"namespace": NAMESPACE}}
    second_payload = {"namespace": NAMESPACE, "job_type": "run_evaluation", "payload": {"namespace": NAMESPACE, "max_attempts": 1}}
    _post(service, "/v1/jobs", token, first_payload)
    _post(service, "/v1/jobs", token, second_payload)

    status, run = _post(service, "/v1/jobs/run", token, {"namespace": NAMESPACE, "max_jobs": 1})
    assert status == 200
    assert len(run["data"]) == 1
    remaining = service.memory.list_jobs(namespace=NAMESPACE, status="pending")
    assert len(remaining) == 1

    status, run = _post(service, "/v1/jobs/run", token, {"namespace": NAMESPACE, "max_jobs": 5})
    assert status == 200
    failed = service.memory.list_jobs(namespace=NAMESPACE, status="failed")
    completed = service.memory.list_jobs(namespace=NAMESPACE, status="completed")
    assert failed and completed
    audit_rows = service.memory.store.connection.execute(
        "SELECT action FROM audit_log WHERE target_id = ?",
        (failed[0].id,),
    ).fetchall()
    assert any(row["action"] == "job.failed" for row in audit_rows)


def test_stale_schema_refused_when_auto_migrate_disabled(tmp_path):
    db_path = tmp_path / "old.db"
    connection = sqlite3.connect(db_path)
    connection.execute("CREATE TABLE schema_version (id INTEGER PRIMARY KEY, version TEXT NOT NULL, applied_at TEXT)")
    connection.execute("INSERT INTO schema_version VALUES (1, '0.6.0', '2026-01-01T00:00:00+00:00')")
    connection.commit()
    connection.close()

    with pytest.raises(ServiceError) as exc:
        AletheiaService.open(ServiceConfig(db_path=str(db_path), auto_migrate=False))
    assert exc.value.code == "stale_schema"
