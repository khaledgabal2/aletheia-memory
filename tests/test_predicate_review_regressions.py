"""Regression coverage for predicate semantics and conflict review findings."""
import json
import re

import pytest
from openapi_spec_validator import validate

from aletheia import Memory
from aletheia.core.errors import ValidationError
from aletheia.models import ServiceConfig
from aletheia.service.http import AletheiaService, openapi_schema
from tests.test_sync_resolution_effects import pair, conflicting


@pytest.fixture
def memory(tmp_path):
    memory = Memory.open(str(tmp_path / 'review.db'), namespace='review/test')
    yield memory
    memory.close()


def remember(memory, value, **kwargs):
    return memory.remember(memory_type='preference', subject=kwargs.pop('subject', 'user'),
                           predicate=kwargs.pop('predicate', 'likes'), object=value, **kwargs)


def snapshot(memory):
    tables = ('claims', 'conflicts', 'conflict_families', 'conflict_family_claims',
              'conflict_claim_links', 'conflict_resolutions', 'claim_scopes', 'claim_status_history', 'audit_log')
    return {table: [tuple(row) for row in memory.store.connection.execute(f'SELECT * FROM {table}')]
            for table in tables}


def test_subsequent_single_values_join_existing_dispute(memory):
    claims = [remember(memory, value) for value in ('coffee', 'tea', 'water', 'juice', 'milk')]
    families = memory.list_conflict_families()
    assert len(families) == 1
    assert set(families[0].claim_ids) == {claim.id for claim in claims}
    assert all(memory.read_claim(claim.id).status == 'disputed' for claim in claims)
    assert memory.retrieve(subject='user', predicate='likes') == []
    assert len(memory.retrieve(subject='user', predicate='likes', include_disputed=True)) == 5
    memory.resolve_conflict(families[0].id, active_claim_id=claims[-1].id)
    assert [result.object for result in memory.retrieve(subject='user', predicate='likes')] == ['milk']


def test_case_variants_share_conflict_and_candidate_comparisons(memory):
    memory.set_predicate_semantics('home_city', cardinality='single')
    first = remember(memory, 'Paris', predicate='home_city')
    second = remember(memory, 'London', predicate='HOME_CITY', subject='USER')
    assert memory.read_claim(first.id).status == memory.read_claim(second.id).status == 'disputed'
    family, = memory.list_conflict_families()
    third = remember(memory, 'Berlin', predicate='Home_City')
    assert memory.list_conflict_families()[0].id == family.id
    assert set(memory.read_conflict_family(family.id).claim_ids) == {first.id, second.id, third.id}
    assert memory._candidate_contradiction_risk(namespace=memory.namespace, subject='USER',
                                               predicate='HOME_CITY', object='Rome') == .9


def test_object_normalization_is_shared(memory):
    remember(memory, '  CAFÉ  ')
    args = dict(namespace=memory.namespace, subject='USER', predicate='LIKES', object='café')
    assert memory._candidate_duplicate_risk(**args) == 1
    assert memory._candidate_contradiction_risk(**args) == 0


@pytest.mark.parametrize('strategy', ['context_scope', 'time_scope'])
def test_approved_scopes_survive_rescan_and_new_claims_still_conflict(memory, strategy):
    a, b = remember(memory, 'concise'), remember(memory, 'detailed')
    family, = memory.list_conflict_families()
    if strategy == 'context_scope':
        scopes = [{'claim_id': a.id, 'applies_when': 'progress_update'},
                  {'claim_id': b.id, 'applies_when': 'architecture_or_design_request'}]
    else:
        scopes = [{'claim_id': a.id, 'valid_to': '2026-01-01T00:00:00Z'},
                  {'claim_id': b.id, 'valid_from': '2026-01-01T00:00:00Z'}]
    memory.resolve_conflict(family.id, strategy=strategy, scoped_claims=scopes)
    assert memory.detect_conflicts() == []
    assert memory.detect_conflicts(claim_id=a.id) == []
    assert memory.read_claim(a.id).status == memory.read_claim(b.id).status == 'active'
    incoming = remember(memory, 'new unscoped preference')
    unresolved = memory.list_conflict_families(status='unresolved')
    assert len(unresolved) == 1
    assert set(unresolved[0].claim_ids) == {a.id, b.id, incoming.id}
    assert memory.read_claim(incoming.id).status == 'disputed'


def test_changed_scope_is_not_covered_by_an_old_approval(memory):
    a, b = remember(memory, 'concise'), remember(memory, 'detailed')
    family, = memory.list_conflict_families()
    memory.resolve_conflict(family.id, strategy='context_scope', scoped_claims=[
        {'claim_id': a.id, 'applies_when': 'progress_update'},
        {'claim_id': b.id, 'applies_when': 'architecture_or_design_request'}])
    memory.scope_claim(a.id, scope_type='contextual', applies_when='architecture_or_design_request', reason='broaden')
    memory.detect_conflicts()
    assert memory.read_claim(a.id).status == memory.read_claim(b.id).status == 'disputed'


@pytest.mark.parametrize('mode', ['supersede_winner', 'reject_winner', 'overlap', 'duplicate', 'partial', 'no_outcome'])
def test_invalid_resolution_is_atomic(memory, mode):
    a, b, c = [remember(memory, value) for value in ('coffee', 'tea', 'water')]
    family, = memory.list_conflict_families()
    payloads = {
        'supersede_winner': dict(active_claim_id=a.id, superseded_claim_ids=[a.id, b.id, c.id]),
        'reject_winner': dict(active_claim_id=a.id, rejected_claim_ids=[a.id, b.id, c.id]),
        'overlap': dict(active_claim_id=a.id, superseded_claim_ids=[b.id, c.id], rejected_claim_ids=[b.id]),
        'duplicate': dict(active_claim_id=a.id, superseded_claim_ids=[b.id, b.id, c.id]),
        'partial': dict(active_claim_id=a.id, superseded_claim_ids=[b.id]),
        'no_outcome': {},
    }
    before = snapshot(memory)
    with pytest.raises(ValidationError):
        memory.resolve_conflict(family.id, **payloads[mode])
    assert snapshot(memory) == before


def test_coexist_is_explicit_and_only_for_multivalued_properties(memory):
    a, b = remember(memory, 'coffee'), remember(memory, 'tea')
    family, = memory.list_conflict_families()
    with pytest.raises(ValidationError, match='multivalued'):
        memory.resolve_conflict(family.id, strategy='coexist')
    memory.set_predicate_semantics('likes', cardinality='multiple')
    memory.resolve_conflict(family.id, strategy='coexist', note='both are positive memberships')
    assert memory.read_claim(a.id).status == memory.read_claim(b.id).status == 'active'
    assert len(memory.retrieve(subject='user', predicate='likes')) == 2
    assert not memory.detect_conflicts()


def credential(service, *, project_only=False, privacy='personal'):
    client = service.auth.create_client(name='Synthetic review regression', client_type='test')
    _, raw = service.auth.create_token(client_id=client.id, capabilities=['memory:review', 'memory:read'],
        namespace_grants=[service.memory.namespace + ('/projects/public' if project_only else '')],
        privacy_ceiling=privacy)
    return {'Authorization': 'Bearer ' + raw}


@pytest.mark.parametrize('project_only', [False, True])
def test_http_detection_cannot_mutate_or_expose_hidden_sources(memory, project_only):
    memory.set_predicate_semantics('secret_property', cardinality='multiple')
    claims = [remember(memory, value, predicate='secret_property', privacy_level='secret') for value in ('a', 'b')]
    memory.set_predicate_semantics('secret_property', cardinality='single')
    memory.set_predicate_semantics('public_property', cardinality='multiple')
    public = [remember(memory, value, predicate='public_property') for value in ('public-a', 'public-b')]
    memory.set_predicate_semantics('public_property', cardinality='single')
    service = AletheiaService(memory, ServiceConfig(db_path=memory.store.path, rate_limit_enabled=False))
    headers = credential(service, project_only=project_only)
    before = snapshot(memory)
    status, response = service.handle_http(method='POST', path='/v1/conflicts/detect', headers=headers,
        body=json.dumps({'namespace': memory.namespace, 'project_id': 'public'}).encode())
    assert status == 403, response
    assert snapshot(memory) == before
    assert all(memory.read_claim(claim.id).status == 'active' for claim in [*claims, *public])


def test_detection_filters_readonly_results_and_preflights_only_selected_group(memory):
    for value in ('a', 'b'):
        remember(memory, value, subject='secret-subject', predicate='secret_property', privacy_level='secret')
    public = remember(memory, 'coffee')
    service = AletheiaService(memory, ServiceConfig(db_path=memory.store.path, rate_limit_enabled=False))
    headers = credential(service)
    before = snapshot(memory)
    status, response = service.handle_http(method='POST', path='/v1/conflicts/detect', headers=headers,
        body=json.dumps({'namespace': memory.namespace, 'create': False}).encode())
    assert status == 200 and response['data'] == []
    assert snapshot(memory) == before
    status, response = service.handle_http(method='POST', path='/v1/conflicts/detect', headers=headers,
        body=json.dumps({'namespace': memory.namespace, 'claim_id': public.id}).encode())
    assert status == 200 and response['data'] == []


def test_fully_authorized_detection_remains_available(memory):
    memory.set_predicate_semantics('likes', cardinality='multiple')
    claims = [remember(memory, value, privacy_level='secret') for value in ('coffee', 'tea')]
    memory.set_predicate_semantics('likes', cardinality='single')
    service = AletheiaService(memory, ServiceConfig(db_path=memory.store.path, rate_limit_enabled=False))
    status, body = service.handle_http(method='POST', path='/v1/conflicts/detect',
        headers=credential(service, privacy='secret'), body=json.dumps({'namespace': memory.namespace}).encode())
    assert status == 200, body
    assert set(body['data'][0]['claim_ids']) == {claim.id for claim in claims}


@pytest.mark.parametrize('imported_first', [False, True])
def test_existing_sync_conflict_retains_both_members_when_declared_multiple(pair, imported_first):
    memory, local, conflict, source = conflicting(pair, imported_first=imported_first, active=imported_first)
    memory.set_predicate_semantics('has', cardinality='multiple')
    receipt = memory.resolve_sync_conflict(conflict.id, strategy='accept_remote_active', reason='compatible memberships')
    assert receipt.metadata['postconditions_verified']
    assert memory.read_claim(local.id).status == 'active'
    assert {result.object for result in memory.retrieve(query='syncneedle')} == {'local choice', 'remote choice'}
    assert not any(item.relationship_type == 'supersedes' for item in memory.list_claim_relationships(local.id))


@pytest.mark.parametrize('policy', ['trusted_device', 'candidate_only'])
def test_federation_obeys_receiving_multivalued_declaration(pair, policy):
    left, right, _ = pair
    left.set_predicate_semantics('has', cardinality='multiple')
    right.set_predicate_semantics('has', cardinality='multiple')
    local = right.remember(memory_type='project', subject='syncneedle', predicate='HAS', object='local choice')
    # The fixture bundle contains the remote value and no replicated declarations.
    right.import_share_bundle(input_path=str(pair[2]), trust_policy=policy)
    assert not right.list_sync_conflicts(status='unresolved')
    if policy == 'candidate_only':
        candidate, = right.list_candidates(right.namespace)
        right.promote_candidate(candidate.id, reason='compatible membership')
    assert right.read_claim(local.id).status == 'active'
    assert {result.object for result in right.retrieve(query='syncneedle')} == {'local choice', 'remote choice'}


def test_complete_openapi_and_every_uri_parameter_are_valid():
    document = openapi_schema()
    validate(document)
    for path, operations in document['paths'].items():
        for operation in operations.values():
            declared = {item['name'] for item in operation.get('parameters', [])
                        if item.get('in') == 'path' and item.get('required') is True}
            assert set(re.findall(r'\{([^}]+)\}', path)) <= declared


@pytest.mark.parametrize('strategy,scopes', [
    ('context_scope', [{'applies_when': 'progress'}, {'applies_when': 'PROGRESS'}]),
    ('time_scope', [{'valid_from': '2026-01-01'}, {'valid_from': '2026-02-01'}]),
])
def test_scope_resolution_refuses_overlapping_values_atomically(memory, strategy, scopes):
    a, b = remember(memory, 'coffee'), remember(memory, 'tea')
    family, = memory.list_conflict_families()
    before = snapshot(memory)
    with pytest.raises(ValidationError, match='distinct contexts|nonoverlapping'):
        memory.resolve_conflict(family.id, strategy=strategy,
                                scoped_claims=[{'claim_id': claim.id, **scope} for claim, scope in zip((a, b), scopes)])
    assert snapshot(memory) == before


@pytest.mark.parametrize('field,value', [
    ('superseded_claim_ids', 'not-a-list'), ('rejected_claim_ids', [{}]),
    ('scoped_claims', {'claim_id': 'not-a-list'}), ('scoped_claims', ['not-an-object']),
    ('strategy', []),
])
def test_http_malformed_resolution_returns_400_without_mutation(memory, field, value):
    remember(memory, 'coffee')
    remember(memory, 'tea')
    family, = memory.list_conflict_families()
    service = AletheiaService(memory, ServiceConfig(db_path=memory.store.path, rate_limit_enabled=False))
    headers = credential(service)
    before = snapshot(memory)
    status, response = service.handle_http(method='POST', path=f'/v1/conflicts/{family.id}/resolve',
        headers=headers, body=json.dumps({field: value}).encode())
    assert status == 400, response
    assert snapshot(memory) == before


def test_detection_receipt_rechecks_current_source_privacy(memory):
    memory.set_predicate_semantics('likes', cardinality='multiple')
    a, b = remember(memory, 'coffee'), remember(memory, 'tea')
    memory.set_predicate_semantics('likes', cardinality='single')
    service = AletheiaService(memory, ServiceConfig(db_path=memory.store.path, rate_limit_enabled=False))
    headers = {**credential(service), 'Idempotency-Key': 'detect-operation'}
    fields = dict(method='POST', path='/v1/conflicts/detect', headers=headers,
                  body=json.dumps({'namespace': memory.namespace}).encode())
    assert service.handle_http(**fields)[0] == 200
    memory.store.connection.execute('UPDATE evidence_events SET privacy_level=? WHERE id=?', ('secret', a.evidence_ids[0]))
    before = snapshot(memory)
    assert service.handle_http(**fields)[0] == 403
    assert snapshot(memory) == before


def test_concurrent_assertions_do_not_escape_conflict_detection(memory):
    from concurrent.futures import ThreadPoolExecutor
    import threading

    other = Memory.open(memory.store.path, namespace=memory.namespace)
    barrier = threading.Barrier(2)
    def write(store, value):
        barrier.wait(timeout=5)
        return remember(store, value).id
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            a = pool.submit(write, memory, 'coffee')
            b = pool.submit(write, other, 'tea')
            ids = {a.result(timeout=10), b.result(timeout=10)}
        family, = memory.list_conflict_families()
        assert set(family.claim_ids) == ids
        assert all(memory.read_claim(claim_id).status == 'disputed' for claim_id in ids)
        assert memory.retrieve(subject='user', predicate='likes') == []
    finally:
        other.close()


def test_conflict_http_responses_match_published_schemas(memory):
    from jsonschema import Draft202012Validator

    memory.set_predicate_semantics('likes', cardinality='multiple')
    remember(memory, 'coffee')
    remember(memory, 'tea')
    memory.set_predicate_semantics('likes', cardinality='single')
    service = AletheiaService(memory, ServiceConfig(db_path=memory.store.path, rate_limit_enabled=False))
    headers = credential(service)
    document = openapi_schema()
    def request(path, payload, *, template=None):
        status, body = service.handle_http(method='POST', path=path, headers=headers,
                                           body=json.dumps(payload).encode())
        shape = document['paths'][template or path]['post']['responses'][str(status)]['content']['application/json']['schema']
        Draft202012Validator({**shape, 'components': document['components']}).validate(body)
        return status, body
    status, body = request('/v1/conflicts/detect', {'namespace': memory.namespace})
    assert status == 200
    family, = body['data']
    status, body = request(f"/v1/conflicts/{family['id']}/resolve", {}, template='/v1/conflicts/{conflict_id}/resolve')
    assert status == 400
    status, body = request(f"/v1/conflicts/{family['id']}/resolve", {'active_claim_id': family['claim_ids'][0]},
                           template='/v1/conflicts/{conflict_id}/resolve')
    assert status == 200
    assert body['data']['status'] == 'resolved'


@pytest.mark.parametrize('strategy', ['manual', 'latest_wins', 'reject_weak_claims'])
def test_strategy_defaults_cannot_hide_an_explicit_invalid_outcome(memory, strategy):
    a, b = remember(memory, 'coffee'), remember(memory, 'tea')
    family, = memory.list_conflict_families()
    before = snapshot(memory)
    with pytest.raises(ValidationError, match='active claim'):
        memory.resolve_conflict(family.id, strategy=strategy, active_claim_id=a.id, rejected_claim_ids=[a.id])
    assert snapshot(memory) == before
