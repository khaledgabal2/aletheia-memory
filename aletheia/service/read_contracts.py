"""Read-profile schemas and opt-in canonical input validation (stdlib only)."""

from dataclasses import fields, is_dataclass
import types
from typing import get_args, get_origin, get_type_hints

from aletheia.models import (Claim, RetrievalResult, ContextItem, ContextWarning, EvidenceEvent,
                             CandidateClaim, EvidenceSpan, Conflict, ConflictFamily, ClaimRelationship,
                             ClaimScope, ConfidenceSnapshot, ReviewTask)
from aletheia.service.contracts import _object, _ref, _strings, DISCOVERY_PATHS
from aletheia.service.errors import validation_error


READ_PROFILE = "memory-read-v1"
READ_PATHS = {
    "/v1/dashboard/overview": ("get", "getOverview", "Overview"),
    "/v1/retrieve": ("post", "retrieveMemory", "RetrievalResults"),
    "/v1/search": ("post", "searchMemory", "RetrievalResults"),
    "/v1/context-pack": ("post", "createContextPack", "ReadContextPack"),
    "/v1/context": ("post", "createContext", "ReadContextPack"),
    "/v1/claims/{claim_id}": ("get", "getClaim", "Claim"),
    "/v1/claims/{claim_id}/explain": ("get", "explainClaim", "ReadClaimExplanation"),
    "/v1/audit/{target_type}/{target_id}": ("get", "getAudit", "ReadAudit"),
}
STRING = {"type": "string"}
NULL_STRING = {"type": ["string", "null"]}
BOOL = {"type": "boolean"}
MODES = {"type": "string", "enum": ["lexical", "semantic", "hybrid"], "default": "hybrid"}
COMMON_INPUT = {"namespace": {"type": "string", "minLength": 1}, "query": {**STRING, "default": ""},
                "project_id": NULL_STRING, "session_id": NULL_STRING}
RETRIEVE_INPUT = _object({**COMMON_INPUT, "mode": MODES,
    "limit": {"type": "integer", "minimum": 1, "maximum": 200, "default": 10},
    "memory_types": {"anyOf": [_strings(), {"type": "null"}]},
    "include_disputed": {**BOOL, "default": False}, "include_archived": {**BOOL, "default": False},
}, required=["namespace"], additional=True)
CONTEXT_INPUT = _object({**COMMON_INPUT, "retrieval_mode": MODES,
    "token_budget": {"type": "integer", "minimum": 1, "maximum": 12000, "default": 1500},
    "include_reflections": {**BOOL, "default": True}, "include_inferences": {**BOOL, "default": False},
    "include_derivation_metadata": {**BOOL, "default": False}, "record_usage": {**BOOL, "default": False},
    "policy_version_id": NULL_STRING,
}, required=["namespace"], additional=True)


def _matches(value, schema):
    if "anyOf" in schema:
        return any(_matches(value, option) for option in schema["anyOf"])
    kind = schema.get("type")
    if isinstance(kind, list):
        return any(_matches(value, {**schema, "type": item}) for item in kind)
    valid = {"null": value is None, "boolean": type(value) is bool,
             "integer": type(value) is int, "string": isinstance(value, str),
             "array": isinstance(value, list)}.get(kind, False)
    if not valid or ("enum" in schema and value not in schema["enum"]):
        return False
    if kind == "integer":
        return schema.get("minimum", value) <= value <= schema.get("maximum", value)
    if kind == "string":
        return len(value) >= schema.get("minLength", 0)
    if kind == "array":
        return all(_matches(item, schema["items"]) for item in value)
    return True


def validate_read_input(endpoint, query, payload, contract):
    # No implicit tightening of accepted legacy coercions/extensions.
    if contract != READ_PROFILE:
        return
    if endpoint == "/v1/dashboard/overview":
        if not query.get("namespace", [""])[0]:
            raise validation_error("The read profile requires an explicit namespace.")
        return
    shape = RETRIEVE_INPUT if endpoint in {"/v1/retrieve", "/v1/search"} else CONTEXT_INPUT if endpoint in {"/v1/context-pack", "/v1/context"} else None
    if shape:
        for name, schema in shape["properties"].items():
            if name in shape["required"] and name not in payload or name in payload and not _matches(payload[name], schema):
                raise validation_error(f"Invalid read-profile field: {name}", {"field": name})


def read_schemas():
    schemas = {}
    def shape(hint):
        origin, args = get_origin(hint), get_args(hint)
        if origin is types.UnionType:
            return {"anyOf": [shape(item) for item in args]}
        if origin is list:
            return {"type": "array", "items": shape(args[0])}
        if hint is dict:
            return {"type": "object", "additionalProperties": True}
        if is_dataclass(hint):
            return _ref(hint.__name__)
        return {"type": {str: "string", int: "integer", float: "number", bool: "boolean", type(None): "null"}[hint]}
    for model in [Claim, RetrievalResult, ContextItem, ContextWarning, EvidenceEvent, CandidateClaim, EvidenceSpan,
                  Conflict, ConflictFamily, ClaimRelationship, ClaimScope, ConfidenceSnapshot, ReviewTask]:
        hints = get_type_hints(model)
        schemas[model.__name__] = _object({field.name: shape(hints[field.name]) for field in fields(model)})
    schemas["ContextItem"]["properties"]["derivation"] = {"type": "null", "description": "Unclassified derivation graphs are redacted; use typed provenance."}
    def array(name):
        return {"type": "array", "items": _ref(name)}
    schemas["AuditRecord"] = _object({**{key: STRING for key in ["id", "namespace", "target_type", "target_id", "action", "created_at"]},
                                       "details": {"const": "{}", "description": "Unclassified free-form audit details are redacted."}})
    schemas["ClaimHistory"] = _object({**{key: STRING for key in ["id", "namespace", "claim_id", "new_status", "created_at"]},
                                        **{key: NULL_STRING for key in ["old_status", "reason", "changed_by"]}})
    schemas["ReadClaimExplanation"] = _object({"claim_id": STRING, "claim": _ref("Claim"), "evidence": array("EvidenceEvent"),
        "confidence": {"anyOf": [_ref("ConfidenceSnapshot"), {"type": "null"}]}, "conflicts": array("Conflict"),
        "relationships": array("ClaimRelationship"), "scopes": array("ClaimScope"), "history": array("ClaimHistory"), "audit": array("AuditRecord")})
    schemas["ExtractionAuditDecision"] = _object({**{key: STRING for key in ["id", "namespace", "candidate_id", "decision", "reason", "reviewer", "created_at"]}, "edits_json": {"type": "null"}})
    schemas["AuditClaimLink"] = _object({key: STRING for key in ["claim_id", "relation", "created_at"]})
    base = {"target_type": STRING, "target_id": STRING, "requested_target_type": STRING, "audit": array("AuditRecord")}
    schemas["ReadAudit"] = {"oneOf": [
        _object({**base, "target_type": {"const": "claim"}, "claim": _ref("Claim"), "evidence": array("EvidenceEvent"), "conflicts": array("Conflict")}),
        _object({**base, "target_type": {"const": "candidate_claim"}, "candidate": _ref("CandidateClaim"), "evidence": array("EvidenceEvent"),
                 "decisions": array("ExtractionAuditDecision"), "claim_links": array("AuditClaimLink")}),
        _object({**base, "target_type": {"const": "evidence"}, "evidence": _ref("EvidenceEvent")}),
    ]}
    metrics = {key: {"type": "integer", "minimum": 0} for key in ["active_claim_count", "core_memory_count", "stale_claim_count", "unresolved_conflict_count"]}
    metrics.update({key: {"type": ["integer", "null"], "minimum": 0} for key in ["candidate_count", "pending_review_count", "open_review_task_count", "critical_review_task_count"]})
    metrics["project_id"] = NULL_STRING
    schemas["OverviewMetrics"] = _object(metrics)
    schemas["OverviewHealth"] = _object({"id": STRING, "namespace": STRING, "project_id": NULL_STRING, "generated_at": STRING,
                                         "metrics": _ref("OverviewMetrics"), "warnings": _strings(), "recommendations": _strings()})
    schemas["Overview"] = _object({"metrics": _ref("OverviewMetrics"), "health": _ref("OverviewHealth"), "review_tasks": array("ReviewTask"),
        "candidates": array("CandidateClaim"), "conflicts": array("ConflictFamily"),
        "jobs": {"type": "array", "items": False, "maxItems": 0}, "service_requests": {"type": "array", "items": False, "maxItems": 0},
        "unavailable_sections": {"type": "array", "items": {"enum": ["jobs", "service_requests", "review_tasks", "candidates"]}}})
    schemas["ReadProvenance"] = _object({"target_id": STRING, "claim_id": STRING, "source_kind": STRING, "evidence_ids": _strings()})
    schemas["ReadContextPack"] = _object({"context_pack_id": STRING, "markdown": STRING,
        "sections": _object({**{key: array("ContextItem") for key in ["core_memory", "project_memory", "session_memory", "procedural_memory", "reflections", "relevant_memory"]}, "warnings": array("ContextWarning")}),
        "items": array("ContextItem"), "warnings": array("ContextWarning"), "provenance": array("ReadProvenance"),
        "policy": _object({"ranking_policy_version_id": NULL_STRING, "context_policy_version_id": NULL_STRING}), "access_warnings": _strings(),
    }, required=["context_pack_id", "markdown", "sections", "items", "warnings", "provenance", "policy"])
    schemas["RetrievalResults"] = array("RetrievalResult")
    schemas["RetrieveRequest"], schemas["ContextRequest"] = RETRIEVE_INPUT, CONTEXT_INPUT
    for name in {item[2] for item in READ_PATHS.values()}:
        schemas[name + "Envelope"] = _object({"data": _ref(name), "request_id": STRING, "warnings": _strings(), "pagination": {"type": "null"}}, required=["data", "request_id", "warnings"])
    return schemas


def apply_read_contracts(schema):
    schema["components"]["schemas"].update(read_schemas())
    for path, (method, operation_id, result) in READ_PATHS.items():
        operation = schema["paths"][path][method]
        capability = "memory:context" if result == "ReadContextPack" else "memory:audit" if result == "ReadAudit" else "memory:read"
        operation.update(operationId=operation_id, security=[{"bearerAuth": []}])
        if result == "Overview":
            operation["security"] += [{"consoleSession": []}, {"consoleCookie": []}]
        operation["x-permissions"] = {"any_of": [capability, "memory:admin"], "all_of": [],
            "resource_policy": "Stored namespace/project and full provenance privacy; administrative capability never widens scope.",
            "additional": {"candidate_audit": ["memory:review"], "explanation_audit_history": ["memory:audit"]}}
        operation["description"] = "Read contract. Use X-Aletheia-Contract: memory-read-v1 for canonical input validation and limits. Legacy coercions and extension inputs remain accepted without that header. Ranked/nested lists are bounded, not exhaustive pagination; no cursor."
        params = [{"name": "X-Aletheia-Contract", "in": "header", "required": False, "schema": {"type": "string", "enum": [READ_PROFILE]}},
                  {"name": "X-Request-ID", "in": "header", "required": False, "schema": STRING}]
        for key in ["claim_id", "target_id", "target_type"]:
            if "{" + key + "}" in path:
                params.append({"name": key, "in": "path", "required": True, "schema": {"type": "string", **({"enum": ["claim", "candidate_claim", "candidate", "evidence", "event"]} if key == "target_type" else {})}})
        if result == "Overview":
            params += [{"name": "namespace", "in": "query", "required": True, "schema": STRING}, {"name": "project_id", "in": "query", "required": False, "schema": STRING}]
        operation["parameters"] = params
        if method == "post":
            operation["requestBody"] = {"required": True, "content": {"application/json": {"schema": _ref("ContextRequest" if result == "ReadContextPack" else "RetrieveRequest")}}}
        operation["responses"] = {str(status): {"description": "Success" if status == 200 else "Service error envelope",
            "content": {"application/json": {"schema": _ref(result + "Envelope" if status == 200 else "ErrorEnvelope")}},
            "headers": {"Cache-Control": {"schema": {"const": "no-store"}}, "X-Request-ID": {"schema": STRING}},
        } for status in [200, 400, 401, 403, 404, 413, 429, 500]}
    return schema


def read_document(schema):
    return {**schema, "paths": {path: schema["paths"][path] for path in [*DISCOVERY_PATHS, *READ_PATHS]}}
