"""Every SDK request facade against real handlers and the independent OpenAPI.

This qualifies routing, typed errors and unprivileged mutation refusal. Positive
domain workflows live in the milestone, review, federation and live-model tests.
Transport is in-process here; socket and installed artifacts have separate runs.
"""
import asyncio
from contextlib import closing
import inspect
import json
import re
from urllib.parse import urlsplit

import pytest

from aletheia import Memory
from aletheia.client import AletheiaClient, AsyncAletheiaClient, AletheiaClientError
from aletheia.models import ServiceConfig
from aletheia.service.http import AletheiaService, openapi_schema


METHODS = [(kind, name) for kind, cls in [('sync', AletheiaClient), ('async', AsyncAletheiaClient)]
           for name, method in inspect.getmembers(cls, inspect.isfunction) if not name.startswith('_')]


def test_async_pagination_and_envelope_follow_real_response_then_clear_on_health(tmp_path):
    from scripts.v1_4_phase0 import local_service, NAMESPACE
    with local_service(tmp_path) as (service, url, tokens):
        for text in ['User prefers concise notes.', 'User prefers careful reviews.']:
            batch = service.memory.ingest(NAMESPACE, source_type='manual', content=text)
            service.memory.extract_candidates(NAMESPACE, batch_id=batch.id)
        client = AsyncAletheiaClient(url, tokens['reviewer'])
        async def run():
            rows = await client.list_candidates_for_review(namespace=NAMESPACE, limit=1)
            assert len(rows) == 1
            assert client.last_pagination['next_cursor']
            assert client.last_envelope['data'] == rows
            first_id = client.last_request_id
            await client.health()
            assert client.last_request_id != first_id
            assert client.last_pagination is None
            assert 'schema_version' in client.last_envelope['data']
        asyncio.run(run())


@pytest.mark.parametrize('kind,name', METHODS)
def test_sdk_request_has_declared_route_and_cannot_mutate_without_permission(tmp_path, kind, name):
    with closing(Memory.open(str(tmp_path / 'sdk.db'), namespace='sdk/surface')) as m:
        service = AletheiaService(m, ServiceConfig(db_path=m.store.path, rate_limit_enabled=False,
            local_pairing_enabled=False, advertise_local=False))
        identity = service.auth.create_client(name='Synthetic read-only SDK probe', client_type='test')
        _, token = service.auth.create_token(client_id=identity.id, namespace_grants=[m.namespace],
            capabilities=['memory:read'], privacy_ceiling='personal')
        client = AletheiaClient('http://in-process.invalid', token) if kind == 'sync' else AsyncAletheiaClient('http://in-process.invalid', token)
        sync = client if kind == 'sync' else client._sync
        observed = []
        paths = openapi_schema()['paths']

        def transport(method, path, payload=None, **kwargs):
            route = urlsplit(path).path
            matched = [template for template, operations in paths.items()
                       if re.fullmatch(re.sub(r'\{[^}]+\}', '[^/]+', template), route)
                       and method.lower() in operations]
            assert matched, f'Undeclared SDK route: {method} {route}'
            status, envelope = service.handle_http(method=method, path=path,
                headers={'Authorization': f'Bearer {token}'},
                body=json.dumps(payload).encode() if payload is not None else b'')
            observed.append((method, status))
            assert status < 500, envelope
            if status >= 400:
                raise AletheiaClientError(envelope['error']['message'], code=envelope['error']['code'], status_code=status)
            return envelope['data']

        sync._request = transport
        method = getattr(client, name)
        values = {'namespace': m.namespace, 'target_type': 'claim', 'target_id': 'missing',
                  'display_name': 'Synthetic read-only probe', 'reason': 'Synthetic permission probe',
                  'action': 'promote', 'expected_revision': 'missing', 'idempotency_key': 'synthetic-operation',
                  'suite': 'kernel', 'recovery_path': str(tmp_path / 'must-not-write.json')}
        kwargs = {p.name: values.get(p.name, 'missing') for p in inspect.signature(getattr(sync, name)).parameters.values()
                  if p.default is p.empty and p.kind not in (p.VAR_KEYWORD, p.VAR_POSITIONAL)}
        try:
            result = method(**kwargs)
            if inspect.isawaitable(result):
                asyncio.run(result)
        except AletheiaClientError as error:
            assert error.status_code in {400, 401, 403, 404, 409, 412, 422}, (name, error)
        assert observed, f'{name} did not reach a handler'
        assert not m.list_claims(namespace=m.namespace)
        assert not m.list_candidates(m.namespace)
        assert not (tmp_path / 'must-not-write.json').exists()
