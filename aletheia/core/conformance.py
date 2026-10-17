"""Executable built-in conformance probes using isolated synthetic fixtures.

No caller content, providers or third-party code are executed. These bounded
probes certify their declared in-process scope; socket, installed-artifact,
real-model, platform and load evidence belongs to the external live harness.
"""
from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
import hashlib
import io
import json
import os
from pathlib import Path
from aletheia.storage.private_files import private_temporary_directory
import traceback


SUITES = {'kernel', 'context-pack-schema', 'http-api', 'python-sdk', 'mcp', 'plugin',
          'agent-adapter', 'backup-archive', 'protected-mode', 'semantic-retrieval',
          'llm-governance', 'federation-identity', 'peer-trust', 'share-bundle',
          'sync-protocol', 'federation-conflict', 'federation-redaction'}


def implementation_digest():
    root = Path(__file__).resolve().parents[1]
    digest = hashlib.sha256()
    for path in sorted(root.rglob('*.py')):
        digest.update(str(path.relative_to(root)).encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def observe(suite):
    if suite not in SUITES:
        return None
    from aletheia import Memory
    from aletheia.core.errors import ValidationError
    names = ['contract_registered', 'governance_preserved',
             'privacy_enforced' if suite in {'semantic-retrieval', 'llm-governance', 'federation-identity',
                'peer-trust', 'share-bundle', 'sync-protocol', 'federation-conflict', 'federation-redaction'} else 'error_envelope']
    evidence = {'assurance': 'behavioral', 'contract': f'builtin-{suite}-v1',
                'implementation_sha256': implementation_digest(), 'scope': 'isolated synthetic built-in behavior; no external providers'}
    try:
        if not __debug__:
            raise RuntimeError('Behavioral probes require assertion-enabled Python.')
        with private_temporary_directory(prefix='aletheia-conformance-') as directory, closing(
                Memory.open(str(Path(directory) / 'fixture.db'), namespace='conformance/fixture')) as m:
            path = Path(directory)
            if suite in {'kernel', 'context-pack-schema'}:
                claim = _claim(m)
                pack = m.context_pack(m.namespace, 'needle', record_usage=False)
                assert [item.claim_id for item in pack.items()] == [claim.id]
                assert pack.sources == claim.evidence_ids
                assert not m.retrieve('conformance/other', 'needle')
                assert not m.context_pack(m.namespace, 'needle', token_budget=0).items()
                before = len(m.list_claims(namespace=m.namespace))
                _denied(lambda: m.write_claim(namespace=m.namespace, memory_type='fact', subject='a', predicate='b', object='c', evidence_ids=[]), ValidationError)
                assert len(m.list_claims(namespace=m.namespace)) == before
                proofs = {'context_items': len(pack.items()), 'evidence_links': len(pack.sources), 'denied_evidence_free_write': True}
            elif suite in {'http-api', 'python-sdk', 'mcp'}:
                proofs = _interfaces(m, suite)
            elif suite == 'agent-adapter':
                from aletheia.core.adapter_contract import check_adapter
                from aletheia.core.platform import _adapter_loop_source
                adapter = path / 'adapter'
                adapter.mkdir()
                (adapter / 'README.md').write_text('Synthetic bundled adapter conformance')
                (adapter / 'aletheia-adapter.json').write_text(json.dumps({'type': 'python-sdk'}))
                (adapter / 'agent_loop.py').write_text(_adapter_loop_source('python-sdk'))
                results, detail = check_adapter(adapter, _adapter_loop_source('python-sdk'), expected_type='python-sdk')
                assert detail['assurance'] == 'behavioral' and all(status == 'passed' for status, _ in results.values())
                proofs = detail['probes']
            elif suite == 'plugin':
                plugin = path / 'plugin'
                plugin.mkdir()
                (plugin / 'aletheia-plugin.toml').write_text('''[plugin]
name = "conformance-fixture"
version = "1.0.0"
plugin_type = "extractor"
entrypoint = "not_imported:Plugin"
description = "Synthetic permission probe"
[compatibility]
aletheia_min_version = "1.3.0"
api_contract_version = "v1"
[permissions]
permissions_required = ["write_candidate"]
external_network_access = false
reads_memory_content = false
writes_memory = true
stores_data = false
''')
                installation = m.install_plugin(plugin_path=str(plugin), trust_level='local')
                m.enable_plugin(installation.id, reason='isolated conformance permission approval', approved_permissions=['write_candidate'])
                assert m.run_plugin_operation(plugin_id=installation.id, operation='attempt_active_write', namespace=m.namespace)['status'] == 'blocked'
                result = m.run_plugin_operation(plugin_id=installation.id, operation='remember_candidate', namespace=m.namespace,
                    payload={'memory_type': 'fact', 'subject': 'probe', 'predicate': 'observes', 'object': 'needle', 'evidence_text': 'probe observes needle'})
                assert result['status'] == 'ok'
                assert m.read_candidate(result['candidate_id']).candidate_status == 'pending_review'
                assert not m.list_claims(namespace=m.namespace)
                proofs = {'candidate_writes': 1, 'active_writes': 0, 'blocked_active_operation': True}
            elif suite == 'backup-archive':
                claim = _claim(m)
                archive = path / 'backup.alet'
                m.create_backup(output_path=str(archive), namespace=m.namespace, encrypt=True, passphrase='synthetic-probe-passphrase')
                assert m.verify_backup(backup_path=str(archive), passphrase='synthetic-probe-passphrase').status == 'passed'
                assert m.verify_backup(backup_path=str(archive), passphrase='wrong').status == 'failed'
                target = path / 'restore.db'
                m.restore_backup(backup_path=str(archive), target_db_path=str(target), passphrase='synthetic-probe-passphrase', dry_run=True)
                assert not target.exists()
                m.restore_backup(backup_path=str(archive), target_db_path=str(target), passphrase='synthetic-probe-passphrase', dry_run=False)
                with closing(Memory.open(str(target), namespace=m.namespace)) as restored:
                    assert restored.read_claim(claim.id).object == claim.object
                    assert restored.store.connection.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
                proofs = {'verified_restore': True, 'wrong_key_refused': True, 'dry_run_created_target': False}
            elif suite == 'protected-mode':
                key = m.create_key(provider='passphrase', label='isolated-probe')
                variable = f'ALETHEIA_KEY_{key.id}'
                # The generated key ID is unique; never replace a caller's key.
                assert variable not in os.environ
                os.environ[variable] = 'synthetic-isolated-conformance-key'
                try:
                    m.enable_protected_mode()
                    claim = _claim(m, privacy_level='secret')
                    event = m.read_event(claim.evidence_ids[0])
                    raw = m.store.connection.execute('SELECT content FROM evidence_events WHERE id = ?', (event.id,)).fetchone()[0]
                    assert raw.startswith('enc:v3:') and event.content not in raw
                    assert m.index_semantic(m.namespace, provider='local_hash', dimension=32).indexed_count == 0
                    os.environ[variable] = 'wrong-probe-key'
                    _denied(lambda: m.read_event(event.id), ValidationError)
                finally:
                    os.environ.pop(variable, None)
                proofs = {'ciphertext_at_rest': True, 'secret_vectors': 0, 'wrong_key_refused': True}
            elif suite == 'semantic-retrieval':
                claim = _claim(m)
                secret = _claim(m, subject='private-probe', privacy_level='secret')
                m.index_semantic(m.namespace, provider='local_hash', dimension=32)
                hits = m.retrieve(m.namespace, 'needle', mode='semantic', semantic_provider='local_hash')
                assert claim.id in {hit.claim_id for hit in hits} and secret.id not in {hit.claim_id for hit in hits}
                m.demote_claim(claim.id, target_status='rejected', reason='probe rejection')
                assert claim.id not in {hit.claim_id for hit in m.retrieve(m.namespace, 'needle', mode='semantic', semantic_provider='local_hash')}
                _denied(lambda: m.index_semantic(m.namespace, provider='unavailable-probe'), (ValueError, ValidationError))
                proofs = {'provider': 'local_hash', 'indexed_public_claim_retrieved': True, 'secret_and_rejected_excluded': True}
            elif suite == 'llm-governance':
                batch = m.ingest(m.namespace, source_type='manual', content='User prefers concise notes.')
                run = m.extract_candidates(m.namespace, batch_id=batch.id, extractor='llm')
                candidates = m.list_candidates(m.namespace, extraction_run_id=run.id)
                assert candidates and all(item.candidate_status == 'pending_review' for item in candidates)
                summary = m.summarize_evidence(namespace=m.namespace, evidence_ids=batch.evidence_ids)
                assert summary['summary'] and summary['status'] == 'pending_review'
                assert not m.list_claims(namespace=m.namespace)
                _denied(lambda: m.expand_query(namespace=m.namespace, query='private', privacy_level='secret'), ValidationError)
                proofs = {'provider': 'mock_llm', 'candidate_count': len(candidates), 'active_claims': 0, 'secret_task_refused': True}
            else:
                proofs = _federation(m, path, suite)
            evidence['probes'] = proofs
        return ({name: ('passed', f'Observed {suite} behavior: ' + ', '.join(proofs)) for name in names}, evidence)
    except Exception as error:
        origin = traceback.extract_tb(error.__traceback__)[-1]
        evidence.update(probes={}, failure_type=type(error).__name__,
                        failure_location=f'{Path(origin.filename).name}:{origin.lineno}:{origin.name}')
        return ({name: ('failed', f'Isolated {suite} behavioral probe failed ({type(error).__name__}).') for name in names}, evidence)


def _claim(m, **kwargs):
    return m.remember(namespace=m.namespace, memory_type='fact', subject=kwargs.pop('subject', 'probe'),
                      predicate='records', object='needle synthetic conformance', **kwargs)


def _denied(operation, kind):
    try:
        operation()
    except kind:
        return
    raise AssertionError('Expected operation refusal')


def _interfaces(m, suite):
    from aletheia.client import AletheiaClient, AsyncAletheiaClient
    from aletheia.models import ServiceConfig
    from aletheia.service.http import AletheiaService
    from aletheia.service.mcp import McpToolRegistry
    public = _claim(m)
    _claim(m, subject='private-probe', privacy_level='secret')
    service = AletheiaService(m, ServiceConfig(db_path=m.store.path, rate_limit_enabled=False))
    client = service.auth.create_client(name='isolated probe', client_type='test')
    _, token = service.auth.create_token(client_id=client.id, namespace_grants=[m.namespace],
        capabilities=['memory:read', 'memory:context', 'memory:write_candidate'], privacy_ceiling='personal')
    def request(method, path, payload=None):
        return service.handle_http(method=method, path=path, headers={'Authorization': f'Bearer {token}'},
            body=json.dumps(payload).encode() if payload is not None else b'')
    payload = {'namespace': m.namespace, 'memory_type': 'fact', 'subject': 'agent', 'predicate': 'observes',
               'object': 'needle', 'evidence_text': 'Agent observes needle.'}
    if suite == 'mcp':
        registry = McpToolRegistry(service, token=token, namespace=m.namespace, mode='read_write_candidate')
        messages = [
            {'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {'protocolVersion': '2025-06-18', 'capabilities': {}, 'clientInfo': {'name': 'probe', 'version': '1'}}},
            {'jsonrpc': '2.0', 'method': 'notifications/initialized'},
            {'jsonrpc': '2.0', 'id': 2, 'method': 'tools/call', 'params': {'name': 'memory_search', 'arguments': {'query': 'needle'}}},
            {'jsonrpc': '2.0', 'id': 3, 'method': 'tools/call', 'params': {'name': 'memory_remember', 'arguments': payload}},
            {'jsonrpc': '2.0', 'id': 4, 'method': 'tools/call', 'params': {'name': 'memory_remember', 'arguments': {**payload, 'write_mode': 'active'}}},
            {'jsonrpc': '2.0', 'id': 5, 'method': 'missing'},
        ]
        output = io.StringIO()
        registry.serve_stdio(io.StringIO(''.join(json.dumps(row) + '\n' for row in messages)), output)
        rows = [json.loads(line) for line in output.getvalue().splitlines()]
        assert [row['id'] for row in rows] == [1, 2, 3, 4, 5]
        assert [item['claim_id'] for item in json.loads(rows[1]['result']['content'][0]['text'])] == [public.id]
        assert not rows[2]['result']['isError'] and rows[3]['result']['isError']
        assert rows[4]['error']['code'] == -32601
    elif suite == 'python-sdk':
        class Client(AletheiaClient):
            def _request(self, method, path, payload=None, **kwargs):
                status, envelope = request(method, path, payload)
                if status >= 400:
                    self._raise_error(envelope, status)
                return envelope['data']
        sdk = Client('http://fixture.invalid', token)
        assert [hit['claim_id'] for hit in sdk.retrieve(namespace=m.namespace, query='needle')] == [public.id]
        sdk.remember_candidate(**payload)
        from aletheia.client import AletheiaForbiddenError
        _denied(lambda: sdk.remember_active(**payload), AletheiaForbiddenError)
        async def read_async():
            asynchronous = AsyncAletheiaClient('http://fixture.invalid', token)
            asynchronous._sync = sdk
            return await asynchronous.retrieve(namespace=m.namespace, query='needle')
        with ThreadPoolExecutor(max_workers=1) as pool:
            assert pool.submit(lambda: asyncio.run(read_async())).result(timeout=10)[0]['claim_id'] == public.id
    else:
        status, envelope = request('POST', '/v1/retrieve', {'namespace': m.namespace, 'query': 'needle'})
        assert status == 200 and [item['claim_id'] for item in envelope['data']] == [public.id]
        status, _ = request('POST', '/v1/remember', {**payload, 'write_mode': 'candidate'})
        assert status == 200
        before = len(m.list_claims(namespace=m.namespace))
        status, envelope = request('POST', '/v1/remember', {**payload, 'write_mode': 'active'})
        assert status == 403 and envelope['error']['code'] == 'forbidden'
        assert len(m.list_claims(namespace=m.namespace)) == before
        status, envelope = request('POST', '/v1/retrieve', {'namespace': 'conformance/foreign', 'query': 'needle'})
        assert status == 403
    assert len(m.list_candidates(m.namespace)) == 1 and len(m.list_claims(namespace=m.namespace)) == 2
    return {'transport': 'in_process_jsonrpc' if suite == 'mcp' else 'in_process_service',
            'visible_claims': 1, 'candidate_writes': 1, 'denied_active_write': True, 'private_source_excluded': True}


def _federation(left, path, suite):
    from aletheia import Memory
    from aletheia.core.errors import ValidationError
    with closing(Memory.open(str(path / 'right.db'), namespace=left.namespace)) as right:
        left.create_federation_identity(display_name='isolated left', protected=False)
        right.create_federation_identity(display_name='isolated right', protected=False)
        exported = left.export_federation_identity()
        assert 'private_key_ref' not in exported and 'private_key' not in exported
        peer = left.add_peer(peer_identity=right.export_federation_identity(), reason='probe recipient')
        sender = right.add_peer(peer_identity=exported, reason='probe sender')
        assert right.get_peer(sender.id).trust_status == 'unknown'
        claim = _claim(left)
        _claim(left, subject='private-probe', privacy_level='secret')
        share = left.create_share_grant(name='isolated share', namespace=left.namespace, recipient_peer_ids=[peer.id],
            permissions=['read', 'sync_pull', 'receive_redactions'], privacy_ceiling='personal',
            statuses=['active'], reason='probe explicit consent')
        bundle = path / 'fixture.aletsync'
        left.export_share_bundle(share_id=share.id, output_path=str(bundle), encrypt=True)
        if suite == 'federation-conflict':
            right.remember(namespace=right.namespace, memory_type='fact', subject='probe', predicate='records', object='local distinct value')
        result = right.import_share_bundle(input_path=str(bundle), trust_policy='candidate_only')
        assert result.status in {'completed', 'completed_with_conflicts'}
        assert len(right.list_candidates(right.namespace)) == 1
        assert all(item.object != 'needle synthetic conformance' for item in right.list_claims(namespace=right.namespace))
        if suite == 'federation-conflict':
            conflict = right.list_sync_conflicts(status='unresolved')[0]
            right.resolve_sync_conflict(conflict.id, strategy='keep_local', reason='probe operator review')
            assert right.list_claims(namespace=right.namespace)[0].object == 'local distinct value'
        if suite == 'federation-redaction':
            left.redact(target_type='claim', target_id=claim.id, reason='probe redaction', dry_run=False)
            next_bundle = path / 'redaction.aletsync'
            left.export_share_bundle(share_id=share.id, output_path=str(next_bundle), encrypt=True)
            right.import_share_bundle(input_path=str(next_bundle), trust_policy='candidate_only')
            assert right.store.connection.execute('SELECT count(*) FROM deletion_tombstones').fetchone()[0] >= 1
        if suite == 'peer-trust':
            right.trust_peer(sender.id, trust_status='trusted_device', reason='probe approval')
            right.revoke_peer(sender.id, reason='probe revocation')
            assert right.get_peer(sender.id).trust_status == 'revoked'
        with closing(Memory.open(str(path / 'wrong-recipient.db'), namespace=left.namespace)) as wrong:
            wrong.create_federation_identity(display_name='wrong recipient', protected=False)
            _denied(lambda: wrong.import_share_bundle(input_path=str(bundle)), ValidationError)
            assert not wrong.list_claims(namespace=left.namespace) and not wrong.list_candidates(left.namespace)
        return {'bundle_roundtrip': True, 'candidate_only': True, 'secret_excluded': True,
                'wrong_recipient_refused': True, 'suite_specific_action': suite}
