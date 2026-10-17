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
                'evidence_span':{'evidence_id':event.id,'start_char':0,'end_char':len(event.content),'text':event.content}}]}
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
