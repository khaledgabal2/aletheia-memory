"""MCP-style tool registry for local Aletheia agents."""

from __future__ import annotations

import json
import sys
import time
from dataclasses import dataclass
from typing import Any

from aletheia.core.ids import new_id
from aletheia.models import ServiceConfig
from aletheia.service.auth import DEFAULT_LOCAL_AGENT_CAPABILITIES
from aletheia.service.errors import ServiceError
from aletheia.service.http import AletheiaService


MODE_CAPABILITIES = {
    "read_only": ["memory:read", "memory:context", "memory:audit"],
    "read_write_candidate": DEFAULT_LOCAL_AGENT_CAPABILITIES,
    "read_write_active": [*DEFAULT_LOCAL_AGENT_CAPABILITIES, "memory:write_active"],
    "admin": [
        "memory:read",
        "memory:context",
        "memory:write_candidate",
        "memory:write_active",
        "memory:feedback",
        "memory:audit",
        "memory:admin",
        "memory:jobs",
        "memory:evaluate",
        "memory:learn",
        "memory:policy",
    ],
}


@dataclass(frozen=True)
class McpTool:
    name: str
    description: str
    required_capability: str
    input_schema: dict


class McpToolRegistry:
    def __init__(
        self,
        service: AletheiaService,
        *,
        token: str | None = None,
        namespace: str | None = None,
        mode: str = "read_write_candidate",
    ):
        if mode not in MODE_CAPABILITIES:
            raise ValueError(f"Unknown MCP mode: {mode}")
        self.service = service
        self.token = token
        self.namespace = namespace or service.config.mcp_default_namespace
        self.mode = mode

    def list_tools(self) -> list[dict]:
        return [
            {
                "name": tool.name,
                "description": tool.description,
                "required_capability": tool.required_capability,
                "input_schema": tool.input_schema,
            }
            for tool in self.tools()
        ]

    def tools(self) -> list[McpTool]:
        return [
            McpTool(
                "memory_context_pack",
                "Builds a governed context pack. Requires memory:context and never bypasses evidence, conflict, policy, or privacy rules.",
                "memory:context",
                {"type": "object", "required": ["query"]},
            ),
            McpTool(
                "memory_search",
                "Searches retrievable memory through the Aletheia kernel. Requires memory:read.",
                "memory:read",
                {"type": "object", "required": ["query"]},
            ),
            McpTool(
                "memory_remember",
                "Stores a candidate memory by default. Active writes require memory:write_active. This tool does not promote memories to core.",
                "memory:write_candidate",
                {"type": "object", "required": ["memory_type", "subject", "predicate", "object"]},
            ),
            McpTool(
                "memory_feedback",
                "Records governed feedback without treating assistant repetition as truth evidence.",
                "memory:feedback",
                {"type": "object", "required": ["target_id", "signal"]},
            ),
            McpTool(
                "memory_audit",
                "Reads provenance and audit information for a target. Requires memory:audit.",
                "memory:audit",
                {"type": "object", "required": ["target_id"]},
            ),
            McpTool(
                "memory_explain_claim",
                "Explains a claim with evidence, confidence, scope, history, and audit trail.",
                "memory:read",
                {"type": "object", "required": ["claim_id"]},
            ),
            McpTool(
                "memory_health",
                "Generates a local memory health report. Requires admin mode or memory:admin.",
                "memory:admin",
                {"type": "object"},
            ),
            McpTool(
                "memory_ingest",
                "Ingests raw content as evidence, not trusted fact. Requires memory:ingest.",
                "memory:ingest",
                {"type": "object", "required": ["content"]},
            ),
            McpTool(
                "memory_extract_candidates",
                "Extracts candidate memories from evidence; candidates remain untrusted until reviewed.",
                "memory:extract",
                {"type": "object"},
            ),
            McpTool(
                "memory_llm_expand_query",
                "Runs governed LLM query expansion without creating memory.",
                "memory:read",
                {"type": "object", "required": ["query"]},
            ),
            McpTool(
                "memory_llm_suggest_entities",
                "Suggests entities from evidence as review-only LLM output.",
                "memory:review",
                {"type": "object", "required": ["evidence_ids"]},
            ),
            McpTool(
                "memory_llm_suggest_categories",
                "Suggests categories from evidence as review-only LLM output.",
                "memory:review",
                {"type": "object", "required": ["evidence_ids"]},
            ),
            McpTool(
                "memory_llm_suggest_scope",
                "Suggests candidate scope as review-only LLM output.",
                "memory:review",
                {"type": "object", "required": ["candidate_id"]},
            ),
            McpTool(
                "memory_llm_suggest_duplicate_merge",
                "Suggests possible duplicate merge targets without applying them.",
                "memory:review",
                {"type": "object", "required": ["candidate_id"]},
            ),
            McpTool(
                "memory_list_candidates",
                "Lists candidate memories for review.",
                "memory:review",
                {"type": "object"},
            ),
            McpTool(
                "memory_promote_candidate",
                "Promotes a reviewed candidate through Aletheia integrity gates. Requires memory:review.",
                "memory:review",
                {"type": "object", "required": ["candidate_id", "reason"]},
            ),
            McpTool(
                "memory_reject_candidate",
                "Rejects a candidate with audit trail. Requires memory:review.",
                "memory:review",
                {"type": "object", "required": ["candidate_id", "reason"]},
            ),
            McpTool(
                "memory_trace_derivation",
                "Traces derivation lineage to source evidence.",
                "memory:read",
                {"type": "object", "required": ["target_type", "target_id"]},
            ),
            McpTool(
                "memory_record_outcome",
                "Records a task outcome as usefulness/policy signal, not truth confirmation.",
                "memory:feedback",
                {"type": "object", "required": ["task_id", "outcome"]},
            ),
        ]

    def invoke(self, tool_name: str, arguments: dict[str, Any]) -> dict:
        started = time.perf_counter()
        request_id = arguments.pop("request_id", None) or new_id("req")
        namespace = arguments.setdefault("namespace", self.namespace)
        self._require_mode(tool_name, namespace, arguments)
        headers = {"X-Request-ID": request_id}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        else:
            token = self._mode_token()
            if token:
                headers["Authorization"] = f"Bearer {token}"
        try:
            endpoint, payload, method = self._tool_to_http(tool_name, arguments)
            status, envelope = self.service.handle_http(
                method=method,
                path=endpoint,
                headers=headers,
                body=json.dumps(payload).encode("utf-8") if payload is not None else b"",
            )
            if status >= 400:
                raise ServiceError(
                    envelope["error"]["code"],
                    envelope["error"]["message"],
                    status_code=status,
                    details=envelope["error"].get("details") or {},
                )
            result = envelope["data"]
            self.service.log_mcp_invocation(
                request_id=request_id,
                client_id=None,
                tool_name=tool_name,
                namespace=namespace,
                status="ok",
                duration_ms=int((time.perf_counter() - started) * 1000),
                input_payload=arguments,
                output_payload=result,
                metadata={"mode": self.mode},
            )
            return result
        except Exception as exc:
            self.service.log_mcp_invocation(
                request_id=request_id,
                client_id=None,
                tool_name=tool_name,
                namespace=namespace,
                status="error",
                duration_ms=int((time.perf_counter() - started) * 1000),
                input_payload=arguments,
                output_payload={"error": str(exc)},
                metadata={"mode": self.mode},
            )
            raise

    def serve_stdio(self) -> None:
        print(json.dumps({"type": "ready", "tools": self.list_tools()}), flush=True)
        for line in sys.stdin:
            if not line.strip():
                continue
            try:
                message = json.loads(line)
                result = self.invoke(message["tool"], message.get("arguments") or {})
                print(json.dumps({"ok": True, "data": result}), flush=True)
            except Exception as exc:  # noqa: BLE001 - MCP stdio returns errors as JSON.
                print(json.dumps({"ok": False, "error": str(exc)}), flush=True)

    def _tool_to_http(self, tool_name: str, arguments: dict) -> tuple[str, dict | None, str]:
        if tool_name == "memory_context_pack":
            return "/v1/context-pack", arguments, "POST"
        if tool_name == "memory_search":
            return "/v1/search", arguments, "POST"
        if tool_name == "memory_remember":
            arguments.setdefault("write_mode", "candidate")
            return "/v1/remember", arguments, "POST"
        if tool_name == "memory_feedback":
            return "/v1/feedback", arguments, "POST"
        if tool_name == "memory_audit":
            target_type = arguments.get("target_type", "claim")
            return f"/v1/audit/{target_type}/{arguments['target_id']}", {}, "GET"
        if tool_name == "memory_explain_claim":
            return f"/v1/claims/{arguments['claim_id']}/explain", {}, "GET"
        if tool_name == "memory_health":
            namespace = arguments.get("namespace", self.namespace)
            return f"/v1/health-report?namespace={namespace}", None, "GET"
        if tool_name == "memory_ingest":
            return "/v1/ingest", arguments, "POST"
        if tool_name == "memory_extract_candidates":
            return "/v1/extract", arguments, "POST"
        if tool_name == "memory_llm_expand_query":
            return "/v1/llm/expand-query", arguments, "POST"
        if tool_name == "memory_llm_suggest_entities":
            return "/v1/llm/suggest-entities", arguments, "POST"
        if tool_name == "memory_llm_suggest_categories":
            return "/v1/llm/suggest-categories", arguments, "POST"
        if tool_name == "memory_llm_suggest_scope":
            return "/v1/llm/suggest-scope", arguments, "POST"
        if tool_name == "memory_llm_suggest_duplicate_merge":
            return "/v1/llm/suggest-duplicate-merge", arguments, "POST"
        if tool_name == "memory_list_candidates":
            namespace = arguments.get("namespace", self.namespace)
            return f"/v1/candidates?namespace={namespace}", None, "GET"
        if tool_name == "memory_promote_candidate":
            return f"/v1/candidates/{arguments['candidate_id']}/promote", {"reason": arguments["reason"]}, "POST"
        if tool_name == "memory_reject_candidate":
            return f"/v1/candidates/{arguments['candidate_id']}/reject", {"reason": arguments["reason"]}, "POST"
        if tool_name == "memory_trace_derivation":
            return f"/v1/derivation/{arguments['target_type']}/{arguments['target_id']}", None, "GET"
        if tool_name == "memory_record_outcome":
            return "/v1/outcomes", arguments, "POST"
        raise ValueError(f"Unknown MCP tool: {tool_name}")

    def _require_mode(self, tool_name: str, namespace: str, arguments: dict) -> None:
        tool = next((item for item in self.tools() if item.name == tool_name), None)
        if not tool:
            raise ValueError(f"Unknown MCP tool: {tool_name}")
        required = tool.required_capability
        if tool_name == "memory_remember" and arguments.get("write_mode") == "active":
            required = "memory:write_active"
        capabilities = MODE_CAPABILITIES[self.mode]
        if required not in capabilities and "memory:admin" not in capabilities:
            raise PermissionError(f"MCP mode {self.mode} lacks {required}.")
        if not self.token and namespace != self.namespace:
            raise PermissionError("MCP namespace is not granted in this mode.")

    def _mode_token(self) -> str | None:
        if self.service.config.auth_required:
            return None
        return None


def config_for_mcp(db_path: str, namespace: str, mode: str) -> ServiceConfig:
    return ServiceConfig(
        db_path=db_path,
        auto_migrate=True,
        auth_required=False,
        mcp_default_namespace=namespace,
        mcp_default_mode=mode,
    )
