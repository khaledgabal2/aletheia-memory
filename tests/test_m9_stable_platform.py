from __future__ import annotations

import json
import urllib.error
from pathlib import Path

import pytest

from aletheia import ExtractorPlugin, Memory
from aletheia.cli.main import main
from aletheia.core import platform as platform_module
from aletheia.core.errors import ValidationError
from aletheia.models import ServiceConfig
from aletheia.service.auth import AuthService
from aletheia.service.http import AletheiaService, openapi_schema


NAMESPACE = "user/default"


def _json(payload: dict) -> bytes:
    return json.dumps(payload).encode("utf-8")


def _service(tmp_path) -> tuple[AletheiaService, str]:
    db_path = str(tmp_path / "service.db")
    memory = Memory.open(db_path, namespace=NAMESPACE)
    service = AletheiaService(
        memory,
        ServiceConfig(db_path=db_path, auto_migrate=True, auth_required=True, console_enabled=True),
    )
    auth = AuthService(memory)
    client = auth.create_client(name="m9-admin", client_type="admin")
    _token, raw = auth.create_token(
        client_id=client.id,
        namespace_grants=["*"],
        capabilities=["memory:admin"],
        privacy_ceiling="secret",
    )
    return service, raw


def _get(service: AletheiaService, path: str, token: str):
    return service.handle_http(method="GET", path=path, headers={"Authorization": f"Bearer {token}"})


def _post(service: AletheiaService, path: str, token: str, payload: dict):
    return service.handle_http(
        method="POST",
        path=path,
        headers={"Authorization": f"Bearer {token}"},
        body=_json(payload),
    )


def _plugin_dir(tmp_path: Path, *, name: str = "demo-plugin", permissions: list[str] | None = None) -> Path:
    permissions = permissions or ["write_candidate"]
    plugin_dir = tmp_path / name
    plugin_dir.mkdir()
    plugin_dir.joinpath("aletheia-plugin.toml").write_text(
        f"""
[plugin]
name = "{name}"
display_name = "Demo Plugin"
version = "1.3.0"
plugin_type = "extractor"
entrypoint = "demo_plugin:Plugin"
description = "Demo governed plugin."

[compatibility]
aletheia_min_version = "1.3.0"
api_contract_version = "v1"

[permissions]
permissions_required = {json.dumps(permissions)}
external_network_access = false
reads_memory_content = false
writes_memory = true
stores_data = false
""",
        encoding="utf-8",
    )
    return plugin_dir


def test_m9_migration_backfills_stable_platform_contracts(tmp_path):
    memory = Memory.open(str(tmp_path / "m9.db"), namespace=NAMESPACE)
    try:
        assert memory.health()["schema_version"] == "1.3.0"
        contracts = memory.list_public_contracts()
        names = {contract.name for contract in contracts}
        assert {"HTTP API v1", "Python SDK v1", "Plugin interface v1", "MCP tools v1"} <= names
        assert memory.check_deprecations()["status"] == "passed"
        report = memory.compatibility_report(include_runtime=False)
        assert report["api_version"] == "v1"
        assert report["schema_version"] == "1.3.0"
        assert any(entry["component_type"] == "plugin_api" for entry in report["matrix"])
        sdk_names = {record.sdk_name for record in memory.list_sdk_releases()}
        assert {"python-sync", "python-async"} <= sdk_names
        assert isinstance(ExtractorPlugin, type)
    finally:
        memory.close()


def test_m9_plugin_manifest_permissions_and_candidate_first_execution(tmp_path):
    memory = Memory.open(str(tmp_path / "plugins.db"), namespace=NAMESPACE)
    plugin_dir = _plugin_dir(tmp_path)
    try:
        discovered = memory.discover_plugins(str(plugin_dir))
        assert discovered[0]["name"] == "demo-plugin"
        installation = memory.install_plugin(plugin_path=str(plugin_dir), trust_level="local")
        assert installation.status == "installed"

        approved_at_install = memory.install_plugin(
            plugin_path=str(plugin_dir),
            trust_level="local",
            approve_permissions=True,
        )
        assert approved_at_install.status == "installed"
        grant_count = memory.store.connection.execute(
            "SELECT count(*) AS count FROM plugin_capability_grants WHERE plugin_installation_id = ?",
            (approved_at_install.id,),
        ).fetchone()["count"]
        assert grant_count == 0

        enabled = memory.enable_plugin(
            installation.id,
            reason="Unit-test local plugin.",
            approved_permissions=["write_candidate"],
            actor="pytest",
        )
        assert enabled.status == "enabled"

        blocked = memory.run_plugin_operation(plugin_id=installation.id, operation="attempt_active_write")
        assert blocked["status"] == "blocked"
        assert blocked["missing_permissions"] == ["write_active_claim"]

        active_writer_dir = _plugin_dir(
            tmp_path,
            name="active-writer-plugin",
            permissions=["write_active_claim"],
        )
        active_writer = memory.install_plugin(plugin_path=str(active_writer_dir), trust_level="local")
        memory.enable_plugin(
            active_writer.id,
            reason="Unit-test high-risk active write grant.",
            approved_permissions=["write_active_claim"],
            actor="pytest",
        )
        governance_blocked = memory.run_plugin_operation(
            plugin_id=active_writer.id,
            operation="attempt_active_write",
        )
        assert governance_blocked["status"] == "blocked"
        assert governance_blocked["created_active_claim"] is False

        result = memory.run_plugin_operation(
            plugin_id=installation.id,
            operation="remember_candidate",
            namespace=NAMESPACE,
            payload={
                "subject": "user",
                "predicate": "prefers_plugin_writes",
                "object": "candidate review",
                "memory_type": "preference",
                "evidence_text": "Plugin writes should land in candidate review.",
            },
        )
        assert result["status"] == "ok"
        assert result["candidate_id"].startswith("cand_")
        assert memory.list_claims(namespace=NAMESPACE) == []
        assert memory.read_candidate(result["candidate_id"]).candidate_status == "pending_review"
        assert len(memory.list_plugin_logs(plugin_id=installation.id)) >= 2

        metadata_only_dir = _plugin_dir(
            tmp_path,
            name="metadata-only-plugin",
            permissions=["read_metadata"],
        )
        metadata_only = memory.install_plugin(plugin_path=str(metadata_only_dir), trust_level="local")
        memory.enable_plugin(
            metadata_only.id,
            reason="Unit-test metadata-only plugin.",
            approved_permissions=["read_metadata"],
            actor="pytest",
        )
        denied = memory.run_plugin_operation(
            plugin_id=metadata_only.id,
            operation="remember_candidate",
            namespace=NAMESPACE,
            payload={"subject": "blocked", "predicate": "needs", "object": "grant"},
        )
        assert denied["status"] == "blocked"
        assert denied["missing_permissions"] == ["write_candidate"]
        denied_logs = memory.list_plugin_logs(plugin_id=metadata_only.id)
        assert denied_logs[0].status == "blocked"
        assert "unapproved permissions" in denied_logs[0].error

        run = memory.run_conformance(suite="plugin", target=installation.id)
        assert run.status == "passed"
    finally:
        memory.close()


def test_m9_conformance_docs_adapters_doctor_and_v1_gate(tmp_path):
    memory = Memory.open(str(tmp_path / "gate.db"), namespace=NAMESPACE)
    try:
        docs = memory.build_docs(output_dir=str(tmp_path / "site"))
        assert docs.status == "passed"
        assert (tmp_path / "site" / "index.md").read_text(encoding="utf-8").startswith("# Aletheia Documentation Index")
        assert (tmp_path / "site" / "encryption_layer.md").exists()
        assert (tmp_path / "site" / "troubleshooting.md").exists()
        assert (tmp_path / "site" / "openapi.generated.json").exists()
        assert memory.test_doc_examples()["status"] == "passed"

        scaffold = memory.scaffold_adapter(
            adapter_type="python-sdk",
            name="pytest-adapter",
            output_path=str(tmp_path / "pytest-adapter"),
        )
        assert "agent_loop.py" in scaffold["files"]
        adapter_run = memory.run_conformance(suite="agent-adapter", target=scaffold["path"], target_type="agent_adapter")
        assert adapter_run.status == "passed"
        certification = memory.certify_adapter(path=scaffold["path"], adapter_type="python-sdk")
        assert certification.status == "certified"

        for suite in ["kernel", "http-api", "mcp", "python-sdk", "context-pack-schema", "plugin", "agent-adapter"]:
            assert memory.run_conformance(suite=suite).status == "passed"

        doctor = memory.doctor_run()
        assert doctor.status in {"healthy", "healthy_with_warnings"}
        gate = memory.v1_gate_run(metadata={"allow_missing_backup": True})
        assert gate.status == "passed"
    finally:
        memory.close()


def test_doctor_service_url_rejects_redirects_and_spoofed_localhost(monkeypatch):
    class RedirectingOpener:
        def open(self, url, timeout):
            raise urllib.error.HTTPError(
                url,
                302,
                "Found",
                {"Location": "http://169.254.169.254/latest/meta-data"},
                None,
            )

    monkeypatch.setattr(
        platform_module.urllib.request,
        "build_opener",
        lambda *args, **kwargs: RedirectingOpener(),
    )
    with pytest.raises(ValidationError, match="loopback|redirect"):
        platform_module._open_loopback_url("http://127.0.0.1:8765/v1/health", timeout=1)

    monkeypatch.setattr(
        platform_module.socket,
        "getaddrinfo",
        lambda host, port, type=None: [(None, None, None, None, ("203.0.113.10", port or 80))],
    )
    with pytest.raises(ValidationError, match="loopback"):
        platform_module._validate_service_url("http://localhost:8765")


def test_m9_http_openapi_and_cli_surfaces(tmp_path, capsys):
    service, token = _service(tmp_path)
    try:
        status, envelope = _get(service, "/v1/contracts", token)
        assert status == 200
        assert any(item["name"] == "HTTP API v1" for item in envelope["data"])

        status, envelope = _get(service, "/v1/compatibility/report", token)
        assert status == 200
        assert envelope["data"]["api_version"] == "v1"

        status, envelope = _post(service, "/v1/docs/build", token, {"output_dir": str(tmp_path / "http-docs")})
        assert status == 200
        assert envelope["data"]["status"] == "passed"

        status, envelope = _post(service, "/v1/docs/build", token, {"output_dir": str(tmp_path.parent / "outside-docs")})
        assert status == 400
        assert envelope["error"]["code"] == "validation_error"
        assert "admin safe root" in envelope["error"]["message"]

        status, envelope = _post(service, "/v1/plugins/install", token, {"plugin_path": str(tmp_path.parent / "outside-plugin")})
        assert status == 400
        assert envelope["error"]["code"] == "validation_error"

        status, envelope = _post(service, "/v1/doctor/run", token, {})
        assert status == 200
        assert envelope["data"]["checks"]

        status, envelope = _post(service, "/v1/doctor/run", token, {"service_url": "http://example.com"})
        assert status == 400
        assert envelope["error"]["code"] == "validation_error"
        assert "loopback" in envelope["error"]["message"]

        status, envelope = _post(service, "/v1/v1-gate/run", token, {"metadata": {"allow_missing_backup": True}})
        assert status == 200
        assert envelope["data"]["status"] == "passed"

        schema = openapi_schema()
        assert schema["info"]["version"] == "1.3.0"
        assert "/v1/plugins" in schema["paths"]
        assert "/v1/v1-gate/run" in schema["paths"]
    finally:
        service.close()

    db_path = tmp_path / "cli.db"
    assert main(["init", "--db", str(db_path)]) == 0
    assert main(["contracts", "list", "--db", str(db_path)]) == 0
    assert "HTTP API v1" in capsys.readouterr().out
    assert main(["doctor", "--db", str(db_path)]) == 0
    assert "package_version" in capsys.readouterr().out
