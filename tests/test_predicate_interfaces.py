"""Predicate configuration across HTTP, CLI and both Python SDKs."""
import asyncio
import json
from urllib.parse import urlencode

import pytest
from jsonschema import Draft202012Validator
from openapi_spec_validator import validate

from aletheia import Memory
from aletheia.cli.main import main
from aletheia.client import AletheiaClient, AsyncAletheiaClient, AletheiaForbiddenError
from aletheia.models import ServiceConfig
from aletheia.service.http import AletheiaService, openapi_schema
from scripts.v1_4_phase0 import local_service, request, NAMESPACE

PATH = '/v1/predicate-semantics'


def token(service, capabilities, grants=None):
    client = service.auth.create_client(name='Predicate test', client_type='test')
    return service.auth.create_token(client_id=client.id, capabilities=capabilities,
                                     namespace_grants=grants or [NAMESPACE])


@pytest.fixture
def service(tmp_path):
    memory = Memory.open(str(tmp_path / 'predicates.db'), namespace=NAMESPACE)
    service = AletheiaService(memory, ServiceConfig(db_path=memory.store.path, rate_limit_enabled=False))
    yield service
    service.close()


def call(service, raw, method, fields, *, key=None):
    path = PATH + ('?' + urlencode(fields, doseq=True) if method == 'GET' else '')
    headers = {'Authorization': f'Bearer {raw}'} if raw else {}
    if key:
        headers['Idempotency-Key'] = key
    return service.handle_http(method=method, path=path, headers=headers,
                               body=json.dumps(fields).encode() if method == 'POST' else b'')


def conform(method, status, body):
    document = openapi_schema()
    shape = document['paths'][PATH][method.lower()]['responses'][str(status)]['content']['application/json']['schema']
    Draft202012Validator({**shape, 'components': document['components']}).validate(body)


@pytest.mark.parametrize('capabilities,grants,method,expected', [
    (['memory:read'], [NAMESPACE], 'GET', 200),
    (['memory:read'], [NAMESPACE], 'POST', 403),
    (['memory:review'], [NAMESPACE], 'POST', 403),
    (['memory:write_active'], [NAMESPACE], 'POST', 403),
    (['memory:admin'], ['other'], 'POST', 403),
    (['memory:admin'], [NAMESPACE + '/projects/demo'], 'POST', 403),
    (['memory:read'], [NAMESPACE + '/projects/demo'], 'GET', 403),
    (['memory:read'], ['other'], 'GET', 403),
    (['memory:admin'], [NAMESPACE], 'POST', 200),
])
def test_http_permissions_and_namespace_scope(service, capabilities, grants, method, expected):
    _, raw = token(service, capabilities, grants)
    fields = {'namespace': NAMESPACE, 'predicate': 'likes'}
    if method == 'POST':
        fields['cardinality'] = 'multiple'
    status, body = call(service, raw, method, fields)
    assert status == expected, body
    conform(method, status, body)
    assert service.memory.get_predicate_semantics('likes')['cardinality'] == (
        'multiple' if expected == 200 and method == 'POST' else 'single')


@pytest.mark.parametrize('patch', [
    {'namespace': None}, {'namespace': []}, {'namespace': ' '},
    {'predicate': ''}, {'predicate': []}, {'predicate': ' '},
    {'cardinality': 'many'}, {'cardinality': []}, {'cardinality': None},
    {'project_id': 'demo'}, {'extra': True},
])
def test_invalid_http_writes_do_not_change_semantics(service, patch):
    _, raw = token(service, ['memory:admin'])
    status, body = call(service, raw, 'POST', {
        'namespace': NAMESPACE, 'predicate': 'likes', 'cardinality': 'multiple', **patch})
    assert status == 400, body
    conform('POST', status, body)
    assert service.memory.get_predicate_semantics('likes')['cardinality'] == 'single'


@pytest.mark.parametrize('fields', [
    {}, {'namespace': NAMESPACE}, {'predicate': 'likes'},
    {'namespace': NAMESPACE, 'predicate': ' '},
    {'namespace': NAMESPACE, 'predicate': ['likes', 'home_city']},
    {'namespace': NAMESPACE, 'predicate': 'likes', 'project_id': 'demo'},
    {'namespace': NAMESPACE, 'predicate': 'likes', 'extra': ''},
])
def test_invalid_http_reads(service, fields):
    _, raw = token(service, ['memory:read'])
    status, body = call(service, raw, 'GET', fields)
    assert status == 400, body
    conform('GET', status, body)


def test_http_idempotency_and_changed_authority(service):
    item, raw = token(service, ['memory:admin'])
    fields = {'namespace': NAMESPACE, 'predicate': 'likes', 'cardinality': 'multiple'}
    first = call(service, raw, 'POST', fields, key='predicate-operation')
    assert first[0] == 200
    epoch = service.memory.store.connection.execute('SELECT epoch FROM review_state').fetchone()[0]
    assert call(service, raw, 'POST', fields, key='predicate-operation') == first
    assert service.memory.store.connection.execute('SELECT epoch FROM review_state').fetchone()[0] == epoch
    assert call(service, raw, 'POST', {**fields, 'cardinality': 'single'}, key='predicate-operation')[0] == 409
    service.memory.store.connection.execute('DELETE FROM namespace_access_grants WHERE token_id=?', (item.id,))
    assert call(service, raw, 'POST', fields, key='predicate-operation')[0] == 403


def test_unauthenticated_requests_rejected(service):
    for method in ('GET', 'POST'):
        assert call(service, None, method, {'namespace': NAMESPACE, 'predicate': 'likes',
                                           **({'cardinality': 'multiple'} if method == 'POST' else {})})[0] == 401


def test_openapi_contract():
    document = openapi_schema()
    validate(document)
    operation = document['paths'][PATH]
    assert operation['get']['operationId'] == 'getPredicateSemantics'
    assert operation['post']['x-required-capability'] == 'memory:admin'


def test_live_http_and_sync_async_sdks(tmp_path):
    with local_service(tmp_path) as (service, url, tokens):
        _, admin = token(service, ['memory:admin'])
        client = AletheiaClient(url, admin)
        predicate = 'likes / tea? & coffee+#'
        assert client.get_predicate_semantics(predicate, namespace=NAMESPACE)['cardinality'] == 'single'
        declaration = client.set_predicate_semantics(predicate, namespace=NAMESPACE,
                                                      cardinality='multiple', idempotency_key='sync-declare')
        assert declaration['semantics'] == 'set_membership'
        result = request(url, 'GET', PATH + '?' + urlencode({'namespace': NAMESPACE, 'predicate': predicate}),
                         token=tokens['reader'])
        assert result['status'] == 200
        assert result['body']['data'] == declaration
        assert result['headers']['Cache-Control'] == 'no-store'
        conform('GET', 200, result['body'])
        post = request(url, 'POST', PATH, token=admin,
                       payload={'namespace': NAMESPACE, 'predicate': 'likes', 'cardinality': 'multiple'})
        assert post['status'] == 200
        assert post['headers']['Cache-Control'] == 'no-store'
        conform('POST', 200, post['body'])
        for value in ('coffee', 'tea'):
            client.remember_active(namespace=NAMESPACE, subject='user', predicate='likes',
                                   object=value, memory_type='preference')
        hits = client.retrieve(namespace=NAMESPACE, query='user likes', mode='lexical')
        assert len(hits) == 2
        assert not service.memory.list_conflicts(namespace=NAMESPACE)
        client.set_predicate_semantics('home_city', namespace=NAMESPACE, cardinality='single')
        for value in ('Paris', 'London'):
            client.remember_active(namespace=NAMESPACE, subject='user', predicate='home_city',
                                   object=value, memory_type='fact')
        assert len(service.memory.list_conflicts(namespace=NAMESPACE)) == 1
        assert client.retrieve(namespace=NAMESPACE, query='home_city', mode='lexical') == []
        assert len(client.retrieve(namespace=NAMESPACE, query='home_city', mode='lexical',
                                   include_disputed=True)) == 2
        reader = AletheiaClient(url, tokens['reader'])
        with pytest.raises(AletheiaForbiddenError):
            reader.set_predicate_semantics('likes', namespace=NAMESPACE, cardinality='single')

        async def run():
            async_client = AsyncAletheiaClient(url, admin)
            assert await async_client.get_predicate_semantics(predicate, namespace=NAMESPACE) == declaration
            changed = await async_client.set_predicate_semantics(
                predicate, namespace=NAMESPACE, cardinality='single', idempotency_key='async-declare')
            assert changed['semantics'] == 'exclusive_value'
            assert (await async_client.get_predicate_semantics(predicate, namespace=NAMESPACE)) == changed
            denied = AsyncAletheiaClient(url, tokens['reader'])
            with pytest.raises(AletheiaForbiddenError):
                await denied.set_predicate_semantics('likes', namespace=NAMESPACE, cardinality='single')
        asyncio.run(run())


def test_cli_get_set_and_ordinary_recall(tmp_path, capsys):
    db = str(tmp_path / 'cli.db')
    options = ['--db', db, '--namespace', NAMESPACE]
    assert main(['predicates', 'get', 'likes', *options, '--json']) == 0
    assert json.loads(capsys.readouterr().out)['cardinality'] == 'single'
    assert main(['predicates', 'set', 'likes', '--cardinality', 'multiple', *options, '--json']) == 0
    assert json.loads(capsys.readouterr().out)['semantics'] == 'set_membership'
    assert main(['predicates', 'get', 'likes', *options]) == 0
    assert 'multiple (set_membership)' in capsys.readouterr().out
    for value in ('coffee', 'tea'):
        assert main(['remember', '--type', 'preference', '--subject', 'user',
                     '--predicate', 'likes', '--object', value, *options]) == 0
    capsys.readouterr()
    with_memory = Memory.open(db, namespace=NAMESPACE)
    try:
        assert len(with_memory.retrieve(subject='user', predicate='likes')) == 2
        assert with_memory.get_predicate_semantics('likes', namespace='other')['cardinality'] == 'single'
    finally:
        with_memory.close()
    assert main(['predicates', 'set', 'home_city', '--cardinality', 'single', *options]) == 0
    assert 'single (exclusive_value)' in capsys.readouterr().out


def test_cli_rejects_invalid_cardinality(tmp_path):
    with pytest.raises(SystemExit) as error:
        main(['predicates', 'set', 'likes', '--cardinality', 'many', '--db', str(tmp_path / 'no.db')])
    assert error.value.code == 2
