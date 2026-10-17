"""Production blocker regressions; Windows assertions use native access checks."""
import os
from contextlib import closing
import pytest
from aletheia import Memory
from aletheia.extraction import LLMExtractor

@pytest.mark.parametrize('field', ['subject', 'predicate', 'object', 'memory_type'])
@pytest.mark.parametrize('value', [' ', '', 123, None])
def test_extraction_rejects_blank_or_nonstring_fields(tmp_path, field, value):
    with closing(Memory.open(str(tmp_path / 'm.db'))) as memory:
        event = memory.write_event(namespace='test', source_type='manual', content='用户喜欢简洁的回答。')
        extractor = LLMExtractor(provider='mock_llm')
        item = {'subject':'user','predicate':'prefers','object':'concise answers','memory_type':'preference',
                'evidence_span':{'evidence_id':event.id,'start_char':0,'end_char':len(event.content),'text':event.content}}
        item[field] = value
        with pytest.raises(ValueError, match='nonblank'):
            extractor._drafts_from_output({'candidates':[item]}, evidence_by_id={event.id:event})

@pytest.mark.skipif(os.name != 'nt', reason='Native Windows ACL and token access test')
def test_windows_acl_owner_access_restricted_token_denied(tmp_path):
    import ctypes as c
    from ctypes import wintypes as w
    from aletheia.storage.private_files import create_private_file, windows_private_directory, require_windows_private_directory
    directory = tmp_path / 'private'
    directory.mkdir()
    windows_private_directory(directory)
    require_windows_private_directory(directory)
    memory = Memory.open(str(directory / 'm.db'))
    try:
        memory.write_event(namespace='test', source_type='manual', content='synthetic ACL canary')
        archive = directory / 'export.bin'
        fd = create_private_file(archive)
        os.write(fd, b'synthetic export')
        os.close(fd)
        # Positive control: the restricted token must be able to read an object
        # explicitly granting its restricting SID, not merely fail every I/O.
        control = directory / 'readable-control'
        control.write_bytes(b'control')
        import subprocess
        subprocess.run(['icacls',str(control),'/grant','*S-1-5-32-545:R'],check=True,capture_output=True)
        files = [directory / name for name in ('m.db', 'm.db-wal', 'm.db-shm', 'export.bin')]
        assert all(p.exists() for p in files)
        assert all(p.open('rb').read(1) for p in files)
        adv = c.WinDLL('advapi32', use_last_error=True)
        kernel = c.WinDLL('kernel32', use_last_error=True)
        kernel.GetCurrentProcess.restype = w.HANDLE
        kernel.CloseHandle.argtypes = [w.HANDLE]
        adv.OpenProcessToken.argtypes = [w.HANDLE,w.DWORD,c.POINTER(w.HANDLE)]
        adv.OpenProcessToken.restype = w.BOOL
        adv.ConvertStringSidToSidW.argtypes = [w.LPCWSTR,c.POINTER(c.c_void_p)]
        adv.ConvertStringSidToSidW.restype = w.BOOL
        class SID(c.Structure):
            _fields_ = [('sid',c.c_void_p),('attributes',w.DWORD)]
        adv.CreateRestrictedToken.argtypes = [w.HANDLE,w.DWORD,w.DWORD,c.c_void_p,w.DWORD,c.c_void_p,w.DWORD,c.POINTER(SID),c.POINTER(w.HANDLE)]
        adv.CreateRestrictedToken.restype = w.BOOL
        adv.ImpersonateLoggedOnUser.argtypes = [w.HANDLE]
        adv.ImpersonateLoggedOnUser.restype = w.BOOL
        adv.RevertToSelf.restype = w.BOOL
        token, restricted, sid = w.HANDLE(), w.HANDLE(), c.c_void_p()
        assert adv.OpenProcessToken(kernel.GetCurrentProcess(), 0x0002|0x0008|0x0004, c.byref(token)), c.get_last_error()
        try:
            assert adv.ConvertStringSidToSidW('S-1-5-32-545',c.byref(sid)), c.get_last_error()
            group = SID(sid,0)
            assert adv.CreateRestrictedToken(token,1,0,None,0,None,1,c.byref(group),c.byref(restricted)), c.get_last_error()
            assert adv.ImpersonateLoggedOnUser(restricted), c.get_last_error()
            try:
                assert control.read_bytes() == b'control'
                for path in files:
                    for mode in ('rb','ab'):
                        with pytest.raises(PermissionError):
                            with path.open(mode):
                                pass
                with pytest.raises(PermissionError):
                    (directory/'intruder').write_text('denied')
            finally:
                assert adv.RevertToSelf(), c.get_last_error()
        finally:
            if restricted: kernel.CloseHandle(restricted)
            kernel.CloseHandle(token)
            kernel.LocalFree.argtypes = [c.c_void_p]
            if sid: kernel.LocalFree(sid)
        assert archive.read_bytes() == b'synthetic export'
    finally:
        memory.close()

@pytest.mark.skipif(os.name != 'nt', reason='Native Windows broad-DACL refusal')
def test_windows_shared_parent_refused_before_database_creation(tmp_path):
    import subprocess
    directory = tmp_path/'shared'
    directory.mkdir()
    subprocess.run(['icacls',str(directory),'/grant','*S-1-1-0:(OI)(CI)F'],check=True,capture_output=True)
    with pytest.raises(PermissionError, match='private directory'):
        Memory.open(str(directory/'refused.db'))
    assert not (directory/'refused.db').exists()


def test_extraction_prompt_keeps_unicode_and_schema_anchors(monkeypatch, tmp_path):
    from aletheia.models import ExtractionPolicy
    from jsonschema import validate
    with closing(Memory.open(str(tmp_path/'unicode.db'))) as memory:
        event = memory.write_event(namespace='metadata-must-not-be-evidence', source_type='manual', content='用户喜欢简洁的回答。')
        extractor = LLMExtractor(provider='mock_llm')
        seen = {}
        def complete_json(**kwargs):
            seen.update(kwargs)
            output = {'candidates':[{'subject':'用户','predicate':'喜欢','object':'简洁的回答','memory_type':'preference',
                'scope_ref': 'unqualified', 'evidence_span':{'evidence_id':event.id,'start_char':0,'end_char':len(event.content),'text':event.content}}]}
            validate(output,kwargs['schema'])
            return output
        monkeypatch.setattr(extractor.provider,'complete_json',complete_json)
        drafts = extractor.extract(namespace=event.namespace,evidence=[event],policy=ExtractionPolicy())
        assert drafts[0].object == '简洁的回答'
        user_message = seen['messages'][1]['content']
        assert event.content in user_message
        assert '\\u7528' not in user_message
        assert event.namespace not in user_message
        altered = {'candidates':[{'subject':'用户','predicate':'喜欢','object':'简洁的回答','memory_type':'preference',
            'evidence_span':{'evidence_id':event.id,'start_char':0,'end_char':len(event.content)-1,'text':event.content}}]}
        with pytest.raises(ValueError,match='does not match'):
            extractor._drafts_from_output(altered,evidence_by_id={event.id:event})


@pytest.mark.parametrize('pairing', [False, True])
def test_daemon_readiness_does_not_wait_for_reverse_dns(monkeypatch, tmp_path, pairing):
    if pairing and os.name != 'posix':
        pytest.skip('Local pairing is POSIX-only')
    import socket
    import threading
    import json
    from urllib.request import urlopen
    from aletheia.models import ServiceConfig
    from aletheia.service.http import AletheiaDaemon
    def blocked_dns(*args):
        raise AssertionError('Reverse DNS must not be on the daemon startup path')
    monkeypatch.setattr(socket, 'getfqdn', blocked_dns)
    daemon = AletheiaDaemon(ServiceConfig(db_path=str(tmp_path/'ready.db'),port=0,auto_migrate=True,
        advertise_local=False,local_pairing_enabled=pairing,identity_directory=str(tmp_path/"identities")))
    try:
        host,port = daemon.start()
        thread = threading.Thread(target=daemon.httpd.serve_forever,daemon=True)
        thread.start()
        with urlopen(f'http://{host}:{port}/v1/ready',timeout=2) as response:
            assert json.load(response)['data']['ready'] is True
    finally:
        daemon.shutdown()


@pytest.mark.parametrize('scope', [
    {'type':'temporal','valid_from':'2026-10-01T00:00:00+00:00','valid_to':None},
    {'type':'temporal','valid_from':None,'valid_to':'2026-10-01T00:00:00+00:00'},
])
def test_approved_candidate_preserves_temporal_boundaries(tmp_path, scope):
    with closing(Memory.open(str(tmp_path/'temporal.db'))) as memory:
        batch = memory.ingest('test',source_type='manual',content='Remember that the office is Berlin since October 2026.')
        run = memory.extract_candidates('test',batch_id=batch.id,extractor='mock')
        candidate = memory.list_candidates('test',extraction_run_id=run.id)[0]
        memory.review_candidate(candidate.id,decision='edit',reason='Review source time boundary',edits={'suggested_scope':scope})
        memory.review_candidate(candidate.id,decision='validate',reason='Human source verification')
        claim = memory.promote_candidate(candidate.id,reason='Human approval')
        assert claim.valid_from == scope['valid_from']
        assert claim.valid_to == scope['valid_to']
        scopes = memory.list_claim_scopes(claim.id)
        assert any(s.valid_from == scope['valid_from'] and s.valid_to == scope['valid_to'] for s in scopes)


@pytest.mark.parametrize('expression,expected', [
    ('project=Orion', {'id-a':True,'id-b':False,None:False}),
    ('project!=Orion', {'id-a':False,'id-b':True,None:True}),
])
def test_project_condition_inclusion_and_exclusion_use_actual_context(tmp_path, expression, expected):
    with closing(Memory.open(str(tmp_path/'projects.db'))) as memory:
        memory.create_project('test','id-a',title='Orion')
        memory.create_project('test','id-b',title='Vega')
        memory.create_project('foreign','id-b',title='Orion')
        claim = memory.remember(namespace='test',memory_type='preference',subject='user',predicate='prefers_answers',object='detailed answers')
        memory.scope_claim(claim.id,scope_type='conditional',applies_when=expression,reason='Approved source condition')
        for project_id, allowed in expected.items():
            hits = memory.retrieve('test','detailed answers',project_id=project_id)
            assert (claim.id in {h.claim_id for h in hits}) is allowed
            # Query text must never override the supplied project identity.
            assert memory._scope_matches_claim(claim.id,query='project=Orion',project_id=project_id,session_id=None) is allowed


def test_qualifier_repair_is_bounded_audited_and_preserves_source(monkeypatch,tmp_path):
    from copy import deepcopy
    from aletheia.models import ExtractionPolicy
    with closing(Memory.open(str(tmp_path/'repair.db'))) as memory:
        event = memory.write_event(namespace='test',source_type='manual',content='The previous office was Paris. Since October 2026 the office is Berlin.')
        extractor = LLMExtractor(provider='mock_llm',max_repair_attempts=1)
        item = {'subject':'office','predicate':'was','object':'Paris','memory_type':'fact',
                'suggested_scope':{'type':'temporal','valid_from':'2026-10-01'},
                'evidence_span':{'evidence_id':event.id,'start_char':0,'end_char':len(event.content),'text':event.content}}
        calls=[]
        def complete_json(**kwargs):
            calls.append(deepcopy(kwargs['messages']))
            candidate=deepcopy(item)
            if len(calls)>1: candidate['suggested_scope']={'type':'temporal','valid_to':'2026-10-01'}
            return {'candidates':[candidate]}
        monkeypatch.setattr(extractor.provider,'complete_json',complete_json)
        drafts=extractor.extract(namespace='test',evidence=[event],policy=ExtractionPolicy())
        assert len(calls)==2 and len(drafts)==1
        assert drafts[0].suggested_scope=={'type':'temporal','valid_to':'2026-10-01'}
        assert [a['status'] for a in extractor.last_invocation.metadata['attempts']]==['rejected','completed']
        assert 'upper time boundary' in calls[1][-1]['content']
        calls.clear()
        monkeypatch.setattr(extractor.provider,'complete_json',lambda **kw: calls.append(kw) or {'candidates':[deepcopy(item)]})
        assert extractor.extract(namespace='test',evidence=[event],policy=ExtractionPolicy())==[]
        assert len(calls)==2
        assert extractor.last_invocation.status=='invalid_schema'


def test_quality_oracle_rejects_reversed_dates_and_text_only_project_scope():
    from scripts.beta_live_workflows import qualified_transition,qualified_project
    rows=[{'object':'Berlin','suggested_scope':{'valid_from':'2026-10-01'}},
          {'object':'Paris','suggested_scope':{'valid_from':'2026-10-01'}}]
    assert not qualified_transition(rows,'berlin','paris','2026-10-01')
    rows[1]['suggested_scope']={'valid_to':'2026-10-01'}
    assert qualified_transition(rows,'berlin','paris','2026-10-01')
    assert not qualified_project([{'object':'detailed answers for Orion'},{'object':'concise answers elsewhere'}],'orion','detailed','concise')


def test_source_scope_catalog_has_only_evidence_derived_choices():
    from aletheia.extraction import _source_scopes
    assert _source_scopes('User prefers tea.')=={'unqualified':None}
    office=_source_scopes('The previous office was Paris. Since October 2026 the office is Berlin.')
    assert office['since:2026-10-01']=={'type':'temporal','valid_from':'2026-10-01'}
    assert office['until:2026-10-01']=={'type':'temporal','valid_to':'2026-10-01'}
    warehouse=_source_scopes('Until May 2024 the warehouse was Oslo. Since June 2024 the warehouse is Lisbon.')
    assert 'since:2024-05-01' not in warehouse
    assert warehouse['until:2024-05-01']['valid_to']=='2024-05-01'
    assert warehouse['since:2024-06-01']['valid_from']=='2024-06-01'
    assert _source_scopes('Only for project Vega use bullets.')['project!=Vega']['applies_when']=='project!=Vega'


def test_scope_reference_cannot_borrow_another_events_anchor(tmp_path):
    with closing(Memory.open(str(tmp_path/'binding.db'))) as memory:
        plain=memory.write_event(namespace='test',source_type='manual',content='User prefers tea.')
        dated=memory.write_event(namespace='test',source_type='manual',content='Since October 2026 the office is Berlin.')
        extractor=LLMExtractor(provider='mock_llm')
        item={'subject':'user','predicate':'prefers','object':'tea','memory_type':'preference','scope_ref':'since:2026-10-01',
              'evidence_span':{'evidence_id':plain.id,'start_char':0,'end_char':len(plain.content),'text':plain.content}}
        with pytest.raises(ValueError,match='not an anchor'):
            extractor._drafts_from_output({'candidates':[item]},evidence_by_id={plain.id:plain,dated.id:dated})
        item['scope_ref']='unqualified'
        assert extractor._drafts_from_output({'candidates':[item]},evidence_by_id={plain.id:plain})[0].suggested_scope is None


def test_source_interval_anchor_preserves_both_bounds():
    from aletheia.extraction import _source_scopes
    anchors=_source_scopes('The office is Rome from March 2025 until July 2025.')
    assert anchors['between:2025-03-01:2025-07-01']=={'type':'temporal','valid_from':'2025-03-01','valid_to':'2025-07-01'}


def test_owned_scratch_directory_has_private_acl_before_database_creation():
    from pathlib import Path
    from aletheia.storage.private_files import private_temporary_directory,require_windows_private_directory
    with private_temporary_directory(prefix='aletheia-scratch-test-') as directory:
        path=Path(directory)
        if os.name=='nt':
            require_windows_private_directory(path)
        else:
            assert path.stat().st_mode & 0o077 == 0
        with closing(Memory.open(str(path/'scratch.db'))) as memory:
            memory.write_event(namespace='test',source_type='manual',content='synthetic private scratch')
    assert not path.exists()


def test_temporal_quality_oracle_rejects_invented_other_boundaries():
    from scripts.beta_live_workflows import qualified_transition
    rows=[{'object':'Lisbon','suggested_scope':{'valid_from':'2024-06-01'}},
          {'object':'Oslo','suggested_scope':{'valid_from':'2024-05-01','valid_to':'2024-05-31'}}]
    assert not qualified_transition(rows,'lisbon','oslo','2024-06-01')
    rows[1]['suggested_scope']={'valid_to':'2024-05-01'}
    assert qualified_transition(rows,'lisbon','oslo','2024-06-01')
    rows[0]['suggested_scope']['valid_to']='2024-12-31'
    assert not qualified_transition(rows,'lisbon','oslo','2024-06-01')


@pytest.mark.skipif(os.name!='nt',reason='Native Windows directory creation and refusal')
def test_windows_reservation_creates_private_parent_and_refuses_shared_restore(tmp_path):
    import subprocess
    from pathlib import Path
    from aletheia.onboarding import reserve_database
    from aletheia.storage.private_files import require_windows_private_directory
    target=tmp_path/'new'/'nested'/'m.db'
    reserve_database(target)
    require_windows_private_directory(target.parent)
    require_windows_private_directory(target)
    with closing(Memory.open(str(target))) as memory:
        memory.write_event(namespace='test',source_type='manual',content='owned')
        shared=tmp_path/'shared-copy'
        shared.mkdir()
        subprocess.run(['icacls',str(shared),'/grant','*S-1-1-0:(OI)(CI)F'],check=True,capture_output=True)
        from aletheia.core.hardening import _sqlite_copy
        with pytest.raises(PermissionError):
            _sqlite_copy(memory.store.connection,shared/'must-not-exist.db')
        assert not (shared/'must-not-exist.db').exists()
