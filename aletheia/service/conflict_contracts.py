"""Published conflict governance contracts and namespace-wide detection policy."""
from aletheia.core.memory import RESOLUTION_STRATEGIES
from aletheia.service.contracts import _object, _ref

TEXT = {"type": "string"}
NULL_TEXT = {"type": ["string", "null"]}
IDS = {"type": "array", "items": TEXT, "uniqueItems": True}
SCOPES = {"type": "array", "items": {"type": "object", "additionalProperties": True}}


def apply_conflict_contracts(schema):
    schemas = schema['components']['schemas']
    schemas['DetectConflictsRequest'] = _object({
        'namespace': NULL_TEXT, 'subject': NULL_TEXT, 'predicate': NULL_TEXT, 'claim_id': NULL_TEXT,
        'include_resolved': {'type': 'boolean', 'default': False},
        'create': {'type': 'boolean', 'default': True},
        'project_id': {**NULL_TEXT, 'description': 'Legacy label only; never narrows namespace-wide authorization.'},
    }, required=[], additional=True)
    schemas['ResolveConflictRequest'] = _object({
        'strategy': {'type': 'string', 'enum': sorted(RESOLUTION_STRATEGIES), 'default': 'manual'},
        'active_claim_id': NULL_TEXT, 'superseded_claim_ids': IDS, 'rejected_claim_ids': IDS,
        'scoped_claims': SCOPES, 'note': NULL_TEXT,
    }, required=[], additional=True)
    schemas['ConflictResolution'] = _object({
        **{name: TEXT for name in ('id', 'namespace', 'conflict_id', 'strategy', 'note', 'created_at', 'status')},
        'active_claim_id': NULL_TEXT, 'superseded_claim_ids': IDS, 'rejected_claim_ids': IDS, 'scoped_claims': SCOPES,
    })
    for name, result in (
        ('ConflictFamilies', {'type': 'array', 'items': _ref('ConflictFamily')}),
        ('ConflictResolution', _ref('ConflictResolution')),
    ):
        schemas[name + 'Envelope'] = _object({
            'data': result, 'request_id': TEXT, 'warnings': {'type': 'array', 'items': TEXT},
            'pagination': {'type': ['object', 'null']},
        }, required=['data', 'request_id', 'warnings'])
    detect = schema['paths']['/v1/conflicts/detect']['post']
    detect.update(operationId='detectConflicts', description=(
        'Requires memory:review (or admin) with namespace-wide access. Project-only grants are insufficient. '
        'Before creation, every selected active/core/disputed claim and its provenance must be visible; '
        'otherwise 403 without conflict mutations. Returned families are visibility-filtered. '
        'Subject/predicate filters compare ASCII case-insensitively; claim_id selects its property group. '
        'Existing unresolved disputes include subsequent values. Approved unchanged contextual/temporal '
        'resolutions survive rescans. create=false only returns existing visible families.'))
    resolve = schema['paths']['/v1/conflicts/{conflict_id}/resolve']['post']
    resolve.update(operationId='resolveConflict', description=(
        'Requires review capability and visibility of all family members. Outcomes must be unique, disjoint '
        'and complete before a family is resolved. The winner cannot be superseded/rejected. Invalid decisions '
        'return 400 without mutations. coexist requires a multivalued declaration and restores every member '
        'without selecting an exclusive winner; scope resolutions require every member in the same decision.'))
    for operation, request, result in ((detect, 'DetectConflictsRequest', 'ConflictFamiliesEnvelope'),
                                       (resolve, 'ResolveConflictRequest', 'ConflictResolutionEnvelope')):
        operation['x-permissions'] = {
            'any_of': ['memory:review', 'memory:admin'], 'all_of': [],
            'resource_policy': operation['description'],
        }
        operation['requestBody'] = {'required': True, 'content': {'application/json': {'schema': _ref(request)}}}
        operation['responses'] = {
            str(status): {'description': 'Success' if status == 200 else 'Service error envelope',
                          'content': {'application/json': {'schema': _ref(result if status == 200 else 'ErrorEnvelope')}}}
            for status in (200, 400, 401, 403, 409, 413, 429, 500, 503)
        }
    return schema
