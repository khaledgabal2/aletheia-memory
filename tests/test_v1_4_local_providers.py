"""Model-free transport/preset guards; real inference has a separate opt-in gate."""
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import threading

import pytest

from aletheia import Memory
from aletheia.core.errors import ValidationError
from aletheia.extraction import LLMExtractor
from aletheia.llm import HTTPLLMProvider
from aletheia.semantic import HTTPEmbeddingProvider


@contextmanager
def provider_fixture():
    calls = []
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass
        def do_POST(self):
            payload = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            calls.append((self.path, payload))
            if self.path == '/redirect':
                self.send_response(302)
                self.send_header('Location', '/forbidden-target')
                self.end_headers()
                return
            body = {'embeddings': [[1.0, 0.0, 0.5] for _ in payload.get('input', [])]}
            if self.path == '/chat':
                body = {'message': {'content': json.dumps({'candidates': []})}}
            if self.path == '/malformed':
                body = {'embeddings': [[float('nan')]]}
            raw = json.dumps(body).encode()
            self.send_response(200)
            self.send_header('Content-Length', str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f'http://127.0.0.1:{server.server_port}', calls
    finally:
        server.shutdown()
        thread.join(5)
        server.server_close()


@pytest.mark.parametrize('endpoint', ['https://example.com:443/api', 'http://localhost:11434/api',
    'http://127.0.0.1/api', 'http://user:pass@127.0.0.1:1234/api', 'http://192.0.2.1:1234/api'])
def test_explicit_local_only_mode_refuses_nonliteral_or_credentialed_endpoints(endpoint):
    with pytest.raises(ValueError, match='loopback'):
        HTTPEmbeddingProvider(name='test', provider_type='ollama_style', endpoint=endpoint, model='local', dimension=3, local_only=True)
    with pytest.raises(ValueError, match='loopback'):
        HTTPLLMProvider(name='test', provider_type='ollama_style', endpoint=endpoint, model='local', local_only=True)


def test_local_provider_bypasses_proxy_rejects_redirects_and_bounds_output(monkeypatch):
    with provider_fixture() as (url, calls):
        monkeypatch.setenv('http_proxy', 'http://127.0.0.1:1')
        monkeypatch.setenv('HTTP_PROXY', 'http://127.0.0.1:1')
        monkeypatch.setenv('no_proxy', '')
        engine = HTTPEmbeddingProvider(name='test', provider_type='ollama_style', endpoint=url+'/embed', model='local',
            dimension=3, document_prefix='search_document: ', query_prefix='search_query: ', local_only=True)
        assert engine.embed_texts(['source']) == [[1., 0., .5]]
        engine.embed_texts(['question'], purpose='semantic_query')
        assert calls[0][1]['input'] == ['search_document: source']
        assert calls[1][1]['input'] == ['search_query: question']
        engine.endpoint = url+'/redirect'
        with pytest.raises(ValueError):
            engine.embed_texts(['safe synthetic input'])
        assert not any(path == '/forbidden-target' for path, _ in calls)
        engine.endpoint = url+'/malformed'
        with pytest.raises(ValueError, match='non-finite'):
            engine.embed_texts(['safe'])


def test_ollama_structured_recipe_sends_schema_budget_and_non_thinking_option():
    with provider_fixture() as (url, calls):
        engine = HTTPLLMProvider(name='test', provider_type='ollama_style', endpoint=url+'/chat', model='local',
            local_only=True, structured_output=True, thinking=False, context_length=4096, keep_alive=0)
        schema = {'type': 'object', 'required': ['candidates']}
        assert engine.complete_json(messages=[{'role':'user','content':'Synthetic input'}],schema=schema,temperature=0.,max_tokens=128) == {'candidates':[]}
        sent = calls[0][1]
        assert sent['format'] == schema and sent['think'] is False and sent['keep_alive'] == 0
        assert sent['options'] == {'temperature':0.,'num_predict':128,'num_ctx':4096}


def test_input_preset_changes_require_reindex_and_cannot_silently_reuse_old_dimensions(tmp_path, monkeypatch):
    with provider_fixture() as (url, calls):
        for key, value in {'ENDPOINT':url+'/embed','MODEL':'test-local','DIMENSION':'3','LOCAL_ONLY':'true',
                           'DOCUMENT_PREFIX':'search_document: ','QUERY_PREFIX':'search_query: ','MODEL_REVISION':'test-digest'}.items():
            monkeypatch.setenv('ALETHEIA_EMBEDDING_OLLAMA_STYLE_'+key, value)
        memory = Memory.open(str(tmp_path/'preset.db'))
        try:
            namespace='user/preset'
            memory.remember(namespace=namespace,memory_type='preference',subject='user',predicate='prefers',object='architecture')
            memory.index_semantic(namespace,provider='ollama_style')
            assert memory.retrieve(namespace,'architecture',mode='semantic',semantic_provider='ollama_style')
            before = len(calls)
            monkeypatch.setenv('ALETHEIA_EMBEDDING_OLLAMA_STYLE_DIMENSION','4')
            with pytest.raises(ValidationError,match='reindex'):
                memory.retrieve(namespace,'architecture',mode='semantic',semantic_provider='ollama_style')
            assert len(calls) == before
            monkeypatch.setenv('ALETHEIA_EMBEDDING_OLLAMA_STYLE_DIMENSION','3')
            monkeypatch.setenv('ALETHEIA_EMBEDDING_OLLAMA_STYLE_QUERY_PREFIX','changed: ')
            with pytest.raises(ValidationError,match='reindex'):
                memory.retrieve(namespace,'architecture',mode='semantic',semantic_provider='ollama_style')
            assert memory.index_semantic(namespace,provider='ollama_style').stale_count == 1
            assert memory.retrieve(namespace,'architecture',mode='semantic',semantic_provider='ollama_style')
            for key in ['DOCUMENT_PREFIX','QUERY_PREFIX','MODEL_REVISION']:
                monkeypatch.delenv('ALETHEIA_EMBEDDING_OLLAMA_STYLE_'+key)
            with pytest.raises(ValidationError,match='reindex'):
                memory.retrieve(namespace,'architecture',mode='semantic',semantic_provider='ollama_style')
        finally:
            memory.close()
