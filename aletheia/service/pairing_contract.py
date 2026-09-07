"""Typed schemas for the local pairing v1 profile. Endpoints require pinned TLS
except public info; the operator invitation command is an out-of-band boundary.
"""
from .contracts import _object, _ref, _strings
from .local_pairing import PROTOCOL, PAIRING_CAPABILITIES


def apply_pairing_contract(schema):
    string = {"type": "string"}
    port = {"type": "integer", "minimum": 1024, "maximum": 65535}
    fingerprint = {"type": "string", "pattern": "^[0-9a-f]{64}$"}
    binding = {"protocol": {"const": PROTOCOL}, "certificate_sha256": fingerprint, "service_identity": string}
    models = {
        "LocalPairingInfo": _object({**binding, "public_port": port, "tls_port": port, "certificate_pem": string}),
        "LocalPairingRequest": _object({"invitation_id": {"type": "string", "format": "uuid"}, "secret": {"type": "string", "pattern": "^[A-Za-z0-9_-]{43}$"}}),
        "LocalPairingInspection": _object({**binding, "expires_at_ms": {"type": "integer"}, "client_name": string,
            "namespace_grants": _strings(), "capabilities": {"type": "array", "items": {"enum": sorted(PAIRING_CAPABILITIES)}},
            "privacy_ceiling": {"enum": ["public", "personal", "private", "sensitive", "secret"]},
            "token_ttl_seconds": {"type": "integer", "minimum": 300, "maximum": 2592000}}),
        "LocalPairingCredential": _object({**binding, "token": {"type": "string", "description": "Sensitive bearer; returned once over pinned TLS to the credential host."}, "expires_at": {"type": "string", "format": "date-time"}}),
        "LocalPairingCanceled": _object({"canceled": {"const": True}}),
        "LocalPairingRevoked": _object({"revoked": {"const": True}}),
    }
    for name, model in list(models.items()):
        if name != "LocalPairingRequest":
            models[name + "Envelope"] = _object({"data": _ref(name), "request_id": string, "warnings": _strings(), "pagination": {"type": "null"}}, required=["data", "request_id", "warnings"])
    schema["components"]["schemas"].update(models)
    for method, endpoint, operation, response in [
        ("get", "/v1/pairing/info", "getLocalPairingInfo", "LocalPairingInfo"),
        ("post", "/v1/pairing/inspect", "inspectLocalPairing", "LocalPairingInspection"),
        ("post", "/v1/pairing/complete", "completeLocalPairing", "LocalPairingCredential"),
        ("post", "/v1/pairing/cancel", "cancelLocalPairing", "LocalPairingCanceled"),
        ("delete", "/v1/pairing/current", "revokeLocalPairing", "LocalPairingRevoked"),
    ]:
        route = {"operationId": operation, "summary": "Local pairing v1; pinned TLS required except for public info.",
                 "security": [{"bearerAuth": []}] if method == "delete" else [],
                 "x-aletheia-profile": "local-pairing-v1", "x-aletheia-transport": "pinned-local-tls" if method != "get" else "public-discovery",
                 "responses": {"200": {"description": "Success; Cache-Control: no-store.", "content": {"application/json": {"schema": _ref(response + "Envelope")}}}}}
        for status in (400, 401, 403, 404, 413, 500, 503):
            route["responses"][str(status)] = {"description": "Pairing rejected; no secret values are echoed.", "content": {"application/json": {"schema": _ref("ErrorEnvelope")}}}
        if method == "post":
            route["requestBody"] = {"required": True, "content": {"application/json": {"schema": _ref("LocalPairingRequest")}}}
        schema["paths"][endpoint] = {method: route}
    return schema
