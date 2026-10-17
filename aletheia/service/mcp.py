"""MCP-style tool registry for local Aletheia agents."""

from __future__ import annotations

import json
import math
import sys
import time
from dataclasses import dataclass, replace
from typing import Any
from urllib.parse import quote, urlencode

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
        if not token and not service.config.auth_required:
            service.config = replace(
                service.config,
                tokenless_capabilities=tuple(MODE_CAPABILITIES[mode]),
            )

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

    def serve_stdio(self, input_stream=None, output_stream=None) -> None:
        """Newline-delimited MCP JSON-RPC; legacy tool/arguments input remains supported.

        Nothing is emitted before the client's first request. Tool execution
        always goes through the same mode, namespace and HTTP access gates.
        """
        from aletheia.version import software_version

        input_stream = sys.stdin if input_stream is None else input_stream
        output_stream = sys.stdout if output_stream is None else output_stream
        initialized = ready = False
        def send(value):
            print(json.dumps(value, allow_nan=False), file=output_stream, flush=True)
        def error(request_id, code, message):
            send({"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}})
        def invalid_constant(value):
            raise ValueError("Nonfinite JSON number")
        while True:
            line = input_stream.readline(1024 * 1024 + 1)
            if not line:
                break
            if len(line) > 1024 * 1024:
                error(None, -32700, "Message exceeds the stdio size limit.")
                break
            if not line.strip():
                continue
            try:
                message = json.loads(line, parse_constant=invalid_constant)
            except (ValueError, RecursionError):
                error(None, -32700, "Invalid JSON.")
                continue
            if isinstance(message, dict) and "tool" in message and "jsonrpc" not in message and not initialized:
                try:
                    result = self.invoke(message["tool"], dict(message.get("arguments") or {}))
                    send({"ok": True, "data": result})
                except Exception as exc:
                    send({"ok": False, "error": str(exc)})
                continue
            if not isinstance(message, dict) or message.get("jsonrpc") != "2.0" or not isinstance(message.get("method"), str):
                error(None, -32600, "Invalid JSON-RPC request.")
                continue
            request_id = message.get("id")
            if "id" in message and (type(request_id) not in (str, int)):
                error(None, -32600, "Invalid request ID.")
                continue
            method, params = message["method"], message.get("params", {})
            if "id" not in message:
                if method == "notifications/initialized" and initialized:
                    ready = True
                continue
            if not isinstance(params, dict):
                error(request_id, -32602, "params must be an object.")
                continue
            if method == "initialize":
                if initialized or not isinstance(params.get("protocolVersion"), str) or not isinstance(params.get("capabilities"), dict) or not isinstance(params.get("clientInfo"), dict):
                    error(request_id, -32602, "Invalid or repeated initialization.")
                    continue
                requested = params["protocolVersion"]
                version = requested if requested in {"2025-06-18", "2024-11-05"} else "2025-06-18"
                result = {"protocolVersion": version, "capabilities": {"tools": {}},
                          "serverInfo": {"name": "aletheia-memory", "version": software_version()}}
                initialized = True
            elif method == "ping":
                result = {}
            elif not ready:
                error(request_id, -32002, "Initialize and send notifications/initialized before using tools.")
                continue
            elif method == "tools/list":
                if params.get("cursor"):
                    error(request_id, -32602, "Unknown tools cursor.")
                    continue
                capabilities = MODE_CAPABILITIES[self.mode]
                result = {"tools": [{"name": tool.name, "description": tool.description,
                                     "inputSchema": self._wire_schema(tool)} for tool in self.tools()
                                    if tool.required_capability in capabilities or "memory:admin" in capabilities]}
            elif method == "tools/call":
                name, arguments = params.get("name"), params.get("arguments", {})
                tool = next((tool for tool in self.tools() if tool.name == name), None)
                if tool is None or not isinstance(arguments, dict):
                    error(request_id, -32602, "Unknown tool or invalid arguments.")
                    continue
                schema = self._wire_schema(tool)
                if any(key not in arguments for key in schema.get("required", [])):
                    error(request_id, -32602, "Required tool argument is missing.")
                    continue
                if not self._wire_arguments_valid(arguments, schema):
                    error(request_id, -32602, "Tool argument has an invalid type or value.")
                    continue
                try:
                    data = self.invoke(name, dict(arguments))
                    result = {"content": [{"type": "text", "text": json.dumps(data)}], "isError": False}
                    if isinstance(data, dict):
                        result["structuredContent"] = data
                except Exception as exc:
                    result = {"content": [{"type": "text", "text": str(exc)}], "isError": True}
            else:
                error(request_id, -32601, "Method not found.")
                continue
            send({"jsonrpc": "2.0", "id": request_id, "result": result})

    @staticmethod
    def _wire_arguments_valid(arguments: dict, schema: dict) -> bool:
        for key, value in arguments.items():
            spec = schema.get("properties", {}).get(key, {})
            kind = spec.get("type")
            if kind == "string" and not isinstance(value, str):
                return False
            if kind == "array" and (not isinstance(value, list) or any(not isinstance(item, str) for item in value)):
                return False
            if kind in {"integer", "number"}:
                if type(value) not in ((int,) if kind == "integer" else (int, float)) or type(value) is float and not math.isfinite(value):
                    return False
                if not spec.get("minimum", -math.inf) <= value <= spec.get("maximum", math.inf):
                    return False
            if "enum" in spec and value not in spec["enum"]:
                return False
        return True

    @staticmethod
    def _wire_schema(tool: McpTool) -> dict:
        properties = {key: {"type": "string"} for key in [
            "namespace", "query", "memory_type", "subject", "predicate", "object", "content",
            "target_id", "target_type", "claim_id", "candidate_id", "reason", "signal", "note",
            "task_id", "outcome", "provider", "batch_id", "extractor", "source_type", "evidence_text"]}
        properties.update({"evidence_ids": {"type": "array", "items": {"type": "string"}},
                           "limit": {"type": "integer", "minimum": 0},
                           "token_budget": {"type": "integer", "minimum": 0},
                           "strength": {"type": "number", "minimum": 0, "maximum": 1},
                           "write_mode": {"enum": ["candidate", "active"]}})
        return {**tool.input_schema, "properties": properties}

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
            target_type = quote(str(arguments.get("target_type", "claim")), safe="")
            target_id = quote(str(arguments["target_id"]), safe="")
            return f"/v1/audit/{target_type}/{target_id}", {}, "GET"
        if tool_name == "memory_explain_claim":
            claim_id = quote(str(arguments["claim_id"]), safe="")
            return f"/v1/claims/{claim_id}/explain", {}, "GET"
        if tool_name == "memory_health":
            namespace = arguments.get("namespace", self.namespace)
            return "/v1/health-report?" + urlencode({"namespace": namespace}), None, "GET"
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
            return "/v1/candidates?" + urlencode({"namespace": namespace}), None, "GET"
        if tool_name == "memory_promote_candidate":
            candidate_id = quote(str(arguments["candidate_id"]), safe="")
            return f"/v1/candidates/{candidate_id}/promote", {"reason": arguments["reason"]}, "POST"
        if tool_name == "memory_reject_candidate":
            candidate_id = quote(str(arguments["candidate_id"]), safe="")
            return f"/v1/candidates/{candidate_id}/reject", {"reason": arguments["reason"]}, "POST"
        if tool_name == "memory_trace_derivation":
            target_type = quote(str(arguments["target_type"]), safe="")
            target_id = quote(str(arguments["target_id"]), safe="")
            return f"/v1/derivation/{target_type}/{target_id}", None, "GET"
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

def config_for_mcp(db_path: str, namespace: str, mode: str) -> ServiceConfig:
    return ServiceConfig(
        db_path=db_path,
        auto_migrate=True,
        auth_required=False,
        mcp_default_namespace=namespace,
        mcp_default_mode=mode,
        tokenless_capabilities=tuple(MODE_CAPABILITIES[mode]),
    )
