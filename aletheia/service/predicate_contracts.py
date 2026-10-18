"""HTTP contract for namespace-local predicate semantics."""
from aletheia.service.contracts import _object, _ref

PATH = "/v1/predicate-semantics"
TEXT = {"type": "string", "minLength": 1, "pattern": r"\S"}
CARDINALITY = {"type": "string", "enum": ["single", "multiple"]}


def apply_predicate_contracts(schema):
    schemas = schema["components"]["schemas"]
    schemas["PredicateSemanticsRequest"] = _object({
        "namespace": TEXT, "predicate": TEXT, "cardinality": CARDINALITY,
    })
    schemas["PredicateSemantics"] = _object({
        "namespace": TEXT, "predicate": TEXT, "cardinality": CARDINALITY,
        "semantics": {"type": "string", "enum": ["exclusive_value", "set_membership"]},
    })
    schemas["PredicateSemanticsEnvelope"] = _object({
        "data": _ref("PredicateSemantics"), "request_id": {"type": "string"},
        "warnings": {"type": "array", "items": {"type": "string"}},
        "pagination": {"type": ["object", "null"]},
    }, required=["data", "request_id", "warnings"])
    for method in ("get", "post"):
        operation = schema["paths"][PATH][method]
        capability = "memory:read" if method == "get" else "memory:admin"
        operation.update(
            operationId="getPredicateSemantics" if method == "get" else "setPredicateSemantics",
            description=("Namespace-wide predicate declaration; explicit namespace required. Undeclared predicates "
                         "default to single/exclusive_value. Multiple means positive set membership, not negation "
                         "inference. Changes invalidate review snapshots but preserve existing disputes and "
                         "candidate review state. Project-only namespace grants are insufficient."),
        )
        operation["x-permissions"] = {
            "any_of": [capability, "memory:admin"], "all_of": [],
            "resource_policy": "Explicit authorized namespace; namespace-wide grants required.",
        }
        if method == "get":
            operation["parameters"] = [
                {"name": name, "in": "query", "required": True, "schema": TEXT}
                for name in ("namespace", "predicate")
            ]
        else:
            operation["requestBody"] = {
                "required": True,
                "content": {"application/json": {"schema": _ref("PredicateSemanticsRequest")}},
            }
        operation["responses"] = {
            str(status): {
                "description": "Success" if status == 200 else "Service error envelope",
                "content": {"application/json": {"schema": _ref(
                    "PredicateSemanticsEnvelope" if status == 200 else "ErrorEnvelope")}},
                "headers": {"Cache-Control": {"schema": {"const": "no-store"}},
                            "X-Request-ID": {"schema": {"type": "string"}}},
            }
            for status in (200, 400, 401, 403, 409, 413, 429, 500, 503)
        }
    return schema
