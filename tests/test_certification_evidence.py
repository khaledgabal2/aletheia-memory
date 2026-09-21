"""Certification requires observed behavior; structure and missing probes do not pass."""
from contextlib import closing
import json
from pathlib import Path

import pytest

from aletheia import Memory
from aletheia.client import AletheiaClient
from aletheia.core import platform


@pytest.fixture
def memory(tmp_path):
    with closing(Memory.open(str(tmp_path / "memory.db"), namespace="audit/certification")) as memory:
        yield memory


def scaffold(memory, tmp_path, kind="python-sdk"):
    return Path(memory.scaffold_adapter(adapter_type=kind, name="synthetic adapter", output_path=str(tmp_path / "adapter"))["path"])


@pytest.mark.parametrize("source", ["this is not valid python !!!", "def run_once(: pass", "return 1"])
def test_invalid_python_is_not_certified(memory, tmp_path, source):
    path = scaffold(memory, tmp_path)
    (path / "agent_loop.py").write_text(source)
    certificate = memory.certify_adapter(path=str(path), adapter_type="python-sdk")
    assert certificate.status == "failed" and certificate.certified_at is None
    assert memory.get_conformance_run(certificate.conformance_run_id).failed_count > 0


@pytest.mark.parametrize("change", ["no_op", "active_write", "wrong_namespace", "swallow_errors", "top_level_effect"])
def test_valid_but_unverified_code_is_never_executed_or_certified(memory, tmp_path, change):
    path = scaffold(memory, tmp_path)
    source = (path / "agent_loop.py").read_text()
    sentinel = tmp_path / "must-not-exist"
    if change == "no_op":
        source = "def run_once(base_url, token, namespace, query):\n    return 'success'\n"
    elif change == "active_write":
        source = source.replace("remember_candidate", "remember_active")
    elif change == "wrong_namespace":
        source = source.replace("namespace=namespace", "namespace='other'")
    elif change == "swallow_errors":
        source += "\ndef run_once(*args):\n    return 'success'\n"
    else:
        source = f"from pathlib import Path\nPath({str(sentinel)!r}).write_text('unsafe')\n" + source
    (path / "agent_loop.py").write_text(source)
    certificate = memory.certify_adapter(path=str(path), adapter_type="python-sdk")
    assert certificate.status == "not_certified" and certificate.certified_at is None
    assert certificate.metadata["assurance"] == "structural"
    assert not sentinel.exists()


@pytest.mark.parametrize("kind", ["generic-http", "mcp-client", "python-sdk"])
def test_bundled_loop_certification_records_observed_effects_without_touching_user_memory(memory, tmp_path, kind):
    path = scaffold(memory, tmp_path, kind)
    before = memory.store.connection.total_changes
    certificate = memory.certify_adapter(path=str(path), adapter_type=kind)
    assert certificate.status == "certified"
    assert certificate.metadata["assurance"] == "behavioral"
    assert certificate.metadata["contract"] == "bundled-sdk-loop-v1"
    assert len(certificate.metadata["source_sha256"]) == 64
    checks = certificate.metadata["probes"]
    assert checks["candidate_writes"] == 1 and checks["active_writes"] == 0
    assert checks["context_read"] and checks["denied_write_preserved_state"] and checks["foreign_namespace_denied"]
    assert not memory.list_claims(namespace=memory.namespace) and not memory.list_candidates(memory.namespace)
    assert memory.store.connection.total_changes > before  # Only certification records in this database.


def test_behavioral_probe_detects_a_regression_in_the_real_sdk(memory, tmp_path, monkeypatch):
    path = scaffold(memory, tmp_path)
    monkeypatch.setattr(AletheiaClient, "remember_candidate", lambda self, **payload: {"status": "success"})
    certificate = memory.certify_adapter(path=str(path), adapter_type="python-sdk")
    assert certificate.status == "failed" and certificate.certified_at is None


@pytest.mark.parametrize("suite", ["kernel", "http-api", "mcp", "python-sdk", "context-pack-schema", "plugin",
                                    "protected-mode", "federation-redaction", "semantic-retrieval", "llm-governance"])
def test_structural_checks_never_claim_behavioral_conformance(memory, suite):
    run = memory.run_conformance(suite=suite, metadata={"assurance": "behavioral", "passed": True})
    assert run.status in {"structural_passed", "incomplete"}
    assert run.metadata["assurance"] == "structural"
    assert run.passed_count == 0


def test_empty_or_unknown_case_suite_cannot_pass(memory):
    suite = platform.get_conformance_suite(memory, "kernel")
    with memory.store.transaction():
        memory.store.connection.execute("DELETE FROM conformance_cases WHERE suite_id = ?", (suite.id,))
    assert memory.run_conformance(suite="kernel").status == "incomplete"
    with memory.store.transaction():
        memory.store.connection.execute("INSERT INTO conformance_cases (id, suite_id, name, description, severity, required, test_ref, created_at, metadata_json) VALUES ('unknown', ?, 'unimplemented', 'fixture', 'critical', 1, 'fixture', '2026-01-01', '{}')", (suite.id,))
    run = memory.run_conformance(suite="kernel")
    assert run.status == "incomplete" and run.skipped_count == 1


def test_structural_or_obsolete_evidence_cannot_satisfy_release_gate(memory):
    for suite in memory.list_conformance_suites():
        run = memory.run_conformance(suite=suite.name)
        # Simulate the historical rows written by the old implementation.
        with memory.store.transaction():
            memory.store.connection.execute("UPDATE conformance_runs SET status = 'passed', metadata_json = '{}' WHERE id = ?", (run.id,))
    gate = memory.v1_gate_run(auto_run_conformance=False, metadata={"allow_missing_backup": True})
    checks = {item["name"]: item for item in gate.checks}
    assert checks["conformance_passed"]["status"] == "failed"
    assert checks["unit_tests_passed"]["status"] == "failed"
    assert checks["integration_tests_passed"]["status"] == "failed"


def test_manifest_adapter_type_must_match_certificate_request(memory, tmp_path):
    path = scaffold(memory, tmp_path)
    certificate = memory.certify_adapter(path=str(path), adapter_type="mcp-client")
    assert certificate.status == "failed" and certificate.certified_at is None


def test_legacy_certificates_and_federation_inventory_do_not_claim_verified_behavior(memory, tmp_path):
    path = scaffold(memory, tmp_path)
    certificate = memory.certify_adapter(path=str(path), adapter_type="python-sdk")
    with memory.store.transaction():
        memory.store.connection.execute("UPDATE adapter_certifications SET metadata_json = '{}' WHERE id = ?", (certificate.id,))
    listed, = memory.list_adapter_certifications()
    assert listed.status == "not_certified" and listed.certified_at is None
    assert listed.metadata["assurance"] == "unverified"
    assert memory.federation_conformance()["status"] == "structural_passed"
    assert memory.federation_conformance()["assurance"] == "structural"


def test_gate_uses_latest_suite_evidence_even_if_an_older_run_passed(memory):
    old = memory.run_conformance(suite="kernel")
    with memory.store.transaction():
        memory.store.connection.execute("UPDATE conformance_runs SET status = 'passed', metadata_json = ? WHERE id = ?",
            (json.dumps({"assurance": "behavioral"}), old.id))
        memory.store.connection.execute("UPDATE conformance_suites SET required_for_v1 = CASE WHEN id = ? THEN 1 ELSE 0 END", (old.suite_id,))
    memory.run_conformance(suite="kernel")
    gate = memory.v1_gate_run(auto_run_conformance=False)
    assert next(check for check in gate.checks if check["name"] == "conformance_passed")["status"] == "failed"
