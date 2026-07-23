"""Live M6 scorecard: local service, agent interoperability, and protocol security."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import tempfile
import threading
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from aletheia import Memory
from aletheia.adapters import HttpAgentMemoryAdapter
from aletheia.client import AletheiaClient, AletheiaForbiddenError
from aletheia.models import ServiceConfig
from aletheia.service.auth import CAPABILITIES, AuthService, DEFAULT_LOCAL_AGENT_CAPABILITIES
from aletheia.service.errors import ServiceError
from aletheia.service.http import AletheiaDaemon, AletheiaService, openapi_schema
from aletheia.service.mcp import McpToolRegistry


NAMESPACE = "user/default"
PROJECT = "aletheia"

REQUIRED_M6_TABLES = {
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
}

REQUIRED_ENDPOINTS = {
    "/v1/health",
    "/v1/ready",
    "/v1/version",
    "/v1/openapi.json",
    "/v1/context-pack",
    "/v1/retrieve",
    "/v1/search",
    "/v1/remember",
    "/v1/feedback",
    "/v1/outcomes",
    "/v1/retrieval-judgments",
    "/v1/ingest",
    "/v1/extract",
    "/v1/candidates",
    "/v1/candidates/{candidate_id}",
    "/v1/candidates/{candidate_id}/promote",
    "/v1/candidates/{candidate_id}/reject",
    "/v1/claims/{claim_id}",
    "/v1/claims/{claim_id}/explain",
    "/v1/claims/{claim_id}/promote",
    "/v1/claims/{claim_id}/demote",
    "/v1/claims/{claim_id}/scope",
    "/v1/claims/{old_claim_id}/supersede/{new_claim_id}",
    "/v1/audit/{target_type}/{target_id}",
    "/v1/sessions/start",
    "/v1/projects",
    "/v1/conflicts",
    "/v1/confidence/{claim_id}",
    "/v1/curate/preview",
    "/v1/infer/run",
    "/v1/inferences",
    "/v1/reflections",
    "/v1/derivation/{target_type}/{target_id}",
    "/v1/eval/sets",
    "/v1/optimize/retrieval",
    "/v1/learning/run",
    "/v1/policies/proposals",
    "/v1/jobs",
    "/v1/jobs/run",
    "/v1/health-report",
}


@dataclass
class CaseResult:
    category: str
    case: str
    interface: str
    passed: bool
    details: str


class M6Runner:
    def __init__(self, db_path: Path, verbose: bool = False):
        self.db_path = db_path
        self.verbose = verbose
        self.results: list[CaseResult] = []
        self.ids: dict[str, str] = {}
        self.tokens: dict[str, str] = {}

    def run(self) -> list[CaseResult]:
        cases: list[tuple[str, str, str, Callable[[], str]]] = [
            ("Migration", "M5-compatible database migrates to 1.3.0 with M6 tables", "API", self.case_migration),
            ("Migration", "Migration is idempotent and creates no clients, tokens, daemon, or MCP process", "API", self.case_migration_idempotent),
            ("Auth", "API clients and scoped tokens can be created explicitly", "API", self.case_create_clients_tokens),
            ("Auth", "Raw token is shown once and only token hashes are stored", "API", self.case_token_hash_storage),
            ("Seed", "Seed retrievable, secret, project, and explainable memories", "API", self.case_seed_memory),
            ("Daemon", "Stale schema is refused when auto-migrate is disabled", "Service", self.case_stale_schema_refusal),
            ("HTTP", "Health, readiness, version, and OpenAPI endpoints return envelopes", "HTTP", self.case_health_openapi),
            ("OpenAPI", "OpenAPI includes all required M6 endpoints and shared schemas", "HTTP", self.case_openapi_complete),
            ("HTTP", "Context-pack endpoint returns markdown, structure, provenance, and usage", "HTTP", self.case_context_pack),
            ("HTTP", "Retrieve/search endpoints return governed memory with provenance IDs", "HTTP", self.case_retrieve_search),
            ("HTTP", "Remember defaults to candidate write with evidence and audit", "HTTP", self.case_remember_candidate),
            ("HTTP", "Active write is blocked without memory:write_active", "HTTP", self.case_active_write_blocked),
            ("HTTP", "Idempotency key replays same write and rejects changed payload", "HTTP", self.case_idempotency),
            ("HTTP", "Feedback, outcomes, and retrieval judgments are exposed", "HTTP", self.case_feedback_outcome_judgment),
            ("HTTP", "Audit and explain endpoints work without direct DB access", "HTTP", self.case_audit_explain),
            ("HTTP", "Ingest, extract, candidate list, promote, and reject endpoints work", "HTTP", self.case_ingest_extract_candidates),
            ("HTTP", "Sessions and projects endpoints work", "HTTP", self.case_sessions_projects),
            ("HTTP", "Governance endpoints are capability gated", "HTTP", self.case_governance_gates),
            ("HTTP", "Inference, reflection, and derivation endpoints are exposed through service", "HTTP", self.case_reasoning_endpoints),
            ("HTTP", "Evaluation, learning, policies, jobs, and health-report admin gates hold", "HTTP", self.case_admin_endpoints),
            ("Auth", "Requests without tokens, revoked tokens, and expired tokens are rejected", "HTTP", self.case_token_failures),
            ("Auth", "Namespace grants block ungranted projects and do not downgrade silently", "HTTP", self.case_namespace_isolation),
            ("Auth", "Privacy ceiling omits secret memory without leaking secret text", "HTTP", self.case_privacy_ceiling),
            ("Audit", "Service request logs are metadata-only by default", "HTTP", self.case_request_logging),
            ("RateLimit", "Per-token rate limit returns rate_limited and can be disabled", "HTTP", self.case_rate_limit),
            ("MCP", "MCP registry exposes required governed tools", "MCP", self.case_mcp_tool_manifest),
            ("MCP", "memory_context_pack, memory_search, memory_feedback, and memory_audit work", "MCP", self.case_mcp_read_feedback_audit),
            ("MCP", "memory_remember is candidate-first and logs invocations", "MCP", self.case_mcp_remember_candidate),
            ("MCP", "MCP active writes and namespace escapes are blocked", "MCP", self.case_mcp_gates),
            ("Client", "Local daemon starts on 127.0.0.1 and Python client calls health/context/remember", "Daemon+SDK", self.case_daemon_and_client),
            ("Client", "Generic HTTP adapter supports before/after call and candidate memory", "SDK", self.case_adapter),
            ("Worker", "Worker run processes success and failure jobs with audit", "HTTP", self.case_worker),
            ("Compatibility", "Existing library recall still works after M6 service operations", "API", self.case_backward_compatibility),
        ]
        for category, case, interface, fn in cases:
            try:
                detail = fn()
                self.results.append(CaseResult(category, case, interface, True, detail))
            except Exception as exc:  # noqa: BLE001 - live scorecard should continue.
                self.results.append(CaseResult(category, case, interface, False, str(exc)))
        return self.results

    def case_migration(self) -> str:
        memory = Memory.open(str(self.db_path), namespace=NAMESPACE)
        try:
            health = memory.health()
            assert health["schema_version"] == "1.3.0"
            names = self._tables(memory)
            assert REQUIRED_M6_TABLES.issubset(names)
            assert memory.get_ranking_policy("rpol_default").active_version_id == "rpv_default_v1"
            return f"schema_version={health['schema_version']}, m6_tables={len(REQUIRED_M6_TABLES)}"
        finally:
            memory.close()

    def case_migration_idempotent(self) -> str:
        memory = Memory.open(str(self.db_path), namespace=NAMESPACE)
        try:
            before_policy_versions = len(memory.list_ranking_policy_versions("rpol_default"))
            memory.store.migrate()
            after_policy_versions = len(memory.list_ranking_policy_versions("rpol_default"))
            assert before_policy_versions == after_policy_versions
            assert self._count(memory, "api_tokens") == 0
            assert self._count(memory, "api_clients") == 0
            assert self._count(memory, "service_instance_log") == 0
            assert self._count(memory, "mcp_tool_invocation_log") == 0
            return "no token/client/daemon/mcp side effects"
        finally:
            memory.close()

    def case_create_clients_tokens(self) -> str:
        memory = Memory.open(str(self.db_path), namespace=NAMESPACE)
        try:
            auth = AuthService(memory)
            agent = auth.create_client(name="local-contract-agent", client_type="agent")
            admin = auth.create_client(name="local-admin", client_type="admin")
            project_agent = auth.create_client(name="project-scoped-agent", client_type="agent")
            expired_agent = auth.create_client(name="expired-agent", client_type="agent")
            _token, raw = auth.create_token(
                client_id=agent.id,
                namespace_grants=[NAMESPACE],
                capabilities=DEFAULT_LOCAL_AGENT_CAPABILITIES,
                privacy_ceiling="personal",
            )
            _admin_token, admin_raw = auth.create_token(
                client_id=admin.id,
                namespace_grants=[NAMESPACE],
                capabilities=sorted(CAPABILITIES),
                privacy_ceiling="secret",
            )
            _project_token, project_raw = auth.create_token(
                client_id=project_agent.id,
                namespace_grants=[f"{NAMESPACE}/projects/{PROJECT}"],
                capabilities=["memory:context", "memory:read"],
                privacy_ceiling="personal",
            )
            _expired_token, expired_raw = auth.create_token(
                client_id=expired_agent.id,
                namespace_grants=[NAMESPACE],
                capabilities=["memory:context"],
                expires_at="2000-01-01T00:00:00+00:00",
            )
            self.tokens.update({"agent": raw, "admin": admin_raw, "project": project_raw, "expired": expired_raw})
            self.ids.update({"agent_client": agent.id, "admin_client": admin.id})
            return f"clients={len(auth.list_clients())}, tokens={len(auth.list_tokens())}"
        finally:
            memory.close()

    def case_token_hash_storage(self) -> str:
        memory = Memory.open(str(self.db_path), namespace=NAMESPACE)
        try:
            raw = self.tokens["agent"]
            row = memory.store.connection.execute("SELECT token_prefix, token_hash FROM api_tokens LIMIT 1").fetchone()
            assert raw.startswith("atl_")
            assert row["token_prefix"] == raw[:12]
            assert row["token_hash"] != raw
            assert raw not in json.dumps([dict(item) for item in memory.store.connection.execute("SELECT * FROM api_tokens")])
            return f"raw_prefix={row['token_prefix']}, stored_hash_len={len(row['token_hash'])}"
        finally:
            memory.close()

    def case_seed_memory(self) -> str:
        memory = Memory.open(str(self.db_path), namespace=NAMESPACE)
        try:
            memory.create_project(NAMESPACE, PROJECT, title="Aletheia Memory Service")
            visible = memory.remember(
                namespace=NAMESPACE,
                memory_type="project",
                subject="project:aletheia",
                predicate="current_milestone",
                object="M6 Agent Interoperability",
                confidence=0.92,
                importance=0.9,
                project_id=PROJECT,
            )
            secret_event = memory.write_event(
                namespace=NAMESPACE,
                source_type="manual",
                content="m6-secret-service-detail",
                privacy_level="secret",
            )
            secret = memory.write_claim(
                namespace=NAMESPACE,
                memory_type="project",
                subject="project:aletheia",
                predicate="has_secret_note",
                object="m6-secret-service-detail",
                evidence_ids=[secret_event.id],
                confidence=0.9,
                project_id=PROJECT,
            )
            self.ids.update({"visible_claim": visible.id, "secret_claim": secret.id})
            return f"visible_claim={visible.id}, secret_claim={secret.id}"
        finally:
            memory.close()

    def case_stale_schema_refusal(self) -> str:
        stale = self.db_path.with_name("stale.db")
        connection = sqlite3.connect(stale)
        connection.execute("CREATE TABLE schema_version (id INTEGER PRIMARY KEY, version TEXT NOT NULL, applied_at TEXT)")
        connection.execute("INSERT INTO schema_version VALUES (1, '0.6.0', '2026-01-01T00:00:00+00:00')")
        connection.commit()
        connection.close()
        try:
            AletheiaService.open(ServiceConfig(db_path=str(stale), auto_migrate=False))
        except ServiceError as exc:
            assert exc.code == "stale_schema"
            return "stale_schema refused"
        raise AssertionError("stale schema unexpectedly opened")

    def case_health_openapi(self) -> str:
        with self.open_service() as service:
            for path in ["/v1/health", "/v1/ready", "/v1/version", "/v1/openapi.json"]:
                status, envelope = self.get(service, path)
                assert status == 200
                self.assert_success_envelope(envelope)
            return "health/ready/version/openapi envelopes ok"

    def case_openapi_complete(self) -> str:
        schema = openapi_schema()
        assert schema["info"]["version"] == "1.3.0"
        assert REQUIRED_ENDPOINTS.issubset(schema["paths"])
        assert "bearerAuth" in schema["components"]["securitySchemes"]
        assert "ResponseEnvelope" in schema["components"]["schemas"]
        assert "ErrorEnvelope" in schema["components"]["schemas"]
        return f"documented_paths={len(schema['paths'])}"

    def case_context_pack(self) -> str:
        with self.open_service() as service:
            status, envelope = self.post(
                service,
                "/v1/context-pack",
                self.tokens["agent"],
                {
                    "namespace": NAMESPACE,
                    "project_id": PROJECT,
                    "query": "current milestone service",
                    "retrieval_mode": "hybrid",
                    "record_usage": True,
                },
            )
            assert status == 200
            self.assert_success_envelope(envelope)
            assert "## Memory Context" in envelope["data"]["markdown"]
            assert envelope["data"]["provenance"]
            usage_count = self._count(service.memory, "context_usage_events")
            assert usage_count > 0
            return f"context_pack={envelope['data']['context_pack_id']}, usage_events={usage_count}"

    def case_retrieve_search(self) -> str:
        with self.open_service() as service:
            payload = {"namespace": NAMESPACE, "project_id": PROJECT, "query": "M6 Agent Interoperability", "mode": "hybrid"}
            for path in ["/v1/retrieve", "/v1/search"]:
                status, envelope = self.post(service, path, self.tokens["agent"], payload)
                assert status == 200
                assert any(item["claim_id"] == self.ids["visible_claim"] for item in envelope["data"])
                assert envelope["data"][0]["evidence_ids"]
            return "retrieve/search returned visible project memory"

    def case_remember_candidate(self) -> str:
        with self.open_service() as service:
            status, envelope = self.post(service, "/v1/remember", self.tokens["agent"], self.remember_payload())
            assert status == 200
            candidate = envelope["data"]["candidate"]
            assert envelope["data"]["write_mode"] == "candidate"
            audit = service.memory.audit(candidate["id"])
            assert any(row["action"] == "service.remember_candidate" for row in audit["audit"])
            self.ids["service_candidate"] = candidate["id"]
            return f"candidate={candidate['id']}"

    def case_active_write_blocked(self) -> str:
        with self.open_service() as service:
            status, envelope = self.post(
                service,
                "/v1/remember",
                self.tokens["agent"],
                self.remember_payload(write_mode="active"),
            )
            assert status == 403
            assert envelope["error"]["details"]["required_capability"] == "memory:write_active"
            return "active write blocked with 403"

    def case_idempotency(self) -> str:
        with self.open_service() as service:
            payload = self.remember_payload(predicate="idempotent_service_write")
            status, first = self.post(service, "/v1/remember", self.tokens["agent"], payload, {"Idempotency-Key": "m6-live-1"})
            assert status == 200
            status, replay = self.post(service, "/v1/remember", self.tokens["agent"], payload, {"Idempotency-Key": "m6-live-1"})
            assert status == 200
            assert replay["data"]["candidate"]["id"] == first["data"]["candidate"]["id"]
            changed = dict(payload, object="changed payload")
            status, conflict = self.post(service, "/v1/remember", self.tokens["agent"], changed, {"Idempotency-Key": "m6-live-1"})
            assert status == 409
            assert conflict["error"]["code"] == "idempotency_conflict"
            return f"replayed_candidate={first['data']['candidate']['id']}"

    def case_feedback_outcome_judgment(self) -> str:
        with self.open_service() as service:
            claim_id = self.ids["visible_claim"]
            status, feedback = self.post(
                service,
                "/v1/feedback",
                self.tokens["agent"],
                {"namespace": NAMESPACE, "target_id": claim_id, "signal": "useful", "note": "Useful service context."},
            )
            assert status == 200
            status, outcome = self.post(
                service,
                "/v1/outcomes",
                self.tokens["agent"],
                {"namespace": NAMESPACE, "task_id": "m6-live-task", "outcome": "success", "score": 1.0},
            )
            assert status == 200
            status, judgment = self.post(
                service,
                "/v1/retrieval-judgments",
                self.tokens["agent"],
                {
                    "namespace": NAMESPACE,
                    "query": "M6",
                    "result_id": claim_id,
                    "judgment": "relevant",
                    "expected_rank": 1,
                },
            )
            assert status == 200
            return f"feedback={feedback['data']['id']}, outcome={outcome['data']['id']}, judgment={judgment['data']['id']}"

    def case_audit_explain(self) -> str:
        with self.open_service() as service:
            status, audit = self.get(service, f"/v1/audit/claim/{self.ids['visible_claim']}", self.tokens["agent"])
            assert status == 200
            assert audit["data"]["audit"]
            status, explanation = self.get(service, f"/v1/claims/{self.ids['visible_claim']}/explain", self.tokens["agent"])
            assert status == 200
            assert explanation["data"]["claim"]["id"] == self.ids["visible_claim"]
            return "audit trail and claim explanation returned"

    def case_ingest_extract_candidates(self) -> str:
        with self.open_service() as service:
            status, ingest = self.post(
                service,
                "/v1/ingest",
                self.tokens["admin"],
                {
                    "namespace": NAMESPACE,
                    "content": "Aletheia M6 should focus on local service protocols. User prefers candidate-first agent memory writes.",
                    "source_type": "live_m6",
                    "project_id": PROJECT,
                },
            )
            assert status == 200
            status, extract = self.post(
                service,
                "/v1/extract",
                self.tokens["admin"],
                {"namespace": NAMESPACE, "batch_id": ingest["data"]["id"], "max_candidates": 3},
            )
            assert status == 200
            assert extract["data"]["stored_candidate_count"] > 0
            status, candidates = self.get(service, f"/v1/candidates?namespace={NAMESPACE}", self.tokens["admin"])
            assert status == 200
            assert candidates["data"]
            candidate_id = candidates["data"][0]["id"]
            status, promoted = self.post(service, f"/v1/candidates/{candidate_id}/promote", self.tokens["admin"], {"reason": "Live M6 review."})
            assert status == 200
            reject_payload = self.remember_payload(predicate="reject_me")
            status, remembered = self.post(service, "/v1/remember", self.tokens["agent"], reject_payload)
            assert status == 200
            reject_id = remembered["data"]["candidate"]["id"]
            status, rejected = self.post(service, f"/v1/candidates/{reject_id}/reject", self.tokens["admin"], {"reason": "Live M6 rejection."})
            assert status == 200
            return f"extracted={extract['data']['stored_candidate_count']}, promoted={promoted['data']['id']}, rejected={rejected['data']['candidate_id']}"

    def case_sessions_projects(self) -> str:
        with self.open_service() as service:
            status, session = self.post(
                service,
                "/v1/sessions/start",
                self.tokens["agent"],
                {"namespace": NAMESPACE, "project_id": PROJECT, "title": "M6 live service session"},
            )
            assert status == 200
            session_id = session["data"]["id"]
            status, listed = self.get(service, f"/v1/sessions?namespace={NAMESPACE}", self.tokens["agent"])
            assert status == 200
            assert any(item["id"] == session_id for item in listed["data"])
            status, ended = self.post(service, f"/v1/sessions/{session_id}/end", self.tokens["agent"], {"summary": "M6 live test ended."})
            assert status == 200
            status, projects = self.get(service, f"/v1/projects?namespace={NAMESPACE}", self.tokens["agent"])
            assert status == 200
            assert any(item["id"] == PROJECT for item in projects["data"])
            return f"session={ended['data']['id']}, projects={len(projects['data'])}"

    def case_governance_gates(self) -> str:
        with self.open_service() as service:
            status, conflicts = self.get(service, f"/v1/conflicts?namespace={NAMESPACE}", self.tokens["agent"])
            assert status == 200
            status, confidence = self.get(service, f"/v1/confidence/{self.ids['visible_claim']}", self.tokens["agent"])
            assert status == 200
            status, recompute = self.post(service, "/v1/confidence/recompute", self.tokens["agent"], {"namespace": NAMESPACE})
            assert status == 403
            status, curate = self.post(service, "/v1/curate/preview", self.tokens["agent"], {"namespace": NAMESPACE})
            assert status == 403
            return f"conflicts={len(conflicts['data'])}, confidence={confidence['data']['truth_confidence']:.2f}"

    def case_reasoning_endpoints(self) -> str:
        with self.open_service() as service:
            status, infer = self.post(service, "/v1/infer/run", self.tokens["admin"], {"namespace": NAMESPACE, "max_inferences": 3})
            assert status == 200
            status, inferences = self.get(service, f"/v1/inferences?namespace={NAMESPACE}", self.tokens["agent"])
            assert status == 200
            status, reflection = self.post(
                service,
                "/v1/reflections",
                self.tokens["admin"],
                {
                    "namespace": NAMESPACE,
                    "title": "M6 service reflection",
                    "source_claim_ids": [self.ids["visible_claim"]],
                    "text": "Aletheia now exposes memory over service protocols.",
                    "reason": "Live M6 reflection.",
                },
            )
            assert status == 200
            reflection_id = reflection["data"]["id"]
            status, reflections = self.get(service, f"/v1/reflections?namespace={NAMESPACE}", self.tokens["agent"])
            assert status == 200
            status, expanded = self.get(service, f"/v1/reflections/{reflection_id}/expand", self.tokens["agent"])
            assert status == 200
            status, derivation = self.get(service, f"/v1/derivation/reflection/{reflection_id}", self.tokens["agent"])
            assert status == 200
            return f"inference_run={infer['data']['id']}, reflections={len(reflections['data'])}, derivation_nodes={len(derivation['data']['nodes'])}"

    def case_admin_endpoints(self) -> str:
        with self.open_service() as service:
            status, health_forbidden = self.get(service, f"/v1/health-report?namespace={NAMESPACE}", self.tokens["agent"])
            assert status == 403
            status, health = self.get(service, f"/v1/health-report?namespace={NAMESPACE}", self.tokens["admin"])
            assert status == 200
            status, eval_set = self.post(service, "/v1/eval/sets", self.tokens["admin"], {"namespace": NAMESPACE, "name": "m6_live_eval"})
            assert status == 200
            status, case = self.post(
                service,
                f"/v1/eval/sets/{eval_set['data']['id']}/cases",
                self.tokens["admin"],
                {"query": "M6 service", "expected_claim_ids": [self.ids["visible_claim"]]},
            )
            assert status == 200
            status, eval_run = self.post(
                service,
                f"/v1/eval/sets/{eval_set['data']['id']}/run",
                self.tokens["admin"],
                {"namespace": NAMESPACE},
            )
            assert status == 200
            status, learning = self.post(service, "/v1/learning/run", self.tokens["admin"], {"namespace": NAMESPACE, "dry_run": True})
            assert status == 200
            status, policies = self.get(service, f"/v1/policies/proposals?namespace={NAMESPACE}", self.tokens["admin"])
            assert status == 200
            return f"health={health['data']['id']}, eval_run={eval_run['data']['id']}, learning={learning['data']['id']}, policies={len(policies['data'])}"

    def case_token_failures(self) -> str:
        with self.open_service() as service:
            status, no_token = self.post(service, "/v1/context-pack", None, {"namespace": NAMESPACE, "query": "m6"})
            assert status == 401
            memory = service.memory
            auth = service.auth
            active = next(token for token in auth.list_tokens(include_inactive=True) if token.token_prefix == self.tokens["agent"][:12])
            auth.revoke_token(active.id, reason="Live M6 revocation test.")
            status, revoked = self.post(service, "/v1/context-pack", self.tokens["agent"], {"namespace": NAMESPACE, "query": "m6"})
            assert status == 401
            status, expired = self.post(service, "/v1/context-pack", self.tokens["expired"], {"namespace": NAMESPACE, "query": "m6"})
            assert status == 401
            new_token, raw = auth.create_token(
                client_id=self.ids["agent_client"],
                namespace_grants=[NAMESPACE],
                capabilities=DEFAULT_LOCAL_AGENT_CAPABILITIES,
            )
            self.tokens["agent"] = raw
            assert memory.store.connection.execute("SELECT status FROM api_tokens WHERE id = ?", (new_token.id,)).fetchone()
            return "missing/revoked/expired tokens rejected"

    def case_namespace_isolation(self) -> str:
        with self.open_service() as service:
            status, allowed = self.post(
                service,
                "/v1/context-pack",
                self.tokens["project"],
                {"namespace": NAMESPACE, "project_id": PROJECT, "query": "M6"},
            )
            assert status == 200
            status, denied = self.post(
                service,
                "/v1/context-pack",
                self.tokens["project"],
                {"namespace": NAMESPACE, "project_id": "private_finances", "query": "M6"},
            )
            assert status == 403
            assert "private_finances" not in json.dumps(denied)
            return "project-scoped token allowed aletheia and denied private_finances"

    def case_privacy_ceiling(self) -> str:
        with self.open_service() as service:
            status, envelope = self.post(
                service,
                "/v1/context-pack",
                self.tokens["agent"],
                {"namespace": NAMESPACE, "project_id": PROJECT, "query": "m6-secret-service-detail"},
            )
            assert status == 200
            raw = json.dumps(envelope)
            assert "m6-secret-service-detail" not in raw
            assert "access policy" in raw or envelope["data"]["items"] == []
            return "secret memory omitted with generic access-policy warning"

    def case_request_logging(self) -> str:
        with self.open_service() as service:
            status, envelope = self.post(
                service,
                "/v1/context-pack",
                self.tokens["agent"],
                {"namespace": NAMESPACE, "query": "logging body secret should not be stored"},
                {"X-Request-ID": "req_live_m6_logging"},
            )
            assert status == 200
            rows = service.service_requests(limit=100)
            row = next(item for item in rows if item["request_id"] == "req_live_m6_logging")
            assert row["request_hash"] is None
            assert row["response_hash"] is None
            assert row["log_mode"] == "metadata_only"
            assert "logging body secret" not in json.dumps(rows)
            return f"request_id={row['request_id']}, log_mode={row['log_mode']}"

    def case_rate_limit(self) -> str:
        with tempfile.TemporaryDirectory() as temp:
            db_path = Path(temp) / "rate.db"
            memory = Memory.open(str(db_path), namespace=NAMESPACE)
            auth = AuthService(memory)
            client = auth.create_client(name="rate-agent", client_type="agent")
            _token, raw = auth.create_token(client_id=client.id, namespace_grants=[NAMESPACE], capabilities=["memory:context"])
            service = AletheiaService(
                memory,
                ServiceConfig(db_path=str(db_path), auto_migrate=True, auth_required=True, rate_limit_per_minute=1),
            )
            try:
                assert self.post(service, "/v1/context-pack", raw, {"namespace": NAMESPACE, "query": "one"})[0] == 200
                status, limited = self.post(service, "/v1/context-pack", raw, {"namespace": NAMESPACE, "query": "two"})
                assert status == 429
                assert limited["error"]["code"] == "rate_limited"
                service.config = ServiceConfig(db_path=str(db_path), auto_migrate=True, auth_required=True, rate_limit_enabled=False)
                assert self.post(service, "/v1/context-pack", raw, {"namespace": NAMESPACE, "query": "three"})[0] == 200
                return "rate_limited then disabled config allowed request"
            finally:
                service.close()

    def case_mcp_tool_manifest(self) -> str:
        with self.open_service(auth_required=False) as service:
            registry = McpToolRegistry(service, namespace=NAMESPACE, mode="read_write_candidate")
            names = {tool["name"] for tool in registry.list_tools()}
            assert {
                "memory_context_pack",
                "memory_search",
                "memory_remember",
                "memory_feedback",
                "memory_audit",
                "memory_explain_claim",
                "memory_health",
            }.issubset(names)
            assert not any("SQL" in tool["description"] for tool in registry.list_tools())
            return f"mcp_tools={len(names)}"

    def case_mcp_read_feedback_audit(self) -> str:
        with self.open_service(auth_required=False) as service:
            registry = McpToolRegistry(service, namespace=NAMESPACE, mode="read_write_candidate")
            context = registry.invoke("memory_context_pack", {"query": "M6 service"})
            search = registry.invoke("memory_search", {"query": "M6 service"})
            feedback = registry.invoke("memory_feedback", {"target_id": self.ids["visible_claim"], "signal": "useful"})
            audit = registry.invoke("memory_audit", {"target_type": "claim", "target_id": self.ids["visible_claim"]})
            assert context["context_pack_id"].startswith("ctx_")
            assert search
            assert feedback["id"].startswith("fbk_")
            assert audit["audit"]
            return "context/search/feedback/audit succeeded"

    def case_mcp_remember_candidate(self) -> str:
        with self.open_service(auth_required=False) as service:
            registry = McpToolRegistry(service, namespace=NAMESPACE, mode="read_write_candidate")
            result = registry.invoke(
                "memory_remember",
                {
                    "memory_type": "preference",
                    "subject": "user",
                    "predicate": "uses_mcp",
                    "object": "candidate-first memory",
                    "evidence_text": "MCP should create candidates by default.",
                },
            )
            assert result["write_mode"] == "candidate"
            assert not any(claim.predicate == "uses_mcp" for claim in service.memory.list_claims(namespace=NAMESPACE))
            assert any(row["tool_name"] == "memory_remember" for row in service.mcp_invocations(limit=20))
            return f"mcp_candidate={result['candidate']['id']}"

    def case_mcp_gates(self) -> str:
        with self.open_service(auth_required=False) as service:
            registry = McpToolRegistry(service, namespace=NAMESPACE, mode="read_write_candidate")
            try:
                registry.invoke("memory_remember", {**self.remember_payload(), "write_mode": "active"})
            except PermissionError:
                active_blocked = True
            else:
                active_blocked = False
            try:
                registry.invoke("memory_search", {"namespace": "user/other", "query": "M6"})
            except PermissionError:
                namespace_blocked = True
            else:
                namespace_blocked = False
            assert active_blocked and namespace_blocked
            return "active write and namespace escape blocked"

    def case_daemon_and_client(self) -> str:
        daemon = AletheiaDaemon(
            ServiceConfig(
                db_path=str(self.db_path),
                host="127.0.0.1",
                port=0,
                auto_migrate=False,
                auth_required=True,
                rate_limit_enabled=False,
            )
        )
        thread = None
        try:
            host, port = daemon.start()
            assert host == "127.0.0.1"
            assert port > 0
            thread = threading.Thread(target=daemon.httpd.serve_forever, daemon=True)
            thread.start()
            base_url = f"http://{host}:{port}"
            with urllib.request.urlopen(base_url + "/v1/health", timeout=5) as response:  # noqa: S310 - local daemon.
                assert response.status == 200
            client = AletheiaClient(base_url, token=self.tokens["admin"], timeout=5)
            assert client.health()["status"] == "ok"
            pack = client.context_pack(namespace=NAMESPACE, project_id=PROJECT, query="M6 service")
            assert "## Memory Context" in pack["markdown"]
            remembered = client.remember(
                idempotency_key="m6-daemon-client",
                namespace=NAMESPACE,
                write_mode="candidate",
                memory_type="project",
                subject="project:aletheia",
                predicate="daemon_client_live_test",
                object="passed",
                evidence_text="Daemon and client live test passed.",
            )
            self.ids["daemon_candidate"] = remembered["candidate"]["id"]
            self.ids["daemon_base_url"] = base_url
            return f"daemon={base_url}, candidate={remembered['candidate']['id']}"
        finally:
            daemon.shutdown()
            if thread is not None:
                thread.join(timeout=2)

    def case_adapter(self) -> str:
        daemon = AletheiaDaemon(
            ServiceConfig(
                db_path=str(self.db_path),
                host="127.0.0.1",
                port=0,
                auto_migrate=False,
                auth_required=True,
                rate_limit_enabled=False,
            )
        )
        thread = None
        try:
            host, port = daemon.start()
            thread = threading.Thread(target=daemon.httpd.serve_forever, daemon=True)
            thread.start()
            client = AletheiaClient(f"http://{host}:{port}", token=self.tokens["admin"], timeout=5)
            adapter = HttpAgentMemoryAdapter(client)
            markdown = adapter.before_agent_call(namespace=NAMESPACE, query="M6 adapter", project_id=PROJECT)
            candidate_id = adapter.remember_candidate(
                namespace=NAMESPACE,
                subject="agent",
                predicate="uses_adapter",
                object="Aletheia HTTP memory adapter",
                memory_type="project",
                evidence_text="The live adapter test wrote a candidate memory.",
            )
            adapter.after_agent_call(namespace=NAMESPACE, task_id="m6-adapter-live", outcome="success", notes="Adapter worked.")
            assert markdown.startswith("## Memory Context")
            assert candidate_id.startswith("cand_")
            return f"adapter_candidate={candidate_id}"
        finally:
            daemon.shutdown()
            if thread is not None:
                thread.join(timeout=2)

    def case_worker(self) -> str:
        with self.open_service() as service:
            success_payload = {"namespace": NAMESPACE, "job_type": "memory_health_check", "payload": {"namespace": NAMESPACE}}
            failure_payload = {
                "namespace": NAMESPACE,
                "job_type": "run_evaluation",
                "payload": {"namespace": NAMESPACE, "max_attempts": 1},
            }
            assert self.post(service, "/v1/jobs", self.tokens["admin"], success_payload)[0] == 200
            assert self.post(service, "/v1/jobs", self.tokens["admin"], failure_payload)[0] == 200
            status, first = self.post(service, "/v1/jobs/run", self.tokens["admin"], {"namespace": NAMESPACE, "max_jobs": 1})
            assert status == 200
            assert len(first["data"]) == 1
            status, second = self.post(service, "/v1/jobs/run", self.tokens["admin"], {"namespace": NAMESPACE, "max_jobs": 5})
            assert status == 200
            failed = service.memory.list_jobs(namespace=NAMESPACE, status="failed")
            completed = service.memory.list_jobs(namespace=NAMESPACE, status="completed")
            assert failed and completed
            audit_rows = service.memory.store.connection.execute(
                "SELECT action FROM audit_log WHERE target_id IN (?, ?)",
                (failed[0].id, completed[0].id),
            ).fetchall()
            actions = {row["action"] for row in audit_rows}
            assert {"job.failed", "job.completed"}.issubset(actions)
            return f"completed={completed[0].id}, failed={failed[0].id}"

    def case_backward_compatibility(self) -> str:
        memory = Memory.open(str(self.db_path), namespace=NAMESPACE)
        try:
            claim = memory.remember(
                namespace=NAMESPACE,
                memory_type="preference",
                subject="user",
                predicate="prefers_backward_compatibility",
                object="library APIs still work after service milestones",
            )
            assert memory.retrieve(NAMESPACE, "backward compatibility")[0].claim_id == claim.id
            assert memory.context_pack(NAMESPACE, query="backward compatibility").items()
            return f"library_claim={claim.id}"
        finally:
            memory.close()

    def open_service(self, *, auth_required: bool = True):
        runner = self

        class ServiceContext:
            def __enter__(self):
                self.memory = Memory.open(str(runner.db_path), namespace=NAMESPACE)
                self.service = AletheiaService(
                    self.memory,
                    ServiceConfig(
                        db_path=str(runner.db_path),
                        auto_migrate=True,
                        auth_required=auth_required,
                        rate_limit_per_minute=1000,
                    ),
                )
                return self.service

            def __exit__(self, exc_type, exc, tb):
                self.service.close()
                return False

        return ServiceContext()

    def get(self, service: AletheiaService, path: str, token: str | None = None, headers: dict | None = None):
        request_headers = headers or {}
        if token:
            request_headers = {"Authorization": f"Bearer {token}", **request_headers}
        return service.handle_http(method="GET", path=path, headers=request_headers)

    def post(
        self,
        service: AletheiaService,
        path: str,
        token: str | None,
        payload: dict,
        headers: dict | None = None,
    ):
        request_headers = headers or {}
        if token:
            request_headers = {"Authorization": f"Bearer {token}", **request_headers}
        return service.handle_http(method="POST", path=path, headers=request_headers, body=json.dumps(payload).encode("utf-8"))

    def remember_payload(self, **overrides) -> dict:
        payload = {
            "namespace": NAMESPACE,
            "write_mode": "candidate",
            "memory_type": "project",
            "subject": "project:aletheia",
            "predicate": "service_memory_write",
            "object": "candidate-first over HTTP",
            "project_id": PROJECT,
            "evidence_text": "Live M6 service write should create a candidate.",
        }
        payload.update(overrides)
        return payload

    @staticmethod
    def assert_success_envelope(envelope: dict) -> None:
        assert "data" in envelope
        assert "request_id" in envelope
        assert "warnings" in envelope
        assert "pagination" in envelope

    @staticmethod
    def _tables(memory: Memory) -> set[str]:
        return {
            row["name"]
            for row in memory.store.connection.execute(
                "SELECT name FROM sqlite_master WHERE type IN ('table', 'virtual table')"
            ).fetchall()
        }

    @staticmethod
    def _count(memory: Memory, table: str) -> int:
        return int(memory.store.connection.execute(f"SELECT count(*) AS count FROM {table}").fetchone()["count"])


def print_scorecard(results: list[CaseResult]) -> None:
    passed = sum(1 for result in results if result.passed)
    total = len(results)
    print("# M6 Agent Interoperability Live Scorecard")
    print(f"Passed: {passed}/{total}")
    print()
    current = None
    for result in results:
        if result.category != current:
            current = result.category
            print(f"## {current}")
        mark = "PASS" if result.passed else "FAIL"
        print(f"- [{mark}] {result.case} ({result.interface})")
        print(f"  {result.details}")
    print()
    if passed != total:
        raise SystemExit(1)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run live M6 agent interoperability checks.")
    parser.add_argument("--db")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    if args.db:
        db_path = Path(args.db)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        runner = M6Runner(db_path, verbose=args.verbose)
        print_scorecard(runner.run())
        return 0

    with tempfile.TemporaryDirectory(prefix="aletheia-m6-live-") as temp:
        runner = M6Runner(Path(temp) / "aletheia.db", verbose=args.verbose)
        print_scorecard(runner.run())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
