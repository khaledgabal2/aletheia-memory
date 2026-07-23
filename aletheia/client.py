"""Python client SDK for the local Aletheia service."""

from __future__ import annotations

import asyncio
import json
import urllib.error
import urllib.request
from typing import Any
from urllib.parse import urlencode


class AletheiaClientError(Exception):
    def __init__(self, message: str, *, code: str | None = None, status_code: int | None = None, details: dict | None = None):
        super().__init__(message)
        self.code = code
        self.status_code = status_code
        self.details = details or {}


class AletheiaUnauthorizedError(AletheiaClientError):
    pass


class AletheiaForbiddenError(AletheiaClientError):
    pass


class AletheiaValidationError(AletheiaClientError):
    pass


class AletheiaIntegrityGateError(AletheiaClientError):
    pass


class AletheiaRateLimitError(AletheiaClientError):
    pass


class AletheiaServerError(AletheiaClientError):
    pass


ERROR_TYPES = {
    "unauthorized": AletheiaUnauthorizedError,
    "forbidden": AletheiaForbiddenError,
    "validation_error": AletheiaValidationError,
    "integrity_gate_failed": AletheiaIntegrityGateError,
    "rate_limited": AletheiaRateLimitError,
    "idempotency_conflict": AletheiaValidationError,
}


class AletheiaClient:
    def __init__(self, base_url: str, token: str | None = None, *, timeout: float = 10.0):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.timeout = timeout
        self.last_request_id: str | None = None
        self.last_warnings: list[str] = []
        self.last_pagination: dict | None = None
        self.last_envelope: dict | None = None

    def health(self, *, request_id: str | None = None) -> dict:
        return self._request("GET", "/v1/health", request_id=request_id)

    def version(self, *, request_id: str | None = None) -> dict:
        return self._request("GET", "/v1/version", request_id=request_id)

    def check_compatibility(self) -> dict:
        report = self.compatibility_report()
        version = self.version()
        api_version = version.get("api_version")
        compatible = api_version == "v1" and report.get("schema_version") == report.get("aletheia_version")
        return {
            "compatible": compatible,
            "client_api_version": "v1",
            "server_api_version": api_version,
            "server_version": version.get("service_version"),
            "warnings": report.get("warnings", []),
            "report": report,
        }

    def context_pack(self, **payload) -> dict:
        return self._request("POST", "/v1/context-pack", payload)

    def retrieve(self, **payload) -> list[dict]:
        return self._request("POST", "/v1/retrieve", payload)

    def remember(self, *, idempotency_key: str | None = None, **payload) -> dict:
        return self._request("POST", "/v1/remember", payload, idempotency_key=idempotency_key)

    def remember_candidate(self, *, idempotency_key: str | None = None, **payload) -> dict:
        return self.remember(idempotency_key=idempotency_key, write_mode="candidate", **payload)

    def remember_active(self, *, idempotency_key: str | None = None, **payload) -> dict:
        return self.remember(idempotency_key=idempotency_key, write_mode="active", **payload)

    def feedback(self, **payload) -> dict:
        return self._request("POST", "/v1/feedback", payload)

    def record_outcome(self, **payload) -> dict:
        return self._request("POST", "/v1/outcomes", payload)

    def ingest(self, **payload) -> dict:
        return self._request("POST", "/v1/ingest", payload)

    def extract(self, **payload) -> dict:
        return self._request("POST", "/v1/extract", payload)

    def llm_expand_query(self, **payload) -> dict:
        return self._request("POST", "/v1/llm/expand-query", payload)

    def llm_summarize_evidence(self, **payload) -> dict:
        return self._request("POST", "/v1/llm/summarize-evidence", payload)

    def llm_suggest_entities(self, **payload) -> dict:
        return self._request("POST", "/v1/llm/suggest-entities", payload)

    def llm_suggest_categories(self, **payload) -> dict:
        return self._request("POST", "/v1/llm/suggest-categories", payload)

    def llm_suggest_scope(self, **payload) -> dict:
        return self._request("POST", "/v1/llm/suggest-scope", payload)

    def llm_suggest_duplicate_merge(self, **payload) -> dict:
        return self._request("POST", "/v1/llm/suggest-duplicate-merge", payload)

    def llm_explain_conflict(self, **payload) -> dict:
        return self._request("POST", "/v1/llm/explain-conflict", payload)

    def llm_runs(self, *, namespace: str | None = None, task: str | None = None, limit: int = 50) -> dict:
        query: dict[str, Any] = {"limit": limit}
        if namespace:
            query["namespace"] = namespace
        if task:
            query["task"] = task
        return self._request("GET", "/v1/llm/runs?" + urlencode(query))

    def list_candidates(self, *, namespace: str, status: str | None = None, memory_type: str | None = None, limit: int = 50) -> list[dict]:
        query = {"namespace": namespace, "limit": limit}
        if status:
            query["status"] = status
        if memory_type:
            query["memory_type"] = memory_type
        return self._request("GET", "/v1/candidates?" + urlencode(query))

    def promote_candidate(self, candidate_id: str, *, reason: str) -> dict:
        return self._request("POST", f"/v1/candidates/{candidate_id}/promote", {"reason": reason})

    def audit(self, target_type: str, target_id: str, *, request_id: str | None = None) -> dict:
        return self._request("GET", f"/v1/audit/{target_type}/{target_id}", request_id=request_id)

    def explain_claim(self, claim_id: str) -> dict:
        return self._request("GET", f"/v1/claims/{claim_id}/explain")

    def start_session(self, **payload) -> dict:
        return self._request("POST", "/v1/sessions/start", payload)

    def end_session(self, session_id: str, **payload) -> dict:
        return self._request("POST", f"/v1/sessions/{session_id}/end", payload)

    def create_project(self, **payload) -> dict:
        return self._request("POST", "/v1/projects", payload)

    def list_jobs(self, namespace: str | None = None) -> list[dict]:
        suffix = f"?namespace={namespace}" if namespace else ""
        return self._request("GET", f"/v1/jobs{suffix}")

    def run_jobs(self, **payload) -> list[dict]:
        return self._request("POST", "/v1/jobs/run", payload)

    def health_report(self, *, namespace: str) -> dict:
        return self._request("GET", "/v1/health-report?" + urlencode({"namespace": namespace}))

    def backup_status(self) -> list[dict]:
        return self._request("GET", "/v1/backups")

    def compatibility_report(self) -> dict:
        return self._request("GET", "/v1/compatibility/report")

    def contracts(self, *, contract_type: str | None = None, stability: str | None = None) -> list[dict]:
        query = {}
        if contract_type:
            query["contract_type"] = contract_type
        if stability:
            query["stability"] = stability
        suffix = "?" + urlencode(query) if query else ""
        return self._request("GET", "/v1/contracts" + suffix)

    def deprecations(self) -> list[dict]:
        return self._request("GET", "/v1/deprecations")

    def list_plugins(self) -> list[dict]:
        return self._request("GET", "/v1/plugins")

    def conformance_suites(self) -> list[dict]:
        return self._request("GET", "/v1/conformance/suites")

    def run_conformance(self, *, suite: str, target: str | None = None, target_type: str | None = None) -> dict:
        payload = {"suite": suite}
        if target:
            payload["target"] = target
        if target_type:
            payload["target_type"] = target_type
        return self._request("POST", "/v1/conformance/run", payload)

    def doctor(self, *, service_url: str | None = None) -> dict:
        return self._request("POST", "/v1/doctor/run", {"service_url": service_url})

    def docs_status(self) -> dict:
        return self._request("GET", "/v1/docs/status")

    def v1_gate(self) -> dict:
        return self._request("POST", "/v1/v1-gate/run", {})

    def federation_status(self) -> dict:
        return self._request("GET", "/v1/federation/status")

    def federation_identity(self) -> dict:
        return self._request("GET", "/v1/federation/identity")

    def create_federation_identity(self, *, display_name: str, key_algorithm: str = "default", protected: bool = True) -> dict:
        return self._request("POST", "/v1/federation/identity", {
            "display_name": display_name,
            "key_algorithm": key_algorithm,
            "protected": protected,
        })

    def rotate_federation_key(self, *, reason: str, actor: str = "sdk") -> dict:
        return self._request("POST", "/v1/federation/identity/rotate", {"reason": reason, "actor": actor})

    def list_peers(self, *, include_revoked: bool = False) -> list[dict]:
        suffix = "?" + urlencode({"include_revoked": str(include_revoked).lower()})
        return self._request("GET", "/v1/peers" + suffix)

    def add_peer(self, **payload) -> dict:
        return self._request("POST", "/v1/peers", payload)

    def trust_peer(self, peer_id: str, **payload) -> dict:
        return self._request("POST", f"/v1/peers/{peer_id}/trust", payload)

    def revoke_peer(self, peer_id: str, **payload) -> dict:
        return self._request("POST", f"/v1/peers/{peer_id}/revoke", payload)

    def trust_domains(self) -> list[dict]:
        return self._request("GET", "/v1/peers/trust-domains")

    def list_shares(self, *, namespace: str | None = None, status: str | None = None) -> list[dict]:
        query = {}
        if namespace:
            query["namespace"] = namespace
        if status:
            query["status"] = status
        suffix = "?" + urlencode(query) if query else ""
        return self._request("GET", "/v1/shares" + suffix)

    def create_share(self, **payload) -> dict:
        return self._request("POST", "/v1/shares", payload)

    def get_share(self, share_id: str) -> dict:
        return self._request("GET", f"/v1/shares/{share_id}")

    def share_recipients(self, share_id: str) -> list[dict]:
        return self._request("GET", f"/v1/shares/{share_id}/recipients")

    def export_share(self, share_id: str, **payload) -> dict:
        return self._request("POST", f"/v1/shares/{share_id}/export", payload)

    def import_share(self, **payload) -> dict:
        return self._request("POST", "/v1/shares/import", payload)

    def revoke_share(self, share_id: str, **payload) -> dict:
        return self._request("POST", f"/v1/shares/{share_id}/revoke", payload)

    def sync_run(self, **payload) -> dict:
        return self._request("POST", "/v1/sync/run", payload)

    def sync_collections(self, *, status: str | None = None) -> list[dict]:
        suffix = "?" + urlencode({"status": status}) if status else ""
        return self._request("GET", "/v1/sync/collections" + suffix)

    def sync_runs(self, *, limit: int = 50) -> list[dict]:
        return self._request("GET", "/v1/sync/runs?" + urlencode({"limit": limit}))

    def sync_conflicts(self, *, namespace: str | None = None, status: str | None = None) -> list[dict]:
        query = {}
        if namespace:
            query["namespace"] = namespace
        if status:
            query["status"] = status
        suffix = "?" + urlencode(query) if query else ""
        return self._request("GET", "/v1/sync/conflicts" + suffix)

    def resolve_sync_conflict(self, conflict_id: str, **payload) -> dict:
        return self._request("POST", f"/v1/sync/conflicts/{conflict_id}/resolve", payload)

    def remote_sources(self, *, local_object_id: str | None = None) -> list[dict]:
        suffix = "?" + urlencode({"local_object_id": local_object_id}) if local_object_id else ""
        return self._request("GET", "/v1/sync/remote-sources" + suffix)

    def import_trust_policies(self) -> list[dict]:
        return self._request("GET", "/v1/sync/trust-policies")

    def list_workspaces(self, *, namespace: str | None = None) -> list[dict]:
        suffix = "?" + urlencode({"namespace": namespace}) if namespace else ""
        return self._request("GET", "/v1/workspaces" + suffix)

    def create_workspace(self, **payload) -> dict:
        return self._request("POST", "/v1/workspaces", payload)

    def workspace_members(self, workspace_id: str) -> list[dict]:
        return self._request("GET", f"/v1/workspaces/{workspace_id}/members")

    def add_workspace_member(self, workspace_id: str, **payload) -> dict:
        return self._request("POST", f"/v1/workspaces/{workspace_id}/members", payload)

    def remove_workspace_member(self, workspace_id: str, member_id: str) -> dict:
        return self._request("DELETE", f"/v1/workspaces/{workspace_id}/members/{member_id}", {})

    def list_revocations(self) -> list[dict]:
        return self._request("GET", "/v1/revocations")

    def propagate_revocations(self, *, peer_id: str | None = None) -> dict:
        return self._request("POST", "/v1/revocations/propagate", {"peer_id": peer_id})

    def _request(
        self,
        method: str,
        path: str,
        payload: dict | None = None,
        *,
        request_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> Any:
        raw = json.dumps(payload or {}).encode("utf-8") if payload is not None else None
        headers = {"Accept": "application/json"}
        if raw is not None:
            headers["Content-Type"] = "application/json"
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        if request_id:
            headers["X-Request-ID"] = request_id
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key
        request = urllib.request.Request(
            self.base_url + path,
            data=raw,
            headers=headers,
            method=method,
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:  # noqa: S310 - local SDK.
                envelope = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8")
            try:
                envelope = json.loads(body)
            except json.JSONDecodeError:
                raise AletheiaServerError(body, status_code=exc.code) from exc
            self._raise_error(envelope, exc.code)
        if "error" in envelope:
            self._raise_error(envelope, None)
        self.last_envelope = envelope
        self.last_request_id = envelope.get("request_id")
        self.last_warnings = envelope.get("warnings") or []
        self.last_pagination = envelope.get("pagination")
        return envelope.get("data")

    def _raise_error(self, envelope: dict, status_code: int | None) -> None:
        error = envelope.get("error") or {}
        code = error.get("code")
        cls = ERROR_TYPES.get(code, AletheiaServerError if status_code and status_code >= 500 else AletheiaClientError)
        raise cls(
            error.get("message", "Aletheia service error."),
            code=code,
            status_code=status_code,
            details=error.get("details") or {},
        )


class AsyncAletheiaClient:
    def __init__(self, base_url: str, token: str | None = None, *, timeout: float = 10.0):
        self._sync = AletheiaClient(base_url, token, timeout=timeout)

    @property
    def last_request_id(self) -> str | None:
        return self._sync.last_request_id

    @property
    def last_warnings(self) -> list[str]:
        return self._sync.last_warnings

    @property
    def last_pagination(self) -> dict | None:
        return self._sync.last_pagination

    @property
    def last_envelope(self) -> dict | None:
        return self._sync.last_envelope

    async def health(self, **kwargs) -> dict:
        return await asyncio.to_thread(self._sync.health, **kwargs)

    async def version(self, **kwargs) -> dict:
        return await asyncio.to_thread(self._sync.version, **kwargs)

    async def check_compatibility(self) -> dict:
        return await asyncio.to_thread(self._sync.check_compatibility)

    async def context_pack(self, **payload) -> dict:
        return await asyncio.to_thread(self._sync.context_pack, **payload)

    async def retrieve(self, **payload) -> list[dict]:
        return await asyncio.to_thread(self._sync.retrieve, **payload)

    async def remember(self, **payload) -> dict:
        return await asyncio.to_thread(self._sync.remember, **payload)

    async def remember_candidate(self, **payload) -> dict:
        return await asyncio.to_thread(self._sync.remember_candidate, **payload)

    async def remember_active(self, **payload) -> dict:
        return await asyncio.to_thread(self._sync.remember_active, **payload)

    async def feedback(self, **payload) -> dict:
        return await asyncio.to_thread(self._sync.feedback, **payload)

    async def record_outcome(self, **payload) -> dict:
        return await asyncio.to_thread(self._sync.record_outcome, **payload)

    async def ingest(self, **payload) -> dict:
        return await asyncio.to_thread(self._sync.ingest, **payload)

    async def extract(self, **payload) -> dict:
        return await asyncio.to_thread(self._sync.extract, **payload)

    async def list_candidates(self, **payload) -> list[dict]:
        return await asyncio.to_thread(self._sync.list_candidates, **payload)

    async def promote_candidate(self, candidate_id: str, *, reason: str) -> dict:
        return await asyncio.to_thread(self._sync.promote_candidate, candidate_id, reason=reason)

    async def audit(self, target_type: str, target_id: str) -> dict:
        return await asyncio.to_thread(self._sync.audit, target_type, target_id)

    async def explain_claim(self, claim_id: str) -> dict:
        return await asyncio.to_thread(self._sync.explain_claim, claim_id)

    async def start_session(self, **payload) -> dict:
        return await asyncio.to_thread(self._sync.start_session, **payload)

    async def end_session(self, session_id: str, **payload) -> dict:
        return await asyncio.to_thread(self._sync.end_session, session_id, **payload)

    async def create_project(self, **payload) -> dict:
        return await asyncio.to_thread(self._sync.create_project, **payload)

    async def list_jobs(self, namespace: str | None = None) -> list[dict]:
        return await asyncio.to_thread(self._sync.list_jobs, namespace)

    async def run_jobs(self, **payload) -> list[dict]:
        return await asyncio.to_thread(self._sync.run_jobs, **payload)

    async def health_report(self, **payload) -> dict:
        return await asyncio.to_thread(self._sync.health_report, **payload)

    async def backup_status(self) -> list[dict]:
        return await asyncio.to_thread(self._sync.backup_status)

    async def compatibility_report(self) -> dict:
        return await asyncio.to_thread(self._sync.compatibility_report)

    async def contracts(self, **payload) -> list[dict]:
        return await asyncio.to_thread(self._sync.contracts, **payload)

    async def deprecations(self) -> list[dict]:
        return await asyncio.to_thread(self._sync.deprecations)

    async def list_plugins(self) -> list[dict]:
        return await asyncio.to_thread(self._sync.list_plugins)

    async def conformance_suites(self) -> list[dict]:
        return await asyncio.to_thread(self._sync.conformance_suites)

    async def run_conformance(self, **payload) -> dict:
        return await asyncio.to_thread(self._sync.run_conformance, **payload)

    async def doctor(self, **payload) -> dict:
        return await asyncio.to_thread(self._sync.doctor, **payload)

    async def docs_status(self) -> dict:
        return await asyncio.to_thread(self._sync.docs_status)

    async def v1_gate(self) -> dict:
        return await asyncio.to_thread(self._sync.v1_gate)

    async def federation_status(self) -> dict:
        return await asyncio.to_thread(self._sync.federation_status)

    async def federation_identity(self) -> dict:
        return await asyncio.to_thread(self._sync.federation_identity)

    async def create_federation_identity(self, **payload) -> dict:
        return await asyncio.to_thread(self._sync.create_federation_identity, **payload)

    async def rotate_federation_key(self, **payload) -> dict:
        return await asyncio.to_thread(self._sync.rotate_federation_key, **payload)

    async def list_peers(self, **payload) -> list[dict]:
        return await asyncio.to_thread(self._sync.list_peers, **payload)

    async def add_peer(self, **payload) -> dict:
        return await asyncio.to_thread(self._sync.add_peer, **payload)

    async def trust_peer(self, peer_id: str, **payload) -> dict:
        return await asyncio.to_thread(self._sync.trust_peer, peer_id, **payload)

    async def revoke_peer(self, peer_id: str, **payload) -> dict:
        return await asyncio.to_thread(self._sync.revoke_peer, peer_id, **payload)

    async def trust_domains(self) -> list[dict]:
        return await asyncio.to_thread(self._sync.trust_domains)

    async def list_shares(self, **payload) -> list[dict]:
        return await asyncio.to_thread(self._sync.list_shares, **payload)

    async def create_share(self, **payload) -> dict:
        return await asyncio.to_thread(self._sync.create_share, **payload)

    async def get_share(self, share_id: str) -> dict:
        return await asyncio.to_thread(self._sync.get_share, share_id)

    async def share_recipients(self, share_id: str) -> list[dict]:
        return await asyncio.to_thread(self._sync.share_recipients, share_id)

    async def export_share(self, share_id: str, **payload) -> dict:
        return await asyncio.to_thread(self._sync.export_share, share_id, **payload)

    async def import_share(self, **payload) -> dict:
        return await asyncio.to_thread(self._sync.import_share, **payload)

    async def revoke_share(self, share_id: str, **payload) -> dict:
        return await asyncio.to_thread(self._sync.revoke_share, share_id, **payload)

    async def sync_run(self, **payload) -> dict:
        return await asyncio.to_thread(self._sync.sync_run, **payload)

    async def sync_collections(self, **payload) -> list[dict]:
        return await asyncio.to_thread(self._sync.sync_collections, **payload)

    async def sync_runs(self, **payload) -> list[dict]:
        return await asyncio.to_thread(self._sync.sync_runs, **payload)

    async def sync_conflicts(self, **payload) -> list[dict]:
        return await asyncio.to_thread(self._sync.sync_conflicts, **payload)

    async def resolve_sync_conflict(self, conflict_id: str, **payload) -> dict:
        return await asyncio.to_thread(self._sync.resolve_sync_conflict, conflict_id, **payload)

    async def remote_sources(self, **payload) -> list[dict]:
        return await asyncio.to_thread(self._sync.remote_sources, **payload)

    async def import_trust_policies(self) -> list[dict]:
        return await asyncio.to_thread(self._sync.import_trust_policies)

    async def list_workspaces(self, **payload) -> list[dict]:
        return await asyncio.to_thread(self._sync.list_workspaces, **payload)

    async def create_workspace(self, **payload) -> dict:
        return await asyncio.to_thread(self._sync.create_workspace, **payload)

    async def workspace_members(self, workspace_id: str) -> list[dict]:
        return await asyncio.to_thread(self._sync.workspace_members, workspace_id)

    async def add_workspace_member(self, workspace_id: str, **payload) -> dict:
        return await asyncio.to_thread(self._sync.add_workspace_member, workspace_id, **payload)

    async def remove_workspace_member(self, workspace_id: str, member_id: str) -> dict:
        return await asyncio.to_thread(self._sync.remove_workspace_member, workspace_id, member_id)

    async def list_revocations(self) -> list[dict]:
        return await asyncio.to_thread(self._sync.list_revocations)

    async def propagate_revocations(self, **payload) -> dict:
        return await asyncio.to_thread(self._sync.propagate_revocations, **payload)
