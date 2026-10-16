"""Issue #64: authenticated HTTP must query the operator-selected index."""
from dataclasses import replace
from types import SimpleNamespace

import pytest

from aletheia.models import ServiceConfig
from test_m6_memory_service import _service, _post, NAMESPACE
from test_v1_4_local_providers import provider_fixture


def configure(monkeypatch, url):
    for key, value in {'ENDPOINT': url + '/embed', 'MODEL': 'synthetic-nomic',
                       'DIMENSION': '3', 'LOCAL_ONLY': 'true',
                       'DOCUMENT_PREFIX': 'search_document: ',
                       'QUERY_PREFIX': 'search_query: '}.items():
        monkeypatch.setenv('ALETHEIA_EMBEDDING_OLLAMA_STYLE_' + key, value)


def remember(memory, value, namespace=NAMESPACE):
    return memory.remember(namespace=namespace, memory_type='preference', subject=value,
                           predicate='uses', object=value)


def retrieve(service, token, path='/v1/retrieve', **fields):
    status, body = _post(service, path, token, {'namespace': NAMESPACE, 'query': 'transport',
                                                       'mode': 'semantic', **fields})
    return SimpleNamespace(status_code=status, body=body)


def test_server_provider_configuration(tmp_path, monkeypatch):
    monkeypatch.delenv('ALETHEIA_SEMANTIC_PROVIDER', raising=False)
    assert ServiceConfig.load().semantic_provider == 'mock'
    config = tmp_path / 'service.toml'
    config.write_text('[server]\nsemantic_provider = "local_hash"\n')
    assert ServiceConfig.load(str(config)).semantic_provider == 'local_hash'
    monkeypatch.setenv('ALETHEIA_SEMANTIC_PROVIDER', 'ollama_style')
    assert ServiceConfig.load(str(config)).semantic_provider == 'ollama_style'
    assert ServiceConfig.load(str(config)).redacted()['server']['semantic_provider'] == 'ollama_style'
    assert ServiceConfig.load(overrides={'semantic_provider': 'mock'}).semantic_provider == 'mock'


@pytest.mark.parametrize('path', ['/v1/retrieve', '/v1/search'])
@pytest.mark.parametrize('mode', ['semantic', 'hybrid'])
def test_http_matches_sdk_and_preserves_governance(tmp_path, monkeypatch, path, mode):
    with provider_fixture() as (url, calls):
        configure(monkeypatch, url)
        service, token = _service(tmp_path)
        service.config = replace(service.config, semantic_provider='ollama_style')
        memory = service.memory
        try:
            original = remember(memory, 'synthetic canoe')
            other = remember(memory, 'synthetic balloon', 'agents/other')
            memory.index_semantic(NAMESPACE, provider='ollama_style')
            memory.index_semantic('agents/other', provider='ollama_style')
            sdk = memory.retrieve(NAMESPACE, 'transport', mode=mode, semantic_provider='ollama_style')
            before = len(calls)
            # Provider/endpoints in a request cannot override the operator's choice.
            response = retrieve(service, token, path, mode=mode, semantic_provider='openai_compatible')
            assert response.status_code == 200, response.body
            rows = response.body['data']
            assert [(r['claim_id'], r['semantic_score']) for r in rows] == [(r.claim_id, r.semantic_score) for r in sdk]
            assert rows[0]['semantic_score'] > 0
            assert rows[0]['semantic_status'] == 'indexed'
            assert calls[before:][0][1] == {'model': 'synthetic-nomic', 'input': ['search_query: transport']}
            assert other.id not in [r['claim_id'] for r in rows]
            before = len(calls)
            assert retrieve(service, token, path, namespace='agents/other').status_code == 403
            assert len(calls) == before
            replacement = remember(memory, 'synthetic glider')
            memory.supersede_claim(original.id, replacement.id, reason='synthetic correction')
            pending = retrieve(service, token, path, mode=mode)
            assert pending.status_code == 200, pending.body
            assert pending.body['data'][0]['claim_id'] == replacement.id
            assert pending.body['data'][0]['semantic_score'] == 0
            assert pending.body['data'][0]['semantic_status'] == 'unavailable'
            assert pending.body['data'][0]['retrieval_mode'] == 'lexical'
            memory.index_semantic(NAMESPACE, provider='ollama_style')
            updated = retrieve(service, token, path, mode=mode).body['data']
            assert [r['claim_id'] for r in updated] == [replacement.id]
            assert updated[0]['semantic_score'] > 0
            memory.forget(selector={'target_type': 'claim', 'target_id': replacement.id},
                          reason='synthetic cleanup', dry_run=False)
            assert retrieve(service, token, path, mode=mode).body['data'] == []
        finally:
            memory.close()


def test_default_fallback_and_lexical_do_not_call_external_provider(tmp_path, monkeypatch):
    with provider_fixture() as (url, calls):
        configure(monkeypatch, url)
        service, token = _service(tmp_path)
        try:
            remember(service.memory, 'synthetic transport')
            for mode in ['semantic', 'hybrid']:
                response = retrieve(service, token, mode=mode)
                assert response.status_code == 200
                assert response.body['data'][0]['retrieval_mode'] == 'lexical'
                assert response.body['data'][0]['semantic_status'] == 'unavailable'
            service.config = replace(service.config, semantic_provider='ollama_style')
            result = retrieve(service, token, mode='lexical').body['data'][0]
            assert result['semantic_status'] == 'not_requested'
            assert not calls
        finally:
            service.memory.close()


@pytest.mark.parametrize('key,value', [('DIMENSION', '4'), ('QUERY_PREFIX', 'different: '), ('MODEL', 'different')])
def test_http_incompatible_index_never_calls_provider(tmp_path, monkeypatch, key, value):
    with provider_fixture() as (url, calls):
        configure(monkeypatch, url)
        service, token = _service(tmp_path)
        service.config = replace(service.config, semantic_provider='ollama_style')
        try:
            remember(service.memory, 'synthetic transport')
            service.memory.index_semantic(NAMESPACE, provider='ollama_style')
            before = len(calls)
            monkeypatch.setenv('ALETHEIA_EMBEDDING_OLLAMA_STYLE_' + key, value)
            response = retrieve(service, token)
            assert response.status_code == 400, response.body
            assert len(calls) == before
        finally:
            service.memory.close()


def test_http_dimension_guard_without_prefix_and_privacy_ceiling(tmp_path, monkeypatch):
    with provider_fixture() as (url, calls):
        configure(monkeypatch, url)
        monkeypatch.delenv('ALETHEIA_EMBEDDING_OLLAMA_STYLE_DOCUMENT_PREFIX')
        monkeypatch.delenv('ALETHEIA_EMBEDDING_OLLAMA_STYLE_QUERY_PREFIX')
        service, token = _service(tmp_path, privacy_ceiling='public')
        service.config = replace(service.config, semantic_provider='ollama_style')
        try:
            remember(service.memory, 'synthetic personal transport')
            service.memory.index_semantic(NAMESPACE, provider='ollama_style')
            before = len(calls)
            response = retrieve(service, token)
            assert response.status_code == 200
            assert response.body['data'] == []
            assert len(calls) == before
            _, reader = service.auth.create_token(
                client_id=service.auth.create_client(name='synthetic reader', client_type='test').id,
                namespace_grants=[NAMESPACE], capabilities=['memory:read'], privacy_ceiling='personal')
            monkeypatch.setenv('ALETHEIA_EMBEDDING_OLLAMA_STYLE_DIMENSION', '4')
            assert retrieve(service, reader).status_code == 400
            assert len(calls) == before
        finally:
            service.memory.close()
