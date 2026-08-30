"""G1 discovery/version contracts, real HTTP payloads and authorization boundaries."""

import asyncio
from contextlib import contextmanager
from dataclasses import replace
from datetime import timedelta
import json
from pathlib import Path
import tomllib

import pytest
from jsonschema import Draft202012Validator
from openapi_spec_validator import validate

from aletheia import AletheiaClient, AsyncAletheiaClient, Memory
from aletheia.client import AletheiaUnauthorizedError
from aletheia.core.time import utc_now
from aletheia.models import ServiceConfig
from aletheia.service.auth import CAPABILITIES
from aletheia.service.contracts import DISCOVERY_PATHS, discovery_document
from aletheia.service.http import AletheiaService, openapi_schema
from aletheia import version as versions
from scripts.v1_4_phase0 import local_service, load_legacy_client, request


@contextmanager
def service_at(path, **config):
    memory = Memory.open(str(path), namespace="user/discovery")
    service = AletheiaService(memory, ServiceConfig(db_path=str(path), auth_required=True, **config))
    try:
        yield service
    finally:
        service.close()


def token_for(service, *, capabilities=None, grants=None, privacy="personal", expires_at=None):
    client = service.auth.create_client(name="Discovery test", client_type="test", metadata={"secret_metadata": "do not expose"})
    token, raw = service.auth.create_token(
        client_id=client.id, capabilities=capabilities or ["memory:context"],
        namespace_grants=grants or ["user/discovery"], privacy_ceiling=privacy,
        expires_at=expires_at, metadata={"secret_metadata": "do not expose"},
    )
    return client, token, raw


def get(service, path, raw=None, **headers):
    if raw is not None:
        headers["Authorization"] = f"Bearer {raw}"
    return service.handle_http(method="GET", path=path, headers=headers)


def validate_envelope(document, path, status, body):
    response = document["paths"][path]["get"]["responses"][str(status)]
    schema = response["content"]["application/json"]["schema"]
    Draft202012Validator({**schema, "components": document["components"]}).validate(body)


def test_version_uses_build_metadata_and_safe_development_fallback(tmp_path, monkeypatch):
    monkeypatch.setattr(versions.metadata, "version", lambda _: "1.4.0rc2")
    assert versions.software_version() == "1.4.0rc2"
    def not_installed(_):
        raise versions.metadata.PackageNotFoundError
    monkeypatch.setattr(versions.metadata, "version", not_installed)
    project = tomllib.loads((Path(__file__).resolve().parents[1] / "pyproject.toml").read_text())["project"]
    assert versions.software_version() == project["version"]
    assert versions._source_version(tmp_path / "missing.toml") == "0+unknown"
    path = tmp_path / "pyproject.toml"
    for text in ['[project', 'project = "invalid"', '[project]\nname="another-package"\nversion="9.0"']:
        path.write_text(text)
        assert versions._source_version(path) == "0+unknown"


def test_software_schema_and_legacy_bridge_are_independent(tmp_path, monkeypatch):
    monkeypatch.setattr(versions.metadata, "version", lambda _: "1.4.0")
    with local_service(tmp_path) as (service, url, tokens):
        version = AletheiaClient(url, tokens["agent"]).version()
        assert version["software_version"] == version["service_version"] == "1.4.0"
        assert service.memory.health()["schema_version"] == "1.3.0"
        assert load_legacy_client()(url, tokens["agent"]).check_compatibility()["compatible"] is True
        report = AletheiaClient(url, tokens["agent"]).compatibility_report()
        assert report["aletheia_version"] == report["schema_version"] == "1.3.0"
        assert report["software_version"] == "1.4.0"
        assert "aletheia_version" in report["deprecated_fields"]
        for path in ["/v1/health", "/v1/ready", "/v1/version", "/v1/compatibility/report", "/v1/auth/me"]:
            result = request(url, "GET", path, token=tokens["agent"])
            assert result["body"]["data"]["service_identity"] == version["service_identity"]
            assert result["body"]["data"]["supported_profiles"] == []
        assert openapi_schema()["info"]["version"] == "1.4.0"
        doctor = service.memory.doctor_run()
        assert next(check for check in doctor.checks if check["name"] == "package_version")["detail"] == "Aletheia 1.4.0"


def test_identity_is_per_service_instance_not_database_path(tmp_path):
    path = tmp_path / "instance.db"
    with service_at(path) as first:
        identity = get(first, "/v1/version")[1]["data"]["service_identity"]
        assert identity == get(first, "/v1/health")[1]["data"]["service_identity"]
        assert str(path) not in identity
    with service_at(path) as second:
        assert identity != get(second, "/v1/version")[1]["data"]["service_identity"]


def test_legacy_bridge_preserves_rejection_of_mismatched_storage(tmp_path):
    with local_service(tmp_path) as (service, url, tokens):
        with service.memory.store.transaction():
            service.memory.store.connection.execute("UPDATE schema_version SET version = 'unsupported'")
        assert load_legacy_client()(url, tokens["agent"]).check_compatibility()["compatible"] is False


def test_scoped_principal_needs_no_read_or_admin_and_never_serializes_credentials(tmp_path):
    with service_at(tmp_path / "scope.db") as service:
        expiry = (utc_now() + timedelta(minutes=10)).isoformat()
        client, token, raw = token_for(service, grants=["user/discovery/projects/alpha"], privacy="public", expires_at=expiry)
        other, _, _ = token_for(service, capabilities=["memory:admin"], grants=["*"], privacy="secret")
        status, envelope = get(service, f"/v1/auth/me?client_id={other.id}", raw)
        assert status == 200
        principal = envelope["data"]
        assert principal["principal"] == {"id": client.id, "name": client.name, "client_type": "test"}
        assert principal["capabilities"] == principal["granted_capabilities"] == ["memory:context"]
        assert principal["namespace_grants"] == ["user/discovery/projects/alpha"]
        assert principal["privacy_ceiling"] == "public"
        assert principal["authentication_mode"] == "bearer" and principal["authenticated"] is True
        assert principal["expires_at"] == expiry
        serialized = json.dumps(principal)
        for secret in [raw, token.token_hash, token.token_prefix, "secret_metadata", other.id]:
            assert secret not in serialized
        assert get(service, "/v1/compatibility/report", raw)[0] == 403
        validate_envelope(openapi_schema(), "/v1/auth/me", status, envelope)
        # Effective scope changes must be reflected on the very next request.
        with service.memory.store.transaction():
            service.memory.store.connection.execute("DELETE FROM capability_grants WHERE token_id = ?", (token.id,))
        assert get(service, "/v1/auth/me", raw)[1]["data"]["capabilities"] == []


def test_admin_effective_capabilities_do_not_widen_namespace_or_privacy(tmp_path):
    with service_at(tmp_path / "admin.db") as service:
        _, _, raw = token_for(service, capabilities=["memory:admin"], privacy="public")
        result = get(service, "/v1/auth/me", raw)[1]["data"]
        assert result["capabilities"] == sorted(CAPABILITIES)
        assert result["granted_capabilities"] == ["memory:admin"]
        assert result["namespace_grants"] == ["user/discovery"]
        assert result["privacy_ceiling"] == "public"
        status, _ = service.handle_http(method="POST", path="/v1/retrieve", headers={"Authorization": f"Bearer {raw}"},
                                       body=json.dumps({"namespace": "user/other"}).encode())
        assert status == 403


@pytest.mark.parametrize("failure", ["missing", "invalid", "expired", "revoked", "disabled"])
def test_principal_invalid_auth_fails_without_metadata(tmp_path, failure):
    with service_at(tmp_path / "invalid.db") as service:
        expiry = (utc_now() - timedelta(minutes=1)).isoformat() if failure == "expired" else None
        client, token, raw = token_for(service, expires_at=expiry)
        if failure == "revoked":
            service.auth.revoke_token(token.id)
        elif failure == "disabled":
            service.auth.disable_client(client.id)
        elif failure == "missing":
            raw = None
        elif failure == "invalid":
            raw = "invalid-test-token"
        status, envelope = get(service, "/v1/auth/me", raw)
        assert status == 401 and "data" not in envelope
        assert client.id not in json.dumps(envelope)
        validate_envelope(openapi_schema(), "/v1/auth/me", status, envelope)


def test_tokenless_mode_is_explicit_and_never_ignores_supplied_credentials(tmp_path):
    with service_at(tmp_path / "local.db") as service:
        service.config = replace(service.config, auth_required=False)
        status, envelope = get(service, "/v1/auth/me")
        assert status == 200
        assert envelope["data"]["authentication_mode"] == "local_tokenless"
        assert envelope["data"]["principal"] is None
        assert envelope["data"]["authenticated"] is False
        assert envelope["data"]["namespace_grants"] == ["user/discovery"]
        assert get(service, "/v1/auth/me", "invalid-test-token")[0] == 401
        _, token, raw = token_for(service, privacy="public")
        assert get(service, "/v1/auth/me", raw)[1]["data"]["privacy_ceiling"] == "public"
        service.auth.revoke_token(token.id)
        assert get(service, "/v1/auth/me", raw)[0] == 401
        # Fixture-only protected-state setup: exercise self discovery without creating keys.
        with service.memory.store.transaction():
            service.memory.store.connection.execute("UPDATE protected_mode_config SET enabled = 1")
        assert get(service, "/v1/auth/me")[0] == 401
        with service.memory.store.transaction():
            service.memory.store.connection.execute("DELETE FROM protected_mode_config")
        assert get(service, "/v1/auth/me")[0] == 401
        assert service.memory.store.connection.execute("SELECT count(*) FROM protected_mode_config").fetchone()[0] == 0


def test_console_self_discovery_preserves_legacy_session_and_csrf(tmp_path):
    with service_at(tmp_path / "console.db", console_enabled=True) as service:
        raw = "disposable-console-session"
        now = utc_now()
        with service.memory.store.transaction():
            service.memory.store.connection.execute(
                """INSERT INTO console_sessions
                (id, namespace_grants_json, capabilities_json, privacy_ceiling, created_at, expires_at, metadata_json)
                VALUES (?, ?, ?, ?, ?, ?, ?)""",
                ("cs_fixture", '["user/discovery"]', '["memory:read"]', "public", now.isoformat(),
                 (now + timedelta(minutes=10)).isoformat(), json.dumps({"session_token_hash": service.auth.hash_secret(raw)})),
            )
        headers = {"X-Console-Session": raw}
        status, envelope = get(service, "/v1/auth/me", **headers)
        assert status == 200 and envelope["data"]["authentication_mode"] == "console_session"
        assert envelope["data"]["principal"] is None
        assert raw not in json.dumps(envelope)
        assert get(service, "/v1/auth/me", Cookie=f"aletheia_console={raw}")[0] == 200
        legacy = get(service, "/v1/console/session", **headers)[1]["data"]
        assert set(legacy) == {"authenticated", "capabilities", "namespace_grants"}
        status, denied = service.handle_http(method="POST", path="/v1/dashboard/preferences", headers=headers,
                                            body=b'{"namespace":"user/discovery"}')
        assert status == 403 and "CSRF" in denied["error"]["message"]
        # Logout intentionally retains the existing exemption from CSRF.
        assert service.handle_http(method="POST", path="/v1/console/logout", headers=headers, body=b"{}")[0] == 200
        assert get(service, "/v1/auth/me", **headers)[0] == 401


def test_discovery_schemas_validate_actual_http_and_errors(tmp_path):
    with local_service(tmp_path) as (service, url, tokens):
        plugin = tmp_path / "discovery-plugin"
        plugin.mkdir()
        (plugin / "aletheia-plugin.toml").write_text('''
[plugin]
name = "discovery-plugin"
display_name = "Discovery fixture"
version = "1.0.0"
plugin_type = "extractor"
entrypoint = "fixture:Plugin"
description = "Synthetic manifest for compatibility-response validation."
[compatibility]
aletheia_min_version = "1.3.0"
api_contract_version = "v1"
[permissions]
permissions_required = ["write_candidate"]
external_network_access = false
reads_memory_content = false
writes_memory = true
stores_data = false
''')
        service.memory.install_plugin(plugin_path=str(plugin))
        document = request(url, "GET", "/v1/openapi.json")["body"]["data"]
        validate(discovery_document(document))
        for path in DISCOVERY_PATHS:
            result = request(url, "GET", path, token=tokens["agent"])
            assert result["status"] == 200
            validate_envelope(document, path, 200, result["body"])
            assert result["headers"]["Cache-Control"] == "no-store"
            assert result["headers"]["X-Request-ID"] == result["body"]["request_id"]
            if path == "/v1/compatibility/report":
                assert result["body"]["data"]["plugins"][0]["name"] == "discovery-plugin"
        for query in ["false", "0", "off", "true"]:
            path = "/v1/compatibility/report"
            result = request(url, "GET", path + f"?include_runtime={query}&include_sdks={query}&include_plugins={query}", token=tokens["agent"])
            validate_envelope(document, path, 200, result["body"])
            assert (result["body"]["data"]["python_version"] is None) == (query != "true")
        bad = request(url, "GET", "/v1/auth/me", token="invalid-test-token")
        validate_envelope(document, "/v1/auth/me", 401, bad["body"])
        assert bad["headers"]["Cache-Control"] == "no-store"
        service.config = replace(service.config, rate_limit_enabled=True, rate_limit_per_minute=1)
        request(url, "GET", "/v1/auth/me", token=tokens["agent"])
        limited = request(url, "GET", "/v1/auth/me", token=tokens["agent"])
        assert limited["status"] == 429
        validate_envelope(document, "/v1/auth/me", 429, limited["body"])


@pytest.mark.parametrize("profiles,required,expected", [
    ([], [], True), ([], ["memory-review-v1"], False),
    (["memory-review-v1"], ["memory-review-v1"], True),
    ("memory-review-v1", ["memory-review-v1"], False),
])
def test_sdk_negotiates_profiles_without_software_schema_equality(monkeypatch, profiles, required, expected):
    client = AletheiaClient("http://unused.invalid")
    monkeypatch.setattr(client, "compatibility_report", lambda: {"api_version": "v1", "schema_version": "storage-next", "aletheia_version": "old-alias"})
    monkeypatch.setattr(client, "version", lambda: {"api_version": "v1", "software_version": "9.2.0", "supported_profiles": profiles})
    result = client.check_compatibility(required_profiles=required)
    assert result["compatible"] is expected
    assert result["server_version"] == "9.2.0"
    assert result["limited_capabilities"] is (not isinstance(profiles, list))
    with pytest.raises(ValueError):
        client.check_compatibility(required_profiles="memory-review-v1")


def test_async_sdk_discovers_principal_and_missing_profiles(tmp_path):
    with local_service(tmp_path) as (_, url, tokens):
        client = AsyncAletheiaClient(url, tokens["agent"])
        assert asyncio.run(client.current_principal())["authenticated"] is True
        result = asyncio.run(client.check_compatibility(required_profiles=["memory-review-v1"]))
        assert result["compatible"] is False
        assert result["missing_profiles"] == ["memory-review-v1"]
        with pytest.raises(AletheiaUnauthorizedError):
            asyncio.run(AsyncAletheiaClient(url, "invalid-test-token").current_principal())


@pytest.mark.parametrize("version_api,report_api", [("v2", "v1"), ("v1", "v2")])
def test_sdk_rejects_an_incompatible_protocol(monkeypatch, version_api, report_api):
    client = AletheiaClient("http://unused.invalid")
    monkeypatch.setattr(client, "version", lambda: {"api_version": version_api, "supported_profiles": ["memory-read-v1"]})
    monkeypatch.setattr(client, "compatibility_report", lambda: {"api_version": report_api})
    assert client.check_compatibility(required_profiles=["memory-read-v1"])["compatible"] is False
