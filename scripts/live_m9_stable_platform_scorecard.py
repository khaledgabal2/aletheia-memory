#!/usr/bin/env python3
"""Run live M9 stable-platform scorecard checks."""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from aletheia import AletheiaClient, AsyncAletheiaClient, Memory
from aletheia.cli.main import main as cli_main
from aletheia.models import ServiceConfig
from aletheia.service.auth import AuthService
from aletheia.service.http import AletheiaService, openapi_schema


NAMESPACE = "live/m9"


def run_cli(argv: list[str]) -> str:
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        status = cli_main(argv)
    assert status == 0
    return buffer.getvalue()


def json_body(payload: dict) -> bytes:
    return json.dumps(payload).encode("utf-8")


@dataclass
class ScoreCase:
    category: str
    name: str
    contract_measure: str
    fn: Callable[[], str]


class M9LiveScorecard:
    def __init__(self, base_dir: Path, db_path: Path):
        self.base_dir = base_dir
        self.db_path = db_path
        self.docs_dir = base_dir / "site"
        self.adapter_dir = base_dir / "python-sdk-adapter"
        self.plugin_dir = base_dir / "demo-plugin"
        self.memory = Memory.open(str(self.db_path), namespace=NAMESPACE)
        self._service: AletheiaService | None = None
        self._token: str | None = None
        self.plugin_id: str | None = None

    def close(self) -> None:
        self.memory.close()

    def cases(self) -> list[ScoreCase]:
        return [
            ScoreCase("27.1 Platform Stability", "v1 contracts, semver, compatibility, deprecations", "Stable public contracts and semver policy are recorded and inspectable.", self.case_public_contracts),
            ScoreCase("27.2 Plugin Ecosystem", "Plugin manifest, permission grants, logs, candidate-first writes", "Plugins install safely, require explicit grants, and cannot bypass governance.", self.case_plugins),
            ScoreCase("27.3 Conformance", "Required built-in conformance suites", "Kernel, HTTP, MCP, SDK, plugin, adapter, archive, protected-mode, and context-pack suites run and persist results.", self.case_conformance),
            ScoreCase("27.4 SDK Stability", "Sync and async SDK v1 methods", "Python SDK exposes stable candidate/active write, compatibility, ingestion, review, health, backup, and platform helpers.", self.case_sdk),
            ScoreCase("27.5 Adapters", "Adapter scaffold, conformance, certification", "Agent adapter scaffolds default to candidate writes and can be certified.", self.case_adapters),
            ScoreCase("27.6 Docs And Examples", "Docs build, examples validation, static guides", "Docs and examples build and validate for CLI, HTTP, MCP, plugins, adapters, migration, backup, and privacy.", self.case_docs_examples),
            ScoreCase("27.7 Doctor/Compatibility", "Doctor diagnostics and matrix report", "Doctor and compatibility commands expose actionable platform health.", self.case_doctor_compatibility),
            ScoreCase("27.8 v1 Release", "Release manifest and v1 gate", "The v1 gate checks tests, migrations, docs, conformance, OpenAPI, integrity, tokens, telemetry, and readiness.", self.case_v1_gate),
            ScoreCase("27.9 Console/API", "HTTP, OpenAPI, console, and CLI platform access", "M9 functionality is reachable through CLI, HTTP API, OpenAPI, and console controls.", self.case_console_api_cli),
            ScoreCase("Definition Of Complete", "M0-M8 regression smoke plus M9 tables", "Existing memory behavior remains intact while all M9 tables and live success markers are present.", self.case_definition_complete),
        ]

    def run(self) -> int:
        print("Aletheia M9 Stable Platform Live Scorecard")
        print(f"workspace: {self.base_dir}")
        print(f"database: {self.db_path}")
        passed = 0
        results: list[dict] = []
        for index, case in enumerate(self.cases(), start=1):
            try:
                detail = case.fn()
                status = "PASS"
                passed += 1
            except Exception as exc:  # noqa: BLE001 - live scorecard should record failures.
                detail = f"{type(exc).__name__}: {exc}"
                status = "FAIL"
            results.append({"status": status, "category": case.category, "name": case.name, "detail": detail})
            print(f"[{status}] {index:02d}. {case.category} - {case.name}")
            print(f"      measure: {case.contract_measure}")
            print(f"      outcome: {detail}")
        print()
        print(f"score: {passed}/{len(results)}")
        print(json.dumps(results, indent=2))
        return 0 if passed == len(results) else 1

    def service(self) -> tuple[AletheiaService, str]:
        if self._service and self._token:
            return self._service, self._token
        self._service = AletheiaService(
            self.memory,
            ServiceConfig(db_path=str(self.db_path), auto_migrate=True, auth_required=True, console_enabled=True),
        )
        auth = AuthService(self.memory)
        client = auth.create_client(name="live-m9-admin", client_type="admin")
        _token, raw = auth.create_token(
            client_id=client.id,
            namespace_grants=["*"],
            capabilities=["memory:admin"],
            privacy_ceiling="secret",
        )
        self._token = raw
        return self._service, raw

    def request(self, method: str, path: str, payload: dict | None = None) -> dict:
        service, token = self.service()
        headers = {"Authorization": f"Bearer {token}", "X-Request-ID": "req_live_m9"}
        status, envelope = service.handle_http(
            method=method,
            path=path,
            headers=headers,
            body=json_body(payload or {}) if payload is not None else b"",
        )
        assert status == 200, envelope
        return envelope["data"]

    def ensure_plugin(self) -> str:
        if self.plugin_id:
            return self.plugin_id
        self.plugin_dir.mkdir(exist_ok=True)
        self.plugin_dir.joinpath("aletheia-plugin.toml").write_text(
            """
[plugin]
name = "live-m9-plugin"
display_name = "Live M9 Plugin"
version = "1.3.0"
plugin_type = "extractor"
entrypoint = "live_m9_plugin:Plugin"
description = "Live scorecard plugin."

[compatibility]
aletheia_min_version = "1.3.0"
api_contract_version = "v1"

[permissions]
permissions_required = ["write_candidate"]
external_network_access = false
reads_memory_content = false
writes_memory = true
stores_data = false
""",
            encoding="utf-8",
        )
        discovered = self.memory.discover_plugins(str(self.plugin_dir))
        assert discovered and discovered[0]["name"] == "live-m9-plugin"
        installation = self.memory.install_plugin(plugin_path=str(self.plugin_dir), trust_level="local")
        enabled = self.memory.enable_plugin(
            installation.id,
            reason="Live M9 scorecard plugin.",
            approved_permissions=["write_candidate"],
            actor="live-scorecard",
        )
        assert enabled.status == "enabled"
        self.plugin_id = installation.id
        return installation.id

    def case_public_contracts(self) -> str:
        health = self.memory.health()
        assert health["schema_version"] == "1.3.0"
        contracts = self.memory.list_public_contracts()
        names = {contract.name for contract in contracts}
        required = {"HTTP API v1", "MCP tools v1", "Python SDK v1", "Plugin interface v1", "Config schema v1", "Aletheia archive format v1"}
        assert required <= names
        api_versions = self.memory.list_api_contract_versions()
        assert any(api.api_type == "http" and api.version == "v1" for api in api_versions)
        deprecations = self.memory.check_deprecations()
        assert deprecations["status"] == "passed"
        report = self.memory.compatibility_report(include_runtime=False)
        assert report["migration_support"]["to"] == "1.3.0"
        return f"schema={health['schema_version']}, contracts={len(contracts)}, api_versions={len(api_versions)}, deprecations={deprecations['notice_count']}"

    def case_plugins(self) -> str:
        plugin_id = self.ensure_plugin()
        blocked = self.memory.run_plugin_operation(plugin_id=plugin_id, operation="attempt_active_write", namespace=NAMESPACE)
        assert blocked["status"] == "blocked"
        result = self.memory.run_plugin_operation(
            plugin_id=plugin_id,
            operation="remember_candidate",
            namespace=NAMESPACE,
            payload={
                "subject": "agent",
                "predicate": "uses",
                "object": "candidate-first plugin writes",
                "memory_type": "task",
                "evidence_text": "M9 plugins write candidate memories by default.",
            },
        )
        assert result["status"] == "ok"
        candidate = self.memory.read_candidate(result["candidate_id"])
        assert candidate.candidate_status == "pending_review"
        assert self.memory.list_claims(namespace=NAMESPACE) == []
        logs = self.memory.list_plugin_logs(plugin_id=plugin_id)
        assert len(logs) >= 2
        return f"plugin={plugin_id}, candidate={candidate.id}, logs={len(logs)}"

    def case_conformance(self) -> str:
        self.ensure_plugin()
        passed = []
        for suite in self.memory.list_conformance_suites():
            run = self.memory.run_conformance(suite=suite.name)
            assert run.status == "passed", (suite.name, run)
            assert run.passed_count >= 1
            passed.append(suite.name)
        runs = self.memory.list_conformance_runs(limit=100)
        assert len(runs) >= len(passed)
        return f"suites={','.join(sorted(passed))}, runs={len(runs)}"

    def case_sdk(self) -> str:
        sync_methods = {
            "version",
            "check_compatibility",
            "remember_candidate",
            "remember_active",
            "ingest",
            "list_candidates",
            "promote_candidate",
            "health_report",
            "backup_status",
            "compatibility_report",
            "contracts",
            "doctor",
            "v1_gate",
        }
        async_methods = {"check_compatibility", "remember_candidate", "remember_active", "compatibility_report", "v1_gate"}
        assert all(hasattr(AletheiaClient, method) for method in sync_methods)
        assert all(hasattr(AsyncAletheiaClient, method) for method in async_methods)
        releases = self.memory.list_sdk_releases()
        names = {release.sdk_name for release in releases}
        assert {"python-sync", "python-async"} <= names
        return f"sync_methods={len(sync_methods)}, async_methods={len(async_methods)}, sdk_releases={len(releases)}"

    def case_adapters(self) -> str:
        scaffold = self.memory.scaffold_adapter(
            adapter_type="python-sdk",
            name="live-python-sdk-adapter",
            output_path=str(self.adapter_dir),
        )
        assert (self.adapter_dir / "agent_loop.py").exists()
        run = self.memory.run_conformance(suite="agent-adapter", target=scaffold["path"], target_type="agent_adapter")
        assert run.status == "passed"
        certification = self.memory.certify_adapter(path=scaffold["path"], adapter_type="python-sdk")
        assert certification.status == "certified"
        return f"adapter={scaffold['id']}, conformance={run.id}, certification={certification.id}"

    def case_docs_examples(self) -> str:
        build = self.memory.build_docs(output_dir=str(self.docs_dir))
        assert build.status == "passed"
        assert build.examples_validated is True
        examples = self.memory.list_examples()
        result = self.memory.test_doc_examples()
        assert result["status"] == "passed"
        static_docs = [
            "v1_public_contracts.md",
            "plugin_developer_guide.md",
            "adapter_developer_guide.md",
            "security_privacy_guide.md",
            "backup_restore_guide.md",
            "migration_guide.md",
            "cli_reference.md",
            "http_api_reference.md",
            "mcp_reference.md",
            "examples.md",
        ]
        missing = [name for name in static_docs if not (ROOT / "docs" / name).exists()]
        assert not missing, missing
        return f"docs={build.id}, files={len(build.metadata['files'])}, examples={len(examples)}, static_guides={len(static_docs)}"

    def case_doctor_compatibility(self) -> str:
        doctor = self.memory.doctor_run()
        assert doctor.status in {"healthy", "healthy_with_warnings"}
        assert any(check["name"] == "schema_version" for check in doctor.checks)
        report = self.memory.compatibility_report()
        assert report["api_version"] == "v1"
        assert report["schema_version"] == "1.3.0"
        matrix = self.memory.list_compatibility_matrix()
        assert any(entry.component_type == "plugin_api" for entry in matrix)
        return f"doctor={doctor.status}, checks={len(doctor.checks)}, compatibility_entries={len(matrix)}"

    def case_v1_gate(self) -> str:
        if self.memory.docs_status()["status"] != "passed":
            self.memory.build_docs(output_dir=str(self.docs_dir))
        gate = self.memory.v1_gate_run(metadata={"allow_missing_backup": True, "live_scorecard": True})
        assert gate.status == "passed"
        check_names = {check["name"] for check in gate.checks}
        required = {
            "unit_tests_passed",
            "integration_tests_passed",
            "migration_tests_passed",
            "conformance_passed",
            "docs_examples_passed",
            "openapi_generated",
            "compatibility_matrix_generated",
            "no_critical_integrity_findings",
            "no_unrestricted_default_tokens",
            "no_external_telemetry_default",
            "m8_readiness_ok",
        }
        assert required <= check_names
        release = self.memory.release_manifest()
        assert release.version == "1.3.0"
        assert release.migration_range == "1.0.x -> 1.3.0"
        return f"gate={gate.id}, checks={len(gate.checks)}, release={release.id}"

    def case_console_api_cli(self) -> str:
        contracts = self.request("GET", "/v1/contracts")
        assert any(item["name"] == "HTTP API v1" for item in contracts)
        compatibility = self.request("GET", "/v1/compatibility/report")
        assert compatibility["api_version"] == "v1"
        doctor = self.request("POST", "/v1/doctor/run", {})
        assert doctor["checks"]
        docs = self.request("POST", "/v1/docs/build", {"output_dir": str(self.base_dir / "http-docs")})
        assert docs["status"] == "passed"
        gate = self.request("POST", "/v1/v1-gate/run", {"metadata": {"allow_missing_backup": True}})
        assert gate["status"] == "passed"
        schema = openapi_schema()
        assert "/v1/plugins" in schema["paths"]
        assert "/v1/v1-gate/run" in schema["paths"]
        body = self.service()[0]._console_static("/console")[1]["_raw_body"]
        assert "Stable Platform" in body
        cli_contracts = run_cli(["contracts", "list", "--db", str(self.db_path)])
        cli_doctor = run_cli(["doctor", "--db", str(self.db_path)])
        cli_gate = run_cli(["v1-gate", "report", "--db", str(self.db_path)])
        assert "HTTP API v1" in cli_contracts
        assert "package_version" in cli_doctor
        assert "checks" in cli_gate
        return f"http_contracts={len(contracts)}, openapi_paths={len(schema['paths'])}, cli_ok=true"

    def case_definition_complete(self) -> str:
        claim = self.memory.remember(
            namespace=NAMESPACE,
            memory_type="project",
            subject="aletheia",
            predicate="has_m9_live_regression",
            object="M0-M8 behavior still works",
            confidence=0.9,
        )
        results = self.memory.retrieve(namespace=NAMESPACE, query="M0-M8 behavior", mode="hybrid")
        assert any(result.claim_id == claim.id for result in results)
        pack = self.memory.context_pack(NAMESPACE, "M0-M8 behavior", token_budget=800)
        assert pack.id and any(item.claim_id == claim.id for item in pack.items())
        integrity = self.memory.integrity_check(namespace=NAMESPACE)
        readiness = self.memory.readiness_check(namespace=NAMESPACE)
        assert integrity.status in {"passed", "passed_with_warnings"}
        assert readiness.status in {"ready", "ready_with_warnings"}
        required_tables = {
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
        rows = self.memory.store.connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
        tables = {row["name"] for row in rows}
        assert required_tables <= tables
        return f"claim={claim.id}, context={pack.id}, tables={len(required_tables)}, integrity={integrity.status}, readiness={readiness.status}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Aletheia M9 live scorecard.")
    parser.add_argument("--workdir", help="Directory for live test artifacts.")
    parser.add_argument("--db", help="Database path. Defaults to a temp database inside workdir.")
    parser.add_argument("--allow-existing", action="store_true", help="Allow using an existing database.")
    args = parser.parse_args()
    base_dir = Path(args.workdir) if args.workdir else Path(tempfile.mkdtemp(prefix="aletheia-m9-live-"))
    base_dir.mkdir(parents=True, exist_ok=True)
    db_path = Path(args.db) if args.db else base_dir / "m9_live.db"
    if db_path.exists() and not args.allow_existing:
        parser.error(f"Database already exists: {db_path}. Pass --allow-existing to reuse it.")
    scorecard = M9LiveScorecard(base_dir, db_path)
    try:
        return scorecard.run()
    finally:
        scorecard.close()


if __name__ == "__main__":
    raise SystemExit(main())
