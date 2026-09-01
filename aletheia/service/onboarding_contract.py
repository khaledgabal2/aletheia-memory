"""Typed candidate-first creation and an opt-in atomic agent workflow."""
from copy import deepcopy
from dataclasses import asdict
import re

from aletheia.core.memory import CANDIDATE_MEMORY_TYPES
from aletheia.service.auth import PRIVACY_ORDER
from aletheia.service.contracts import DISCOVERY_PATHS, _object, _ref, _strings
from aletheia.service.errors import ServiceError, forbidden, validation_error
from aletheia.service.read_contracts import READ_PATHS, STRING, NULL_STRING, _matches
from aletheia.service.reads import ReadAccess
from aletheia.service.reviews import canonical
from aletheia.core.ids import content_hash

PROFILE = "agent-onboarding-v1"
REQUEST = _object({
    **{name: {"type": "string", "minLength": 1} for name in ["namespace", "subject", "predicate", "object", "evidence_text"]},
    "write_mode": {"type": "string", "const": "candidate", "default": "candidate"},
    "memory_type": {"type": "string", "enum": sorted(CANDIDATE_MEMORY_TYPES)},
    "privacy_level": {"type": "string", "enum": list(PRIVACY_ORDER)},
    "source_type": STRING, "trust_level": STRING, "project_id": NULL_STRING,
    "session_id": NULL_STRING, "title": NULL_STRING,
    "confidence": {"type": "number", "minimum": 0, "maximum": 1, "default": .75},
    "importance": {"type": "number", "minimum": 0, "maximum": 1, "default": .5},
    "half_life_days": {"type": ["number", "null"], "exclusiveMinimum": 0},
    "scope": {"type": ["object", "null"], "additionalProperties": True},
}, required=["namespace", "memory_type", "subject", "predicate", "object", "evidence_text"], additional=True)


def remember_response(service, payload, headers, request_id, request_hash):
    contract = service._header(headers, "X-Aletheia-Contract")
    if contract not in {None, PROFILE}:
        raise ServiceError("unsupported_contract", "Use agent-onboarding-v1 for negotiated candidate creation.", status_code=409)
    if "expected_revision" in payload:
        raise validation_error("Candidate creation does not accept a review revision.")
    negotiated = contract == PROFILE
    with service.memory.store.transaction(immediate=True):
        context = service._authenticate("POST", "/v1/remember", headers)
        if negotiated:
            for name, schema in REQUEST["properties"].items():
                if name in REQUEST["required"] and name not in payload or name in payload and not _matches(payload[name], schema):
                    raise validation_error("Invalid onboarding field.", {"field": name})
            key = service._header(headers, "Idempotency-Key")
            if not key or not re.fullmatch(r"[A-Za-z0-9_.:-]{1,200}", key):
                raise validation_error("Supply an explicit Idempotency-Key of 1-200 ASCII letters, digits, dots, underscores, colons or hyphens.")
            if not context.token_id:
                raise ServiceError("unauthorized", "Negotiated candidate creation requires a bearer credential.", status_code=401)
        mode = payload.get("write_mode", "candidate")
        service.auth.require_capability(context, "memory:write_active" if mode == "active" else "memory:write_candidate")
        namespace = service._required(payload, "namespace")
        service.auth.require_namespace(context, namespace=namespace, project_id=payload.get("project_id"))
        service._require_read_session(payload, context)
        privacy = payload.get("privacy_level", "public" if context.privacy_ceiling == "public" else "personal")
        if mode == "candidate" and (privacy not in PRIVACY_ORDER or not service.auth.privacy_allows(context, privacy)):
            raise forbidden("Requested privacy exceeds this credential's scope.")
        options = dict(method="POST", endpoint="/v1/remember", headers=headers, payload=payload,
            request_hash=content_hash(canonical(payload)) if negotiated else request_hash, namespace=namespace,
            client_id="credential:" + context.token_id if context.token_id else "tokenless")
        replay = service._idempotency_replay(**options)
        if replay is not None:
            data, access = replay["data"], ReadAccess(service, context)
            if data["write_mode"] == "candidate":
                current = service.memory.read_candidate(data["candidate"]["id"])
                # This is the receipt for this creator's operation, not a grant
                # to browse other candidates without memory:review.
                if (access.removed(current.id) or current.privacy_level not in PRIVACY_ORDER
                        or not service.auth.privacy_allows(context, current.privacy_level)
                        or not access.namespace(current.namespace, [service.memory._project_id_for_candidate(current)])
                        or not access.evidence_set(current.evidence_ids)):
                    raise forbidden("The original candidate is no longer available under current access policy.")
                unchanged = asdict(current) == data["candidate"]
            else:
                access.require("claim", data["claim"]["id"])
                unchanged = asdict(service.memory.read_claim(data["claim"]["id"])) == data["claim"]
            if not unchanged:
                raise ServiceError("replay_result_changed", "The created memory changed; ask the operator to inspect it before continuing.", status_code=409)
            if negotiated:
                replay["request_id"] = request_id
            return int(replay.pop("_status_code", 200)), replay
        normalized = {**payload, **({"privacy_level": privacy} if mode == "candidate" else {})}
        data = service._remember(normalized, context)
        response = service._success(data=data, request_id=request_id, warnings=[], pagination=None)
        service._idempotency_store(**options, status_code=200, response=response)
        return 200, response


def apply_onboarding_contract(schema):
    schemas = schema["components"]["schemas"]
    schemas["RememberCandidateRequest"] = REQUEST
    schemas["RememberCandidateResult"] = _object({"write_mode": {"const": "candidate"}, "candidate": _ref("CandidateClaim")})
    schemas["RememberCandidateEnvelope"] = _object({"data": _ref("RememberCandidateResult"), "request_id": STRING,
        "warnings": _strings(), "pagination": {"type": "null"}})
    operation = schema["paths"]["/v1/remember"]["post"]
    operation.update(operationId="rememberCandidate", security=[{"bearerAuth": []}])
    operation["description"] = "agent-onboarding-v1 creates candidates only, with explicit operation keys and atomic replay. Legacy unconditioned active/candidate writes remain available with their existing permissions. Extension fields remain accepted; supplied review revisions are refused."
    operation["x-permissions"] = {"any_of": ["memory:write_candidate", "memory:admin"], "all_of": [],
        "resource_policy": "Namespace/project/session and privacy bounds; legacy active writes require memory:write_active."}
    operation["parameters"] = [{"name": "X-Aletheia-Contract", "in": "header", "required": False, "schema": {"const": PROFILE}},
        {"name": "Idempotency-Key", "in": "header", "required": False, "schema": {"type": "string", "pattern": "^[A-Za-z0-9_.:-]{1,200}$"}},
        {"name": "X-Request-ID", "in": "header", "required": False, "schema": STRING}]
    operation["requestBody"] = {"required": True, "content": {"application/json": {"schema": {"anyOf": [_ref("RememberCandidateRequest"), {"type": "object", "additionalProperties": True}]}}}}
    legacy = _object({"data": {"type": "object", "additionalProperties": True}, "request_id": STRING,
        "warnings": _strings(), "pagination": {"type": ["object", "null"]}})
    operation["responses"] = {str(status): {"description": "Success" if status == 200 else "Creation/service error",
        "content": {"application/json": {"schema": {"anyOf": [_ref("RememberCandidateEnvelope"), legacy]} if status == 200 else _ref("ErrorEnvelope")}},
        "headers": {"Cache-Control": {"schema": {"const": "no-store"}}, "X-Request-ID": {"schema": STRING}}}
        for status in [200, 400, 401, 403, 404, 409, 413, 429, 500, 503]}
    return schema


def onboarding_document(schema):
    document = deepcopy(schema)
    document["paths"] = {path: document["paths"][path] for path in [*DISCOVERY_PATHS, *READ_PATHS, "/v1/remember"]}
    operation = document["paths"]["/v1/remember"]["post"]
    for parameter in operation["parameters"]:
        if parameter["name"] != "X-Request-ID":
            parameter["required"] = True
    operation["requestBody"]["content"]["application/json"]["schema"] = _ref("RememberCandidateRequest")
    operation["responses"]["200"]["content"]["application/json"]["schema"] = _ref("RememberCandidateEnvelope")
    return document
