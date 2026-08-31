"""Onboarding safety and actual packaged-source behavior; synthetic data only."""
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from importlib import metadata
from importlib.resources import files
import os
from pathlib import Path
import runpy
import re
import socket
import sqlite3
import subprocess
import sys
import threading

import pytest

from aletheia import Memory
from aletheia.cli.main import main
from aletheia.diagnostics import diagnose
from aletheia.onboarding import create_starter
from scripts.v1_4_phase0 import local_service, NAMESPACE
from tests.test_v1_4_reads import domain_state, seed, credential


def codes(report):
    return {item["code"] for item in report["checks"]}


def deny_network(*args, **kwargs):
    raise AssertionError("Offline onboarding attempted a network connection")


@pytest.mark.parametrize("answer", ["approve", "decline", None])
def test_embedded_source_runs_offline_with_explicit_review_and_safe_rerun(tmp_path, monkeypatch, capsys, answer):
    create_starter("embedded", tmp_path / "demo")
    monkeypatch.chdir(tmp_path / "demo")
    monkeypatch.setattr(socket.socket, "connect", deny_network)
    def decide(*args):
        if answer is None:
            raise EOFError
        return answer
    monkeypatch.setattr("builtins.input", decide)
    runpy.run_path("memory_demo.py", run_name="__main__")
    output = capsys.readouterr().out
    assert "Trusted results before approval: 0" in output
    assert "User prefers careful architecture notes." in output
    assert ("Reopened successfully" in output) == (answer == "approve")
    memory = Memory.open("aletheia-demo.db", namespace="user/demo", auto_migrate=False)
    try:
        assert len(memory.retrieve("user/demo", "architecture", mode="lexical")) == (1 if answer == "approve" else 0)
        assert len(memory.list_candidates("user/demo", status="pending_review")) == (0 if answer == "approve" else 1)
    finally:
        memory.close()
    before = Path("aletheia-demo.db").read_bytes()
    with pytest.raises(SystemExit, match="already exists"):
        runpy.run_path("memory_demo.py", run_name="__main__")
    assert Path("aletheia-demo.db").read_bytes() == before


@pytest.mark.parametrize("kind", ["embedded", "http-agent", "typescript-agent"])
def test_cli_starter_generation_creates_no_database_and_never_overwrites(tmp_path, monkeypatch, capsys, kind):
    monkeypatch.chdir(tmp_path)
    def no_open(*args, **kwargs):
        raise AssertionError("Generation opened Memory")
    monkeypatch.setattr(Memory, "open", no_open)
    assert main(["examples", "create", "--type", kind, "--output", "demo"]) == 0
    assert not list(tmp_path.glob("*.db"))
    before = {path.name: path.read_bytes() for path in (tmp_path / "demo").iterdir()}
    with pytest.raises(SystemExit):
        main(["examples", "create", "--type", kind, "--output", "demo"])
    assert {path.name: path.read_bytes() for path in (tmp_path / "demo").iterdir()} == before
    assert "raw_token" not in json.dumps(before, default=str)


def test_init_new_and_legacy_scaffolds_refuse_existing_paths_and_symlinks(tmp_path):
    db = tmp_path / "demo.db"
    assert main(["init", "--new", "--db", str(db)]) == 0
    before = db.read_bytes()
    for target in [db, tmp_path / "link.db"]:
        if target != db:
            target.symlink_to(db)
        with pytest.raises(SystemExit):
            main(["init", "--new", "--db", str(target)])
        assert db.read_bytes() == before
    broken = tmp_path / "broken.db"
    broken.symlink_to(tmp_path / "missing.db")
    with pytest.raises(SystemExit):
        main(["init", "--new", "--db", str(broken)])
    assert not (tmp_path / "missing.db").exists()
    memory = Memory.open(str(db))
    try:
        destination = tmp_path / "adapter"
        memory.scaffold_adapter(adapter_type="python-sdk", name="sample", output_path=str(destination))
        marker = destination / "agent_loop.py"
        marker.write_text("do not replace")
        from aletheia.core.errors import ValidationError
        with pytest.raises(ValidationError, match="already exists"):
            memory.scaffold_adapter(adapter_type="python-sdk", name="sample", output_path=str(destination))
        assert marker.read_text() == "do not replace"
    finally:
        memory.close()


def test_read_only_diagnostics_do_not_create_migrate_or_record_data(tmp_path, monkeypatch):
    monkeypatch.setattr(socket.socket, "connect", deny_network)
    missing = tmp_path / "missing" / "database.db"
    assert "database_missing" in codes(diagnose(db_path=str(missing)))
    assert not missing.parent.exists()
    db = tmp_path / "demo.db"
    memory = Memory.open(str(db), namespace="user/demo")
    try:
        empty = diagnose(db_path=str(db), namespace="user/demo")
        assert "empty_namespace" in codes(empty)
        assert empty["status"] == "attention"
        batch = memory.ingest("user/demo", source_type="manual", content="User prefers careful architecture notes.")
        run = memory.extract_candidates("user/demo", batch_id=batch.id)
        pending = memory.list_candidates("user/demo", extraction_run_id=run.id)[0]
        assert "pending_review" in codes(diagnose(db_path=str(db), namespace="user/demo"))
        memory.promote_candidate(pending.id, reason="Explicit fixture approval")
        before = domain_state(memory)
        monkeypatch.setattr(Memory, "open", lambda *args, **kwargs: pytest.fail("Read-only diagnostics called Memory.open"))
        assert "lexical_match" in codes(diagnose(db_path=str(db), namespace="user/demo", query="architecture"))
        assert "lexical_no_match" in codes(diagnose(db_path=str(db), namespace="user/demo", query="zzzz-no-match"))
        assert before == domain_state(memory)
    finally:
        memory.close()


@pytest.mark.parametrize("version,expected", [("1.2.0", "migration_required"), ("9.0.0", "schema_newer")])
def test_read_only_diagnostics_preserve_old_and_future_schemas(tmp_path, version, expected):
    db = tmp_path / "version.db"
    memory = Memory.open(str(db))
    with memory.store.transaction():
        memory.store.connection.execute("UPDATE schema_version SET version=?", (version,))
    memory.close()
    before = db.read_bytes()
    assert expected in codes(diagnose(db_path=str(db)))
    assert db.read_bytes() == before


def test_read_only_diagnostics_identify_invalid_locked_and_unreadable_paths(tmp_path, monkeypatch):
    invalid = tmp_path / "invalid.db"
    invalid.write_bytes(b"not a database")
    assert "database_invalid" in codes(diagnose(db_path=str(invalid)))
    assert "database_unreadable" in codes(diagnose(db_path=str(tmp_path)))
    db = tmp_path / "locked.db"
    Memory.open(str(db)).close()
    with sqlite3.connect(db) as writer:
        writer.execute("PRAGMA journal_mode=DELETE")
        writer.execute("BEGIN EXCLUSIVE")
        assert "database_locked" in codes(diagnose(db_path=str(db)))
        writer.rollback()
    monkeypatch.setattr(os, "access", lambda *args: False)
    assert "database_path_unwritable" in codes(diagnose(db_path=str(tmp_path / "missing.db")))


def test_configuration_errors_and_optional_models_never_leak_values(tmp_path, monkeypatch):
    db = tmp_path / "sensitive-path-marker.db"
    Memory.open(str(db)).close()
    config = tmp_path / "settings.toml"
    config.write_text('[server]\ndb = "' + str(db) + '"\n')
    report = diagnose(config_path=str(config))
    assert "database_ready" in codes(report)
    assert "sensitive-path-marker" not in json.dumps(report)
    monkeypatch.setenv("ALETHEIA_EMBEDDING_ENDPOINT", "http://127.0.0.1:1/secret-path-marker")
    monkeypatch.setenv("ALETHEIA_EMBEDDING_API_KEY", "credential-marker")
    monkeypatch.setenv("ALETHEIA_EMBEDDING_MODEL", "private-model-marker")
    monkeypatch.setenv("ALETHEIA_EMBEDDING_DIMENSION", "bad-dimension")
    monkeypatch.setattr(socket.socket, "connect", deny_network)
    report = diagnose(db_path=str(db), embedding_provider="local_http")
    assert "embedding_configuration_invalid" in codes(report)
    for marker in ["secret-path-marker", "credential-marker", "private-model-marker", "bad-dimension"]:
        assert marker not in json.dumps(report)
    config.write_text('[server]\nport = "bad-port-marker"')
    report = diagnose(config_path=str(config))
    assert "configuration_invalid" in codes(report) and "bad-port-marker" not in json.dumps(report)


def test_service_diagnostics_use_current_permissions_without_admin_or_content(tmp_path, monkeypatch):
    with local_service(tmp_path) as (service, url, tokens):
        visible = seed(service.memory, "diagnostic-content-marker")
        hidden = seed(service.memory, "private-content-marker", privacy="secret")
        monkeypatch.setenv("DIAGNOSTIC_TOKEN", tokens["reader"])
        report = diagnose(service_url=url, token_env="DIAGNOSTIC_TOKEN", namespace=NAMESPACE, query="architecture", claim_id=hidden.id)
        assert {"service_read_ready", "resource_scope_or_privacy_denied"} <= codes(report)
        assert "scope_denied" in codes(diagnose(service_url=url, token_env="DIAGNOSTIC_TOKEN", namespace="user/other"))
        _, no_read = credential(service, ["memory:context"])
        monkeypatch.setenv("DIAGNOSTIC_TOKEN", no_read)
        assert "capability_missing" in codes(diagnose(service_url=url, token_env="DIAGNOSTIC_TOKEN", namespace=NAMESPACE))
        monkeypatch.setenv("DIAGNOSTIC_TOKEN", "invalid-token-marker")
        assert "credentials_invalid" in codes(diagnose(service_url=url, token_env="DIAGNOSTIC_TOKEN", namespace=NAMESPACE))
        for marker in [visible.object, hidden.object, tokens["reader"], hidden.id]:
            assert marker not in json.dumps(report)


@contextmanager
def diagnostic_server(mode):
    requests = []
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass
        def do_GET(self):
            requests.append(self.path)
            status = 302 if mode == "redirect" else 503 if mode == "unavailable" else 404 if mode == "legacy" and self.path.endswith("auth/me") else 200
            self.send_response(status)
            if status == 302:
                self.send_header("Location", "http://203.0.113.1/do-not-follow")
            self.end_headers()
            self.wfile.write(json.dumps({"data": {"api_version": "v2" if mode == "incompatible" else "v1"}}).encode())
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}", requests
    finally:
        server.shutdown(); server.server_close(); thread.join(timeout=5)


@pytest.mark.parametrize("mode,expected", [("legacy", "service_legacy"), ("incompatible", "service_incompatible"), ("redirect", "service_http_error"), ("profile-missing", "profile_missing")])
def test_service_diagnostics_distinguish_legacy_incompatibility_and_redirects(mode, expected):
    with diagnostic_server(mode) as (url, requests):
        assert expected in codes(diagnose(service_url=url))
        assert all("do-not-follow" not in path for path in requests)


def test_provider_checks_are_opt_in_and_unavailability_does_not_fail_core(tmp_path, monkeypatch):
    db = tmp_path / "provider.db"
    Memory.open(str(db)).close()
    with diagnostic_server("unavailable") as (url, requests):
        monkeypatch.setenv("ALETHEIA_EMBEDDING_ENDPOINT", url + "/embeddings")
        monkeypatch.setenv("ALETHEIA_EMBEDDING_MODEL", "synthetic")
        monkeypatch.setenv("ALETHEIA_EMBEDDING_DIMENSION", "4")
        assert "embedding_configured" in codes(diagnose(db_path=str(db), embedding_provider="local_http"))
        assert requests == []
        report = diagnose(db_path=str(db), embedding_provider="local_http", probe_provider=True)
        assert "embedding_unavailable" in codes(report)
        assert report["status"] != "error" and requests == ["/embeddings"]


def test_provider_redirects_warn_without_forwarding_credentials(tmp_path, monkeypatch):
    db = tmp_path / "provider.db"
    Memory.open(str(db)).close()
    with diagnostic_server("redirect") as (url, requests):
        monkeypatch.setenv("ALETHEIA_LLM_ENDPOINT", url)
        monkeypatch.setenv("ALETHEIA_LLM_MODEL", "synthetic")
        monkeypatch.setenv("ALETHEIA_LLM_API_KEY", "synthetic-key-marker")
        report = diagnose(db_path=str(db), llm_provider="local_http", probe_provider=True)
        assert "llm_http_error" in codes(report) and report["status"] == "attention"
        assert requests == ["/"]
        assert "synthetic-key-marker" not in json.dumps(report)


@pytest.mark.parametrize("answer", ["approve", "decline"])
def test_http_starter_runs_separate_agent_and_explicit_operator_review(tmp_path, answer):
    project = tmp_path / "http"
    create_starter("http-agent", project)
    result = subprocess.run([sys.executable, str(project / "operator_demo.py")], cwd=project,
        input=answer + "\n", text=True, capture_output=True, timeout=40)
    assert result.returncode == 0, result.stderr
    assert "Visible context items: 0" in result.stdout
    assert ("Reopened successfully" in result.stdout) == (answer == "approve")
    memory = Memory.open(str(project / "aletheia-http-demo.db"), namespace="user/demo", auto_migrate=False)
    try:
        assert len(memory.retrieve("user/demo", "architecture", mode="lexical")) == (1 if answer == "approve" else 0)
        assert memory.store.connection.execute("SELECT count(*) FROM api_tokens WHERE revoked_at IS NULL").fetchone()[0] == 0
        rows = memory.store.connection.execute("SELECT capability FROM capability_grants JOIN api_tokens ON api_tokens.id=capability_grants.token_id JOIN api_clients ON api_clients.id=api_tokens.client_id WHERE api_clients.name='Demo agent'").fetchall()
        assert {row[0] for row in rows} == {"memory:read", "memory:context", "memory:write_candidate"}
    finally:
        memory.close()
    before = (project / "aletheia-http-demo.db").read_bytes()
    again = subprocess.run([sys.executable, str(project / "operator_demo.py")], cwd=project, text=True, capture_output=True, timeout=10)
    assert again.returncode != 0 and "already exists" in again.stderr
    assert (project / "aletheia-http-demo.db").read_bytes() == before


def test_diagnostics_report_index_mismatch_and_stale_state_without_rebuilding(tmp_path, monkeypatch):
    db = tmp_path / "indexed.db"
    memory = Memory.open(str(db), namespace=NAMESPACE)
    try:
        seed(memory, "index fixture")
        memory.index_semantic(NAMESPACE, provider="local_hash", dimension=8)
        with memory.store.transaction():
            memory.store.connection.execute("UPDATE semantic_index_records SET status='stale'")
        before = domain_state(memory)
        monkeypatch.setattr(socket.socket, "connect", deny_network)
        report = diagnose(db_path=str(db), namespace=NAMESPACE, embedding_provider="local_hash")
        assert {"semantic_index_stale", "semantic_index_mismatch"} <= codes(report)
        assert report["status"] != "error"
        assert before == domain_state(memory)
    finally:
        memory.close()


def test_environment_schema_and_plugin_failures_have_safe_explanations(tmp_path, monkeypatch):
    db = tmp_path / "demo.db"
    memory = Memory.open(str(db))
    memory.close()
    def no_metadata(*args):
        raise metadata.PackageNotFoundError
    monkeypatch.setattr(metadata, "version", no_metadata)
    monkeypatch.setattr(socket.socket, "connect", deny_network)
    import aletheia.llm
    monkeypatch.setattr(aletheia.llm, "PluginLLMProvider", lambda **kwargs: pytest.fail("Diagnostics loaded a plugin"))
    report = diagnose(db_path=str(db), llm_provider="plugin:untrusted_module:factory")
    assert {"package_not_installed", "llm_configuration_invalid"} <= codes(report)
    assert report["status"] != "error"
    monkeypatch.setenv("ALETHEIA_LLM_ENDPOINT", "http://127.0.0.1:1")
    monkeypatch.setenv("ALETHEIA_LLM_MODEL", "synthetic")
    assert "llm_configured" in codes(diagnose(db_path=str(db), llm_provider="local_http"))
    with sqlite3.connect(db) as connection:
        connection.execute("DROP TABLE candidate_claims")
    assert "migration_required" in codes(diagnose(db_path=str(db)))


def test_service_unavailable_and_cli_diagnostics_never_create_database(tmp_path, monkeypatch, capsys):
    # Reserve then close an ephemeral port; no service listens there.
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    assert "service_unavailable" in codes(diagnose(service_url=f"http://127.0.0.1:{port}"))
    monkeypatch.chdir(tmp_path)
    assert main(["doctor", "--read-only", "--db", "absent.db"]) == 1
    assert "database_missing" in capsys.readouterr().out
    assert list(tmp_path.iterdir()) == []
    with pytest.raises(SystemExit):
        main(["doctor", "--read-only", "--db", "absent.db", "--service-url", "http://127.0.0.1:1"])
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("document", ["README.md", "docs/quickstart.md"])
def test_primary_documentation_is_the_actual_packaged_example(document):
    root = Path(__file__).resolve().parents[1]
    code = re.search(r"```python\n(.*?)\n```", (root / document).read_text(), re.S).group(1)
    assert code == files("aletheia").joinpath("starters", "embedded", "memory_demo.py").read_text().strip()


@pytest.mark.parametrize("kind,script,dbname", [("embedded", "memory_demo.py", "aletheia-demo.db"), ("http-agent", "operator_demo.py", "aletheia-http-demo.db")])
def test_new_database_paths_preserve_orphaned_sqlite_companions(tmp_path, monkeypatch, kind, script, dbname):
    create_starter(kind, tmp_path / "demo")
    monkeypatch.chdir(tmp_path / "demo")
    companion = Path(dbname + "-wal")
    companion.write_bytes(b"preserve for recovery")
    with pytest.raises(SystemExit, match="companion"):
        runpy.run_path(script, run_name="__main__")
    assert companion.read_bytes() == b"preserve for recovery"
    assert not Path(dbname).exists()
    with pytest.raises(SystemExit):
        main(["init", "--new", "--db", dbname])
    assert companion.read_bytes() == b"preserve for recovery"
    assert not Path(dbname).exists()
