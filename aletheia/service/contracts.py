"""Published discovery contracts reconciled with runtime by actual-service tests.

Only the operations listed here have endpoint-specific schemas. The remaining
legacy OpenAPI paths keep their existing guarantees and representation.
"""

from copy import deepcopy

from aletheia.service.auth import CAPABILITIES, CLIENT_TYPES, PRIVACY_ORDER


DISCOVERY_PATHS = {
    "/v1/health": ("getHealth", "Health"),
    "/v1/ready": ("getReadiness", "Readiness"),
    "/v1/version": ("getVersion", "Version"),
    "/v1/openapi.json": ("getOpenApi", "OpenApiDocument"),
    "/v1/compatibility/report": ("getCompatibility", "CompatibilityReport"),
    "/v1/auth/me": ("getCurrentPrincipal", "CurrentPrincipal"),
}


def _ref(name):
    return {"$ref": f"#/components/schemas/{name}"}


def _object(properties, *, required=None, additional=False):
    return {"type": "object", "properties": properties,
            "required": list(properties) if required is None else required,
            "additionalProperties": additional}


def _strings():
    return {"type": "array", "items": {"type": "string"}}


def discovery_schemas():
    string = {"type": "string"}
    nullable = {"type": ["string", "null"]}
    boolean = {"type": "boolean"}
    metadata = {"type": "object", "additionalProperties": True}
    common = {
        "software_version": string, "api_version": {"const": "v1"},
        "supported_profiles": _strings(), "supported_features": _strings(),
        "service_identity": {"type": "string", "minLength": 1},
    }
    health = {
        **common, "status": {"enum": ["ok", "degraded"]}, "database": string,
        "schema_version": string, "service_version": string,
        "auth_required": boolean, "warnings": _strings(),
    }
    schemas = {
        "Health": _object(health),
        "Readiness": _object({**health, "ready": boolean}),
        "Version": _object({**common, "service_version": string}),
        "Principal": _object({"id": string, "name": string, "client_type": {"enum": sorted(CLIENT_TYPES)}}),
        "CurrentPrincipal": _object({
            **common,
            "authentication_mode": {"enum": ["bearer", "console_session", "local_tokenless"]},
            "authenticated": boolean,
            "principal": {"anyOf": [_ref("Principal"), {"type": "null"}]},
            "granted_capabilities": {"type": "array", "items": {"enum": sorted(CAPABILITIES)}},
            "capabilities": {"type": "array", "items": {"enum": sorted(CAPABILITIES)}},
            "namespace_grants": _strings(),
            "privacy_ceiling": {"enum": list(PRIVACY_ORDER)}, "expires_at": nullable,
        }),
        "CompatibilityEntry": _object({
            **{key: string for key in ["id", "component_type", "component_name", "component_version",
                                      "aletheia_min_version", "status"]},
            **{key: nullable for key in ["aletheia_max_version", "tested_at", "notes"]}, "metadata": metadata,
        }),
        "SDKRelease": _object({
            **{key: string for key in ["id", "sdk_name", "sdk_version", "language", "api_contract_version", "status"]},
            "released_at": nullable, "metadata": metadata,
        }),
        "CompatibilityPlugin": _object({
            **{key: string for key in ["id", "plugin_manifest_id", "install_path", "status", "trust_level",
                                      "installed_at", "name", "display_name", "version", "plugin_type"]},
            "enabled_at": nullable, "disabled_at": nullable, "metadata": metadata,
            "external_network_access": boolean, "permissions_required": _strings(),
        }),
        "CompatibilityReport": _object({
            **common,
            "aletheia_version": {"type": "string", "deprecated": True,
                                 "description": "Historical expected-schema version for the 1.3.1 SDK; not software version."},
            "schema_version": string,
            "deprecated_fields": _object({"aletheia_version": string}),
            "python_version": nullable, "platform": nullable, "sqlite_version": nullable,
            "plugins": {"type": "array", "items": _ref("CompatibilityPlugin")},
            "sdk_versions": {"type": "array", "items": _ref("SDKRelease")},
            "matrix": {"type": "array", "items": _ref("CompatibilityEntry")},
            "archive_formats": _strings(), "warnings": _strings(),
            "migration_support": _object({"from": string, "to": string, "safe": boolean}),
        }),
        # OpenAPI itself is an extensible specification, not an untyped domain result.
        "OpenApiDocument": _object({
            "openapi": string, "info": _object({"title": string, "version": string}, additional=True),
            "paths": metadata, "components": metadata,
            "security": {"type": "array", "items": {"type": "object", "additionalProperties": _strings()}},
        }, additional=True),
    }
    for name in [entry[1] for entry in DISCOVERY_PATHS.values()]:
        schemas[name + "Envelope"] = _object({
            "data": _ref(name), "request_id": string, "warnings": _strings(),
            "pagination": {"type": "null"},
        }, required=["data", "request_id", "warnings"])
    return schemas


def apply_discovery_contracts(schema):
    schema["components"]["schemas"].update(discovery_schemas())
    schema["components"]["securitySchemes"].update({
        "consoleSession": {"type": "apiKey", "in": "header", "name": "X-Console-Session"},
        "consoleCookie": {"type": "apiKey", "in": "cookie", "name": "aletheia_console"},
    })
    for path, (operation_id, response_name) in DISCOVERY_PATHS.items():
        operation = schema["paths"][path]["get"]
        public = path not in {"/v1/auth/me", "/v1/compatibility/report"}
        capability = "memory:read" if path == "/v1/compatibility/report" else None
        operation["operationId"] = operation_id
        operation["security"] = [] if public else [
            {"bearerAuth": []}, {"consoleSession": []}, {"consoleCookie": []},
        ]
        if path == "/v1/auth/me":
            operation["security"].append({})
        operation["x-permissions"] = {
            "authentication": "public" if public else "configured",
            "all_of": [], "any_of": [capability, "memory:admin"] if capability else [],
            "note": "Tokenless self discovery is limited to explicitly unauthenticated, unprotected local mode. Grants never imply per-resource authorization.",
        }
        operation["parameters"] = [{
            "name": "X-Request-ID", "in": "header", "required": False,
            "schema": {"type": "string"},
            "description": "Correlation ID; printable ASCII up to 200 characters is also returned as a header.",
        }]
        if path == "/v1/compatibility/report":
            operation["parameters"] += [{
                "name": key, "in": "query", "required": False,
                "schema": {"type": "boolean", "default": True},
                "description": "Legacy truthy spellings 1, true, yes, on are accepted; other supplied values are false.",
            } for key in ["include_plugins", "include_sdks", "include_runtime"]]
        statuses = [200, 400, 403, 413, 429, 500]
        if not public:
            statuses.append(401)
        if capability:
            statuses.append(403)
        operation["responses"] = {
            str(status): {
                "description": "Success envelope" if status == 200 else "Service error envelope",
                "content": {"application/json": {"schema": _ref(response_name + "Envelope" if status == 200 else "ErrorEnvelope")}},
                "headers": {
                    "Cache-Control": {"schema": {"const": "no-store"}},
                    "X-Request-ID": {"schema": {"type": "string"}},
                },
            } for status in statuses
        }
    return schema


def discovery_document(schema):
    """Project the published document for strict validation/generation of this slice."""
    document = deepcopy(schema)
    document["paths"] = {path: document["paths"][path] for path in DISCOVERY_PATHS}
    return document
