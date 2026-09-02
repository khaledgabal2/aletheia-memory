"""Review profile schemas, plus explicit legacy branches for the full v1 API."""
from copy import deepcopy
from aletheia.service.contracts import DISCOVERY_PATHS, _object, _ref, _strings
from aletheia.service.read_contracts import READ_PATHS, STRING, NULL_STRING, read_schemas
from aletheia.service.reviews import REVIEW_PROFILE


REVIEW_PATHS = {
    "/v1/candidates": ("get", "listReviewCandidates", "ReviewCandidatePage"),
    "/v1/candidates/{candidate_id}": ("get", "getReviewCandidate", "ReviewCandidate"),
    "/v1/candidates/{candidate_id}/promote": ("post", "promoteReviewedCandidate", "ReviewOutcome"),
    "/v1/candidates/{candidate_id}/reject": ("post", "rejectReviewedCandidate", "ReviewOutcome"),
}
REVISION = {"type": "string", "minLength": 1, "maxLength": 256}
REVIEW_REQUEST = _object({"reason": {"type": "string", "minLength": 1, "maxLength": 4096}, "expected_revision": REVISION})
ERRORS = ["precondition_required", "stale_revision", "review_conflict", "stale_cursor", "invalid_cursor",
          "unsupported_contract", "review_scan_limit", "database_busy", "replay_result_changed"]


def review_schemas():
    candidate = deepcopy(read_schemas()["CandidateClaim"])
    candidate["properties"]["revision"] = REVISION
    candidate["required"].append("revision")
    schemas = {
        "ReviewCandidate": candidate,
        "ReviewPagination": _object({"limit": {"type": "integer", "minimum": 1, "maximum": 200},
            "count": {"type": "integer", "minimum": 0, "maximum": 200}, "next_cursor": NULL_STRING}),
        "ReviewOutcome": _object({**{name: STRING for name in ["operation_id", "audit_id", "candidate_id", "decision_id", "applied_at"]},
            "action": {"enum": ["promote", "reject"]}, "claim_id": NULL_STRING,
            "reviewed_revision": REVISION, "result_revision": REVISION}),
        "ReviewRequest": REVIEW_REQUEST,
        "LegacyReviewRequest": _object({"reason": {"type": "string", "minLength": 1}}, additional=True),
        "RejectionDecision": _object({**{name: STRING for name in ["id", "namespace", "candidate_id", "decision", "reason", "reviewer", "created_at"]}, "edits": {"type": "null"}}),
    }
    for name in ["ReviewCandidate", "ReviewOutcome", "ReviewCandidatePage"]:
        result = {"type": "array", "items": _ref("ReviewCandidate")} if name == "ReviewCandidatePage" else _ref(name)
        schemas[name + "Envelope"] = _object({"data": result, "request_id": STRING, "warnings": _strings(),
            "pagination": _ref("ReviewPagination") if name == "ReviewCandidatePage" else {"type": "null"}}, required=["data", "request_id", "warnings", "pagination"])
    return schemas


def apply_review_contracts(schema):
    schema["components"]["schemas"].update(review_schemas())
    schema["components"]["schemas"]["ErrorEnvelope"]["properties"]["error"]["properties"]["code"]["enum"] += ERRORS
    for path, (method, operation_id, result) in REVIEW_PATHS.items():
        operation = schema["paths"][path][method]
        operation.update(operationId=operation_id, security=[{"bearerAuth": []}])
        operation["description"] = "Negotiated review uses memory-review-v1; the full API also preserves legacy calls. Supplying expected_revision selects the guarded workflow even without a profile header. Guarded writes return content-free receipts and require an idempotency key. Read the review contract before retrying."
        operation["x-permissions"] = {"any_of": ["memory:review", "memory:admin"], "all_of": [],
            "resource_policy": "Current stored namespace/project and candidate/provenance privacy; admin does not widen scope."}
        params = [{"name": "X-Aletheia-Contract", "in": "header", "required": False, "schema": {"const": REVIEW_PROFILE}},
                  {"name": "X-Request-ID", "in": "header", "required": False, "schema": STRING}]
        if "{candidate_id}" in path:
            params.append({"name": "candidate_id", "in": "path", "required": True, "schema": STRING})
        if path == "/v1/candidates":
            params += [{"name": name, "in": "query", "required": name == "namespace", "schema": STRING} for name in ["namespace", "status", "memory_type", "project_id", "cursor"]]
            params.append({"name": "limit", "in": "query", "required": False, "schema": {"type": "integer", "minimum": 1, "maximum": 200, "default": 50}})
        if method == "post":
            params.append({"name": "Idempotency-Key", "in": "header", "required": False,
                "schema": {"type": "string", "pattern": "^[A-Za-z0-9_.:-]{1,200}$"}, "description": "Required for guarded review; keep the same key and payload after an uncertain response."})
            operation["requestBody"] = {"required": True, "content": {"application/json": {"schema": {"anyOf": [_ref("ReviewRequest"), _ref("LegacyReviewRequest")]}}}}
        operation["parameters"] = params
        legacy_result = {"type": "array", "items": _ref("CandidateClaim")} if path == "/v1/candidates" else _ref("CandidateClaim" if method == "get" else "Claim" if path.endswith("promote") else "RejectionDecision")
        legacy_envelope = _object({"data": legacy_result, "request_id": STRING, "warnings": _strings(),
            "pagination": {"type": ["object", "null"]}}, required=["data", "request_id", "warnings"])
        operation["responses"] = {str(status): {"description": "Success" if status == 200 else "Review/service error",
            "content": {"application/json": {"schema": {"anyOf": [_ref(result + "Envelope"), legacy_envelope]} if status == 200 else _ref("ErrorEnvelope")}},
            "headers": {"Cache-Control": {"schema": {"const": "no-store"}}, "X-Request-ID": {"schema": STRING}}}
            for status in [200, 400, 401, 403, 404, 409, 412, 413, 428, 429, 500, 503]}
    return schema


def review_document(schema):
    document = deepcopy(schema)
    document["paths"] = {path: document["paths"][path] for path in [*DISCOVERY_PATHS, *READ_PATHS, *REVIEW_PATHS]}
    for path, (method, _, result) in REVIEW_PATHS.items():
        operation = document["paths"][path][method]
        for parameter in operation["parameters"]:
            if parameter["name"] in {"X-Aletheia-Contract", "Idempotency-Key"}:
                parameter["required"] = True
        operation["responses"]["200"]["content"]["application/json"]["schema"] = _ref(result + "Envelope")
        if method == "post":
            operation["requestBody"]["content"]["application/json"]["schema"] = _ref("ReviewRequest")
    return document
