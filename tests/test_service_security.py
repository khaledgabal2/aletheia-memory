"""Synthetic HTTP regressions for audit findings 03–08.

Denied requests must not invoke a provider or mutate the referenced memory.
All tokens, source content, providers, and databases are local test fixtures.
"""
from __future__ import annotations

import json
import sys
import types

import pytest

from aletheia import Memory
from aletheia.llm import MockLLMProvider
from aletheia.models import ServiceConfig
from aletheia.service.http import AletheiaService


NS = "tenant/a"
OTHER = "tenant/b"
MARKER = "SYNTHETIC_RESTRICTED_SOURCE"


@pytest.fixture
def memory(tmp_path):
    memory = Memory.open(str(tmp_path / "security.db"), namespace=NS)
    yield memory
    memory.close()


def client(memory, capabilities, *, grants=None, privacy="personal"):
    service = AletheiaService(memory, ServiceConfig(db_path=memory.store.path, rate_limit_enabled=False))
    principal = service.auth.create_client(name="synthetic security fixture", client_type="test")
    _, token = service.auth.create_token(client_id=principal.id, capabilities=capabilities,
                                          namespace_grants=grants or [NS], privacy_ceiling=privacy)

    def call(method, path, payload=None):
        return service.handle_http(method=method, path=path, headers={"Authorization": f"Bearer {token}"},
                                   body=json.dumps(payload).encode() if payload is not None else b"")

    return call


def remember(memory, namespace=NS, **kwargs):
    return memory.remember(namespace=namespace, memory_type="fact", subject=kwargs.pop("subject", "security"),
                           predicate="records", object=kwargs.pop("object", MARKER), **kwargs)


def rows(memory, *tables):
    return {table: [tuple(row) for row in memory.store.connection.execute(f"SELECT * FROM {table} ORDER BY rowid")]
            for table in tables}


@pytest.mark.parametrize("provider", ["plugin:security_probe:factory", "plugin"])
def test_request_cannot_execute_unapproved_python_provider(memory, monkeypatch, provider):
    invoked = []
    module = types.ModuleType("security_probe")
    def factory():
        invoked.append(True)
        return MockLLMProvider()
    module.factory = factory
    monkeypatch.setitem(sys.modules, module.__name__, module)
    monkeypatch.setenv("ALETHEIA_LLM_PLUGIN_ENTRYPOINT", "security_probe:factory")
    call = client(memory, ["memory:read"])
    status, _ = call("POST", "/v1/llm/expand-query", {"namespace": NS, "query": "memory", "provider": provider})
    assert status in {400, 403, 404}
    assert invoked == []
    assert memory.list_llm_runs(namespace=NS) == []
    status, response = call("POST", "/v1/llm/expand-query", {"namespace": NS, "query": "memory", "provider": "mock_llm"})
    assert status == 200, response


@pytest.mark.parametrize("target", ["session", "feedback", "feedback_evidence", "superseding_claim"])
def test_foreign_object_mutations_are_denied_without_changes(memory, target):
    victim = remember(memory, OTHER)
    own = remember(memory, object="own source")
    session = memory.start_session(OTHER, title="foreign session")
    call = client(memory, ["memory:write_candidate", "memory:feedback", "memory:review"])
    requests = {
        "session": (f"/v1/sessions/{session.id}/end", {"namespace": NS, "summary": "foreign mutation"}),
        "feedback": ("/v1/feedback", {"namespace": NS, "target_id": victim.id, "signal": "wrong"}),
        "feedback_evidence": ("/v1/feedback", {"namespace": NS, "target_id": own.id, "signal": "confirmed", "evidence_id": victim.evidence_ids[0]}),
        "superseding_claim": (f"/v1/claims/{own.id}/supersede/{victim.id}", {"reason": "cross-scope replacement"}),
    }
    before = rows(memory, "claims", "sessions", "feedback", "evidence_events", "audit_log")
    path, payload = requests[target]
    status, _ = call("POST", path, payload)
    assert status == 403
    assert rows(memory, *before) == before


@pytest.mark.parametrize("mode", ["candidate", "active", "none"])
def test_session_summary_obeys_explicit_write_mode(memory, mode):
    capabilities = ["memory:write_candidate"] + (["memory:write_active"] if mode == "active" else [])
    call = client(memory, capabilities)
    session = memory.start_session(NS)
    payload = {"summary": "Review this synthetic summary"}
    if mode == "active":
        payload["write_mode"] = "active"
    if mode == "none":
        payload["remember_summary"] = False
    status, response = call("POST", f"/v1/sessions/{session.id}/end", payload)
    assert status == 200, response
    assert memory.get_session(session.id).ended_at
    claims, candidates = memory.list_claims(namespace=NS), memory.list_candidates(NS)
    assert len(claims) == int(mode == "active")
    assert len(candidates) == int(mode == "candidate")
    if candidates:
        assert candidates[0].candidate_status == "pending_review"
        evidence = memory.read_event(candidates[0].evidence_ids[0])
        assert evidence.session_id == session.id
        assert evidence.trust_level != "tool_verified"


def test_candidate_writer_cannot_request_active_session_summary(memory):
    call = client(memory, ["memory:write_candidate"])
    session = memory.start_session(NS)
    before = rows(memory, "sessions", "claims", "candidate_claims", "evidence_events")
    status, _ = call("POST", f"/v1/sessions/{session.id}/end", {"summary": MARKER, "write_mode": "active"})
    assert status == 403
    assert rows(memory, *before) == before


@pytest.mark.parametrize("trace_type", ["retrieval", "context-pack"])
@pytest.mark.parametrize("preexisting", [False, True])
def test_traces_apply_source_privacy_on_creation_and_read(memory, trace_type, preexisting):
    secret = remember(memory, privacy_level="secret")
    public = remember(memory, subject="public", object="security public control", privacy_level="public")
    call = client(memory, ["memory:read"])
    if preexisting:
        trace = (memory.trace_retrieval(NS, query="security", retrieval_mode="lexical") if trace_type == "retrieval"
                 else memory.trace_context_pack(NS, query="security", retrieval_mode="lexical"))
        trace_id = trace.id
    else:
        status, response = call("POST", f"/v1/traces/{trace_type}", {"namespace": NS, "query": "security", "retrieval_mode": "lexical"})
        assert status == 200, response
        trace_id = response["data"]["id"]
        assert secret.id not in {item.target_id for item in memory.list_trace_items(trace_id)}
    for suffix in ["", "/items"]:
        status, response = call("GET", f"/v1/traces/{trace_id}{suffix}")
        assert status == 200, response
        assert MARKER not in json.dumps(response)
        assert secret.id not in json.dumps(response)
        assert public.id in json.dumps(response)
    # Access is evaluated again, including for an older snapshot of a public claim.
    memory.store.connection.execute("UPDATE evidence_events SET privacy_level = 'secret' WHERE id = ?", (public.evidence_ids[0],))
    status, response = call("GET", f"/v1/traces/{trace_id}/items")
    assert status == 200
    assert public.id not in json.dumps(response)


@pytest.mark.parametrize("task", ["summarize-evidence", "suggest-entities", "suggest-categories"])
@pytest.mark.parametrize("restriction", ["privacy", "namespace"])
def test_llm_sources_are_authorized_before_any_provider_call(memory, monkeypatch, task, restriction):
    event = memory.write_event(namespace=NS if restriction == "privacy" else OTHER,
                               source_type="manual", content=MARKER, privacy_level="private" if restriction == "privacy" else "public")
    call = client(memory, ["memory:review"])
    invoked = []
    from aletheia.core import memory as core
    original = core.llm_provider_for_name
    def factory(*args, **kwargs):
        invoked.append(True)
        return original(*args, **kwargs)
    monkeypatch.setattr(core, "llm_provider_for_name", factory)
    status, _ = call("POST", f"/v1/llm/{task}", {"namespace": NS, "evidence_ids": [event.id], "provider": "mock_llm"})
    assert status == 403
    assert invoked == []
    assert memory.list_llm_runs() == []


@pytest.mark.parametrize("path", ["/v1/traces", "/v1/llm/runs", "/v1/metrics/snapshots", "/v1/metrics/latest", "/v1/notifications", "/v1/reports", "/v1/jobs"])
def test_unscoped_operational_lists_require_authorized_scope(memory, path):
    memory.trace_retrieval(OTHER, query=MARKER, retrieval_mode="lexical")
    memory.expand_query(namespace=OTHER, query=MARKER)
    memory.metrics_snapshot(namespace=OTHER)
    call = client(memory, ["memory:read", "memory:review", "memory:jobs"])
    status, response = call("GET", path)
    assert status in {400, 403}
    assert MARKER not in json.dumps(response)
    status, response = call("GET", path + "?namespace=" + NS)
    assert status == 200, response
    assert MARKER not in json.dumps(response)
    status, _ = call("GET", path + "?namespace=" + OTHER)
    assert status == 403


@pytest.mark.parametrize("target", ["session", "feedback", "candidate"])
def test_project_grant_is_checked_against_target_provenance(memory, target):
    memory.create_project(namespace=NS, project_id="allowed", title="Allowed")
    memory.create_project(namespace=NS, project_id="denied", title="Denied")
    own = remember(memory, project_id="allowed", object="allowed control")
    victim = remember(memory, project_id="denied")
    session = memory.start_session(NS, project_id="denied")
    batch = memory.ingest(NS, source_type="manual", content="Remember that denied project information.", project_id="denied")
    memory.extract_candidates(NS, batch_id=batch.id, extractor="mock")
    candidate = memory.list_candidates(NS)[0]
    call = client(memory, ["memory:feedback", "memory:write_candidate", "memory:review"], grants=[NS + "/projects/allowed"])
    requests = {
        "session": (f"/v1/sessions/{session.id}/end", {"project_id": "allowed", "summary": MARKER}),
        "feedback": ("/v1/feedback", {"namespace": NS, "project_id": "allowed", "target_id": victim.id, "signal": "wrong"}),
        "candidate": (f"/v1/candidates/{candidate.id}/promote", {"project_id": "allowed", "reason": "spoofed project"}),
    }
    before = rows(memory, "claims", "sessions", "feedback", "candidate_claims", "audit_log")
    path, payload = requests[target]
    status, _ = call("POST", path, payload)
    assert status == 403
    assert rows(memory, *before) == before
    status, response = call("POST", "/v1/feedback", {"namespace": NS, "project_id": "allowed", "target_id": own.id, "signal": "useful"})
    assert status == 200, response


@pytest.mark.parametrize("route", ["suggest-scope", "suggest-duplicate-merge"])
def test_llm_candidate_source_privacy_is_checked_before_provider(memory, monkeypatch, route):
    batch = memory.ingest(NS, source_type="manual", content=MARKER, privacy_level="private")
    memory.extract_candidates(NS, batch_id=batch.id, extractor="mock")
    candidate = memory.list_candidates(NS)[0]
    call = client(memory, ["memory:review"])
    invoked = []
    monkeypatch.setattr("aletheia.core.memory.llm_provider_for_name", lambda *a, **kw: invoked.append(True))
    status, _ = call("POST", "/v1/llm/" + route, {"namespace": NS, "candidate_id": candidate.id})
    assert status == 403
    assert invoked == []


def test_llm_duplicate_suggestion_authorizes_hidden_merge_targets(memory, monkeypatch):
    batch = memory.ingest(NS, source_type="manual", content="Remember that a public value.", privacy_level="public")
    memory.extract_candidates(NS, batch_id=batch.id, extractor="mock")
    candidate = memory.list_candidates(NS)[0]
    memory.remember(namespace=NS, subject=candidate.subject, predicate=candidate.predicate,
                    object=MARKER, memory_type="fact", privacy_level="private")
    assert memory._llm_merge_candidates(candidate)
    call = client(memory, ["memory:review"])
    invoked = []
    monkeypatch.setattr("aletheia.core.memory.llm_provider_for_name", lambda *a, **kw: invoked.append(True))
    status, _ = call("POST", "/v1/llm/suggest-duplicate-merge", {"namespace": NS, "candidate_id": candidate.id})
    assert status == 403
    assert invoked == []


def test_approved_llm_plugin_requires_enablement_and_live_permission_grants(memory, tmp_path, monkeypatch):
    invoked = []
    module = types.ModuleType("approved_security_provider")
    def factory():
        invoked.append(True)
        return MockLLMProvider()
    module.factory = factory
    monkeypatch.setitem(sys.modules, module.__name__, module)
    plugin = tmp_path / "approved-provider"
    plugin.mkdir()
    (plugin / "aletheia-plugin.toml").write_text('''[plugin]
name = "security-provider"
version = "1.0.0"
plugin_type = "llm_provider"
entrypoint = "approved_security_provider:factory"
description = "Synthetic provider approval test"
[compatibility]
aletheia_min_version = "1.0.0"
api_contract_version = "1.3.0"
[permissions]
permissions_required = ["read_claim_text", "read_evidence_text"]
''')
    installation = memory.install_plugin(plugin_path=str(plugin))
    call = client(memory, ["memory:read", "memory:review"])
    payload = {"namespace": NS, "query": "public memory", "provider": "plugin:" + installation.id}
    status, _ = call("POST", "/v1/llm/expand-query", payload)
    assert status == 403 and invoked == []
    memory.enable_plugin(installation.id, approved_permissions=["read_claim_text", "read_evidence_text"], reason="synthetic operator approval")
    status, response = call("POST", "/v1/llm/expand-query", payload)
    assert status == 200, response
    assert len(invoked) == 1
    event = memory.write_event(namespace=NS, source_type="manual", content="public evidence", privacy_level="public")
    status, response = call("POST", "/v1/llm/summarize-evidence", {**payload, "evidence_ids": [event.id]})
    assert status == 200, response
    # The approved manifest's disclosure policy also applies when a native
    # plugin incorrectly claims it is local-only at runtime.
    permissions = ["read_claim_text", "read_evidence_text", "use_network"]
    memory.store.connection.execute("UPDATE plugin_manifests SET external_network_access = 1, permissions_required_json = ? WHERE id = ?",
                                    (json.dumps(permissions), installation.plugin_manifest_id))
    memory.enable_plugin(installation.id, approved_permissions=permissions, reason="synthetic external provider approval")
    private = memory.write_event(namespace=NS, source_type="manual", content=MARKER, privacy_level="private")
    reviewer = client(memory, ["memory:review"], privacy="private")
    before = len(invoked)
    status, _ = reviewer("POST", "/v1/llm/summarize-evidence", {**payload, "evidence_ids": [private.id]})
    assert status == 403 and len(invoked) == before
    status, response = call("POST", "/v1/llm/summarize-evidence", {**payload, "evidence_ids": [event.id]})
    assert status == 200, response
    before = len(invoked)
    memory.store.connection.execute("DELETE FROM plugin_capability_grants WHERE plugin_installation_id = ? AND permission = 'read_evidence_text'", (installation.id,))
    status, _ = call("POST", "/v1/llm/summarize-evidence", {**payload, "evidence_ids": [event.id]})
    assert status == 403 and len(invoked) == before
    memory.disable_plugin(installation.id, reason="synthetic revocation")
    status, _ = call("POST", "/v1/llm/expand-query", payload)
    assert status == 403 and len(invoked) == before


def test_llm_source_authorization_preserves_provider_disclosure_rules(memory, monkeypatch):
    event = memory.write_event(namespace=NS, source_type="manual", content=MARKER, privacy_level="private")
    call = client(memory, ["memory:review"], privacy="private")
    status, response = call("POST", "/v1/llm/summarize-evidence", {"namespace": NS, "evidence_ids": [event.id]})
    assert status == 200 and MARKER in json.dumps(response)
    class External(MockLLMProvider):
        external_network_access = True
        def complete_json(self, **kwargs):
            pytest.fail("Private evidence must not reach an external provider")
    monkeypatch.setattr("aletheia.core.memory.llm_provider_for_name", lambda *a, **kw: External())
    status, response = call("POST", "/v1/llm/summarize-evidence", {"namespace": NS, "evidence_ids": [event.id], "provider": "local_http"})
    assert status == 400, response


@pytest.mark.parametrize("route", ["/v1/extract", "/v1/eval/sets", "/v1/conflicts", "/v1/inferences"])
def test_analogous_object_routes_authorize_stored_namespace(memory, route):
    call = client(memory, ["memory:review", "memory:evaluate", "memory:extract"])
    if route == "/v1/extract":
        batch = memory.ingest(OTHER, source_type="manual", content=MARKER)
        path, payload = route, {"namespace": NS, "batch_id": batch.id, "extractor": "mock"}
    elif route == "/v1/eval/sets":
        evaluation = memory.create_eval_set(OTHER, name="foreign evaluation")
        path, payload = route + f"/{evaluation.id}/cases", {"query": "foreign", "expected_claim_ids": [], "notes": "cross-scope edit"}
    elif route == "/v1/conflicts":
        remember(memory, OTHER, object="one")
        remember(memory, OTHER, object="two")
        conflict = memory.detect_conflicts(namespace=OTHER)[0]
        path, payload = route + f"/{conflict.id}/resolve", {"strategy": "manual", "note": "cross-scope resolution"}
    else:
        memory.remember(namespace=OTHER, memory_type="project", subject="project:aletheia", predicate="current_milestone", object="M4", project_id="aletheia")
        memory.remember(namespace=OTHER, memory_type="project", subject="M4", predicate="name", object="Reasoned Memory", project_id="aletheia")
        memory.run_inference(OTHER, engines=["factual"], project_id="aletheia", dry_run=False)
        inference = memory.list_inferences(OTHER)[0]
        path, payload = route + f"/{inference.id}/reject", {"reason": "cross-scope rejection"}
    before = rows(memory, "claims", "candidate_claims", "audit_log", "inference_candidates", "conflict_families", "evaluation_cases")
    status, _ = call("POST", path, payload)
    assert status == 403
    assert rows(memory, *before) == before


@pytest.mark.parametrize("path,capability", [("/v1/shares", "memory:share"), ("/v1/grants", "memory:share"),
    ("/v1/sync/conflicts", "memory:sync"), ("/v1/workspaces", "memory:workspace"), ("/v1/workspaces/agent-groups", "memory:workspace"),
    ("/v1/sync/collections", "memory:sync"), ("/v1/sync/runs", "memory:sync"), ("/v1/sync/cursors", "memory:sync"),
    ("/v1/sync/remote-sources", "memory:sync"), ("/v1/grants/consent", "memory:share"), ("/v1/revocations", "memory:sync")])
def test_additional_operational_lists_reject_missing_or_foreign_namespace(memory, path, capability):
    call = client(memory, [capability])
    assert call("GET", path)[0] == 400
    assert call("GET", path + "?namespace=" + OTHER)[0] == 403
    status, response = call("GET", path + "?namespace=" + NS)
    assert status == 200, response


def test_raw_provider_is_rejected_before_import_time_side_effects(memory, tmp_path, monkeypatch):
    marker = tmp_path / "module-loaded"
    (tmp_path / "import_probe.py").write_text("from pathlib import Path\nPath(" + repr(str(marker)) + ").write_text('executed')\n")
    monkeypatch.syspath_prepend(str(tmp_path))
    call = client(memory, ["memory:read"])
    status, _ = call("POST", "/v1/llm/expand-query", {"namespace": NS, "query": "memory", "provider": "plugin:import_probe:provider"})
    assert status in {400, 403, 404}
    assert not marker.exists()
    assert "import_probe" not in sys.modules


def test_llm_conflict_explanation_requires_all_sources(memory, monkeypatch):
    for value, privacy in [("brief", "personal"), (MARKER, "private")]:
        memory.remember(namespace=NS, memory_type="preference", subject="user", predicate="prefers_response_style", object=value, privacy_level=privacy)
    conflict = memory.list_conflicts(namespace=NS)[0]
    call = client(memory, ["memory:review"])
    invoked = []
    monkeypatch.setattr("aletheia.core.memory.llm_provider_for_name", lambda *a, **kw: invoked.append(True))
    status, _ = call("POST", "/v1/llm/explain-conflict", {"conflict_id": conflict.id})
    assert status == 403
    assert invoked == []


def test_project_authorized_llm_evidence_does_not_need_a_caller_project_label(memory):
    memory.create_project(namespace=NS, project_id="allowed", title="Allowed")
    batch = memory.ingest(NS, project_id="allowed", source_type="manual", content="Allowed project evidence")
    call = client(memory, ["memory:review"], grants=[NS + "/projects/allowed"])
    status, response = call("POST", "/v1/llm/summarize-evidence", {"namespace": NS, "evidence_ids": batch.evidence_ids})
    assert status == 200, response
    assert "Allowed project evidence" in json.dumps(response)


@pytest.mark.parametrize("route", ["review", "apply"])
def test_policy_operations_cannot_mutate_foreign_proposals(memory, route):
    proposal = memory.propose_policy_update(OTHER, policy_type="ranking", target_policy_id=None,
        proposed_config={"confidence_weight": 0.4}, reason="synthetic foreign proposal")
    call = client(memory, ["memory:policy"])
    before = rows(memory, "policy_proposals", "audit_log")
    status, _ = call("POST", f"/v1/policies/proposals/{proposal.id}/{route}", {"decision": "approve", "reason": "foreign mutation"})
    assert status == 403
    assert rows(memory, *before) == before


def test_unscoped_global_access_requires_wildcard_grant_even_for_admin(memory, tmp_path):
    memory.trace_retrieval(OTHER, query="foreign query", retrieval_mode="lexical")
    restricted = client(memory, ["memory:admin"])
    assert restricted("GET", "/v1/traces")[0] == 400
    assert restricted("POST", "/v1/jobs/run", {})[0] == 400
    assert restricted("POST", "/v1/metrics/snapshot", {})[0] == 400
    report = memory.export_report(namespace=None, report_type="memory_health", format="json", output_path=str(tmp_path / "global-report.json"))
    assert restricted("GET", f"/v1/reports/{report.id}")[0] == 400
    global_admin = client(memory, ["memory:admin"], grants=["*"])
    assert global_admin("GET", f"/v1/reports/{report.id}")[0] == 200
    global_reader = client(memory, ["memory:read"], grants=["*"])
    status, response = global_reader("GET", "/v1/traces")
    assert status == 200 and OTHER in json.dumps(response)
    no_read = client(memory, ["memory:feedback"], grants=["*"])
    assert no_read("GET", "/v1/metrics/latest")[0] == 403


def test_session_summary_failure_rolls_back_session_end(memory, monkeypatch):
    call = client(memory, ["memory:write_candidate"])
    session = memory.start_session(NS)
    before = rows(memory, "sessions", "evidence_events", "candidate_claims", "audit_log")
    original = memory._write_audit
    def fail_candidate_audit(**kwargs):
        if kwargs.get("action") == "service.remember_candidate":
            raise RuntimeError("synthetic candidate audit failure")
        return original(**kwargs)
    monkeypatch.setattr(memory, "_write_audit", fail_candidate_audit)
    assert call("POST", f"/v1/sessions/{session.id}/end", {"summary": MARKER})[0] == 500
    assert rows(memory, *before) == before


def test_llm_run_list_rechecks_current_source_privacy(memory):
    event = memory.write_event(namespace=NS, source_type="manual", content=MARKER, privacy_level="public")
    run = memory.summarize_evidence(namespace=NS, evidence_ids=[event.id])
    call = client(memory, ["memory:review"])
    status, response = call("GET", "/v1/llm/runs?namespace=" + NS)
    assert status == 200 and run["llm_run_id"] in json.dumps(response)
    memory.store.connection.execute("UPDATE evidence_events SET privacy_level = 'private' WHERE id = ?", (event.id,))
    status, response = call("GET", "/v1/llm/runs?namespace=" + NS)
    assert status == 200 and run["llm_run_id"] not in json.dumps(response)


def test_trace_summary_hides_unclassified_and_higher_privacy_query_text(memory):
    legacy = memory.trace_retrieval(NS, query=MARKER, retrieval_mode="lexical")
    privileged = client(memory, ["memory:read"], privacy="secret")
    status, response = privileged("POST", "/v1/traces/retrieval", {"namespace": NS, "query": MARKER, "retrieval_mode": "lexical"})
    assert status == 200, response
    high_id = response["data"]["id"]
    reader = client(memory, ["memory:read"])
    for path in [f"/v1/traces/{legacy.id}", f"/v1/traces/{high_id}", "/v1/traces?namespace=" + NS]:
        status, response = reader("GET", path)
        assert status == 200 and MARKER not in json.dumps(response)
    status, response = privileged("GET", f"/v1/traces/{high_id}")
    assert status == 200 and response["data"]["trace"]["query"] == MARKER


@pytest.fixture
def federated(memory, tmp_path):
    sender = Memory.open(str(tmp_path / "sender.db"), namespace=NS)
    sender.create_federation_identity(display_name="synthetic sender", protected=False)
    memory.create_federation_identity(display_name="synthetic receiver", protected=False)
    recipient = sender.add_peer(peer_identity=memory.export_federation_identity(), reason="synthetic fixture")
    memory.add_peer(peer_identity=sender.export_federation_identity(), reason="synthetic fixture")
    packages = {}
    for namespace in [NS, OTHER]:
        remember(sender, namespace, object=namespace + " synthetic record")
        grant = sender.create_share_grant(name=namespace, namespace=namespace, recipient_peer_ids=[recipient.id],
            permissions=["read_claims", "read_evidence"], privacy_ceiling="personal", reason="synthetic grant")
        path = tmp_path / (namespace.replace("/", "-") + ".aletsync")
        sender.export_share_bundle(share_id=grant.id, output_path=str(path), encrypt=True)
        packages[namespace] = (grant, path)
    yield sender, recipient, packages
    sender.close()


@pytest.mark.parametrize("dry_run", [False, True])
def test_federation_import_authorizes_the_signed_grant_namespace(memory, federated, dry_run):
    _, _, packages = federated
    call = client(memory, ["memory:share", "memory:sync"])
    before = rows(memory, "candidate_claims", "evidence_events", "peer_devices", "share_grants", "sync_runs", "federation_audit_events")
    status, _ = call("POST", "/v1/shares/import", {"namespace": NS, "input_path": str(packages[OTHER][1]), "dry_run": dry_run})
    assert status == 403
    assert rows(memory, *before) == before
    status, response = call("POST", "/v1/shares/import", {"input_path": str(packages[NS][1]), "dry_run": dry_run})
    assert status == 200, response


def test_federation_import_rejects_signed_items_outside_the_grant_scope(memory, federated):
    from aletheia.core import federation as fed
    sender, _, packages = federated
    grant, path = packages[NS]
    manifest, payload = fed._read_bundle(memory, str(path))
    payload["payloads"]["claims"][0]["namespace"] = OTHER
    fed._write_bundle(str(path), manifest=manifest, payload=payload, encrypt=True,
        signer=sender.active_federation_identity(), recipients=sender.list_share_recipients(grant.id))
    call = client(memory, ["memory:share", "memory:sync"])
    before = rows(memory, "candidate_claims", "evidence_events", "share_grants", "sync_runs")
    status, _ = call("POST", "/v1/shares/import", {"input_path": str(path)})
    assert status == 400
    assert rows(memory, *before) == before


def test_federation_history_filters_scope_before_limit(memory, federated, monkeypatch):
    import asyncio
    from aletheia import AletheiaClient, AsyncAletheiaClient
    _, _, packages = federated
    runs = {namespace: memory.import_share_bundle(input_path=str(path)) for namespace, (_, path) in packages.items()}
    memory.store.connection.execute("UPDATE sync_runs SET started_at = '2099-01-01T00:00:00Z' WHERE id = ?", (runs[OTHER].id,))
    call = client(memory, ["memory:sync", "memory:share"])
    for path in ["/v1/sync/collections", "/v1/sync/runs", "/v1/sync/cursors", "/v1/sync/remote-sources"]:
        status, response = call("GET", path + "?namespace=" + NS + "&limit=1")
        assert status == 200 and response["data"], response
        assert packages[OTHER][0].id not in json.dumps(response)
        assert runs[OTHER].id not in json.dumps(response)
    status, response = call("GET", "/v1/sync/runs?namespace=" + NS + "&limit=1")
    assert response["data"][0]["id"] == runs[NS].id
    before = rows(memory, "sync_runs", "federation_audit_events")
    status, _ = call("POST", "/v1/sync/run", {"collection_id": runs[OTHER].collection_id, "dry_run": True})
    assert status == 403 and rows(memory, *before) == before
    def request(_self, method, path, payload=None):
        status, response = call(method, path, payload)
        assert status == 200, response
        return response["data"]
    monkeypatch.setattr(AletheiaClient, "_request", request)
    assert AletheiaClient("http://127.0.0.1").sync_runs(namespace=NS, limit=1)[0]["id"] == runs[NS].id
    assert asyncio.run(AsyncAletheiaClient("http://127.0.0.1").remote_sources(namespace=NS))
