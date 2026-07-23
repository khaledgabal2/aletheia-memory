"""Dependency-free local HTTP service for M6/M7."""

from __future__ import annotations

import json
import os
import secrets
import sqlite3
import threading
import time
from dataclasses import asdict, replace
from datetime import timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import parse_qs, urlparse

from aletheia import Memory
from aletheia.core.errors import AletheiaError, NotFoundError, ValidationError
from aletheia.core.ids import content_hash, new_id
from aletheia.core.time import parse_iso, utc_now, utc_now_iso
from aletheia.models import ApiToken, ServiceConfig, ServiceHealth
from aletheia.service.auth import AuthContext, AuthService
from aletheia.service.errors import (
    ServiceError,
    forbidden,
    idempotency_conflict,
    not_found,
    rate_limited,
    stale_schema,
    unauthorized,
    validation_error,
)
from aletheia.storage import SCHEMA_VERSION


PUBLIC_ENDPOINTS = {
    ("GET", "/v1/health"),
    ("GET", "/v1/ready"),
    ("GET", "/v1/version"),
    ("GET", "/v1/openapi.json"),
}

STATE_CHANGING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
CONSOLE_API_PREFIXES = (
    "/v1/console",
    "/v1/dashboard",
    "/v1/reviews",
    "/v1/traces",
    "/v1/metrics",
    "/v1/notifications",
    "/v1/reports",
    "/v1/backups",
    "/v1/restore",
    "/v1/encryption",
    "/v1/keys",
    "/v1/redactions",
    "/v1/forget",
    "/v1/tombstones",
    "/v1/retention",
    "/v1/integrity",
    "/v1/migrations",
    "/v1/compact",
    "/v1/exports",
    "/v1/imports",
    "/v1/support",
    "/v1/benchmarks",
    "/v1/release",
    "/v1/readiness",
    "/v1/plugins",
    "/v1/conformance",
    "/v1/compatibility",
    "/v1/contracts",
    "/v1/deprecations",
    "/v1/doctor",
    "/v1/docs",
    "/v1/examples",
    "/v1/adapters",
    "/v1/v1-gate",
    "/v1/federation",
    "/v1/peers",
    "/v1/shares",
    "/v1/sync",
    "/v1/workspaces",
    "/v1/grants",
    "/v1/revocations",
)

CONSOLE_CSS = """
:root { color-scheme: light dark; font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
body { margin: 0; background: #f7f7f4; color: #222; }
header { padding: 24px 28px 16px; border-bottom: 1px solid #ddd8ce; background: #ffffff; }
main { display: grid; gap: 16px; padding: 20px 28px 32px; max-width: 1180px; }
h1 { margin: 0; font-size: 24px; font-weight: 650; }
h2 { margin: 0 0 10px; font-size: 16px; }
section { border: 1px solid #ddd8ce; border-radius: 8px; background: #ffffff; padding: 16px; }
button, input, select { font: inherit; }
button { border: 1px solid #34312b; background: #34312b; color: white; border-radius: 6px; padding: 8px 12px; cursor: pointer; }
input, select { border: 1px solid #c8c2b8; border-radius: 6px; padding: 8px 10px; }
.row { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }
.grid { display: grid; gap: 12px; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); }
.metric { font-size: 24px; font-weight: 700; }
pre { overflow: auto; background: #25231f; color: #f9f5ea; padding: 12px; border-radius: 6px; max-height: 320px; }
@media (prefers-color-scheme: dark) {
  body { background: #171613; color: #eee7d9; }
  header, section { background: #201f1b; border-color: #39352e; }
  input, select { background: #171613; color: #eee7d9; border-color: #4c463d; }
}
"""

CONSOLE_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Aletheia Console</title>
  <link rel="stylesheet" href="/console/assets/app.css" />
</head>
<body>
  <header>
    <h1>Aletheia Console</h1>
  </header>
  <main>
    <section>
      <h2>Session</h2>
      <div class="row">
        <input id="loginToken" type="password" placeholder="Console login token" autocomplete="off" />
        <button id="login">Log In</button>
        <button id="logout">Log Out</button>
      </div>
      <p id="sessionState">Checking session...</p>
    </section>
    <section>
      <h2>Dashboard</h2>
      <div class="row">
        <input id="namespace" value="default" aria-label="Namespace" />
        <button id="refresh">Refresh</button>
        <button id="snapshot">Snapshot</button>
      </div>
      <div id="metrics" class="grid"></div>
    </section>
    <section>
      <h2>Review Queue</h2>
      <div class="row">
        <button id="generate">Generate Tasks</button>
      </div>
      <pre id="reviews">[]</pre>
    </section>
    <section>
      <h2>Trace</h2>
      <div class="row">
        <input id="traceQuery" value="what should I remember?" aria-label="Trace query" />
        <button id="trace">Run Retrieval Trace</button>
      </div>
      <pre id="traceOutput">{}</pre>
    </section>
    <section>
      <h2>Production Hardening</h2>
      <div class="row">
        <button id="encryptStatus">Encryption</button>
        <button id="integrityCheck">Integrity</button>
        <button id="readinessCheck">Readiness</button>
        <button id="supportBundle">Support Bundle</button>
      </div>
      <pre id="hardeningOutput">{}</pre>
    </section>
    <section>
      <h2>Stable Platform</h2>
      <div class="row">
        <button id="contracts">Contracts</button>
        <button id="compatibility">Compatibility</button>
        <button id="doctor">Doctor</button>
        <button id="conformance">Conformance</button>
        <button id="v1Gate">v1 Gate</button>
      </div>
      <pre id="platformOutput">{}</pre>
    </section>
    <section>
      <h2>Federation</h2>
      <div class="row">
        <button id="federationStatus">Status</button>
        <button id="federationPeers">Peers</button>
        <button id="federationShares">Shares</button>
        <button id="federationConflicts">Conflicts</button>
      </div>
      <pre id="federationOutput">{}</pre>
    </section>
  </main>
  <script>
    let csrfToken = sessionStorage.getItem("aletheia_console_csrf") || "";
    const $ = (id) => document.getElementById(id);
    const headers = () => ({
      "Content-Type": "application/json",
      ...(csrfToken ? {"X-CSRF-Token": csrfToken} : {})
    });
    async function api(path, options = {}) {
      const res = await fetch(path, { ...options, headers: { ...headers(), ...(options.headers || {}) } });
      const json = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(json.error?.message || res.statusText);
      return json.data ?? json;
    }
    async function refresh() {
      try {
        const namespace = $("namespace").value || "default";
        const overview = await api(`/v1/dashboard/overview?namespace=${encodeURIComponent(namespace)}`);
        $("sessionState").textContent = "Authenticated";
        $("metrics").innerHTML = Object.entries(overview.metrics || {}).slice(0, 12)
          .map(([key, value]) => `<div><div>${key}</div><div class="metric">${value}</div></div>`).join("");
        const reviews = await api(`/v1/reviews?namespace=${encodeURIComponent(namespace)}&limit=20`);
        $("reviews").textContent = JSON.stringify(reviews, null, 2);
      } catch (err) {
        $("sessionState").textContent = err.message;
      }
    }
    $("login").onclick = async () => {
      const data = await api("/v1/console/login", { method: "POST", body: JSON.stringify({ login_token: $("loginToken").value }) });
      csrfToken = data.csrf_token;
      sessionStorage.setItem("aletheia_console_csrf", csrfToken);
      await refresh();
    };
    $("logout").onclick = async () => {
      await api("/v1/console/logout", { method: "POST", body: "{}" }).catch(() => {});
      csrfToken = "";
      sessionStorage.removeItem("aletheia_console_csrf");
      $("sessionState").textContent = "Logged out";
    };
    $("refresh").onclick = refresh;
    $("snapshot").onclick = async () => {
      await api("/v1/metrics/snapshot", { method: "POST", body: JSON.stringify({ namespace: $("namespace").value || "default", source: "console" }) });
      await refresh();
    };
    $("generate").onclick = async () => {
      await api("/v1/reviews/generate", { method: "POST", body: JSON.stringify({ namespace: $("namespace").value || "default" }) });
      await refresh();
    };
    $("trace").onclick = async () => {
      const trace = await api("/v1/traces/retrieval", { method: "POST", body: JSON.stringify({ namespace: $("namespace").value || "default", query: $("traceQuery").value, limit: 10 }) });
      $("traceOutput").textContent = JSON.stringify(trace, null, 2);
    };
    $("encryptStatus").onclick = async () => {
      $("hardeningOutput").textContent = JSON.stringify(await api("/v1/encryption/status"), null, 2);
    };
    $("integrityCheck").onclick = async () => {
      $("hardeningOutput").textContent = JSON.stringify(await api("/v1/integrity/check", { method: "POST", body: JSON.stringify({ namespace: $("namespace").value || "default", deep: true }) }), null, 2);
    };
    $("readinessCheck").onclick = async () => {
      $("hardeningOutput").textContent = JSON.stringify(await api("/v1/readiness/check", { method: "POST", body: JSON.stringify({ namespace: $("namespace").value || "default" }) }), null, 2);
    };
    $("supportBundle").onclick = async () => {
      $("hardeningOutput").textContent = JSON.stringify(await api("/v1/support/bundle", { method: "POST", body: JSON.stringify({ output_path: "/tmp/aletheia-console-support.zip" }) }), null, 2);
    };
    $("contracts").onclick = async () => {
      $("platformOutput").textContent = JSON.stringify(await api("/v1/contracts"), null, 2);
    };
    $("compatibility").onclick = async () => {
      $("platformOutput").textContent = JSON.stringify(await api("/v1/compatibility/report"), null, 2);
    };
    $("doctor").onclick = async () => {
      $("platformOutput").textContent = JSON.stringify(await api("/v1/doctor/run", { method: "POST", body: "{}" }), null, 2);
    };
    $("conformance").onclick = async () => {
      $("platformOutput").textContent = JSON.stringify(await api("/v1/conformance/suites"), null, 2);
    };
    $("v1Gate").onclick = async () => {
      $("platformOutput").textContent = JSON.stringify(await api("/v1/v1-gate/run", { method: "POST", body: JSON.stringify({ require_docs: false }) }), null, 2);
    };
    $("federationStatus").onclick = async () => {
      $("federationOutput").textContent = JSON.stringify(await api("/v1/federation/status"), null, 2);
    };
    $("federationPeers").onclick = async () => {
      $("federationOutput").textContent = JSON.stringify(await api("/v1/peers"), null, 2);
    };
    $("federationShares").onclick = async () => {
      $("federationOutput").textContent = JSON.stringify(await api("/v1/shares"), null, 2);
    };
    $("federationConflicts").onclick = async () => {
      $("federationOutput").textContent = JSON.stringify(await api("/v1/sync/conflicts"), null, 2);
    };
    refresh();
  </script>
</body>
</html>
"""


class AletheiaService:
    def __init__(self, memory: Memory, config: ServiceConfig):
        self.memory = memory
        self.config = config
        self.auth = AuthService(memory)
        self.lock = threading.RLock()

    @classmethod
    def open(cls, config: ServiceConfig) -> "AletheiaService":
        cls._validate_bind_policy(config)
        if not config.auto_migrate:
            cls._assert_current_schema(config.db_path)
        memory = Memory.open(config.db_path, auto_migrate=config.auto_migrate)
        service = cls(memory, config)
        service._record_config(source="service_open")
        return service

    def close(self) -> None:
        self.memory.close()

    def handle_http(
        self,
        *,
        method: str,
        path: str,
        headers: Mapping[str, str],
        body: bytes = b"",
    ) -> tuple[int, dict]:
        started = time.perf_counter()
        method = method.upper()
        parsed = urlparse(path)
        endpoint = parsed.path
        request_id = self._header(headers, "X-Request-ID") or new_id("req")
        namespace_for_log = None
        client_id = None
        request_hash = self._hash_body(body)
        status = 200
        response: dict[str, Any]
        try:
            if method == "GET" and (endpoint == "/console" or endpoint.startswith("/console/")):
                status, response = self._console_static(endpoint)
                return status, response
            if len(body) > self.config.max_request_bytes:
                raise ServiceError("payload_too_large", "Request body is too large.", status_code=413)
            payload = self._json_body(body)
            query = parse_qs(parsed.query)
            namespace_for_log = payload.get("namespace") if isinstance(payload, dict) else None
            if namespace_for_log is None and query.get("namespace"):
                namespace_for_log = query["namespace"][0]
            auth_context = self._authenticate(method, endpoint, headers)
            client_id = auth_context.client_id
            if self.config.rate_limit_enabled:
                with self.lock:
                    self._check_rate_limit(self._rate_limit_identity(auth_context, headers))
            with self.lock:
                replay = self._idempotency_replay(
                    method=method,
                    endpoint=endpoint,
                    headers=headers,
                    payload=payload,
                    request_hash=request_hash,
                    namespace=namespace_for_log,
                    client_id=client_id,
                )
                if replay is not None:
                    status = int(replay.get("_status_code", 200))
                    response = {key: value for key, value in replay.items() if key != "_status_code"}
                else:
                    replay = None
            if replay is None:
                data, warnings, pagination = self._route(
                    method=method,
                    endpoint=endpoint,
                    query=query,
                    payload=payload,
                    auth_context=auth_context,
                    request_id=request_id,
                    headers=headers,
                )
                response = self._success(data=data, request_id=request_id, warnings=warnings, pagination=pagination)
                with self.lock:
                    self._idempotency_store(
                        method=method,
                        endpoint=endpoint,
                        headers=headers,
                        payload=payload,
                        request_hash=request_hash,
                        namespace=namespace_for_log,
                        client_id=client_id,
                        status_code=status,
                        response=response,
                    )
        except ServiceError as exc:
            status = exc.status_code
            response = self._error(exc, request_id)
        except NotFoundError as exc:
            status = 404
            response = self._error(not_found(str(exc)), request_id)
        except ValidationError as exc:
            status = 400
            response = self._error(validation_error(str(exc)), request_id)
        except AletheiaError as exc:
            status = 400
            response = self._error(validation_error(str(exc)), request_id)
        except Exception:  # noqa: BLE001 - service boundary must envelope errors.
            status = 500
            response = self._error(ServiceError("internal_error", "Internal server error.", status_code=500), request_id)
        finally:
            duration_ms = int((time.perf_counter() - started) * 1000)
            self._log_request(
                request_id=request_id,
                client_id=client_id,
                namespace=namespace_for_log,
                method=method,
                path=endpoint,
                status_code=status,
                duration_ms=duration_ms,
                request_hash=request_hash,
                response=response if "response" in locals() else None,
            )
        return status, response

    def _route(
        self,
        *,
        method: str,
        endpoint: str,
        query: dict[str, list[str]],
        payload: dict,
        auth_context: AuthContext,
        request_id: str,
        headers: Mapping[str, str],
    ) -> tuple[Any, list[str], dict | None]:
        if method == "GET" and endpoint == "/v1/health":
            return asdict(self.service_health()), [], None
        if method == "GET" and endpoint == "/v1/ready":
            return {"ready": True, **asdict(self.service_health())}, [], None
        if method == "GET" and endpoint == "/v1/version":
            return {"service_version": SCHEMA_VERSION, "api_version": "v1"}, [], None
        if method == "GET" and endpoint == "/v1/openapi.json":
            return openapi_schema(), [], None

        if endpoint.startswith("/v1/console"):
            return self._console_endpoint(method, endpoint, query, payload, auth_context, headers=headers), [], None
        if endpoint.startswith("/v1/dashboard"):
            return self._dashboard_endpoint(method, endpoint, query, payload, auth_context), [], None
        if endpoint.startswith("/v1/reviews"):
            return self._reviews_endpoint(method, endpoint, query, payload, auth_context), [], self._pagination_for_list(method, endpoint, query)
        if endpoint.startswith("/v1/traces"):
            return self._traces_endpoint(method, endpoint, query, payload, auth_context), [], self._pagination_for_list(method, endpoint, query)
        if endpoint.startswith("/v1/metrics"):
            return self._metrics_endpoint(method, endpoint, query, payload, auth_context), [], self._pagination_for_list(method, endpoint, query)
        if endpoint.startswith("/v1/notifications"):
            return self._notifications_endpoint(method, endpoint, query, payload, auth_context), [], self._pagination_for_list(method, endpoint, query)
        if endpoint.startswith("/v1/reports"):
            return self._reports_endpoint(method, endpoint, query, payload, auth_context), [], self._pagination_for_list(method, endpoint, query)
        if self._is_m10_endpoint(endpoint):
            return self._m10_endpoint(method, endpoint, query, payload, auth_context), [], self._pagination_for_list(method, endpoint, query)
        if self._is_m9_endpoint(endpoint):
            return self._m9_endpoint(method, endpoint, query, payload, auth_context), [], self._pagination_for_list(method, endpoint, query)
        if self._is_m8_endpoint(endpoint):
            return self._m8_endpoint(method, endpoint, query, payload, auth_context), [], self._pagination_for_list(method, endpoint, query)

        if method == "POST" and endpoint in {"/v1/context-pack", "/v1/context"}:
            self._require(auth_context, "memory:context", payload)
            return self._context_pack(payload, auth_context), [], None
        if method == "POST" and endpoint in {"/v1/retrieve", "/v1/search"}:
            self._require(auth_context, "memory:read", payload)
            return self._retrieve(payload, auth_context), [], None
        if method == "POST" and endpoint == "/v1/remember":
            return self._remember(payload, auth_context), [], None
        if method == "POST" and endpoint == "/v1/feedback":
            self._require(auth_context, "memory:feedback", payload)
            return asdict(self.memory.feedback(**self._feedback_args(payload))), [], None
        if method == "POST" and endpoint == "/v1/outcomes":
            self._require(auth_context, "memory:feedback", payload)
            return asdict(self.memory.record_outcome(**self._outcome_args(payload))), [], None
        if method == "POST" and endpoint == "/v1/retrieval-judgments":
            self._require(auth_context, "memory:feedback", payload)
            return asdict(self.memory.judge_retrieval(**self._retrieval_judgment_args(payload))), [], None
        if method == "POST" and endpoint == "/v1/ingest":
            self._require(auth_context, "memory:ingest", payload)
            return asdict(self.memory.ingest(**self._ingest_args(payload))), [], None
        if method == "POST" and endpoint == "/v1/extract":
            self._require(auth_context, "memory:extract", payload)
            return asdict(self.memory.extract_candidates(**self._extract_args(payload))), [], None
        if endpoint.startswith("/v1/llm/"):
            return self._llm_endpoint(method, endpoint, query, payload, auth_context), [], None

        if method == "GET" and endpoint == "/v1/candidates":
            namespace = self._query_value(query, "namespace")
            self._require(auth_context, "memory:review", {"namespace": namespace})
            candidates = self.memory.list_candidates(
                namespace,
                status=self._query_value(query, "status", none_if_missing=True),
                memory_type=self._query_value(query, "memory_type", none_if_missing=True),
                project_id=self._query_value(query, "project_id", none_if_missing=True),
                limit=self._limit(query),
            )
            return [asdict(candidate) for candidate in candidates], [], self._pagination(len(candidates), query)
        if method == "GET" and endpoint.startswith("/v1/candidates/"):
            parts = endpoint.split("/")
            candidate_id = parts[3]
            if len(parts) == 4:
                self.auth.require_capability(auth_context, "memory:review")
                candidate = self.memory.read_candidate(candidate_id)
                self._require(auth_context, "memory:review", {"namespace": candidate.namespace})
                return asdict(candidate), [], None
            if len(parts) == 5 and method == "GET":
                raise not_found(f"Unsupported candidate endpoint: {endpoint}")
        if method == "POST" and endpoint.startswith("/v1/candidates/"):
            parts = endpoint.split("/")
            candidate_id = parts[3]
            self.auth.require_capability(auth_context, "memory:review")
            candidate = self.memory.read_candidate(candidate_id)
            self._require(auth_context, "memory:review", {"namespace": candidate.namespace})
            if len(parts) == 5 and parts[4] == "promote":
                return asdict(self.memory.promote_candidate(candidate_id, reason=payload["reason"])), [], None
            if len(parts) == 5 and parts[4] == "reject":
                return asdict(self.memory.reject_candidate(candidate_id, reason=payload["reason"])), [], None

        if method == "GET" and endpoint.startswith("/v1/claims/"):
            return self._claim_endpoint(endpoint, auth_context), [], None
        if method == "POST" and endpoint.startswith("/v1/claims/"):
            return self._claim_mutation(endpoint, payload, auth_context), [], None
        if method == "GET" and endpoint.startswith("/v1/audit/"):
            parts = endpoint.split("/")
            if len(parts) != 5:
                raise not_found(endpoint)
            target_type, target_id = parts[3], parts[4]
            self.auth.require_capability(auth_context, "memory:audit")
            namespace = self._namespace_for_target(target_type, target_id)
            if namespace:
                self.auth.require_namespace(auth_context, namespace=namespace)
            return self.memory.audit(target_id) | {"requested_target_type": target_type}, [], None

        if endpoint.startswith("/v1/sessions"):
            return self._sessions_endpoint(method, endpoint, query, payload, auth_context), [], None
        if endpoint.startswith("/v1/projects"):
            return self._projects_endpoint(method, endpoint, query, payload, auth_context), [], None
        if endpoint.startswith("/v1/conflicts") or endpoint.startswith("/v1/confidence") or endpoint.startswith("/v1/curate"):
            return self._governance_endpoint(method, endpoint, query, payload, auth_context), [], None
        if endpoint.startswith("/v1/infer") or endpoint.startswith("/v1/inferences") or endpoint.startswith("/v1/reflections") or endpoint.startswith("/v1/derivation"):
            return self._reasoning_endpoint(method, endpoint, query, payload, auth_context), [], None
        if endpoint.startswith("/v1/eval") or endpoint.startswith("/v1/optimize") or endpoint.startswith("/v1/learning") or endpoint.startswith("/v1/policies") or endpoint.startswith("/v1/jobs") or endpoint == "/v1/health-report":
            return self._admin_endpoint(method, endpoint, query, payload, auth_context), [], None

        raise not_found(f"Endpoint not found: {method} {endpoint}")

    def service_health(self) -> ServiceHealth:
        health = self.memory.health()
        warnings = []
        if health.get("schema_version") != SCHEMA_VERSION:
            warnings.append("schema_version_mismatch")
        return ServiceHealth(
            status="ok" if not warnings else "degraded",
            schema_version=health.get("schema_version", "unknown"),
            service_version=SCHEMA_VERSION,
            auth_required=self.config.auth_required,
            warnings=warnings,
        )

    def _context_pack(self, payload: dict, auth_context: AuthContext) -> dict:
        namespace = self._required(payload, "namespace")
        project_id = payload.get("project_id")
        self.auth.require_namespace(auth_context, namespace=namespace, project_id=project_id)
        pack = self.memory.context_pack(
            namespace=namespace,
            query=payload.get("query", ""),
            project_id=project_id,
            session_id=payload.get("session_id"),
            retrieval_mode=payload.get("retrieval_mode", "hybrid"),
            token_budget=int(payload.get("token_budget", 1500)),
            include_reflections=bool(payload.get("include_reflections", True)),
            include_inferences=bool(payload.get("include_inferences", False)),
            include_derivation_metadata=bool(payload.get("include_derivation_metadata", False)),
            policy_version_id=payload.get("policy_version_id"),
            record_usage=bool(payload.get("record_usage", False)),
        )
        pack, omitted_by_policy = self._filtered_context_pack_privacy(pack, auth_context)
        warnings = ["Some memories were omitted due to access policy."] if omitted_by_policy else []
        data = {
            "context_pack_id": pack.id,
            "markdown": pack.to_markdown(),
            "sections": {
                "core_memory": [asdict(item) for item in pack.core_memory],
                "project_memory": [asdict(item) for item in pack.project_memory],
                "session_memory": [asdict(item) for item in pack.session_memory],
                "procedural_memory": [asdict(item) for item in pack.procedural_memory],
                "reflections": [asdict(item) for item in pack.reflection_memory],
                "relevant_memory": [asdict(item) for item in pack.relevant_memory],
                "warnings": [asdict(warning) for warning in pack.warnings],
            },
            "items": [asdict(item) for item in pack.items()],
            "warnings": [asdict(warning) for warning in pack.warnings],
            "provenance": self._provenance_for_items(pack.items()),
            "policy": {
                "ranking_policy_version_id": pack.ranking_policy_version_id,
                "context_policy_version_id": pack.context_policy_version_id,
            },
        }
        if warnings:
            data["access_warnings"] = warnings
        return data

    def _retrieve(self, payload: dict, auth_context: AuthContext) -> list[dict]:
        namespace = self._required(payload, "namespace")
        project_id = payload.get("project_id")
        self.auth.require_namespace(auth_context, namespace=namespace, project_id=project_id)
        results = self.memory.retrieve(
            namespace=namespace,
            query=payload.get("query", ""),
            mode=payload.get("mode", "hybrid"),
            limit=int(payload.get("limit", 10)),
            project_id=project_id,
            session_id=payload.get("session_id"),
            memory_types=payload.get("memory_types"),
            include_disputed=bool(payload.get("include_disputed", False)),
            include_archived=bool(payload.get("include_archived", False)),
        )
        visible = [result for result in results if self._evidence_allowed(result.evidence_ids, auth_context)]
        return [asdict(result) for result in visible]

    def _llm_endpoint(
        self,
        method: str,
        endpoint: str,
        query: dict[str, list[str]],
        payload: dict,
        auth_context: AuthContext,
    ) -> dict:
        if method == "GET" and endpoint == "/v1/llm/runs":
            namespace = self._query_value(query, "namespace", none_if_missing=True)
            if namespace:
                self._require(auth_context, "memory:review", {"namespace": namespace})
            else:
                self.auth.require_capability(auth_context, "memory:review")
            return {
                "runs": self.memory.list_llm_runs(
                    namespace=namespace,
                    task_type=self._query_value(query, "task", none_if_missing=True),
                    limit=self._limit(query),
                )
            }
        if method != "POST":
            raise not_found(f"Endpoint not found: {method} {endpoint}")
        if endpoint == "/v1/llm/explain-conflict":
            conflict_id = self._required(payload, "conflict_id")
            self.auth.require_capability(auth_context, "memory:review")
            conflict = self.memory.read_conflict(conflict_id)
            self._require(auth_context, "memory:review", {"namespace": conflict.namespace})
            return self.memory.explain_conflict_with_llm(conflict_id, provider=payload.get("provider", "mock_llm"), model=payload.get("model"))
        namespace = self._required(payload, "namespace")
        capability = "memory:read" if endpoint == "/v1/llm/expand-query" else "memory:review"
        self._require(auth_context, capability, {"namespace": namespace})
        provider = payload.get("provider", "mock_llm")
        model = payload.get("model")
        if endpoint == "/v1/llm/expand-query":
            return self.memory.expand_query(
                namespace=namespace,
                query=self._required(payload, "query"),
                provider=provider,
                model=model,
                privacy_level=payload.get("privacy_level", "personal"),
            )
        if endpoint == "/v1/llm/summarize-evidence":
            return self.memory.summarize_evidence(namespace=namespace, evidence_ids=payload.get("evidence_ids") or [], provider=provider, model=model)
        if endpoint == "/v1/llm/suggest-entities":
            return self.memory.suggest_entities(namespace=namespace, evidence_ids=payload.get("evidence_ids") or [], provider=provider, model=model)
        if endpoint == "/v1/llm/suggest-categories":
            return self.memory.suggest_categories(namespace=namespace, evidence_ids=payload.get("evidence_ids") or [], provider=provider, model=model)
        if endpoint == "/v1/llm/suggest-scope":
            return self.memory.suggest_scope_with_llm(
                namespace=namespace,
                candidate_id=self._required(payload, "candidate_id"),
                provider=provider,
                model=model,
            )
        if endpoint == "/v1/llm/suggest-duplicate-merge":
            return self.memory.suggest_duplicate_merge_with_llm(
                namespace=namespace,
                candidate_id=self._required(payload, "candidate_id"),
                provider=provider,
                model=model,
            )
        raise not_found(f"Endpoint not found: {method} {endpoint}")

    def _remember(self, payload: dict, auth_context: AuthContext) -> dict:
        namespace = self._required(payload, "namespace")
        project_id = payload.get("project_id")
        self.auth.require_namespace(auth_context, namespace=namespace, project_id=project_id)
        write_mode = payload.get("write_mode", "candidate")
        if write_mode == "active":
            self.auth.require_capability(auth_context, "memory:write_active")
            claim = self.memory.remember(
                namespace=namespace,
                memory_type=self._required(payload, "memory_type"),
                subject=self._required(payload, "subject"),
                predicate=self._required(payload, "predicate"),
                object=self._required(payload, "object"),
                source_type=payload.get("source_type", "service"),
                confidence=float(payload.get("confidence", 0.75)),
                project_id=project_id,
                session_id=payload.get("session_id"),
                status=payload.get("status", "active"),
            )
            return {"write_mode": "active", "claim": asdict(claim)}
        if write_mode != "candidate":
            raise validation_error("write_mode must be candidate or active.")
        self.auth.require_capability(auth_context, "memory:write_candidate")
        candidate = self._create_service_candidate(payload, auth_context)
        return {"write_mode": "candidate", "candidate": asdict(candidate)}

    def _create_service_candidate(self, payload: dict, auth_context: AuthContext):
        namespace = self._required(payload, "namespace")
        evidence_text = payload.get("evidence_text") or " ".join(
            [payload.get("subject", ""), payload.get("predicate", ""), payload.get("object", "")]
        ).strip()
        batch = self.memory.ingest(
            namespace,
            source_type=payload.get("source_type", "agent_observation"),
            content=evidence_text,
            project_id=payload.get("project_id"),
            session_id=payload.get("session_id"),
            title=payload.get("title"),
            privacy_level=payload.get("privacy_level", min_privacy(auth_context.privacy_ceiling, "personal")),
            trust_level=payload.get("trust_level", "imported"),
            metadata={"service_write": True, "client_id": auth_context.client_id},
        )
        evidence_id = batch.evidence_ids[0]
        run_id = new_id("run")
        span_id = new_id("span")
        candidate_id = new_id("cand")
        now = utc_now_iso()
        with self.memory.store.transaction():
            self.memory.store.connection.execute(
                """
                INSERT INTO extraction_runs (
                    id, namespace, batch_id, extractor_name, extractor_version,
                    policy_json, candidate_count, stored_candidate_count,
                    dry_run, created_at, warnings_json
                )
                VALUES (?, ?, ?, 'service_candidate_writer', '1.3.0', ?, 1, 1, 0, ?, '[]')
                """,
                (run_id, namespace, batch.id, json.dumps({"source": "M6 service"}, sort_keys=True), now),
            )
            self.memory.store.connection.execute(
                """
                INSERT INTO extraction_run_evidence_links (extraction_run_id, evidence_id)
                VALUES (?, ?)
                """,
                (run_id, evidence_id),
            )
            self.memory.store.connection.execute(
                """
                INSERT INTO evidence_spans (
                    id, namespace, evidence_id, start_char, end_char,
                    span_text, role, created_at
                )
                VALUES (?, ?, ?, 0, ?, ?, 'supporting', ?)
                """,
                (span_id, namespace, evidence_id, len(evidence_text), evidence_text, now),
            )
            self.memory.store.connection.execute(
                """
                INSERT INTO candidate_claims (
                    id, namespace, extraction_run_id, subject, predicate, object,
                    memory_type, candidate_status, suggested_confidence,
                    suggested_importance, suggested_half_life_days,
                    suggested_scope_json, contradiction_risk, duplicate_risk,
                    privacy_level, created_at, metadata_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, 'pending_review', ?, ?, ?, ?, 0.0, 0.0, ?, ?, ?)
                """,
                (
                    candidate_id,
                    namespace,
                    run_id,
                    self._required(payload, "subject"),
                    self._required(payload, "predicate"),
                    self._required(payload, "object"),
                    self._required(payload, "memory_type"),
                    float(payload.get("confidence", 0.75)),
                    float(payload.get("importance", 0.5)),
                    payload.get("half_life_days"),
                    json.dumps(payload.get("scope"), sort_keys=True) if payload.get("scope") else None,
                    payload.get("privacy_level", "personal"),
                    now,
                    json.dumps({"service_candidate": True, "client_id": auth_context.client_id}, sort_keys=True),
                ),
            )
            self.memory.store.connection.execute(
                """
                INSERT INTO candidate_evidence_links (
                    candidate_id, evidence_id, evidence_span_id, role
                )
                VALUES (?, ?, ?, 'supporting')
                """,
                (candidate_id, evidence_id, span_id),
            )
            self.memory._write_audit(
                namespace=namespace,
                target_type="candidate_claim",
                target_id=candidate_id,
                action="service.remember_candidate",
                details={"client_id": auth_context.client_id, "request_source": "http_or_mcp"},
            )
        return self.memory.read_candidate(candidate_id)

    def _claim_endpoint(self, endpoint: str, auth_context: AuthContext) -> dict:
        parts = endpoint.split("/")
        claim_id = parts[3]
        self.auth.require_capability(auth_context, "memory:read")
        claim = self.memory.read_claim(claim_id)
        self.auth.require_namespace(auth_context, namespace=claim.namespace)
        if len(parts) == 5 and parts[4] == "explain":
            return asdict(self.memory.explain_claim(claim_id))
        if len(parts) != 4:
            raise not_found(endpoint)
        return asdict(claim)

    def _claim_mutation(self, endpoint: str, payload: dict, auth_context: AuthContext) -> dict:
        parts = endpoint.split("/")
        claim_id = parts[3]
        self.auth.require_capability(auth_context, "memory:review")
        claim = self.memory.read_claim(claim_id)
        self.auth.require_namespace(auth_context, namespace=claim.namespace)
        if len(parts) == 5 and parts[4] == "promote":
            return asdict(self.memory.promote_claim(claim_id, payload.get("to", "active"), reason=payload["reason"]))
        if len(parts) == 5 and parts[4] == "demote":
            return asdict(self.memory.demote_claim(claim_id, payload.get("to", "archived"), reason=payload["reason"]))
        if len(parts) == 5 and parts[4] == "scope":
            return asdict(self.memory.scope_claim(claim_id, **self._scope_claim_args(payload)))
        if len(parts) == 6 and parts[4] == "supersede":
            return asdict(self.memory.supersede_claim(claim_id, parts[5], reason=payload["reason"]))
        raise not_found(endpoint)

    def _sessions_endpoint(self, method: str, endpoint: str, query: dict, payload: dict, auth_context: AuthContext):
        if method == "POST" and endpoint == "/v1/sessions/start":
            self._require(auth_context, "memory:write_candidate", payload)
            return asdict(self.memory.start_session(**self._start_session_args(payload)))
        if method == "POST" and endpoint.startswith("/v1/sessions/") and endpoint.endswith("/end"):
            self.auth.require_capability(auth_context, "memory:write_candidate")
            return asdict(self.memory.end_session(endpoint.split("/")[3], **self._end_session_args(payload)))
        if method == "GET" and endpoint == "/v1/sessions":
            namespace = self._query_value(query, "namespace")
            self._require(auth_context, "memory:read", {"namespace": namespace})
            return [asdict(item) for item in self.memory.list_sessions(namespace=namespace)]
        if method == "GET" and endpoint.startswith("/v1/sessions/"):
            session = self.memory.get_session(endpoint.split("/")[3])
            self._require(auth_context, "memory:read", {"namespace": session.namespace})
            return asdict(session)
        raise not_found(endpoint)

    def _projects_endpoint(self, method: str, endpoint: str, query: dict, payload: dict, auth_context: AuthContext):
        if method == "POST" and endpoint == "/v1/projects":
            self._require(auth_context, "memory:write_candidate", payload)
            return asdict(self.memory.create_project(**self._create_project_args(payload)))
        if method == "GET" and endpoint == "/v1/projects":
            namespace = self._query_value(query, "namespace")
            self._require(auth_context, "memory:read", {"namespace": namespace})
            return [asdict(item) for item in self.memory.list_projects(namespace=namespace)]
        if method == "GET" and endpoint.startswith("/v1/projects/"):
            namespace = self._query_value(query, "namespace")
            self._require(auth_context, "memory:read", {"namespace": namespace})
            return asdict(self.memory.get_project(namespace=namespace, project_id=endpoint.split("/")[3]))
        raise not_found(endpoint)

    def _governance_endpoint(self, method: str, endpoint: str, query: dict, payload: dict, auth_context: AuthContext):
        if method == "GET" and endpoint == "/v1/conflicts":
            namespace = self._query_value(query, "namespace")
            self._require(auth_context, "memory:read", {"namespace": namespace})
            return [asdict(item) for item in self.memory.list_conflict_families(namespace=namespace)]
        if method == "POST" and endpoint == "/v1/conflicts/detect":
            self._require(auth_context, "memory:review", payload)
            return [asdict(item) for item in self.memory.detect_conflicts(**self._detect_conflicts_args(payload))]
        if method == "POST" and endpoint.startswith("/v1/conflicts/") and endpoint.endswith("/resolve"):
            self.auth.require_capability(auth_context, "memory:review")
            return asdict(self.memory.resolve_conflict(endpoint.split("/")[3], **self._resolve_conflict_args(payload)))
        if method == "GET" and endpoint.startswith("/v1/confidence/"):
            self.auth.require_capability(auth_context, "memory:read")
            claim = self.memory.read_claim(endpoint.split("/")[3])
            self._require(auth_context, "memory:read", {"namespace": claim.namespace})
            return asdict(self.memory.compute_confidence(claim.id, explain=True))
        if method == "POST" and endpoint == "/v1/confidence/recompute":
            self._require(auth_context, "memory:admin", payload)
            return [asdict(item) for item in self.memory.recompute_confidence(**self._recompute_confidence_args(payload))]
        if method == "POST" and endpoint == "/v1/curate/preview":
            self._require(auth_context, "memory:review", payload)
            return [asdict(item) for item in self.memory.curate(dry_run=True, **self._curate_args(payload))]
        if method == "POST" and endpoint == "/v1/curate/apply":
            self._require(auth_context, "memory:review", payload)
            return [asdict(item) for item in self.memory.curate(dry_run=False, **self._curate_args(payload))]
        raise not_found(endpoint)

    def _reasoning_endpoint(self, method: str, endpoint: str, query: dict, payload: dict, auth_context: AuthContext):
        if method == "POST" and endpoint == "/v1/infer/run":
            self._require(auth_context, "memory:review", payload)
            return asdict(self.memory.run_inference(**self._run_inference_args(payload)))
        if method == "GET" and endpoint == "/v1/inferences":
            namespace = self._query_value(query, "namespace")
            self._require(auth_context, "memory:read", {"namespace": namespace})
            return [asdict(item) for item in self.memory.list_inferences(namespace)]
        if method == "POST" and endpoint.startswith("/v1/inferences/"):
            self.auth.require_capability(auth_context, "memory:review")
            inference_id = endpoint.split("/")[3]
            if endpoint.endswith("/promote"):
                return asdict(self.memory.promote_inference(inference_id, reason=payload["reason"]))
            if endpoint.endswith("/reject"):
                return asdict(self.memory.review_inference(inference_id, decision="reject", reason=payload["reason"]))
        if method == "POST" and endpoint == "/v1/reflections":
            self._require(auth_context, "memory:review", payload)
            return asdict(self.memory.build_reflection(**self._build_reflection_args(payload)))
        if method == "GET" and endpoint == "/v1/reflections":
            namespace = self._query_value(query, "namespace")
            self._require(auth_context, "memory:read", {"namespace": namespace})
            return [asdict(item) for item in self.memory.list_reflections(namespace=namespace)]
        if method == "GET" and endpoint.startswith("/v1/reflections/") and endpoint.endswith("/expand"):
            self.auth.require_capability(auth_context, "memory:read")
            reflection = self.memory.get_reflection(endpoint.split("/")[3])
            self._require(auth_context, "memory:read", {"namespace": reflection.namespace})
            return asdict(self.memory.expand_reflection(endpoint.split("/")[3]))
        if method == "GET" and endpoint.startswith("/v1/derivation/"):
            parts = endpoint.split("/")
            self.auth.require_capability(auth_context, "memory:read")
            return asdict(self.memory.trace_derivation(parts[4], target_type=parts[3]))
        raise not_found(endpoint)

    def _admin_endpoint(self, method: str, endpoint: str, query: dict, payload: dict, auth_context: AuthContext):
        if method == "POST" and endpoint == "/v1/eval/sets":
            self._require(auth_context, "memory:evaluate", payload)
            return asdict(self.memory.create_eval_set(**self._create_eval_set_args(payload)))
        if method == "POST" and endpoint.startswith("/v1/eval/sets/") and endpoint.endswith("/cases"):
            self.auth.require_capability(auth_context, "memory:evaluate")
            return asdict(self.memory.add_eval_case(endpoint.split("/")[4], **self._add_eval_case_args(payload)))
        if method == "POST" and endpoint.startswith("/v1/eval/sets/") and endpoint.endswith("/run"):
            self.auth.require_capability(auth_context, "memory:evaluate")
            return asdict(self.memory.run_evaluation(payload.get("namespace", self.memory.namespace), eval_set_id=endpoint.split("/")[4]))
        if method == "POST" and endpoint == "/v1/optimize/retrieval":
            self._require(auth_context, "memory:policy", payload)
            return asdict(self.memory.optimize_retrieval(**self._optimize_retrieval_args(payload)))
        if method == "POST" and endpoint == "/v1/learning/run":
            self._require(auth_context, "memory:learn", payload)
            return asdict(self.memory.run_learning(**self._run_learning_args(payload)))
        if method == "GET" and endpoint == "/v1/policies/proposals":
            namespace = self._query_value(query, "namespace")
            self._require(auth_context, "memory:policy", {"namespace": namespace})
            return [asdict(item) for item in self.memory.list_policy_proposals(namespace=namespace)]
        if method == "POST" and endpoint.startswith("/v1/policies/proposals/"):
            self.auth.require_capability(auth_context, "memory:policy")
            proposal_id = endpoint.split("/")[4]
            if endpoint.endswith("/review"):
                return asdict(self.memory.review_policy_proposal(proposal_id, **self._review_policy_args(payload)))
            if endpoint.endswith("/apply"):
                return asdict(self.memory.apply_policy_proposal(proposal_id, **self._apply_policy_args(payload)))
        if method == "POST" and endpoint == "/v1/jobs":
            self._require(auth_context, "memory:jobs", payload)
            return asdict(self.memory.enqueue_job(**self._enqueue_job_args(payload)))
        if method == "POST" and endpoint == "/v1/jobs/run":
            self.auth.require_capability(auth_context, "memory:jobs")
            return [asdict(item) for item in self.memory.run_jobs(**self._run_jobs_args(payload))]
        if method == "GET" and endpoint == "/v1/jobs":
            namespace = self._query_value(query, "namespace", none_if_missing=True)
            self.auth.require_capability(auth_context, "memory:jobs")
            return [asdict(item) for item in self.memory.list_jobs(namespace=namespace)]
        if method == "GET" and endpoint == "/v1/health-report":
            namespace = self._query_value(query, "namespace")
            self._require(auth_context, "memory:admin", {"namespace": namespace})
            return asdict(self.memory.health_report(namespace=namespace))
        raise not_found(endpoint)

    def _console_endpoint(
        self,
        method: str,
        endpoint: str,
        query: dict,
        payload: dict,
        auth_context: AuthContext,
        headers: Mapping[str, str],
    ):
        if method == "POST" and endpoint == "/v1/console/login":
            return self._console_login(payload)
        if method == "POST" and endpoint == "/v1/console/logout":
            return self._console_logout(headers)
        if method == "GET" and endpoint == "/v1/console/session":
            return {"authenticated": True, "capabilities": auth_context.capabilities, "namespace_grants": auth_context.namespace_grants}
        if method == "POST" and endpoint.startswith("/v1/console/actions/candidates/"):
            self.auth.require_capability(auth_context, "memory:review")
            parts = endpoint.split("/")
            candidate_id = parts[5]
            action = parts[6] if len(parts) > 6 else ""
            reason = self._required(payload, "reason")
            confirmation = self._required(payload, "confirmation")
            if action == "promote":
                if confirmation != "promote candidate":
                    raise validation_error("Confirmation text must be 'promote candidate'.")
                candidate = self.memory.read_candidate(candidate_id)
                self.auth.require_namespace(auth_context, namespace=candidate.namespace)
                self._record_console_confirmation(
                    namespace=candidate.namespace,
                    action_type="candidate.promote",
                    target_id=candidate_id,
                    target_type="candidate_claim",
                    confirmation_text=confirmation,
                    reason=reason,
                    actor=auth_context.client_id or "console",
                )
                claim = self.memory.promote_candidate(candidate_id, reason=reason, force=bool(payload.get("force", False)))
                self._resolve_matching_review_task(candidate.namespace, "candidate_review", candidate_id, reason=reason)
                return {"claim": asdict(claim)}
            if action == "reject":
                if confirmation != "reject candidate":
                    raise validation_error("Confirmation text must be 'reject candidate'.")
                candidate = self.memory.read_candidate(candidate_id)
                self.auth.require_namespace(auth_context, namespace=candidate.namespace)
                self._record_console_confirmation(
                    namespace=candidate.namespace,
                    action_type="candidate.reject",
                    target_id=candidate_id,
                    target_type="candidate_claim",
                    confirmation_text=confirmation,
                    reason=reason,
                    actor=auth_context.client_id or "console",
                )
                decision = self.memory.reject_candidate(candidate_id, reason=reason)
                self._resolve_matching_review_task(candidate.namespace, "candidate_review", candidate_id, reason=reason)
                return {"decision": asdict(decision)}
        if method == "POST" and endpoint.startswith("/v1/console/actions/conflicts/") and endpoint.endswith("/resolve"):
            self.auth.require_capability(auth_context, "memory:review")
            conflict_id = endpoint.split("/")[5]
            family = self.memory.read_conflict_family(conflict_id)
            self.auth.require_namespace(auth_context, namespace=family.namespace)
            reason = self._required(payload, "reason")
            confirmation = self._required(payload, "confirmation")
            if confirmation != "resolve conflict":
                raise validation_error("Confirmation text must be 'resolve conflict'.")
            self._record_console_confirmation(
                namespace=family.namespace,
                action_type="conflict.resolve",
                target_id=conflict_id,
                target_type="conflict",
                confirmation_text=confirmation,
                reason=reason,
                actor=auth_context.client_id or "console",
            )
            resolution = self.memory.resolve_conflict(
                conflict_id,
                strategy=payload.get("strategy", "manual"),
                active_claim_id=payload.get("active_claim_id"),
                superseded_claim_ids=payload.get("superseded_claim_ids"),
                rejected_claim_ids=payload.get("rejected_claim_ids"),
                scoped_claims=payload.get("scoped_claims"),
                note=reason,
            )
            self._resolve_matching_review_task(family.namespace, "conflict_resolution", conflict_id, reason=reason)
            return asdict(resolution)
        raise not_found(endpoint)

    def _dashboard_endpoint(self, method: str, endpoint: str, query: dict, payload: dict, auth_context: AuthContext):
        namespace = self._query_value(query, "namespace", none_if_missing=True) or payload.get("namespace") or self.memory.namespace
        self._require(auth_context, "memory:read", {"namespace": namespace})
        if method == "GET" and endpoint == "/v1/dashboard/overview":
            snapshot = self.memory.latest_metric_snapshot(namespace=namespace) or self.memory.metrics_snapshot(namespace=namespace, source="dashboard")
            health = self.memory.health_report(namespace=namespace)
            return {
                "metrics": snapshot.metrics,
                "health": asdict(health),
                "review_tasks": [asdict(task) for task in self.memory.list_review_tasks(namespace=namespace, status="open", limit=10)],
                "candidates": [asdict(candidate) for candidate in self.memory.list_candidates(namespace, status="pending_review", limit=10)],
                "conflicts": [asdict(conflict) for conflict in self.memory.list_conflict_families(namespace=namespace, status="unresolved", limit=10)],
                "jobs": [asdict(job) for job in self.memory.list_jobs(namespace=namespace, limit=10)],
                "service_requests": self.service_requests(limit=10),
            }
        if method == "GET" and endpoint == "/v1/dashboard/preferences":
            return self._dashboard_preferences(namespace)
        if method == "POST" and endpoint == "/v1/dashboard/preferences":
            self.auth.require_capability(auth_context, "memory:admin")
            return self._set_dashboard_preference(namespace, payload)
        if method == "GET" and endpoint == "/v1/dashboard/saved-views":
            return [dict(row) for row in self.memory.store.connection.execute(
                "SELECT * FROM dashboard_saved_views WHERE namespace = ? OR namespace IS NULL ORDER BY updated_at DESC",
                (namespace,),
            ).fetchall()]
        if method == "POST" and endpoint == "/v1/dashboard/saved-views":
            self.auth.require_capability(auth_context, "memory:admin")
            return self._create_saved_view(namespace, payload)
        if method == "DELETE" and endpoint.startswith("/v1/dashboard/saved-views/"):
            self.auth.require_capability(auth_context, "memory:admin")
            view_id = endpoint.split("/")[4]
            with self.memory.store.transaction():
                self.memory.store.connection.execute("DELETE FROM dashboard_saved_views WHERE id = ?", (view_id,))
            return {"deleted": view_id}
        raise not_found(endpoint)

    def _reviews_endpoint(self, method: str, endpoint: str, query: dict, payload: dict, auth_context: AuthContext):
        if method == "GET" and endpoint == "/v1/reviews":
            namespace = self._query_value(query, "namespace", none_if_missing=True) or self.memory.namespace
            self._require(auth_context, "memory:read", {"namespace": namespace})
            return [
                asdict(task)
                for task in self.memory.list_review_tasks(
                    namespace=namespace,
                    status=self._query_value(query, "status", none_if_missing=True),
                    task_type=self._query_value(query, "task_type", none_if_missing=True),
                    severity=self._query_value(query, "severity", none_if_missing=True),
                    limit=self._limit(query),
                )
            ]
        if method == "POST" and endpoint == "/v1/reviews/generate":
            self._require(auth_context, "memory:review", payload)
            return [asdict(task) for task in self.memory.generate_review_tasks(self._required(payload, "namespace"))]
        if endpoint.startswith("/v1/reviews/"):
            review_task_id = endpoint.split("/")[3]
            if method == "GET":
                self.auth.require_capability(auth_context, "memory:read")
            elif "memory:admin" not in auth_context.capabilities and not (
                {"memory:review", "memory:policy", "memory:jobs"} & set(auth_context.capabilities)
            ):
                self.auth.require_capability(auth_context, "memory:review")
            task = self.memory.get_review_task(review_task_id)
            self.auth.require_namespace(auth_context, namespace=task.namespace)
            if method == "GET" and len(endpoint.split("/")) == 4:
                return {"task": asdict(task), "events": [asdict(event) for event in self.memory.list_review_task_events(review_task_id)]}
            self.auth.require_capability(auth_context, self._capability_for_review_task(task.task_type))
            if method == "POST" and endpoint.endswith("/resolve"):
                return asdict(self.memory.resolve_review_task(review_task_id, resolution=payload.get("resolution", "resolved"), reason=self._required(payload, "reason")))
            if method == "POST" and endpoint.endswith("/dismiss"):
                return asdict(self.memory.dismiss_review_task(review_task_id, reason=self._required(payload, "reason")))
            if method == "POST" and endpoint.endswith("/defer"):
                return asdict(self.memory.defer_review_task(review_task_id, reason=self._required(payload, "reason")))
        raise not_found(endpoint)

    def _traces_endpoint(self, method: str, endpoint: str, query: dict, payload: dict, auth_context: AuthContext):
        if method == "POST" and endpoint == "/v1/traces/retrieval":
            self._require(auth_context, "memory:read", payload)
            return asdict(self.memory.trace_retrieval(
                self._required(payload, "namespace"),
                query=self._required(payload, "query"),
                retrieval_mode=payload.get("retrieval_mode", payload.get("mode", "hybrid")),
                project_id=payload.get("project_id"),
                session_id=payload.get("session_id"),
                limit=int(payload.get("limit", 10)),
            ))
        if method == "POST" and endpoint == "/v1/traces/context-pack":
            self._require(auth_context, "memory:read", payload)
            return asdict(self.memory.trace_context_pack(
                self._required(payload, "namespace"),
                query=self._required(payload, "query"),
                project_id=payload.get("project_id"),
                session_id=payload.get("session_id"),
                retrieval_mode=payload.get("retrieval_mode", "hybrid"),
                token_budget=int(payload.get("token_budget", 2000)),
            ))
        if method == "GET" and endpoint == "/v1/traces":
            namespace = self._query_value(query, "namespace", none_if_missing=True)
            if namespace:
                self._require(auth_context, "memory:read", {"namespace": namespace})
            else:
                self.auth.require_capability(auth_context, "memory:read")
            return [asdict(trace) for trace in self.memory.list_traces(namespace=namespace, trace_type=self._query_value(query, "trace_type", none_if_missing=True), limit=self._limit(query))]
        if method == "GET" and endpoint.startswith("/v1/traces/"):
            trace_id = endpoint.split("/")[3]
            trace = self.memory.get_trace(trace_id)
            self._require(auth_context, "memory:read", {"namespace": trace.namespace})
            if endpoint.endswith("/items"):
                return [asdict(item) for item in self.memory.list_trace_items(trace_id)]
            return {
                "trace": asdict(trace),
                "events": [asdict(event) for event in self.memory.list_trace_events(trace_id)],
                "items": [asdict(item) for item in self.memory.list_trace_items(trace_id)],
            }
        raise not_found(endpoint)

    def _metrics_endpoint(self, method: str, endpoint: str, query: dict, payload: dict, auth_context: AuthContext):
        if method == "POST" and endpoint == "/v1/metrics/snapshot":
            self._require(auth_context, "memory:admin", payload)
            return asdict(self.memory.metrics_snapshot(namespace=payload.get("namespace"), project_id=payload.get("project_id"), source=payload.get("source", "api")))
        if method == "GET" and endpoint == "/v1/metrics/snapshots":
            namespace = self._query_value(query, "namespace", none_if_missing=True)
            if namespace:
                self._require(auth_context, "memory:read", {"namespace": namespace})
            else:
                self.auth.require_capability(auth_context, "memory:read")
            return [asdict(item) for item in self.memory.list_metric_snapshots(namespace=namespace, limit=self._limit(query))]
        if method == "GET" and endpoint == "/v1/metrics/latest":
            namespace = self._query_value(query, "namespace", none_if_missing=True)
            if namespace:
                self._require(auth_context, "memory:read", {"namespace": namespace})
            snapshot = self.memory.latest_metric_snapshot(namespace=namespace) or self.memory.metrics_snapshot(namespace=namespace, source="api_latest")
            return asdict(snapshot)
        raise not_found(endpoint)

    def _notifications_endpoint(self, method: str, endpoint: str, query: dict, payload: dict, auth_context: AuthContext):
        if method == "GET" and endpoint == "/v1/notifications":
            namespace = self._query_value(query, "namespace", none_if_missing=True)
            if namespace:
                self._require(auth_context, "memory:read", {"namespace": namespace})
            else:
                self.auth.require_capability(auth_context, "memory:read")
            return [asdict(item) for item in self.memory.list_notifications(namespace=namespace, status=self._query_value(query, "status", none_if_missing=True), limit=self._limit(query))]
        if method == "POST" and endpoint.startswith("/v1/notifications/"):
            self.auth.require_capability(auth_context, "memory:read")
            notification_id = endpoint.split("/")[3]
            if endpoint.endswith("/dismiss"):
                return asdict(self.memory.dismiss_notification(notification_id))
            if endpoint.endswith("/snooze"):
                return asdict(self.memory.snooze_notification(notification_id, until=self._required(payload, "until")))
        raise not_found(endpoint)

    def _reports_endpoint(self, method: str, endpoint: str, query: dict, payload: dict, auth_context: AuthContext):
        if method == "POST" and endpoint == "/v1/reports/export":
            namespace = payload.get("namespace")
            if namespace:
                self._require(auth_context, "memory:read", {"namespace": namespace})
            else:
                self.auth.require_capability(auth_context, "memory:admin")
            return asdict(self.memory.export_report(
                namespace=namespace,
                report_type=self._required(payload, "report_type"),
                format=payload.get("format", "markdown"),
                output_path=payload.get("output_path"),
                filters=payload.get("filters"),
            ))
        if method == "GET" and endpoint == "/v1/reports":
            namespace = self._query_value(query, "namespace", none_if_missing=True)
            if namespace:
                self._require(auth_context, "memory:read", {"namespace": namespace})
            else:
                self.auth.require_capability(auth_context, "memory:read")
            return [asdict(report) for report in self.memory.list_reports(namespace=namespace, report_type=self._query_value(query, "report_type", none_if_missing=True), limit=self._limit(query))]
        if method == "GET" and endpoint.startswith("/v1/reports/"):
            report = self.memory.get_report(endpoint.split("/")[3])
            if report.namespace:
                self._require(auth_context, "memory:read", {"namespace": report.namespace})
            else:
                self.auth.require_capability(auth_context, "memory:admin")
            return asdict(report)
        raise not_found(endpoint)

    def _is_m10_endpoint(self, endpoint: str) -> bool:
        return any(endpoint.startswith(prefix) for prefix in [
            "/v1/federation",
            "/v1/peers",
            "/v1/shares",
            "/v1/sync",
            "/v1/workspaces",
            "/v1/grants",
            "/v1/revocations",
        ])

    def _m10_endpoint(self, method: str, endpoint: str, query: dict, payload: dict, auth_context: AuthContext):
        if endpoint.startswith("/v1/federation"):
            self.auth.require_capability(auth_context, "memory:federation")
            if method == "GET" and endpoint == "/v1/federation/status":
                return self.memory.federation_status()
            if method == "GET" and endpoint == "/v1/federation/identity":
                identity = self.memory.active_federation_identity(none_if_missing=True)
                return asdict(identity) if identity else {"identity": None}
            if method == "POST" and endpoint == "/v1/federation/identity":
                return asdict(self.memory.create_federation_identity(
                    display_name=self._required(payload, "display_name"),
                    key_algorithm=payload.get("key_algorithm", "default"),
                    protected=bool(payload.get("protected", True)),
                ))
            if method == "POST" and endpoint == "/v1/federation/identity/rotate":
                return asdict(self.memory.rotate_federation_key(reason=self._required(payload, "reason"), actor=payload.get("actor", "api")))
            if method == "POST" and endpoint == "/v1/federation/conformance":
                return self.memory.federation_conformance()

        if endpoint.startswith("/v1/peers"):
            if method == "POST" and endpoint.endswith("/revoke"):
                self.auth.require_capability(auth_context, "memory:revoke_peer")
            else:
                self.auth.require_capability(auth_context, "memory:peers")
            if method == "GET" and endpoint == "/v1/peers":
                return [asdict(peer) for peer in self.memory.list_peers(include_revoked=self._query_bool(query, "include_revoked", default=False))]
            if method == "POST" and endpoint == "/v1/peers":
                return asdict(self.memory.add_peer(
                    peer_identity=payload.get("peer_identity"),
                    peer_identity_file=self._optional_safe_admin_path(payload, "peer_identity_file"),
                    display_name=payload.get("display_name"),
                    trust_status=payload.get("trust_status", "unknown"),
                    reason=self._required(payload, "reason"),
                ))
            if method == "GET" and endpoint == "/v1/peers/trust-domains":
                return [asdict(domain) for domain in self.memory.list_trust_domains()]
            parts = endpoint.split("/")
            if len(parts) >= 4:
                peer_id = parts[3]
                if method == "GET" and len(parts) == 4:
                    return asdict(self.memory.get_peer(peer_id))
                if method == "POST" and len(parts) == 5 and parts[4] == "trust":
                    return asdict(self.memory.trust_peer(
                        peer_id,
                        trust_status=self._required(payload, "trust_status"),
                        trust_domain_id=payload.get("trust_domain_id"),
                        reason=self._required(payload, "reason"),
                        actor=payload.get("actor", "api"),
                    ))
                if method == "POST" and len(parts) == 5 and parts[4] == "revoke":
                    return asdict(self.memory.revoke_peer(
                        peer_id,
                        reason=self._required(payload, "reason"),
                        actor=payload.get("actor", "api"),
                        revoke_shares=bool(payload.get("revoke_shares", True)),
                    ))

        if endpoint.startswith("/v1/shares") or endpoint.startswith("/v1/grants"):
            self.auth.require_capability(auth_context, "memory:share")
            if method == "GET" and endpoint in {"/v1/shares", "/v1/grants"}:
                namespace = self._query_value(query, "namespace", none_if_missing=True)
                if namespace:
                    self.auth.require_namespace(auth_context, namespace=namespace)
                return [
                    asdict(share)
                    for share in self.memory.list_share_grants(
                        namespace=namespace,
                        status=self._query_value(query, "status", none_if_missing=True),
                    )
                ]
            if method == "POST" and endpoint == "/v1/shares":
                namespace = self._required(payload, "namespace")
                self.auth.require_namespace(auth_context, namespace=namespace)
                if payload.get("privacy_ceiling") == "secret":
                    self.auth.require_capability(auth_context, "memory:share_sensitive")
                return asdict(self.memory.create_share_grant(
                    name=self._required(payload, "name"),
                    namespace=namespace,
                    recipient_peer_ids=payload.get("recipient_peer_ids") or payload.get("peer_ids") or [],
                    grant_type=payload.get("grant_type", "read_write_candidate"),
                    permissions=payload.get("permissions") or ["read_claims"],
                    privacy_ceiling=payload.get("privacy_ceiling", "personal"),
                    memory_types=payload.get("memory_types"),
                    statuses=payload.get("statuses"),
                    project_id=payload.get("project_id"),
                    include_evidence=bool(payload.get("include_evidence", True)),
                    include_reflections=bool(payload.get("include_reflections", True)),
                    include_inferences=bool(payload.get("include_inferences", False)),
                    include_audit=bool(payload.get("include_audit", False)),
                    expires_at=payload.get("expires_at"),
                    reason=self._required(payload, "reason"),
                    allow_secret=bool(payload.get("allow_secret", False)),
                ))
            if method == "GET" and endpoint == "/v1/grants/consent":
                return [asdict(record) for record in self.memory.list_consent_records()]
            if method == "POST" and endpoint == "/v1/shares/import":
                if payload.get("trust_policy") in {"trusted_device", "active_if_trusted", "active_for_project_state"}:
                    self.auth.require_capability(auth_context, "memory:remote_active_write")
                self.auth.require_capability(auth_context, "memory:sync")
                return asdict(self.memory.import_share_bundle(
                    input_path=self._required_safe_admin_path(payload, "input_path"),
                    trust_policy=payload.get("trust_policy", "candidate_only"),
                    actor=payload.get("actor", "api"),
                    dry_run=bool(payload.get("dry_run", False)),
                ))
            parts = endpoint.split("/")
            if len(parts) >= 4:
                share_id = parts[3]
                share = self.memory.get_share_grant(share_id)
                self.auth.require_namespace(auth_context, namespace=share.namespace, project_id=share.project_id)
                if method == "GET" and len(parts) == 4:
                    return asdict(share)
                if method == "GET" and len(parts) == 5 and parts[4] == "recipients":
                    return [asdict(recipient) for recipient in self.memory.list_share_recipients(share.id)]
                if method == "POST" and len(parts) == 5 and parts[4] == "export":
                    self.auth.require_capability(auth_context, "memory:sync")
                    if share.privacy_ceiling == "secret":
                        self.auth.require_capability(auth_context, "memory:sync_secret")
                    return asdict(self.memory.export_share_bundle(
                        share_id=share.id,
                        output_path=self._required_safe_admin_path(payload, "output_path"),
                        encrypt=bool(payload.get("encrypt", True)),
                        redacted=bool(payload.get("redacted", False)),
                        actor=payload.get("actor", "api"),
                    ))
                if method == "POST" and len(parts) == 5 and parts[4] == "revoke":
                    return asdict(self.memory.revoke_share_grant(share.id, reason=self._required(payload, "reason"), actor=payload.get("actor", "api")))

        if endpoint.startswith("/v1/sync"):
            self.auth.require_capability(auth_context, "memory:sync")
            if method == "GET" and endpoint == "/v1/sync/collections":
                return [asdict(collection) for collection in self.memory.list_sync_collections(status=self._query_value(query, "status", none_if_missing=True))]
            if method == "POST" and endpoint == "/v1/sync/run":
                if payload.get("trust_policy") in {"trusted_device", "active_if_trusted", "active_for_project_state"}:
                    self.auth.require_capability(auth_context, "memory:remote_active_write")
                return asdict(self.memory.sync(
                    collection_id=self._required(payload, "collection_id"),
                    peer_id=payload.get("peer_id"),
                    direction=payload.get("direction", "bidirectional"),
                    transport=payload.get("transport", "file_bundle"),
                    input_path=self._optional_safe_admin_path(payload, "input_path"),
                    output_path=self._optional_safe_admin_path(payload, "output_path"),
                    dry_run=bool(payload.get("dry_run", False)),
                ))
            if method == "GET" and endpoint == "/v1/sync/runs":
                return [asdict(run) for run in self.memory.list_sync_runs(limit=self._limit(query))]
            if method == "GET" and endpoint == "/v1/sync/conflicts":
                namespace = self._query_value(query, "namespace", none_if_missing=True)
                if namespace:
                    self.auth.require_namespace(auth_context, namespace=namespace)
                return [asdict(conflict) for conflict in self.memory.list_sync_conflicts(namespace=namespace, status=self._query_value(query, "status", none_if_missing=True))]
            if method == "POST" and endpoint.startswith("/v1/sync/conflicts/") and endpoint.endswith("/resolve"):
                conflict_id = endpoint.split("/")[4]
                conflict = self.memory.get_sync_conflict(conflict_id)
                self.auth.require_namespace(auth_context, namespace=conflict.namespace)
                return asdict(self.memory.resolve_sync_conflict(
                    conflict_id,
                    strategy=self._required(payload, "strategy"),
                    reason=self._required(payload, "reason"),
                    actor=payload.get("actor", "api"),
                ))
            if method == "GET" and endpoint == "/v1/sync/cursors":
                return [asdict(cursor) for cursor in self.memory.list_replication_cursors()]
            if method == "GET" and endpoint == "/v1/sync/remote-sources":
                return [asdict(source) for source in self.memory.list_remote_sources(local_object_id=self._query_value(query, "local_object_id", none_if_missing=True))]
            if method == "GET" and endpoint == "/v1/sync/trust-policies":
                return [asdict(policy) for policy in self.memory.list_import_trust_policies()]

        if endpoint.startswith("/v1/workspaces"):
            self.auth.require_capability(auth_context, "memory:workspace")
            if method == "GET" and endpoint == "/v1/workspaces":
                namespace = self._query_value(query, "namespace", none_if_missing=True)
                if namespace:
                    self.auth.require_namespace(auth_context, namespace=namespace)
                return [asdict(workspace) for workspace in self.memory.list_workspaces(namespace=namespace)]
            if method == "POST" and endpoint == "/v1/workspaces":
                namespace = self._required(payload, "namespace")
                self.auth.require_namespace(auth_context, namespace=namespace)
                return asdict(self.memory.create_workspace(
                    namespace=namespace,
                    name=self._required(payload, "name"),
                    description=payload.get("description"),
                    owner_identity_id=payload.get("owner_identity_id"),
                    metadata=payload.get("metadata"),
                ))
            if method == "GET" and endpoint == "/v1/workspaces/agent-groups":
                namespace = self._query_value(query, "namespace", none_if_missing=True)
                if namespace:
                    self.auth.require_namespace(auth_context, namespace=namespace)
                return [asdict(group) for group in self.memory.list_agent_groups(namespace=namespace)]
            if method == "POST" and endpoint == "/v1/workspaces/agent-groups":
                namespace = self._required(payload, "namespace")
                self.auth.require_namespace(auth_context, namespace=namespace)
                return asdict(self.memory.create_agent_group(
                    namespace=namespace,
                    name=self._required(payload, "name"),
                    description=payload.get("description"),
                    default_capabilities=payload.get("default_capabilities"),
                    metadata=payload.get("metadata"),
                ))
            parts = endpoint.split("/")
            if len(parts) >= 4:
                workspace_id = parts[3]
                workspace = self.memory.get_workspace(workspace_id)
                self.auth.require_namespace(auth_context, namespace=workspace.namespace)
                if method == "GET" and len(parts) == 4:
                    return asdict(workspace)
                if len(parts) >= 5 and parts[4] == "members":
                    if method == "GET" and len(parts) == 5:
                        return [asdict(member) for member in self.memory.list_workspace_members(workspace.id)]
                    if method == "POST" and len(parts) == 5:
                        return asdict(self.memory.add_workspace_member(
                            workspace.id,
                            member_type=self._required(payload, "member_type"),
                            member_id=self._required(payload, "member_id"),
                            role=self._required(payload, "role"),
                            metadata=payload.get("metadata"),
                        ))
                    if method == "DELETE" and len(parts) == 6:
                        return self.memory.remove_workspace_member(workspace.id, member_id=parts[5])

        if endpoint.startswith("/v1/revocations"):
            self.auth.require_capability(auth_context, "memory:sync")
            if method == "GET" and endpoint == "/v1/revocations":
                return [asdict(record) for record in self.memory.list_revocations()]
            if method == "POST" and endpoint == "/v1/revocations/propagate":
                return self.memory.propagate_revocations(peer_id=payload.get("peer_id"))

        raise not_found(endpoint)

    def _is_m9_endpoint(self, endpoint: str) -> bool:
        return any(endpoint.startswith(prefix) for prefix in [
            "/v1/plugins",
            "/v1/conformance",
            "/v1/compatibility",
            "/v1/contracts",
            "/v1/deprecations",
            "/v1/doctor",
            "/v1/docs",
            "/v1/examples",
            "/v1/adapters",
            "/v1/v1-gate",
        ])

    def _m9_endpoint(self, method: str, endpoint: str, query: dict, payload: dict, auth_context: AuthContext):
        if method == "GET":
            self.auth.require_capability(auth_context, "memory:read")
        else:
            self.auth.require_capability(auth_context, "memory:admin")

        if method == "GET" and endpoint == "/v1/contracts":
            return [
                asdict(item)
                for item in self.memory.list_public_contracts(
                    contract_type=self._query_value(query, "contract_type", none_if_missing=True),
                    stability=self._query_value(query, "stability", none_if_missing=True),
                    limit=self._limit(query),
                )
            ]
        if method == "POST" and endpoint == "/v1/contracts":
            return asdict(self.memory.register_public_contract(
                contract_type=self._required(payload, "contract_type"),
                name=self._required(payload, "name"),
                version=self._required(payload, "version"),
                stability=payload.get("stability", "stable"),
                schema_ref=payload.get("schema_ref"),
                documentation_ref=payload.get("documentation_ref"),
                metadata=payload.get("metadata"),
            ))
        if method == "GET" and endpoint.startswith("/v1/contracts/"):
            return asdict(self.memory.get_public_contract(endpoint.split("/")[3]))

        if method == "GET" and endpoint == "/v1/deprecations":
            return [
                asdict(item)
                for item in self.memory.list_deprecations(
                    target_type=self._query_value(query, "target_type", none_if_missing=True)
                )
            ]
        if method == "GET" and endpoint == "/v1/deprecations/check":
            return self.memory.check_deprecations()

        if method == "GET" and endpoint == "/v1/compatibility/report":
            return self.memory.compatibility_report(
                include_plugins=self._query_bool(query, "include_plugins", default=True),
                include_sdks=self._query_bool(query, "include_sdks", default=True),
                include_runtime=self._query_bool(query, "include_runtime", default=True),
            )
        if method == "GET" and endpoint == "/v1/compatibility/matrix":
            return [
                asdict(item)
                for item in self.memory.list_compatibility_matrix(
                    component_type=self._query_value(query, "component_type", none_if_missing=True)
                )
            ]
        if method == "GET" and endpoint == "/v1/compatibility/status":
            return self.memory.compatibility_status(
                component_type=self._query_value(query, "component_type"),
                component_name=self._query_value(query, "component_name"),
                component_version=self._query_value(query, "component_version"),
            )
        if method == "GET" and endpoint == "/v1/compatibility/sdks":
            return [asdict(item) for item in self.memory.list_sdk_releases()]

        if method == "GET" and endpoint == "/v1/plugins":
            return self.memory.list_plugins(include_disabled=self._query_bool(query, "include_disabled", default=True))
        if method == "POST" and endpoint == "/v1/plugins/discover":
            return self.memory.discover_plugins(self._required_safe_admin_path(payload, "path"))
        if method == "POST" and endpoint == "/v1/plugins/install":
            return asdict(self.memory.install_plugin(
                plugin_path=self._required_safe_admin_path(payload, "plugin_path"),
                trust_level=payload.get("trust_level", "local"),
                approve_permissions=bool(payload.get("approve_permissions", False)),
            ))
        if method == "GET" and endpoint.startswith("/v1/plugins/") and endpoint.endswith("/logs"):
            return [asdict(item) for item in self.memory.list_plugin_logs(plugin_id=endpoint.split("/")[3], limit=self._limit(query))]
        if method == "POST" and endpoint.startswith("/v1/plugins/") and endpoint.endswith("/enable"):
            plugin_id = endpoint.split("/")[3]
            return asdict(self.memory.enable_plugin(
                plugin_id,
                reason=self._required(payload, "reason"),
                approved_permissions=payload.get("approved_permissions") or [],
                actor=auth_context.client_id or "api",
            ))
        if method == "POST" and endpoint.startswith("/v1/plugins/") and endpoint.endswith("/disable"):
            plugin_id = endpoint.split("/")[3]
            return asdict(self.memory.disable_plugin(plugin_id, reason=self._required(payload, "reason"), actor=auth_context.client_id or "api"))
        if method == "POST" and endpoint.startswith("/v1/plugins/") and endpoint.endswith("/run"):
            plugin_id = endpoint.split("/")[3]
            return self.memory.run_plugin_operation(
                plugin_id=plugin_id,
                operation=self._required(payload, "operation"),
                namespace=payload.get("namespace"),
                payload=payload.get("payload") or {},
            )
        if method == "GET" and endpoint.startswith("/v1/plugins/"):
            installation = self.memory.get_plugin_installation(endpoint.split("/")[3])
            manifest = self.memory.get_plugin_manifest(installation.plugin_manifest_id)
            return {"installation": asdict(installation), "manifest": asdict(manifest)}

        if method == "GET" and endpoint == "/v1/conformance/suites":
            return [
                {
                    **asdict(suite),
                    "cases": [asdict(case) for case in self.memory.list_conformance_cases(suite.id)],
                }
                for suite in self.memory.list_conformance_suites()
            ]
        if method == "POST" and endpoint == "/v1/conformance/run":
            return asdict(self.memory.run_conformance(
                suite=self._required(payload, "suite"),
                target=payload.get("target"),
                target_type=payload.get("target_type"),
                fail_fast=bool(payload.get("fail_fast", False)),
                metadata=payload.get("metadata"),
            ))
        if method == "GET" and endpoint == "/v1/conformance/runs":
            return [asdict(item) for item in self.memory.list_conformance_runs(limit=self._limit(query))]
        if method == "GET" and endpoint.startswith("/v1/conformance/runs/") and endpoint.endswith("/results"):
            return [asdict(item) for item in self.memory.list_conformance_results(endpoint.split("/")[4])]
        if method == "GET" and endpoint.startswith("/v1/conformance/runs/"):
            return asdict(self.memory.get_conformance_run(endpoint.split("/")[4]))

        if method == "GET" and endpoint == "/v1/adapters/certifications":
            return [asdict(item) for item in self.memory.list_adapter_certifications()]
        if method == "POST" and endpoint == "/v1/adapters/scaffold":
            return self.memory.scaffold_adapter(
                adapter_type=payload.get("adapter_type", "generic-http"),
                name=self._required(payload, "name"),
                output_path=self._required_safe_admin_path(payload, "output_path"),
            )
        if method == "POST" and endpoint == "/v1/adapters/certify":
            return asdict(self.memory.certify_adapter(
                path=self._required_safe_admin_path(payload, "path"),
                adapter_type=payload.get("adapter_type", "generic-http"),
            ))

        if method == "GET" and endpoint == "/v1/docs/status":
            return self.memory.docs_status()
        if method == "POST" and endpoint == "/v1/docs/build":
            return asdict(self.memory.build_docs(
                output_dir=self._required_safe_admin_path(payload, "output_dir"),
                include_api_reference=bool(payload.get("include_api_reference", True)),
                include_cli_reference=bool(payload.get("include_cli_reference", True)),
                validate_examples=bool(payload.get("validate_examples", True)),
            ))
        if method == "POST" and endpoint == "/v1/docs/test-examples":
            return self.memory.test_doc_examples()

        if method == "GET" and endpoint == "/v1/examples":
            return [asdict(item) for item in self.memory.list_examples()]
        if method == "POST" and endpoint == "/v1/examples/create":
            return self.memory.scaffold_adapter(
                adapter_type=payload.get("example_type", "generic-http"),
                name=self._required(payload, "name"),
                output_path=self._required_safe_admin_path(payload, "output_path"),
            )
        if method == "POST" and endpoint == "/v1/examples/test":
            return self.memory.test_doc_examples()

        if method == "POST" and endpoint == "/v1/doctor/run":
            return asdict(self.memory.doctor_run(service_url=payload.get("service_url")))
        if method == "GET" and endpoint == "/v1/doctor/runs":
            return [asdict(item) for item in self.memory.list_doctor_runs(limit=self._limit(query))]
        if method == "GET" and endpoint.startswith("/v1/doctor/runs/"):
            return asdict(self.memory.get_doctor_run(endpoint.split("/")[4]))

        if method == "POST" and endpoint == "/v1/v1-gate/run":
            return asdict(self.memory.v1_gate_run(
                auto_run_conformance=bool(payload.get("auto_run_conformance", True)),
                require_docs=bool(payload.get("require_docs", True)),
                external_telemetry_enabled=bool(payload.get("external_telemetry_enabled", False)),
                acknowledged_readiness_warnings=bool(payload.get("acknowledged_readiness_warnings", True)),
                metadata=payload.get("metadata"),
            ))
        if method == "GET" and endpoint == "/v1/v1-gate/runs":
            return [asdict(item) for item in self.memory.list_v1_gate_runs(limit=self._limit(query))]
        if method == "GET" and endpoint.startswith("/v1/v1-gate/runs/"):
            return asdict(self.memory.get_v1_gate_run(endpoint.split("/")[4]))

        raise not_found(endpoint)

    def _is_m8_endpoint(self, endpoint: str) -> bool:
        return any(endpoint.startswith(prefix) for prefix in [
            "/v1/backups",
            "/v1/restore",
            "/v1/encryption",
            "/v1/keys",
            "/v1/redactions",
            "/v1/forget",
            "/v1/tombstones",
            "/v1/retention",
            "/v1/integrity",
            "/v1/migrations",
            "/v1/compact",
            "/v1/exports",
            "/v1/imports",
            "/v1/support",
            "/v1/benchmarks",
            "/v1/release",
            "/v1/readiness",
        ])

    def _m8_endpoint(self, method: str, endpoint: str, query: dict, payload: dict, auth_context: AuthContext):
        namespace = payload.get("namespace") or self._query_value(query, "namespace", none_if_missing=True)
        if namespace:
            self._require(auth_context, "memory:admin", {"namespace": namespace})
        else:
            self.auth.require_capability(auth_context, "memory:admin")

        if method == "POST" and endpoint == "/v1/backups/create":
            output_path = self._optional_safe_admin_path(payload, "output_path") or self._default_admin_output_path("backups", f"aletheia-{new_id('backup')}.alet")
            return asdict(self.memory.create_backup(
                output_path=output_path,
                backup_type=payload.get("backup_type", "physical"),
                namespace=namespace,
                encrypt=bool(payload.get("encrypt", False)),
                privacy_mode=payload.get("privacy_mode", "full"),
                passphrase=payload.get("passphrase"),
                key_id=payload.get("key_id"),
                verify_after=bool(payload.get("verify_after", True)),
                created_by=auth_context.client_id or "api",
            ))
        if method == "POST" and endpoint == "/v1/backups/verify":
            return asdict(self.memory.verify_backup(
                backup_path=self._required_safe_admin_path(payload, "backup_path"),
                passphrase=payload.get("passphrase"),
                key_id=payload.get("key_id"),
                deep=bool(payload.get("deep", True)),
            ))
        if method == "GET" and endpoint == "/v1/backups":
            return [asdict(item) for item in self.memory.list_backups(limit=self._limit(query))]
        if method == "GET" and endpoint.startswith("/v1/backups/"):
            return asdict(self.memory.get_backup(endpoint.split("/")[3]))

        if method == "POST" and endpoint == "/v1/restore/dry-run":
            return asdict(self.memory.restore_backup(
                backup_path=self._required_safe_admin_path(payload, "backup_path"),
                target_db_path=self._required_safe_admin_path(payload, "target_db_path"),
                namespace=namespace,
                passphrase=payload.get("passphrase"),
                key_id=payload.get("key_id"),
                dry_run=True,
            ))
        if method == "POST" and endpoint == "/v1/restore/apply":
            if payload.get("confirmation") != "restore backup":
                raise validation_error("Confirmation text must be 'restore backup'.")
            return asdict(self.memory.restore_backup(
                backup_path=self._required_safe_admin_path(payload, "backup_path"),
                target_db_path=self._required_safe_admin_path(payload, "target_db_path"),
                mode=payload.get("mode", "new_database"),
                namespace=namespace,
                passphrase=payload.get("passphrase"),
                key_id=payload.get("key_id"),
                dry_run=False,
            ))

        if method == "GET" and endpoint == "/v1/encryption/status":
            return asdict(self.memory.protected_mode_status())
        if method == "POST" and endpoint == "/v1/encryption/enable":
            return asdict(self.memory.enable_protected_mode(protected=bool(payload.get("protected", True)), actor=auth_context.client_id or "api"))
        if method == "GET" and endpoint == "/v1/keys":
            return [asdict(item) for item in self.memory.list_keys(include_inactive=bool(query.get("include_inactive")))]
        if method == "POST" and endpoint == "/v1/keys":
            return asdict(self.memory.create_key(provider=payload.get("provider", "passphrase"), label=self._required(payload, "label")))
        if method == "POST" and endpoint.startswith("/v1/keys/") and endpoint.endswith("/rotate"):
            key_id = endpoint.split("/")[3]
            return asdict(self.memory.rotate_key(
                old_key_id=key_id,
                new_key_label=self._required(payload, "label"),
                target=payload.get("target", "content"),
                dry_run=not bool(payload.get("apply", False)),
                force=bool(payload.get("force", False)),
            ))

        if method == "POST" and endpoint in {"/v1/redactions/preview", "/v1/redactions/apply"}:
            apply = endpoint.endswith("/apply")
            if apply and payload.get("confirmation") != "redact memory":
                raise validation_error("Confirmation text must be 'redact memory'.")
            return asdict(self.memory.redact(
                target_id=self._required(payload, "target_id"),
                target_type=payload.get("target_type", "evidence"),
                reason=self._required(payload, "reason"),
                replacement_text=payload.get("replacement_text", "[REDACTED]"),
                actor=auth_context.client_id or "api",
                dry_run=not apply,
            ))
        if method == "POST" and endpoint in {"/v1/forget/preview", "/v1/forget/apply"}:
            apply = endpoint.endswith("/apply")
            return asdict(self.memory.forget(
                selector=payload.get("selector") or {"namespace": namespace or self.memory.namespace},
                mode=payload.get("mode", "tombstone"),
                reason=self._required(payload, "reason"),
                actor=auth_context.client_id or "api",
                dry_run=not apply,
                confirmation=payload.get("confirmation"),
            ))
        if method == "GET" and endpoint == "/v1/tombstones":
            return [asdict(item) for item in self.memory.list_tombstones(namespace=namespace, limit=self._limit(query))]

        if method == "GET" and endpoint == "/v1/retention/policies":
            return [asdict(item) for item in self.memory.list_retention_policies(namespace=namespace)]
        if method == "POST" and endpoint == "/v1/retention/policies":
            return asdict(self.memory.create_retention_policy(
                namespace=namespace,
                memory_type=payload.get("memory_type"),
                privacy_level=payload.get("privacy_level"),
                source_type=payload.get("source_type"),
                action=payload.get("action", "queue_review"),
                after_days=int(payload.get("after_days", 365)),
                reason=self._required(payload, "reason"),
            ))
        if method == "POST" and endpoint == "/v1/retention/run":
            return asdict(self.memory.run_retention(namespace=namespace, dry_run=not bool(payload.get("apply", False))))

        if method == "POST" and endpoint == "/v1/integrity/check":
            return asdict(self.memory.integrity_check(namespace=namespace, scope=payload.get("scope", "standard"), deep=bool(payload.get("deep", False))))
        if method == "GET" and endpoint == "/v1/integrity/runs":
            return [asdict(item) for item in self.memory.list_integrity_runs(namespace=namespace, limit=self._limit(query))]
        if method == "GET" and endpoint == "/v1/integrity/findings":
            return [asdict(item) for item in self.memory.list_integrity_findings(run_id=self._query_value(query, "run_id", none_if_missing=True), limit=self._limit(query))]
        if method == "POST" and endpoint.startswith("/v1/integrity/findings/") and endpoint.endswith("/repair"):
            return asdict(self.memory.repair_integrity(finding_id=endpoint.split("/")[4], dry_run=not bool(payload.get("apply", False))))

        if method == "POST" and endpoint == "/v1/migrations/plan":
            return asdict(self.memory.migration_plan(target_version=payload.get("target_version", SCHEMA_VERSION)))
        if method == "POST" and endpoint == "/v1/migrations/apply":
            return asdict(self.memory.migration_apply(
                target_version=payload.get("target_version", SCHEMA_VERSION),
                dry_run=bool(payload.get("dry_run", False)),
                backup_before=bool(payload.get("backup_before", False)),
                backup_output=self._optional_safe_admin_path(payload, "backup_output"),
                passphrase=payload.get("passphrase"),
                verify_after=bool(payload.get("verify_after", False)),
            ))
        if method == "POST" and endpoint == "/v1/migrations/verify":
            return asdict(self.memory.integrity_check(namespace=namespace, scope="migration_verify", deep=bool(payload.get("deep", False))))

        if method == "POST" and endpoint in {"/v1/compact/preview", "/v1/compact/run"}:
            return asdict(self.memory.compact_database(
                dry_run=endpoint.endswith("/preview"),
                backup_before=bool(payload.get("backup_before", False)),
                passphrase=payload.get("passphrase"),
            ))
        if method == "POST" and endpoint == "/v1/exports":
            return asdict(self.memory.export_archive(
                output_path=self._required_safe_admin_path(payload, "output_path"),
                namespace=namespace,
                export_type=payload.get("export_type", "namespace_archive"),
                format=payload.get("format", "alet"),
                encrypt=bool(payload.get("encrypt", False)),
                privacy_mode=payload.get("privacy_mode", "redacted"),
                passphrase=payload.get("passphrase"),
            ))
        if method == "POST" and endpoint in {"/v1/imports/dry-run", "/v1/imports/apply"}:
            return asdict(self.memory.import_archive(
                input_path=self._required_safe_admin_path(payload, "input_path"),
                namespace=namespace,
                dry_run=endpoint.endswith("/dry-run"),
                passphrase=payload.get("passphrase"),
            ))
        if method == "POST" and endpoint == "/v1/support/bundle":
            return asdict(self.memory.support_bundle(
                output_path=self._optional_safe_admin_path(payload, "output_path") or self._default_admin_output_path("support", f"aletheia-support-{new_id('sup')}.zip"),
                encrypt=bool(payload.get("encrypt", False)),
                include_raw_content=bool(payload.get("include_raw_content", False)),
                passphrase=payload.get("passphrase"),
            ))
        if method == "POST" and endpoint == "/v1/benchmarks/run":
            run = self.memory.benchmark_run(profile=payload.get("profile", "tiny"))
            return {"run": asdict(run), "results": [asdict(item) for item in self.memory.list_benchmark_results(run.id)]}
        if method == "GET" and endpoint == "/v1/benchmarks":
            return [asdict(item) for item in self.memory.list_benchmarks(limit=self._limit(query))]
        if method == "POST" and endpoint == "/v1/release/manifest":
            return asdict(self.memory.release_manifest(output_path=self._optional_safe_admin_path(payload, "output_path")))
        if method == "POST" and endpoint == "/v1/readiness/check":
            return asdict(self.memory.readiness_check(namespace=namespace, profile=payload.get("profile", "local_production")))
        raise not_found(endpoint)

    def _console_static(self, endpoint: str) -> tuple[int, dict]:
        if not self.config.console_enabled:
            return 404, self._raw_response("Console is not enabled.", content_type="text/plain")
        if endpoint == "/console/assets/app.css":
            return 200, self._raw_response(CONSOLE_CSS, content_type="text/css; charset=utf-8")
        if endpoint != "/console" and endpoint != "/console/":
            return 404, self._raw_response("Console asset not found.", content_type="text/plain")
        return 200, self._raw_response(CONSOLE_HTML, content_type="text/html; charset=utf-8")

    def _console_login(self, payload: dict) -> dict:
        raw = self._required(payload, "login_token")
        rows = self.memory.store.connection.execute(
            """
            SELECT *
            FROM console_action_confirmations
            WHERE action_type = 'console_login_token'
            ORDER BY created_at DESC
            LIMIT 100
            """
        ).fetchall()
        row = next((item for item in rows if AuthService.verify_secret_hash(raw, item["confirmation_text"])), None)
        if not row:
            raise unauthorized("Invalid console login token.")
        metadata = json.loads(row["metadata_json"] or "{}")
        if metadata.get("used_at"):
            raise unauthorized("Console login token has already been used.")
        expires_at = parse_iso(metadata.get("expires_at"))
        if expires_at and expires_at <= utc_now():
            raise unauthorized("Console login token is expired.")
        session_token = "acs_" + secrets.token_urlsafe(32)
        csrf_token = "csrf_" + secrets.token_urlsafe(24)
        session_id = new_id("csess")
        now = utc_now()
        session_expires = now + timedelta(minutes=self.config.console_session_ttl_minutes)
        namespace_grants = metadata.get("namespace_grants") or ["*"]
        capabilities = metadata.get("capabilities") or ["memory:read"]
        privacy_ceiling = metadata.get("privacy_ceiling") or self.config.default_privacy_ceiling
        with self.memory.store.transaction():
            self.memory.store.connection.execute(
                """
                UPDATE console_action_confirmations
                SET metadata_json = ?
                WHERE id = ?
                """,
                (
                    json.dumps({**metadata, "used_at": utc_now_iso()}, sort_keys=True),
                    row["id"],
                ),
            )
            self.memory.store.connection.execute(
                """
                INSERT INTO console_sessions (
                    id, client_id, token_id, namespace_grants_json,
                    capabilities_json, privacy_ceiling, created_at, expires_at,
                    revoked_at, metadata_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL, ?)
                """,
                (
                    session_id,
                    metadata.get("client_id"),
                    metadata.get("token_id"),
                    json.dumps(namespace_grants, sort_keys=True),
                    json.dumps(capabilities, sort_keys=True),
                    privacy_ceiling,
                    now.isoformat(),
                    session_expires.isoformat(),
                    json.dumps(
                        {
                            "session_token_hash": self._hash_secret(session_token),
                            "csrf_token_hash": self._hash_secret(csrf_token),
                        },
                        sort_keys=True,
                    ),
                ),
            )
        return {
            "session_id": session_id,
            "session_token": session_token,
            "csrf_token": csrf_token,
            "expires_at": session_expires.isoformat(),
            "_headers": {
                "Set-Cookie": f"aletheia_console={session_token}; HttpOnly; SameSite=Strict; Path=/; Max-Age={self.config.console_session_ttl_minutes * 60}"
            },
        }

    def _console_logout(self, headers: Mapping[str, str]) -> dict:
        raw_session = self._header(headers, "X-Console-Session") or self._cookie(headers, "aletheia_console")
        if not raw_session:
            return {"logged_out": False}
        session_ids: list[str] = []
        rows = self.memory.store.connection.execute(
            """
            SELECT id, metadata_json
            FROM console_sessions
            WHERE revoked_at IS NULL
            ORDER BY created_at DESC
            """
        ).fetchall()
        for row in rows:
            metadata = json.loads(row["metadata_json"] or "{}")
            if AuthService.verify_secret_hash(raw_session, metadata.get("session_token_hash")):
                session_ids.append(row["id"])
        with self.memory.store.transaction():
            for session_id in session_ids:
                self.memory.store.connection.execute(
                    "UPDATE console_sessions SET revoked_at = ? WHERE id = ? AND revoked_at IS NULL",
                    (utc_now_iso(), session_id),
                )
        return {
            "logged_out": True,
            "_headers": {"Set-Cookie": "aletheia_console=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0"},
        }

    def _console_session_for_token(self, raw_session: str):
        rows = self.memory.store.connection.execute(
            """
            SELECT *
            FROM console_sessions
            WHERE revoked_at IS NULL
            ORDER BY created_at DESC
            """
        ).fetchall()
        for row in rows:
            metadata = json.loads(row["metadata_json"] or "{}")
            if not AuthService.verify_secret_hash(raw_session, metadata.get("session_token_hash")):
                continue
            expires_at = parse_iso(row["expires_at"])
            if expires_at and expires_at <= utc_now():
                with self.memory.store.transaction():
                    self.memory.store.connection.execute(
                        "UPDATE console_sessions SET revoked_at = ? WHERE id = ?",
                        (utc_now_iso(), row["id"]),
                    )
                raise unauthorized("Console session is expired.")
            return row
        raise unauthorized("Invalid console session.")

    def _require_console_csrf(self, auth_context: AuthContext, headers: Mapping[str, str]) -> None:
        if not auth_context.token or not auth_context.token.metadata.get("console_session"):
            return
        expected = auth_context.token.metadata.get("csrf_token_hash")
        provided = self._header(headers, "X-CSRF-Token")
        if not provided or not AuthService.verify_secret_hash(provided, expected):
            raise forbidden("CSRF token required for console state changes.")

    def _record_console_confirmation(
        self,
        *,
        namespace: str | None,
        action_type: str,
        target_id: str | None,
        target_type: str | None,
        confirmation_text: str,
        reason: str,
        actor: str,
        metadata: dict | None = None,
    ) -> None:
        with self.memory.store.transaction():
            self.memory.store.connection.execute(
                """
                INSERT INTO console_action_confirmations (
                    id, namespace, action_type, target_id, target_type,
                    confirmation_text, reason, actor, created_at, metadata_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    new_id("conf"),
                    namespace,
                    action_type,
                    target_id,
                    target_type,
                    confirmation_text,
                    reason,
                    actor,
                    utc_now_iso(),
                    json.dumps(metadata or {}, sort_keys=True),
                ),
            )

    def _resolve_matching_review_task(self, namespace: str, task_type: str, target_id: str, *, reason: str) -> None:
        for task in self.memory.list_review_tasks(namespace=namespace, status="open", task_type=task_type, limit=20):
            if task.target_id == target_id:
                self.memory.resolve_review_task(task.id, resolution="console_action", reason=reason, actor="console")

    def _capability_for_review_task(self, task_type: str) -> str:
        if task_type in {"candidate_review", "conflict_resolution", "inference_review", "reflection_refresh", "stale_core_memory", "risk_flag_review"}:
            return "memory:review"
        if task_type in {"policy_review"}:
            return "memory:policy"
        if task_type in {"procedure_review"}:
            return "memory:review"
        if task_type in {"job_failure"}:
            return "memory:jobs"
        return "memory:read"

    def _dashboard_preferences(self, namespace: str) -> dict:
        rows = self.memory.store.connection.execute(
            """
            SELECT preference_key, preference_value_json
            FROM dashboard_preferences
            WHERE namespace IS NULL OR namespace = ?
            ORDER BY namespace IS NOT NULL, preference_key
            """,
            (namespace,),
        ).fetchall()
        return {row["preference_key"]: json.loads(row["preference_value_json"]) for row in rows}

    def _set_dashboard_preference(self, namespace: str, payload: dict) -> dict:
        key = self._required(payload, "preference_key")
        value = payload.get("value")
        now = utc_now_iso()
        pref_id = "dpref_" + content_hash(f"{namespace}\0{key}")[:24]
        with self.memory.store.transaction():
            self.memory.store.connection.execute(
                """
                INSERT INTO dashboard_preferences (
                    id, namespace, preference_key, preference_value_json,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    preference_value_json = excluded.preference_value_json,
                    updated_at = excluded.updated_at
                """,
                (pref_id, namespace, key, json.dumps(value, sort_keys=True), now),
            )
        return {"preference_key": key, "value": value, "updated_at": now}

    def _create_saved_view(self, namespace: str, payload: dict) -> dict:
        view_id = new_id("view")
        now = utc_now_iso()
        with self.memory.store.transaction():
            self.memory.store.connection.execute(
                """
                INSERT INTO dashboard_saved_views (
                    id, namespace, name, view_type, filters_json, sort_json,
                    created_at, updated_at, metadata_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    view_id,
                    namespace,
                    self._required(payload, "name"),
                    self._required(payload, "view_type"),
                    json.dumps(payload.get("filters") or {}, sort_keys=True),
                    json.dumps(payload.get("sort"), sort_keys=True) if payload.get("sort") else None,
                    now,
                    now,
                    json.dumps(payload.get("metadata") or {}, sort_keys=True),
                ),
            )
        return {"id": view_id, "created_at": now}

    def _pagination_for_list(self, method: str, endpoint: str, query: dict) -> dict | None:
        if method != "GET":
            return None
        if not any(endpoint.startswith(prefix) for prefix in [
            "/v1/reviews",
            "/v1/traces",
            "/v1/metrics",
            "/v1/notifications",
            "/v1/reports",
            "/v1/backups",
            "/v1/keys",
            "/v1/tombstones",
            "/v1/retention",
            "/v1/integrity",
            "/v1/benchmarks",
            "/v1/plugins",
            "/v1/conformance",
            "/v1/contracts",
            "/v1/deprecations",
            "/v1/doctor",
            "/v1/examples",
            "/v1/adapters",
            "/v1/v1-gate",
            "/v1/federation",
            "/v1/peers",
            "/v1/shares",
            "/v1/sync",
            "/v1/workspaces",
            "/v1/grants",
            "/v1/revocations",
        ]):
            return None
        return self._pagination(0, query)

    @staticmethod
    def _hash_secret(value: str) -> str:
        return AuthService.hash_secret(value)

    @staticmethod
    def _raw_response(body: str, *, content_type: str) -> dict:
        return {"_raw_body": body, "_content_type": content_type}

    def _require(self, auth_context: AuthContext, capability: str, payload: dict) -> None:
        self.auth.require_capability(auth_context, capability)
        namespace = payload.get("namespace")
        if namespace:
            self.auth.require_namespace(auth_context, namespace=namespace, project_id=payload.get("project_id"))

    def _authenticate(self, method: str, endpoint: str, headers: Mapping[str, str]) -> AuthContext:
        if endpoint == "/v1/console/login":
            return AuthContext(token=None, client=None, auth_required=False)
        if self._is_console_api(endpoint):
            return self._authenticate_console_or_api(method, endpoint, headers)
        auth_required = self.config.auth_required and (method, endpoint) not in PUBLIC_ENDPOINTS
        return self.auth.authenticate(
            self._header(headers, "Authorization"),
            auth_required=auth_required,
            default_namespace_grants=[self.memory.namespace],
            default_privacy_ceiling=self.config.default_privacy_ceiling,
        )

    def _is_console_api(self, endpoint: str) -> bool:
        return any(endpoint.startswith(prefix) for prefix in CONSOLE_API_PREFIXES)

    def _authenticate_console_or_api(self, method: str, endpoint: str, headers: Mapping[str, str]) -> AuthContext:
        raw_auth = self._header(headers, "Authorization")
        if raw_auth:
            return self.auth.authenticate(raw_auth, auth_required=True)
        raw_session = self._header(headers, "X-Console-Session") or self._cookie(headers, "aletheia_console")
        if not raw_session:
            raise unauthorized("Console authentication required.")
        session = self._console_session_for_token(raw_session)
        token = ApiToken(
            id=session["id"],
            client_id=session["client_id"] or "console",
            token_prefix=raw_session[:12],
            token_hash="",
            status="active",
            privacy_ceiling=session["privacy_ceiling"],
            expires_at=session["expires_at"],
            created_at=session["created_at"],
            revoked_at=session["revoked_at"],
            capabilities=json.loads(session["capabilities_json"]),
            namespace_grants=json.loads(session["namespace_grants_json"]),
            metadata={**json.loads(session["metadata_json"] or "{}"), "console_session": True},
        )
        context = AuthContext(token=token, client=None, auth_required=True)
        if method in STATE_CHANGING_METHODS and endpoint not in {"/v1/console/logout"}:
            self._require_console_csrf(context, headers)
        return context

    def _rate_limit_identity(self, auth_context: AuthContext, headers: Mapping[str, str]) -> str:
        if auth_context.client_id:
            return f"client:{auth_context.client_id}"
        client_ip = "local"
        if self.config.trust_proxy_headers:
            forwarded_for = self._header(headers, "X-Forwarded-For")
            if forwarded_for:
                client_ip = forwarded_for.split(",", 1)[0].strip()
            else:
                client_ip = (self._header(headers, "X-Real-IP") or "local").strip()
        return f"anonymous:{client_ip or 'local'}"

    def _check_rate_limit(self, client_id: str) -> None:
        if self.config.rate_limit_per_minute <= 0:
            return
        now = utc_now()
        window_start = now.replace(second=0, microsecond=0)
        window_end = window_start.replace(minute=window_start.minute + 1) if window_start.minute < 59 else None
        if window_end is None:
            from datetime import timedelta

            window_end = window_start + timedelta(minutes=1)
        record_id = "rl_" + content_hash(f"{client_id}\0{window_start.isoformat()}")[:24]
        row = self.memory.store.connection.execute(
            "SELECT request_count FROM rate_limit_records WHERE id = ?",
            (record_id,),
        ).fetchone()
        if row and int(row["request_count"]) >= self.config.rate_limit_per_minute:
            raise rate_limited()
        with self.memory.store.transaction():
            if row:
                self.memory.store.connection.execute(
                    "UPDATE rate_limit_records SET request_count = request_count + 1 WHERE id = ?",
                    (record_id,),
                )
            else:
                self.memory.store.connection.execute(
                    """
                    INSERT INTO rate_limit_records (
                        id, client_id, window_start, window_end, request_count, created_at
                    )
                    VALUES (?, ?, ?, ?, 1, ?)
                    """,
                    (record_id, client_id, window_start.isoformat(), window_end.isoformat(), utc_now_iso()),
                )

    def _idempotency_replay(
        self,
        *,
        method: str,
        endpoint: str,
        headers: Mapping[str, str],
        payload: dict,
        request_hash: str,
        namespace: str | None,
        client_id: str | None,
    ) -> dict | None:
        if method not in STATE_CHANGING_METHODS:
            return None
        key = self._header(headers, "Idempotency-Key")
        if not key:
            return None
        record_id = self._idempotency_id(client_id, key, endpoint)
        row = self.memory.store.connection.execute(
            "SELECT * FROM idempotency_records WHERE id = ?",
            (record_id,),
        ).fetchone()
        if not row:
            return None
        expires_at = parse_iso(row["expires_at"]) if row["expires_at"] else None
        if expires_at and expires_at <= utc_now():
            with self.memory.store.transaction():
                self.memory.store.connection.execute("DELETE FROM idempotency_records WHERE id = ?", (record_id,))
            return None
        if row["request_hash"] != request_hash:
            raise idempotency_conflict()
        return json.loads(row["response_json"])

    def _idempotency_store(
        self,
        *,
        method: str,
        endpoint: str,
        headers: Mapping[str, str],
        payload: dict,
        request_hash: str,
        namespace: str | None,
        client_id: str | None,
        status_code: int,
        response: dict,
    ) -> None:
        if method not in STATE_CHANGING_METHODS or status_code >= 400:
            return
        key = self._header(headers, "Idempotency-Key")
        if not key:
            return
        from datetime import timedelta

        record_id = self._idempotency_id(client_id, key, endpoint)
        stored = dict(response)
        stored["_status_code"] = status_code
        with self.memory.store.transaction():
            self.memory.store.connection.execute(
                """
                INSERT OR REPLACE INTO idempotency_records (
                    id, namespace, client_id, idempotency_key, endpoint,
                    request_hash, response_json, status, created_at, expires_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, 'completed', ?, ?)
                """,
                (
                    record_id,
                    namespace,
                    client_id,
                    key,
                    endpoint,
                    request_hash,
                    json.dumps(stored, sort_keys=True),
                    utc_now_iso(),
                    (utc_now() + timedelta(hours=24)).isoformat(),
                ),
            )

    def _idempotency_id(self, client_id: str | None, key: str, endpoint: str) -> str:
        return "idem_" + content_hash(f"{client_id or 'anonymous'}\0{key}\0{endpoint}")[:24]

    def _log_request(
        self,
        *,
        request_id: str,
        client_id: str | None,
        namespace: str | None,
        method: str,
        path: str,
        status_code: int,
        duration_ms: int,
        request_hash: str,
        response: dict | None,
    ) -> None:
        log_request_hash = None
        response_hash = None
        if self.config.request_log_mode == "hashes":
            log_request_hash = request_hash
            response_hash = content_hash(json.dumps(response or {}, sort_keys=True))
        with self.memory.store.transaction():
            with self.lock:
                self.memory.store.connection.execute(
                    """
                    INSERT INTO service_request_log (
                        id, request_id, client_id, agent_id, namespace, method,
                        path, status_code, duration_ms, request_hash,
                        response_hash, log_mode, created_at, metadata_json
                    )
                    VALUES (?, ?, ?, NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        new_id("sreq"),
                        request_id,
                        client_id,
                        namespace,
                        method,
                        path,
                        status_code,
                        duration_ms,
                        log_request_hash,
                        response_hash,
                        self.config.request_log_mode,
                        utc_now_iso(),
                        json.dumps({}, sort_keys=True),
                    ),
                )

    def log_mcp_invocation(
        self,
        *,
        request_id: str,
        client_id: str | None,
        tool_name: str,
        namespace: str | None,
        status: str,
        duration_ms: int,
        input_payload: dict,
        output_payload: dict | None,
        metadata: dict | None = None,
    ) -> None:
        with self.lock:
            with self.memory.store.transaction():
                self.memory.store.connection.execute(
                    """
                    INSERT INTO mcp_tool_invocation_log (
                        id, request_id, client_id, tool_name, namespace, status,
                        duration_ms, input_hash, output_hash, created_at,
                        metadata_json
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        new_id("mcp"),
                        request_id,
                        client_id,
                        tool_name,
                        namespace,
                        status,
                        duration_ms,
                        content_hash(json.dumps(input_payload, sort_keys=True)),
                        content_hash(json.dumps(output_payload or {}, sort_keys=True)),
                        utc_now_iso(),
                        json.dumps(metadata or {}, sort_keys=True),
                    ),
                )

    def _record_config(self, *, source: str) -> None:
        redacted = self.config.redacted()
        with self.lock:
            with self.memory.store.transaction():
                self.memory.store.connection.execute(
                    """
                    INSERT INTO service_config_history (
                        id, config_hash, config_redacted_json, source, created_at
                    )
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        new_id("cfg"),
                        content_hash(json.dumps(redacted, sort_keys=True)),
                        json.dumps(redacted, sort_keys=True),
                        source,
                        utc_now_iso(),
                    ),
                )

    def log_service_instance(
        self,
        *,
        instance_id: str,
        status: str,
        port: int | None = None,
        metadata: dict | None = None,
    ) -> None:
        payload = {"auth_required": self.config.auth_required, **(metadata or {})}
        with self.lock:
            with self.memory.store.transaction():
                self.memory.store.connection.execute(
                    """
                    INSERT INTO service_instance_log (
                        id, instance_id, host, port, db_path, started_at, status,
                        metadata_json
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        new_id("svc"),
                        instance_id,
                        self.config.host,
                        port or self.config.port,
                        self.config.db_path,
                        utc_now_iso(),
                        status,
                        json.dumps(payload, sort_keys=True),
                    ),
                )

    def service_requests(self, *, limit: int = 50) -> list[dict]:
        rows = self.memory.store.connection.execute(
            """
            SELECT *
            FROM service_request_log
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [dict(row) for row in rows]

    def mcp_invocations(self, *, limit: int = 50) -> list[dict]:
        rows = self.memory.store.connection.execute(
            """
            SELECT *
            FROM mcp_tool_invocation_log
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [dict(row) for row in rows]

    def _filtered_context_pack_privacy(self, pack, auth_context: AuthContext):
        omitted = 0

        def visible(items):
            nonlocal omitted
            kept = []
            for item in items:
                if self._evidence_allowed(item.evidence_ids, auth_context):
                    kept.append(item)
                else:
                    omitted += 1
            return kept

        filtered = replace(
            pack,
            core_memory=visible(pack.core_memory),
            project_memory=visible(pack.project_memory),
            session_memory=visible(pack.session_memory),
            procedural_memory=visible(pack.procedural_memory),
            reflection_memory=visible(pack.reflection_memory),
            relevant_memory=visible(pack.relevant_memory),
        )
        return filtered, omitted

    def _evidence_allowed(self, evidence_ids: list[str], auth_context: AuthContext) -> bool:
        if not evidence_ids:
            return self.auth.privacy_allows(auth_context, "personal")
        rows = self.memory.store.connection.execute(
            f"""
            SELECT privacy_level
            FROM evidence_events
            WHERE id IN ({','.join('?' for _ in evidence_ids)})
            """,
            evidence_ids,
        ).fetchall()
        return all(self.auth.privacy_allows(auth_context, row["privacy_level"]) for row in rows)

    def _provenance_for_items(self, items) -> list[dict]:
        provenance = []
        for item in items:
            provenance.append(
                {
                    "target_id": item.reflection_id or item.inference_id or item.claim_id,
                    "claim_id": item.claim_id,
                    "source_kind": item.source_kind,
                    "evidence_ids": item.evidence_ids,
                }
            )
        return provenance

    def _namespace_for_target(self, target_type: str, target_id: str) -> str | None:
        table_map = {
            "claim": ("claims", "id"),
            "candidate": ("candidate_claims", "id"),
            "candidate_claim": ("candidate_claims", "id"),
            "evidence": ("evidence_events", "id"),
            "event": ("evidence_events", "id"),
            "inference": ("inference_candidates", "id"),
            "reflection": ("reflections", "id"),
            "local_job": ("local_jobs", "id"),
        }
        table = table_map.get(target_type)
        if not table:
            return None
        row = self.memory.store.connection.execute(
            f"SELECT namespace FROM {table[0]} WHERE {table[1]} = ?",
            (target_id,),
        ).fetchone()
        return row["namespace"] if row else None

    def _feedback_args(self, payload: dict) -> dict:
        return {
            "namespace": self._required(payload, "namespace"),
            "target_id": self._required(payload, "target_id"),
            "target_type": payload.get("target_type", "claim"),
            "signal": self._required(payload, "signal"),
            "source": payload.get("source", "user"),
            "note": payload.get("note"),
            "evidence_id": payload.get("evidence_id"),
            "strength": float(payload.get("strength", 1.0)),
        }

    def _outcome_args(self, payload: dict) -> dict:
        namespace = self._required(payload, "namespace")
        return {
            "namespace": namespace,
            "task_id": self._required(payload, "task_id"),
            "outcome": self._required(payload, "outcome"),
            "used_context_pack_id": payload.get("used_context_pack_id") or payload.get("context_pack_id"),
            "session_id": payload.get("session_id"),
            "project_id": payload.get("project_id"),
            "user_feedback": payload.get("user_feedback"),
            "score": payload.get("score"),
            "note": payload.get("note"),
            "metadata": payload.get("metadata"),
        }

    def _retrieval_judgment_args(self, payload: dict) -> dict:
        return {
            "namespace": self._required(payload, "namespace"),
            "query": self._required(payload, "query"),
            "result_id": self._required(payload, "result_id"),
            "result_type": payload.get("result_type", "claim"),
            "judgment": self._required(payload, "judgment"),
            "judge": payload.get("judge", "user"),
            "reason": payload.get("reason"),
            "expected_rank": payload.get("expected_rank"),
            "session_id": payload.get("session_id"),
            "project_id": payload.get("project_id"),
        }

    def _ingest_args(self, payload: dict) -> dict:
        return {
            "namespace": self._required(payload, "namespace"),
            "source_type": payload.get("source_type", "service_ingest"),
            "content": self._required(payload, "content"),
            "source_uri": payload.get("source_uri"),
            "project_id": payload.get("project_id"),
            "session_id": payload.get("session_id"),
            "title": payload.get("title"),
            "metadata": payload.get("metadata"),
            "privacy_level": payload.get("privacy_level", "personal"),
            "trust_level": payload.get("trust_level", "unknown"),
        }

    def _extract_args(self, payload: dict) -> dict:
        return {
            "namespace": self._required(payload, "namespace"),
            "batch_id": payload.get("batch_id"),
            "evidence_ids": payload.get("evidence_ids"),
            "extractor": payload.get("extractor", "rule_based"),
            "dry_run": bool(payload.get("dry_run", False)),
            "max_candidates": payload.get("max_candidates"),
        }

    def _scope_claim_args(self, payload: dict) -> dict:
        return {
            "scope_type": self._required(payload, "scope_type"),
            "applies_when": payload.get("applies_when"),
            "valid_from": payload.get("valid_from"),
            "valid_to": payload.get("valid_to"),
            "reason": self._required(payload, "reason"),
        }

    def _start_session_args(self, payload: dict) -> dict:
        return {
            "namespace": self._required(payload, "namespace"),
            "agent_id": payload.get("agent_id"),
            "project_id": payload.get("project_id"),
            "title": payload.get("title"),
            "metadata": payload.get("metadata"),
        }

    def _end_session_args(self, payload: dict) -> dict:
        return {
            "summary": payload.get("summary"),
            "remember_summary": self._bool(payload.get("remember_summary", True)),
        }

    def _create_project_args(self, payload: dict) -> dict:
        return {
            "namespace": self._required(payload, "namespace"),
            "project_id": self._required(payload, "project_id"),
            "title": self._required(payload, "title"),
            "description": payload.get("description"),
            "status": payload.get("status", "active"),
            "metadata": payload.get("metadata"),
        }

    def _detect_conflicts_args(self, payload: dict) -> dict:
        return {
            "namespace": payload.get("namespace"),
            "subject": payload.get("subject"),
            "predicate": payload.get("predicate"),
            "include_resolved": self._bool(payload.get("include_resolved", False)),
            "create": self._bool(payload.get("create", True)),
            "claim_id": payload.get("claim_id"),
        }

    def _resolve_conflict_args(self, payload: dict) -> dict:
        return {
            "strategy": payload.get("strategy", "manual"),
            "active_claim_id": payload.get("active_claim_id"),
            "superseded_claim_ids": payload.get("superseded_claim_ids"),
            "rejected_claim_ids": payload.get("rejected_claim_ids"),
            "scoped_claims": payload.get("scoped_claims"),
            "note": payload.get("note"),
        }

    def _recompute_confidence_args(self, payload: dict) -> dict:
        return {
            "namespace": payload.get("namespace"),
            "claim_id": payload.get("claim_id"),
            "memory_types": payload.get("memory_types"),
            "persist": self._bool(payload.get("persist", True)),
        }

    def _curate_args(self, payload: dict) -> dict:
        return {
            "namespace": payload.get("namespace"),
            "memory_types": payload.get("memory_types"),
            "max_decisions": payload.get("max_decisions"),
        }

    def _run_inference_args(self, payload: dict) -> dict:
        return {
            "namespace": self._required(payload, "namespace"),
            "engines": payload.get("engines"),
            "project_id": payload.get("project_id"),
            "session_id": payload.get("session_id"),
            "target_claim_ids": payload.get("target_claim_ids"),
            "target_evidence_ids": payload.get("target_evidence_ids"),
            "target_entity_ids": payload.get("target_entity_ids"),
            "rule_ids": payload.get("rule_ids"),
            "dry_run": self._bool(payload.get("dry_run", True)),
            "max_inferences": payload.get("max_inferences"),
            "policy": payload.get("policy"),
        }

    def _build_reflection_args(self, payload: dict) -> dict:
        return {
            "namespace": self._required(payload, "namespace"),
            "source_claim_ids": payload.get("source_claim_ids"),
            "source_evidence_ids": payload.get("source_evidence_ids"),
            "source_reflection_ids": payload.get("source_reflection_ids"),
            "title": self._required(payload, "title"),
            "text": payload.get("text"),
            "abstraction_level": int(payload.get("abstraction_level", 2)),
            "project_id": payload.get("project_id"),
            "reason": self._required(payload, "reason"),
            "builder": payload.get("builder", "manual"),
            "require_review": self._bool(payload.get("require_review", True)),
        }

    def _create_eval_set_args(self, payload: dict) -> dict:
        return {
            "namespace": self._required(payload, "namespace"),
            "name": self._required(payload, "name"),
            "description": payload.get("description"),
            "project_id": payload.get("project_id"),
            "metadata": payload.get("metadata"),
        }

    def _add_eval_case_args(self, payload: dict) -> dict:
        return {
            "query": self._required(payload, "query"),
            "expected_claim_ids": payload.get("expected_claim_ids"),
            "expected_reflection_ids": payload.get("expected_reflection_ids"),
            "forbidden_claim_ids": payload.get("forbidden_claim_ids"),
            "expected_sections": payload.get("expected_sections"),
            "project_id": payload.get("project_id"),
            "session_id": payload.get("session_id"),
            "tags": payload.get("tags"),
            "note": payload.get("note"),
        }

    def _optimize_retrieval_args(self, payload: dict) -> dict:
        return {
            "namespace": self._required(payload, "namespace"),
            "eval_set_id": payload.get("eval_set_id"),
            "baseline_policy_version_id": payload.get("baseline_policy_version_id"),
            "objective": payload.get("objective", "balanced"),
            "dry_run": self._bool(payload.get("dry_run", True)),
            "max_trials": int(payload.get("max_trials", 50)),
            "constraints": payload.get("constraints"),
        }

    def _run_learning_args(self, payload: dict) -> dict:
        return {
            "namespace": self._required(payload, "namespace"),
            "project_id": payload.get("project_id"),
            "learning_targets": payload.get("learning_targets"),
            "eval_set_id": payload.get("eval_set_id"),
            "dry_run": self._bool(payload.get("dry_run", True)),
            "max_proposals": int(payload.get("max_proposals", 10)),
        }

    def _review_policy_args(self, payload: dict) -> dict:
        return {
            "decision": self._required(payload, "decision"),
            "reason": self._required(payload, "reason"),
            "reviewer": payload.get("reviewer", "user"),
        }

    def _apply_policy_args(self, payload: dict) -> dict:
        return {
            "reason": self._required(payload, "reason"),
            "applied_by": payload.get("applied_by", "user"),
            "require_evaluation_pass": self._bool(payload.get("require_evaluation_pass", True)),
        }

    def _enqueue_job_args(self, payload: dict) -> dict:
        run_after = payload.get("run_after")
        return {
            "namespace": self._required(payload, "namespace"),
            "job_type": self._required(payload, "job_type"),
            "payload": payload.get("payload") or {},
            "priority": float(payload.get("priority", 0.5)),
            "run_after": parse_iso(run_after) if run_after else None,
        }

    def _run_jobs_args(self, payload: dict) -> dict:
        return {
            "namespace": payload.get("namespace"),
            "job_type": payload.get("job_type"),
            "max_jobs": int(payload.get("max_jobs", 10)),
        }

    @staticmethod
    def _bool(value: Any) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.strip().lower() not in {"", "0", "false", "no", "off"}
        return bool(value)

    def _success(self, *, data: Any, request_id: str, warnings: list[str], pagination: dict | None) -> dict:
        headers = None
        if isinstance(data, dict) and "_headers" in data:
            data = dict(data)
            headers = data.pop("_headers")
        envelope = {"data": data, "request_id": request_id, "warnings": warnings, "pagination": pagination}
        if headers:
            envelope["_headers"] = headers
        return envelope

    def _error(self, exc: ServiceError, request_id: str) -> dict:
        return {
            "error": {"code": exc.code, "message": exc.message, "details": exc.details},
            "request_id": request_id,
        }

    def _json_body(self, body: bytes) -> dict:
        if not body:
            return {}
        try:
            value = json.loads(body.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise validation_error("Request body must be valid JSON.") from exc
        if not isinstance(value, dict):
            raise validation_error("Request body must be a JSON object.")
        return value

    @staticmethod
    def _hash_body(body: bytes) -> str:
        return content_hash(body.decode("utf-8", errors="replace"))

    @staticmethod
    def _header(headers: Mapping[str, str], name: str) -> str | None:
        lowered = name.lower()
        for key, value in headers.items():
            if key.lower() == lowered:
                return value
        return None

    def _cookie(self, headers: Mapping[str, str], name: str) -> str | None:
        raw = self._header(headers, "Cookie")
        if not raw:
            return None
        for part in raw.split(";"):
            key, _, value = part.strip().partition("=")
            if key == name:
                return value
        return None

    @staticmethod
    def _required(payload: dict, key: str) -> Any:
        value = payload.get(key)
        if value is None or value == "":
            raise validation_error(f"The field '{key}' is required.")
        return value

    def _admin_safe_roots(self) -> list[Path]:
        roots = [Path(self.config.db_path).expanduser().resolve().parent]
        extra = os.environ.get("ALETHEIA_ADMIN_SAFE_ROOTS", "")
        for raw in extra.split(os.pathsep):
            if raw.strip():
                roots.append(Path(raw).expanduser().resolve())
        deduped: list[Path] = []
        for root in roots:
            if root not in deduped:
                deduped.append(root)
        return deduped

    def _safe_admin_path(self, value: str, *, field: str) -> str:
        resolved = Path(value).expanduser().resolve(strict=False)
        roots = self._admin_safe_roots()
        if not any(resolved == root or root in resolved.parents for root in roots):
            raise validation_error(
                f"The field '{field}' must resolve under an admin safe root.",
                {"allowed_roots": [str(root) for root in roots]},
            )
        return str(resolved)

    def _optional_safe_admin_path(self, payload: dict, field: str) -> str | None:
        value = payload.get(field)
        if value is None or value == "":
            return None
        return self._safe_admin_path(str(value), field=field)

    def _required_safe_admin_path(self, payload: dict, field: str) -> str:
        return self._safe_admin_path(str(self._required(payload, field)), field=field)

    def _default_admin_output_path(self, subdir: str, filename: str) -> str:
        return str(self._admin_safe_roots()[0] / subdir / filename)

    def _query_value(self, query: dict[str, list[str]], key: str, none_if_missing: bool = False) -> str | None:
        value = query.get(key, [])
        if value:
            return value[0]
        if none_if_missing:
            return None
        raise validation_error(f"The query parameter '{key}' is required.")

    def _limit(self, query: dict[str, list[str]]) -> int:
        value = int(query.get("limit", [self.config.default_page_size])[0])
        return max(1, min(value, self.config.max_page_size))

    @staticmethod
    def _query_bool(query: dict[str, list[str]], key: str, *, default: bool = False) -> bool:
        value = query.get(key)
        if not value:
            return default
        return value[0].strip().lower() in {"1", "true", "yes", "on"}

    @staticmethod
    def _pagination(count: int, query: dict[str, list[str]]) -> dict:
        limit = int(query.get("limit", [count or 50])[0])
        return {"next_cursor": None, "limit": limit}

    @staticmethod
    def _validate_bind_policy(config: ServiceConfig) -> None:
        local_hosts = {"127.0.0.1", "localhost", "::1"}
        if not config.allow_remote and config.host not in local_hosts:
            raise forbidden("Remote binding requires --allow-remote.")
        if config.allow_remote and not config.auth_required:
            raise forbidden("Remote binding requires authentication.")

    @staticmethod
    def _assert_current_schema(db_path: str) -> None:
        path = Path(db_path)
        if not path.exists():
            raise stale_schema("Database does not exist; run migrate or use --auto-migrate.")
        connection = sqlite3.connect(db_path)
        try:
            row = connection.execute("SELECT version FROM schema_version WHERE id = 1").fetchone()
        except sqlite3.Error as exc:
            connection.close()
            raise stale_schema("Database has no schema_version; run migrate or use --auto-migrate.") from exc
        connection.close()
        if not row or row[0] != SCHEMA_VERSION:
            raise stale_schema(f"Schema is {row[0] if row else 'missing'}, expected {SCHEMA_VERSION}.")


class AletheiaDaemon:
    def __init__(self, config: ServiceConfig):
        self.config = config
        self.service = AletheiaService.open(config)
        self.instance_id = new_id("inst")
        self.httpd: ThreadingHTTPServer | None = None
        self._worker_stop = threading.Event()
        self._worker_thread: threading.Thread | None = None

    def start(self) -> tuple[str, int]:
        service = self.service

        class Handler(AletheiaRequestHandler):
            pass

        Handler.service = service
        self.httpd = ThreadingHTTPServer((self.config.host, self.config.port), Handler)
        host, port = self.httpd.server_address
        self.service.log_service_instance(instance_id=self.instance_id, status="running", port=port)
        if self.config.worker_enabled:
            self._start_worker_loop()
        return host, port

    def serve_forever(self) -> None:
        if self.httpd is None:
            self.start()
        assert self.httpd is not None
        try:
            self.httpd.serve_forever()
        finally:
            self.service.close()

    def shutdown(self) -> None:
        self._worker_stop.set()
        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=2)
        if self.httpd is not None:
            self.httpd.shutdown()
            self.httpd.server_close()
        self.service.close()

    def _start_worker_loop(self) -> None:
        if self._worker_thread and self._worker_thread.is_alive():
            return

        def run() -> None:
            while not self._worker_stop.is_set():
                try:
                    with self.service.lock:
                        self.service.memory.run_jobs(max_jobs=self.config.max_jobs_per_tick)
                except Exception as exc:  # noqa: BLE001 - daemon worker keeps serving.
                    self.service.log_service_instance(
                        instance_id=self.instance_id,
                        status="worker_error",
                        port=self.config.port,
                        metadata={"error": str(exc)},
                    )
                self._worker_stop.wait(1.0)

        self._worker_thread = threading.Thread(target=run, name="aletheia-worker", daemon=True)
        self._worker_thread.start()


class AletheiaRequestHandler(BaseHTTPRequestHandler):
    service: AletheiaService

    def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API.
        self._handle()

    def do_POST(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API.
        self._handle()

    def do_DELETE(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API.
        self._handle()

    def log_message(self, format: str, *args) -> None:  # noqa: A003 - stdlib API.
        return

    def _handle(self) -> None:
        request_id = self.headers.get("X-Request-ID") or new_id("req")
        raw_length = self.headers.get("Content-Length", "0")
        try:
            length = int(raw_length)
            if length < 0:
                raise ValueError
        except ValueError:
            self._send_payload(
                400,
                self.service._error(
                    validation_error("Content-Length must be a non-negative integer."),
                    request_id,
                ),
            )
            return
        if length > self.service.config.max_request_bytes:
            self._send_payload(
                413,
                self.service._error(
                    ServiceError("payload_too_large", "Request body is too large.", status_code=413),
                    request_id,
                ),
            )
            return
        body = self.rfile.read(length) if length else b""
        status, payload = self.service.handle_http(
            method=self.command,
            path=self.path,
            headers={key: value for key, value in self.headers.items()},
            body=body,
        )
        self._send_payload(status, payload)

    def _send_payload(self, status: int, payload: dict) -> None:
        response_headers = payload.pop("_headers", {}) if isinstance(payload, dict) else {}
        if isinstance(payload, dict) and "_raw_body" in payload:
            raw = str(payload.get("_raw_body", "")).encode("utf-8")
            content_type = str(payload.get("_content_type", "text/plain; charset=utf-8"))
        else:
            raw = json.dumps(payload, indent=2).encode("utf-8")
            content_type = "application/json"
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(raw)))
        for key, value in response_headers.items():
            self.send_header(str(key), str(value))
        self.end_headers()
        self.wfile.write(raw)


def min_privacy(ceiling: str, default: str) -> str:
    order = {"public": 0, "personal": 1, "private": 2, "sensitive": 2, "secret": 3}
    return ceiling if order.get(ceiling, 1) < order.get(default, 1) else default


def openapi_schema() -> dict:
    routes = [
        ("GET", "/v1/health", None),
        ("GET", "/v1/ready", None),
        ("GET", "/v1/version", None),
        ("GET", "/v1/openapi.json", None),
        ("POST", "/v1/context", "memory:context"),
        ("POST", "/v1/context-pack", "memory:context"),
        ("POST", "/v1/retrieve", "memory:read"),
        ("POST", "/v1/search", "memory:read"),
        ("POST", "/v1/remember", "memory:write_candidate or memory:write_active"),
        ("POST", "/v1/feedback", "memory:feedback"),
        ("POST", "/v1/outcomes", "memory:feedback"),
        ("POST", "/v1/retrieval-judgments", "memory:feedback"),
        ("POST", "/v1/ingest", "memory:ingest"),
        ("POST", "/v1/extract", "memory:extract"),
        ("POST", "/v1/llm/expand-query", "memory:read"),
        ("POST", "/v1/llm/summarize-evidence", "memory:review"),
        ("POST", "/v1/llm/suggest-entities", "memory:review"),
        ("POST", "/v1/llm/suggest-categories", "memory:review"),
        ("POST", "/v1/llm/suggest-scope", "memory:review"),
        ("POST", "/v1/llm/suggest-duplicate-merge", "memory:review"),
        ("POST", "/v1/llm/explain-conflict", "memory:review"),
        ("GET", "/v1/llm/runs", "memory:review"),
        ("GET", "/v1/candidates", "memory:review"),
        ("GET", "/v1/candidates/{candidate_id}", "memory:review"),
        ("POST", "/v1/candidates/{candidate_id}/promote", "memory:review"),
        ("POST", "/v1/candidates/{candidate_id}/reject", "memory:review"),
        ("GET", "/v1/claims/{claim_id}", "memory:read"),
        ("GET", "/v1/claims/{claim_id}/explain", "memory:read"),
        ("POST", "/v1/claims/{claim_id}/promote", "memory:review"),
        ("POST", "/v1/claims/{claim_id}/demote", "memory:review"),
        ("POST", "/v1/claims/{claim_id}/scope", "memory:review"),
        ("POST", "/v1/claims/{old_claim_id}/supersede/{new_claim_id}", "memory:review"),
        ("GET", "/v1/audit/{target_type}/{target_id}", "memory:audit"),
        ("POST", "/v1/sessions/start", "memory:write_candidate"),
        ("POST", "/v1/sessions/{session_id}/end", "memory:write_candidate"),
        ("GET", "/v1/sessions", "memory:read"),
        ("GET", "/v1/sessions/{session_id}", "memory:read"),
        ("POST", "/v1/projects", "memory:write_candidate"),
        ("GET", "/v1/projects", "memory:read"),
        ("GET", "/v1/projects/{project_id}", "memory:read"),
        ("GET", "/v1/conflicts", "memory:read"),
        ("POST", "/v1/conflicts/detect", "memory:review"),
        ("POST", "/v1/conflicts/{conflict_id}/resolve", "memory:review"),
        ("GET", "/v1/confidence/{claim_id}", "memory:read"),
        ("POST", "/v1/confidence/recompute", "memory:admin"),
        ("POST", "/v1/curate/preview", "memory:review"),
        ("POST", "/v1/curate/apply", "memory:review"),
        ("POST", "/v1/infer/run", "memory:review"),
        ("GET", "/v1/inferences", "memory:read"),
        ("POST", "/v1/inferences/{inference_id}/promote", "memory:review"),
        ("POST", "/v1/inferences/{inference_id}/reject", "memory:review"),
        ("POST", "/v1/reflections", "memory:review"),
        ("GET", "/v1/reflections", "memory:read"),
        ("GET", "/v1/reflections/{reflection_id}/expand", "memory:read"),
        ("GET", "/v1/derivation/{target_type}/{target_id}", "memory:read"),
        ("POST", "/v1/eval/sets", "memory:evaluate"),
        ("POST", "/v1/eval/sets/{eval_set_id}/cases", "memory:evaluate"),
        ("POST", "/v1/eval/sets/{eval_set_id}/run", "memory:evaluate"),
        ("POST", "/v1/optimize/retrieval", "memory:policy"),
        ("POST", "/v1/learning/run", "memory:learn"),
        ("GET", "/v1/policies/proposals", "memory:policy"),
        ("POST", "/v1/policies/proposals/{proposal_id}/review", "memory:policy"),
        ("POST", "/v1/policies/proposals/{proposal_id}/apply", "memory:policy"),
        ("POST", "/v1/jobs", "memory:jobs"),
        ("POST", "/v1/jobs/run", "memory:jobs"),
        ("GET", "/v1/jobs", "memory:jobs"),
        ("GET", "/v1/health-report", "memory:admin"),
        ("GET", "/console", None),
        ("GET", "/console/assets/app.css", None),
        ("POST", "/v1/console/login", None),
        ("POST", "/v1/console/logout", "console session"),
        ("GET", "/v1/console/session", "console session"),
        ("POST", "/v1/console/actions/candidates/{candidate_id}/promote", "memory:review"),
        ("POST", "/v1/console/actions/candidates/{candidate_id}/reject", "memory:review"),
        ("POST", "/v1/console/actions/conflicts/{conflict_id}/resolve", "memory:review"),
        ("GET", "/v1/dashboard/overview", "memory:read"),
        ("GET", "/v1/dashboard/preferences", "memory:read"),
        ("POST", "/v1/dashboard/preferences", "memory:admin"),
        ("GET", "/v1/dashboard/saved-views", "memory:read"),
        ("POST", "/v1/dashboard/saved-views", "memory:admin"),
        ("DELETE", "/v1/dashboard/saved-views/{view_id}", "memory:admin"),
        ("GET", "/v1/reviews", "memory:read"),
        ("POST", "/v1/reviews/generate", "memory:review"),
        ("GET", "/v1/reviews/{review_task_id}", "memory:read"),
        ("POST", "/v1/reviews/{review_task_id}/resolve", "review task capability"),
        ("POST", "/v1/reviews/{review_task_id}/dismiss", "review task capability"),
        ("POST", "/v1/reviews/{review_task_id}/defer", "review task capability"),
        ("POST", "/v1/traces/retrieval", "memory:read"),
        ("POST", "/v1/traces/context-pack", "memory:read"),
        ("GET", "/v1/traces", "memory:read"),
        ("GET", "/v1/traces/{trace_id}", "memory:read"),
        ("GET", "/v1/traces/{trace_id}/items", "memory:read"),
        ("POST", "/v1/metrics/snapshot", "memory:admin"),
        ("GET", "/v1/metrics/snapshots", "memory:read"),
        ("GET", "/v1/metrics/latest", "memory:read"),
        ("GET", "/v1/notifications", "memory:read"),
        ("POST", "/v1/notifications/{notification_id}/dismiss", "memory:read"),
        ("POST", "/v1/notifications/{notification_id}/snooze", "memory:read"),
        ("POST", "/v1/reports/export", "memory:read"),
        ("GET", "/v1/reports", "memory:read"),
        ("GET", "/v1/reports/{report_id}", "memory:read"),
        ("POST", "/v1/backups/create", "memory:admin"),
        ("POST", "/v1/backups/verify", "memory:admin"),
        ("GET", "/v1/backups", "memory:admin"),
        ("GET", "/v1/backups/{backup_id}", "memory:admin"),
        ("POST", "/v1/restore/dry-run", "memory:admin"),
        ("POST", "/v1/restore/apply", "memory:admin"),
        ("GET", "/v1/encryption/status", "memory:admin"),
        ("POST", "/v1/encryption/enable", "memory:admin"),
        ("GET", "/v1/keys", "memory:admin"),
        ("POST", "/v1/keys", "memory:admin"),
        ("POST", "/v1/keys/{key_id}/rotate", "memory:admin"),
        ("POST", "/v1/redactions/preview", "memory:admin"),
        ("POST", "/v1/redactions/apply", "memory:admin"),
        ("POST", "/v1/forget/preview", "memory:admin"),
        ("POST", "/v1/forget/apply", "memory:admin"),
        ("GET", "/v1/tombstones", "memory:admin"),
        ("GET", "/v1/retention/policies", "memory:admin"),
        ("POST", "/v1/retention/policies", "memory:admin"),
        ("POST", "/v1/retention/run", "memory:admin"),
        ("POST", "/v1/integrity/check", "memory:admin"),
        ("GET", "/v1/integrity/runs", "memory:admin"),
        ("GET", "/v1/integrity/findings", "memory:admin"),
        ("POST", "/v1/integrity/findings/{finding_id}/repair", "memory:admin"),
        ("POST", "/v1/migrations/plan", "memory:admin"),
        ("POST", "/v1/migrations/apply", "memory:admin"),
        ("POST", "/v1/migrations/verify", "memory:admin"),
        ("POST", "/v1/compact/preview", "memory:admin"),
        ("POST", "/v1/compact/run", "memory:admin"),
        ("POST", "/v1/exports", "memory:admin"),
        ("POST", "/v1/imports/dry-run", "memory:admin"),
        ("POST", "/v1/imports/apply", "memory:admin"),
        ("POST", "/v1/support/bundle", "memory:admin"),
        ("POST", "/v1/benchmarks/run", "memory:admin"),
        ("GET", "/v1/benchmarks", "memory:admin"),
        ("POST", "/v1/release/manifest", "memory:admin"),
        ("POST", "/v1/readiness/check", "memory:admin"),
        ("GET", "/v1/contracts", "memory:read"),
        ("POST", "/v1/contracts", "memory:admin"),
        ("GET", "/v1/contracts/{contract_id}", "memory:read"),
        ("GET", "/v1/deprecations", "memory:read"),
        ("GET", "/v1/deprecations/check", "memory:read"),
        ("GET", "/v1/compatibility/report", "memory:read"),
        ("GET", "/v1/compatibility/matrix", "memory:read"),
        ("GET", "/v1/compatibility/status", "memory:read"),
        ("GET", "/v1/compatibility/sdks", "memory:read"),
        ("GET", "/v1/plugins", "memory:read"),
        ("POST", "/v1/plugins/discover", "memory:admin"),
        ("POST", "/v1/plugins/install", "memory:admin"),
        ("GET", "/v1/plugins/{plugin_id}", "memory:read"),
        ("POST", "/v1/plugins/{plugin_id}/enable", "memory:admin"),
        ("POST", "/v1/plugins/{plugin_id}/disable", "memory:admin"),
        ("POST", "/v1/plugins/{plugin_id}/run", "memory:admin"),
        ("GET", "/v1/plugins/{plugin_id}/logs", "memory:read"),
        ("GET", "/v1/conformance/suites", "memory:read"),
        ("POST", "/v1/conformance/run", "memory:admin"),
        ("GET", "/v1/conformance/runs", "memory:read"),
        ("GET", "/v1/conformance/runs/{run_id}", "memory:read"),
        ("GET", "/v1/conformance/runs/{run_id}/results", "memory:read"),
        ("POST", "/v1/adapters/scaffold", "memory:admin"),
        ("POST", "/v1/adapters/certify", "memory:admin"),
        ("GET", "/v1/adapters/certifications", "memory:read"),
        ("GET", "/v1/docs/status", "memory:read"),
        ("POST", "/v1/docs/build", "memory:admin"),
        ("POST", "/v1/docs/test-examples", "memory:admin"),
        ("GET", "/v1/examples", "memory:read"),
        ("POST", "/v1/examples/create", "memory:admin"),
        ("POST", "/v1/examples/test", "memory:admin"),
        ("POST", "/v1/doctor/run", "memory:admin"),
        ("GET", "/v1/doctor/runs", "memory:read"),
        ("GET", "/v1/doctor/runs/{run_id}", "memory:read"),
        ("POST", "/v1/v1-gate/run", "memory:admin"),
        ("GET", "/v1/v1-gate/runs", "memory:read"),
        ("GET", "/v1/v1-gate/runs/{run_id}", "memory:read"),
        ("GET", "/v1/federation/identity", "memory:federation"),
        ("POST", "/v1/federation/identity", "memory:federation"),
        ("POST", "/v1/federation/identity/rotate", "memory:federation"),
        ("GET", "/v1/federation/status", "memory:federation"),
        ("POST", "/v1/federation/conformance", "memory:federation"),
        ("GET", "/v1/peers", "memory:peers"),
        ("POST", "/v1/peers", "memory:peers"),
        ("GET", "/v1/peers/trust-domains", "memory:peers"),
        ("GET", "/v1/peers/{peer_id}", "memory:peers"),
        ("POST", "/v1/peers/{peer_id}/trust", "memory:peers"),
        ("POST", "/v1/peers/{peer_id}/revoke", "memory:revoke_peer"),
        ("GET", "/v1/shares", "memory:share"),
        ("POST", "/v1/shares", "memory:share"),
        ("GET", "/v1/shares/{share_id}", "memory:share"),
        ("GET", "/v1/shares/{share_id}/recipients", "memory:share"),
        ("POST", "/v1/shares/{share_id}/export", "memory:share and memory:sync"),
        ("POST", "/v1/shares/import", "memory:share and memory:sync"),
        ("POST", "/v1/shares/{share_id}/revoke", "memory:share"),
        ("GET", "/v1/sync/collections", "memory:sync"),
        ("POST", "/v1/sync/run", "memory:sync"),
        ("GET", "/v1/sync/runs", "memory:sync"),
        ("GET", "/v1/sync/conflicts", "memory:sync"),
        ("POST", "/v1/sync/conflicts/{conflict_id}/resolve", "memory:sync"),
        ("GET", "/v1/sync/cursors", "memory:sync"),
        ("GET", "/v1/sync/remote-sources", "memory:sync"),
        ("GET", "/v1/sync/trust-policies", "memory:sync"),
        ("GET", "/v1/workspaces", "memory:workspace"),
        ("POST", "/v1/workspaces", "memory:workspace"),
        ("GET", "/v1/workspaces/agent-groups", "memory:workspace"),
        ("POST", "/v1/workspaces/agent-groups", "memory:workspace"),
        ("GET", "/v1/workspaces/{workspace_id}", "memory:workspace"),
        ("GET", "/v1/workspaces/{workspace_id}/members", "memory:workspace"),
        ("POST", "/v1/workspaces/{workspace_id}/members", "memory:workspace"),
        ("DELETE", "/v1/workspaces/{workspace_id}/members/{member_id}", "memory:workspace"),
        ("GET", "/v1/grants", "memory:share"),
        ("GET", "/v1/grants/{share_id}", "memory:share"),
        ("GET", "/v1/grants/consent", "memory:share"),
        ("GET", "/v1/revocations", "memory:sync"),
        ("POST", "/v1/revocations/propagate", "memory:sync"),
    ]
    paths: dict[str, dict] = {}
    for method, path, capability in routes:
        operation = {
            "summary": f"{method} {path}",
            "x-required-capability": capability,
            "responses": {
                "200": {
                    "description": "Success envelope",
                    "content": {
                        "application/json": {"schema": {"$ref": "#/components/schemas/ResponseEnvelope"}}
                    },
                },
                "400": {
                    "description": "Error envelope",
                    "content": {
                        "application/json": {"schema": {"$ref": "#/components/schemas/ErrorEnvelope"}}
                    },
                },
                "401": {"description": "Unauthorized"},
                "403": {"description": "Forbidden"},
            },
        }
        if method in STATE_CHANGING_METHODS:
            operation["parameters"] = [
                {
                    "name": "Idempotency-Key",
                    "in": "header",
                    "required": False,
                    "schema": {"type": "string"},
                    "description": "Supported for state-changing calls; same key and payload replay the stored response.",
                }
            ]
            operation["requestBody"] = {
                "required": True,
                "content": {"application/json": {"schema": {"type": "object", "additionalProperties": True}}},
            }
        paths.setdefault(path, {})[method.lower()] = operation
    return {
        "openapi": "3.1.0",
        "info": {"title": "Aletheia Local Memory API", "version": SCHEMA_VERSION},
        "security": [{"bearerAuth": []}],
        "components": {
            "securitySchemes": {"bearerAuth": {"type": "http", "scheme": "bearer"}},
            "schemas": {
                "ResponseEnvelope": {
                    "type": "object",
                    "required": ["data", "request_id", "warnings"],
                    "properties": {
                        "data": {},
                        "request_id": {"type": "string"},
                        "warnings": {"type": "array", "items": {"type": "string"}},
                        "pagination": {"type": ["object", "null"]},
                    },
                },
                "ErrorEnvelope": {
                    "type": "object",
                    "required": ["error", "request_id"],
                    "properties": {
                        "error": {
                            "type": "object",
                            "required": ["code", "message", "details"],
                            "properties": {
                                "code": {
                                    "type": "string",
                                    "enum": [
                                        "unauthorized",
                                        "forbidden",
                                        "not_found",
                                        "validation_error",
                                        "conflict",
                                        "integrity_gate_failed",
                                        "stale_schema",
                                        "rate_limited",
                                        "idempotency_conflict",
                                        "payload_too_large",
                                        "unsupported_operation",
                                        "internal_error",
                                    ],
                                },
                                "message": {"type": "string"},
                                "details": {"type": "object"},
                            },
                        },
                        "request_id": {"type": "string"},
                    },
                },
            },
        },
        "paths": paths,
    }
