"""Regressions for the October beta campaign; real stdio and console JS included."""
import io
import json
import shutil
import sqlite3
import subprocess
import sys
from dataclasses import asdict

import pytest

from aletheia import Memory
from aletheia.core.errors import ValidationError
from aletheia.core.memory import FEEDBACK_SIGNALS
from aletheia.llm import MockLLMProvider
from aletheia.service.http import CONSOLE_HTML


@pytest.fixture
def memory(tmp_path):
    m = Memory.open(str(tmp_path / 'beta.db'), namespace='beta/main')
    yield m
    m.close()


def remember(m, **kwargs):
    return m.remember(namespace='beta/main', memory_type='preference', subject='user',
                      predicate='prefers_editor', object=kwargs.pop('object', 'Vim'), confidence=.5, **kwargs)


@pytest.mark.parametrize('signal', sorted(FEEDBACK_SIGNALS))
def test_zero_feedback_preserves_confidence_salience_verification_and_status(memory, signal):
    claim = remember(memory)
    before = memory.compute_confidence(claim.id)
    record = memory.feedback(claim.id, namespace='beta/main', signal=signal, strength=0)
    after = memory.compute_confidence(claim.id, at_time=before.computed_at)
    assert record.strength == 0
    assert asdict(before) == asdict(after)
    current = memory.read_claim(claim.id)
    assert current.status == claim.status
    assert current.last_verified_at == claim.last_verified_at
    assert current.confidence_base == claim.confidence_base


@pytest.mark.parametrize('value', [float('nan'), float('inf'), -float('inf'), -1, True, False, '100', 12.5])
def test_context_invalid_budget_rejected_without_domain_writes(memory, value):
    remember(memory)
    before = memory.store.connection.total_changes
    with pytest.raises(ValidationError, match='token_budget'):
        memory.context_pack('beta/main', 'Vim', token_budget=value, record_usage=True)
    assert memory.store.connection.total_changes == before


def test_zero_budget_is_valid_and_returns_no_items(memory):
    remember(memory)
    assert not memory.context_pack('beta/main', 'Vim', token_budget=0).items()


def test_nested_engine_abort_preserves_original_error_and_transaction_depth(memory):
    original = sqlite3.OperationalError('Synthetic disk-full auto-rollback')
    with pytest.raises(sqlite3.OperationalError) as caught:
        with memory.store.transaction():
            with memory.store.transaction():
                memory.store.connection.rollback()  # SQLite auto-abort destroys savepoints.
                raise original
    assert caught.value is original
    assert memory.store._transaction_depth == 0
    claim = remember(memory)
    assert memory.read_claim(claim.id).object == claim.object


def test_failed_savepoint_creation_never_leaks_transaction_depth(memory):
    connection = memory.store.connection
    class Fault:
        def __getattr__(self, name):
            return getattr(connection, name)
        def execute(self, sql, *args):
            if sql.startswith('SAVEPOINT'):
                raise sqlite3.OperationalError('Synthetic savepoint allocation failure')
            return connection.execute(sql, *args)
    memory.store.connection = Fault()
    try:
        with pytest.raises(sqlite3.OperationalError, match='allocation failure'):
            with memory.store.transaction():
                with memory.store.transaction():
                    pytest.fail('Failed savepoint must never enter the body')
        assert memory.store._transaction_depth == 0
    finally:
        memory.store.connection = connection
    assert remember(memory).status == 'active'


def test_caught_engine_abort_cannot_commit_new_writes_inside_failed_outer_scope(memory):
    with memory.store.transaction():
        try:
            with memory.store.transaction():
                memory.store.connection.rollback()
                raise sqlite3.OperationalError('Synthetic engine abort')
        except sqlite3.OperationalError:
            pass
        with pytest.raises(sqlite3.OperationalError, match='Enclosing transaction was aborted'):
            remember(memory)
    assert not memory.list_claims(namespace=memory.namespace)
    assert remember(memory).status == 'active'


@pytest.mark.parametrize('value', [True, False, '1', float('nan'), float('inf'), None])
def test_feedback_rejects_invalid_strength_without_mutation(memory, value):
    claim = remember(memory)
    before = memory.store.connection.total_changes
    with pytest.raises(ValidationError, match='strength'):
        memory.feedback(claim.id, namespace='beta/main', signal='wrong', strength=value)
    assert memory.store.connection.total_changes == before


def test_advisory_huge_integer_rejected_as_out_of_range():
    from aletheia.advisory import validate
    with pytest.raises(ValidationError, match='out of range'):
        validate(10 ** 1000, {'type': 'number', 'minimum': 0, 'maximum': 1})


@pytest.mark.parametrize('signal', ['confirmed', 'verified'])
def test_repeated_assistant_feedback_is_not_independent_evidence(memory, signal):
    claim = remember(memory)
    before = memory.compute_confidence(claim.id)
    for _ in range(100):
        assert memory.feedback(claim.id, namespace='beta/main', source='assistant', signal=signal).strength == 0
    assert asdict(memory.compute_confidence(claim.id, at_time=before.computed_at)) == asdict(before)


def test_http_and_cli_scope_refusal_preserves_conflict_then_atomic_resolution(memory, capsys):
    from aletheia.cli.main import main
    from aletheia.models import ServiceConfig
    from aletheia.service.http import AletheiaService
    a, b = remember(memory), remember(memory, object='Emacs')
    conflict = memory.list_conflicts(namespace='beta/main')[0]
    service = AletheiaService(memory, ServiceConfig(db_path=memory.store.path,
        auth_required=False, tokenless_capabilities=('memory:admin',)))
    payload = {'namespace': 'beta/main', 'strategy': 'context_scope', 'note': 'operator review'}
    status, envelope = service.handle_http(method='POST', path=f'/v1/conflicts/{conflict.id}/resolve',
        headers={}, body=json.dumps(payload).encode())
    assert status == 400, envelope
    assert memory.read_conflict(conflict.id).status == 'unresolved'
    with pytest.raises(SystemExit) as error:
        main(['conflicts', 'resolve', conflict.id, '--db', str(memory.store.path), '--strategy', 'context_scope'])
    assert error.value.code == 1
    capsys.readouterr()
    payload['scoped_claims'] = [{'claim_id': a.id, 'applies_when': 'architecture'}, {'claim_id': b.id, 'applies_when': 'progress'}]
    status, envelope = service.handle_http(method='POST', path=f'/v1/conflicts/{conflict.id}/resolve',
        headers={}, body=json.dumps(payload).encode())
    assert status == 200, envelope
    assert memory.read_conflict(conflict.id).status == 'resolved'


def test_http_compaction_uses_idle_connection_and_missing_bundle_is_client_error(memory, tmp_path):
    from aletheia.models import ServiceConfig
    from aletheia.service.http import AletheiaService
    claim = remember(memory)
    service = AletheiaService(memory, ServiceConfig(db_path=memory.store.path, local_pairing_enabled=False))
    admin = service.auth.create_client(name='Synthetic maintenance operator', client_type='test')
    _, token = service.auth.create_token(client_id=admin.id, namespace_grants=['*'],
        capabilities=['memory:admin'], privacy_ceiling='secret')
    headers = {'Authorization': 'Bearer ' + token}
    status, result = service.handle_http(method='POST', path='/v1/compact/run', headers=headers,
        body=json.dumps({'namespace': memory.namespace}).encode())
    assert status == 200, result
    assert result['data']['status'] == 'completed'
    assert memory.read_claim(claim.id).object == claim.object
    assert memory.store.connection.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
    before = len(memory.list_sync_runs())
    status, result = service.handle_http(method='POST', path='/v1/shares/import', headers=headers,
        body=json.dumps({'input_path': str(tmp_path / 'absent.aletsync'), 'namespace': memory.namespace}).encode())
    assert status == 400 and result['error']['code'] == 'validation_error', result
    assert len(memory.list_sync_runs()) == before
    reader = service.auth.create_client(name='Synthetic reader', client_type='test')
    _, read_token = service.auth.create_token(client_id=reader.id, namespace_grants=[memory.namespace],
        capabilities=['memory:read'], privacy_ceiling='personal')
    count = memory.store.connection.execute('SELECT count(*) FROM compaction_runs').fetchone()[0]
    assert service.handle_http(method='POST', path='/v1/compact/run', headers={'Authorization': 'Bearer ' + read_token}, body=b'{}')[0] == 403
    assert memory.store.connection.execute('SELECT count(*) FROM compaction_runs').fetchone()[0] == count


@pytest.mark.parametrize('strategy', ['context_scope', 'time_scope'])
def test_scope_resolution_requires_atomic_complete_scopes(memory, strategy):
    a = remember(memory)
    b = remember(memory, object='Emacs')
    conflict = memory.list_conflicts(namespace='beta/main')[0]
    before = memory.store.connection.total_changes
    for scopes in [None, [], [{'claim_id': a.id, 'applies_when': 'architecture'}],
                   [{'claim_id': []}], [{'claim_id': a.id, 'scope_type': []}],
                   [{'claim_id': a.id, 'valid_from': 'bad time'}, {'claim_id': b.id}]]:
        with pytest.raises(ValidationError):
            memory.resolve_conflict(conflict.id, strategy=strategy, scoped_claims=scopes)
    assert memory.store.connection.total_changes == before
    assert memory.read_conflict(conflict.id).status == 'unresolved'
    if strategy == 'context_scope':
        scopes = [{'claim_id': a.id, 'applies_when': 'architecture_or_design_request'},
                  {'claim_id': b.id, 'applies_when': 'progress_update_request'}]
    else:
        scopes = [{'claim_id': a.id, 'scope_type': 'temporal', 'valid_to': '2026-01-01T00:00:00+00:00'},
                  {'claim_id': b.id, 'scope_type': 'temporal', 'valid_from': '2026-01-01T00:00:00+00:00'}]
    memory.resolve_conflict(conflict.id, strategy=strategy, scoped_claims=scopes)
    assert memory.read_conflict(conflict.id).status == 'resolved'
    assert all(memory.list_claim_scopes(c.id) for c in [a, b])


@pytest.mark.parametrize('task', ['expand_query', 'suggest_entities', 'suggest_categories', 'suggest_scope',
                                  'suggest_duplicate_merge', 'summarize_evidence', 'draft_reflection', 'explain_conflict'])
@pytest.mark.parametrize('bad', [{}, {'summary': ' '}, {'review_state': 'approved'}])
def test_wrong_shaped_advice_never_completes_or_creates_memory(memory, monkeypatch, task, bad):
    class Bad(MockLLMProvider):
        def complete_json(self, **kwargs):
            assert kwargs['schema']['properties']
            assert kwargs['schema']['required']
            return bad
    monkeypatch.setattr('aletheia.core.memory.llm_provider_for_name', lambda *a, **kw: Bad())
    batch = memory.ingest('beta/main', source_type='manual', content='User prefers concise architecture notes.')
    run = memory.extract_candidates('beta/main', batch_id=batch.id)
    candidate = memory.list_candidates('beta/main', extraction_run_id=run.id)[0]
    remember(memory)
    remember(memory, object='Emacs')
    conflict = memory.list_conflicts(namespace='beta/main')[0]
    operations = {
        'expand_query': lambda: memory.expand_query(namespace='beta/main', query='architecture'),
        'suggest_entities': lambda: memory.suggest_entities(namespace='beta/main', evidence_ids=batch.evidence_ids),
        'suggest_categories': lambda: memory.suggest_categories(namespace='beta/main', evidence_ids=batch.evidence_ids),
        'suggest_scope': lambda: memory.suggest_scope_with_llm(namespace='beta/main', candidate_id=candidate.id),
        'suggest_duplicate_merge': lambda: memory.suggest_duplicate_merge_with_llm(namespace='beta/main', candidate_id=candidate.id),
        'summarize_evidence': lambda: memory.summarize_evidence(namespace='beta/main', evidence_ids=batch.evidence_ids),
        'draft_reflection': lambda: memory.draft_reflection_with_llm(namespace='beta/main', source_evidence_ids=batch.evidence_ids),
        'explain_conflict': lambda: memory.explain_conflict_with_llm(conflict.id),
    }
    claims = memory.list_claims(namespace='beta/main')
    with pytest.raises(ValidationError, match='valid advisory result'):
        operations[task]()
    assert memory.list_claims(namespace='beta/main') == claims
    assert not memory.list_reflections(namespace='beta/main')
    assert not any(row['status'] == 'completed' for row in memory.list_llm_runs(namespace='beta/main') if row['task_type'] != 'extract_candidates')
    assert memory.read_conflict(conflict.id).status == 'unresolved'


def stdio(tmp_path, messages, mode='read_only'):
    command = [sys.executable, '-m', 'aletheia.cli.main', 'mcp', '--db', str(tmp_path / 'stdio.db'),
               '--namespace', 'beta/custom', '--mode', mode]
    result = subprocess.run(command, input=''.join(json.dumps(m) + '\n' for m in messages),
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    return [json.loads(line) for line in result.stdout.splitlines()]


def initialize():
    return [{'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {
        'protocolVersion': '2025-06-18', 'capabilities': {}, 'clientInfo': {'name': 'regression', 'version': '1'}}},
        {'jsonrpc': '2.0', 'method': 'notifications/initialized'}]


def test_real_mcp_wire_lifecycle_modes_and_custom_namespace(tmp_path):
    rows = stdio(tmp_path, initialize() + [
        {'jsonrpc': '2.0', 'id': 2, 'method': 'tools/list'},
        {'jsonrpc': '2.0', 'id': 3, 'method': 'tools/call', 'params': {'name': 'memory_search', 'arguments': {'query': 'needle'}}},
        {'jsonrpc': '2.0', 'id': 4, 'method': 'tools/call', 'params': {'name': 'memory_search', 'arguments': {'query': 'needle', 'namespace': 'beta/other'}}},
        {'jsonrpc': '2.0', 'id': 5, 'method': 'tools/call', 'params': {'name': 'memory_remember', 'arguments': {
            'memory_type': 'fact', 'subject': 'agent', 'predicate': 'writes', 'object': 'forbidden'}}},
        {'jsonrpc': '2.0', 'id': 6, 'method': 'unknown'},
    ])
    assert [r['id'] for r in rows] == [1, 2, 3, 4, 5, 6]
    assert rows[0]['result']['capabilities'] == {'tools': {}}
    assert 'memory_remember' not in [t['name'] for t in rows[1]['result']['tools']]
    assert rows[2]['result']['isError'] is False
    assert rows[3]['result']['isError'] is True
    assert rows[4]['result']['isError'] is True
    assert rows[5]['error']['code'] == -32601
    m = Memory.open(str(tmp_path / 'stdio.db'))
    try:
        assert not m.list_claims(namespace='beta/custom')
        assert not m.list_candidates('beta/custom')
    finally:
        m.close()


def test_mcp_does_not_execute_requests_before_initialization(tmp_path):
    rows = stdio(tmp_path, [{'jsonrpc': '2.0', 'id': 9, 'method': 'tools/list'}])
    assert rows == [{'jsonrpc': '2.0', 'id': 9, 'error': {'code': -32002,
        'message': 'Initialize and send notifications/initialized before using tools.'}}]


def test_mcp_candidate_writes_remain_pending_and_invalid_arguments_do_not_write(tmp_path):
    arguments = {'memory_type': 'fact', 'subject': 'agent', 'predicate': 'observed', 'object': 'needle', 'evidence_text': 'Agent observed needle.'}
    rows = stdio(tmp_path, initialize() + [
        {'jsonrpc': '2.0', 'id': 2, 'method': 'tools/call', 'params': {'name': 'memory_remember', 'arguments': arguments}},
        {'jsonrpc': '2.0', 'id': 3, 'method': 'tools/call', 'params': {'name': 'memory_remember', 'arguments': {**arguments, 'write_mode': 'active'}}},
        {'jsonrpc': '2.0', 'id': 4, 'method': 'tools/call', 'params': {'name': 'memory_search', 'arguments': {'query': 42}}},
    ], mode='read_write_candidate')
    assert rows[1]['result']['isError'] is False
    assert rows[2]['result']['isError'] is True
    assert rows[3]['error']['code'] == -32602
    m = Memory.open(str(tmp_path / 'stdio.db'))
    try:
        assert len(m.list_candidates('beta/custom')) == 1
        assert not m.list_claims(namespace='beta/custom')
    finally:
        m.close()


def test_legacy_stdio_namespace_remains_supported(tmp_path):
    assert stdio(tmp_path, [{'tool': 'memory_search', 'arguments': {'query': 'needle'}}]) == [{'ok': True, 'data': []}]


def test_every_mcp_tool_executes_through_jsonrpc_with_real_governance(memory):
    from aletheia.models import ServiceConfig
    from aletheia.service.http import AletheiaService
    from aletheia.service.mcp import McpToolRegistry
    claim = remember(memory)
    batch = memory.ingest(memory.namespace, source_type='manual', content='User prefers concise architecture notes.')
    run = memory.extract_candidates(memory.namespace, batch_id=batch.id)
    candidate = memory.list_candidates(memory.namespace, extraction_run_id=run.id)[0]
    other = memory.ingest(memory.namespace, source_type='manual', content='User prefers careful progress summaries.')
    other_run = memory.extract_candidates(memory.namespace, batch_id=other.id)
    rejected = memory.list_candidates(memory.namespace, extraction_run_id=other_run.id)[0]
    service = AletheiaService(memory, ServiceConfig(db_path=memory.store.path, auth_required=False,
        rate_limit_enabled=False, local_pairing_enabled=False, advertise_local=False))
    registry = McpToolRegistry(service, namespace=memory.namespace, mode='admin')
    values = {'query': 'architecture', 'target_id': claim.id, 'target_type': 'claim', 'claim_id': claim.id,
              'signal': 'useful', 'memory_type': 'fact', 'subject': 'mcp agent', 'predicate': 'observes',
              'object': 'synthetic observation', 'content': 'User prefers bounded MCP probes.',
              'candidate_id': candidate.id, 'reason': 'Synthetic operator checked evidence',
              'evidence_ids': batch.evidence_ids, 'task_id': 'synthetic-mcp-task', 'outcome': 'success'}
    messages = initialize()
    names = []
    for index, tool in enumerate(registry.tools(), 2):
        arguments = {key: values[key] for key in tool.input_schema.get('required', [])}
        if tool.name == 'memory_remember':
            arguments['evidence_text'] = 'MCP agent observes synthetic observation.'
        if tool.name == 'memory_extract_candidates':
            arguments.update(batch_id=batch.id, extractor='rule_based')
        if tool.name.startswith('memory_llm_'):
            arguments['provider'] = 'mock'
        if tool.name == 'memory_reject_candidate':
            arguments['candidate_id'] = rejected.id
        messages.append({'jsonrpc': '2.0', 'id': index, 'method': 'tools/call',
                         'params': {'name': tool.name, 'arguments': arguments}})
        names.append(tool.name)
    output = io.StringIO()
    registry.serve_stdio(io.StringIO(''.join(json.dumps(row) + '\n' for row in messages)), output)
    rows = [json.loads(line) for line in output.getvalue().splitlines()]
    assert len(rows) == 1 + len(names)
    for name, row in zip(names, rows[1:]):
        assert 'result' in row and not row['result']['isError'], (name, row)
    assert memory.read_candidate(candidate.id).candidate_status == 'promoted'
    assert memory.read_candidate(rejected.id).candidate_status == 'rejected'
    assert len(memory.list_claims(namespace=memory.namespace)) == 2


def test_nonfinite_json_frame_is_rejected_and_connection_recovers(tmp_path):
    rows = stdio(tmp_path, [{'jsonrpc': '2.0', 'id': 9, 'method': 'ping', 'params': {'value': float('nan')}}] + initialize())
    assert rows[0]['error']['code'] == -32700
    assert rows[1]['result']['protocolVersion'] == '2025-06-18'


def test_console_logout_and_auth_loss_clear_panels_and_discard_late_responses(tmp_path):
    node = shutil.which('node')
    if not node:
        pytest.skip('Actual console JS regression requires Node')
    script = CONSOLE_HTML.split('<script>')[1].split('</script>')[0]
    harness = r'''
const vm=require('node:vm'),assert=require('node:assert/strict');
const nodes=new Map(); const storage=new Map(); let held;
const document={getElementById(id){if(!nodes.has(id))nodes.set(id,{value:'secret',textContent:'secret',innerHTML:'secret',replaceChildren(){this.innerHTML='';}});return nodes.get(id);}};
const ctx={document,sessionStorage:{getItem:k=>storage.get(k),setItem:(k,v)=>storage.set(k,v),removeItem:k=>storage.delete(k)},
 fetch:async(path)=>{if(path==='held')return new Promise(r=>held=r);return {ok:true,status:200,json:async()=>({data:{metrics:{}}})};}};
vm.createContext(ctx); vm.runInContext(SOURCE+';globalThis.probe={api,clearSession};',ctx);
(async()=>{await new Promise(r=>setImmediate(r));
 for(const id of ['metrics','reviews','traceOutput','hardeningOutput','platformOutput','federationOutput'])document.getElementById(id).textContent='canary';
 const pending=ctx.probe.api('held');const rejection=assert.rejects(pending,/Session ended/);
 await document.getElementById('logout').onclick();held({ok:true,status:200,json:async()=>({data:{secret:'canary'}})});await rejection;
 assert.equal(document.getElementById('sessionState').textContent,'Logged out');
 for(const id of ['reviews','traceOutput','hardeningOutput','platformOutput','federationOutput'])assert.equal(document.getElementById(id).textContent,'');
 assert.equal(document.getElementById('loginToken').value,'');assert.equal(document.getElementById('traceQuery').value,'');
 document.getElementById('traceOutput').textContent='canary';ctx.fetch=async()=>({ok:false,status:401,statusText:'Unauthorized',json:async()=>({})});
 await assert.rejects(ctx.probe.api('revoked'));assert.equal(document.getElementById('traceOutput').textContent,'');
 const requested=[];ctx.fetch=async(path)=>{requested.push(path);return {ok:false,status:403,statusText:'Forbidden',json:async()=>({error:{message:'Explicit scoped operator refusal'}})};};
 await document.getElementById('encryptStatus').onclick();assert.match(document.getElementById('actionStatus').textContent,/Request failed: Explicit scoped operator refusal/);
 document.getElementById('namespace').value='project/with space';
 await document.getElementById('federationShares').onclick();await document.getElementById('federationConflicts').onclick();
 assert(requested.includes('/v1/shares?namespace=project%2Fwith%20space'));assert(requested.includes('/v1/sync/conflicts?namespace=project%2Fwith%20space'));
 ctx.probe.clearSession();assert.equal(document.getElementById('actionStatus').textContent,'');
})().catch(e=>{console.error(e);process.exitCode=1;});
'''.replace('SOURCE', json.dumps(script))
    result = subprocess.run([node, '-e', harness], capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
