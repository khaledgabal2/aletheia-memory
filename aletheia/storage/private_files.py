"""Private artifact creation, including native Windows DACLs (not chmod)."""
from __future__ import annotations
import os
from functools import lru_cache
from pathlib import Path


def _windows_api():
    import ctypes
    from ctypes import wintypes as w
    adv = ctypes.WinDLL('advapi32', use_last_error=True)
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    adv.ConvertStringSecurityDescriptorToSecurityDescriptorW.argtypes = [w.LPCWSTR, w.DWORD, ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(w.DWORD)]
    adv.ConvertStringSecurityDescriptorToSecurityDescriptorW.restype = w.BOOL
    adv.SetFileSecurityW.argtypes = [w.LPCWSTR, w.DWORD, ctypes.c_void_p]
    adv.SetFileSecurityW.restype = w.BOOL
    kernel.LocalFree.argtypes = [ctypes.c_void_p]
    kernel.LocalFree.restype = ctypes.c_void_p
    return ctypes, w, adv, kernel


def windows_private_directory(path: Path) -> None:
    """Explicitly initialize an owned directory; callers must choose its scope."""
    c, w, adv, kernel = _windows_api()
    sd = c.c_void_p()
    # Owner and SYSTEM only; inheritable for SQLite's WAL/SHM/journal files.
    if not adv.ConvertStringSecurityDescriptorToSecurityDescriptorW('D:P(A;OICI;FA;;;OW)(A;OICI;FA;;;SY)', 1, c.byref(sd), None):
        raise c.WinError(c.get_last_error())
    try:
        if not adv.SetFileSecurityW(str(path), 0x80000004, sd):
            raise c.WinError(c.get_last_error())
    finally:
        kernel.LocalFree(sd)


def create_private_file(path: str | Path) -> int:
    if os.name != 'nt':
        return os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_NOFOLLOW', 0), 0o600)
    import msvcrt
    c, w, adv, kernel = _windows_api()
    class Attributes(c.Structure):
        _fields_ = [('length', w.DWORD), ('descriptor', c.c_void_p), ('inherit', w.BOOL)]
    sd = c.c_void_p()
    if not adv.ConvertStringSecurityDescriptorToSecurityDescriptorW('D:P(A;;FA;;;OW)(A;;FA;;;SY)', 1, c.byref(sd), None):
        raise c.WinError(c.get_last_error())
    kernel.CreateFileW.argtypes = [w.LPCWSTR, w.DWORD, w.DWORD, c.POINTER(Attributes), w.DWORD, w.DWORD, w.HANDLE]
    kernel.CreateFileW.restype = w.HANDLE
    kernel.CloseHandle.argtypes = [w.HANDLE]
    try:
        attrs = Attributes(c.sizeof(Attributes), sd, False)
        handle = kernel.CreateFileW(str(path), 0x40000000, 0, c.byref(attrs), 1, 0x80, None)
        if handle == w.HANDLE(-1).value:
            error = c.get_last_error()
            if error in (80, 183):
                raise FileExistsError(str(path))
            raise c.WinError(error)
        try:
            return msvcrt.open_osfhandle(handle, os.O_WRONLY | os.O_BINARY)
        except BaseException:
            kernel.CloseHandle(handle)
            raise
    finally:
        kernel.LocalFree(sd)


def require_windows_private_directory(path: Path) -> None:
    """Fail closed if sidecars could inherit access for another standard user.

    SYSTEM and elevated administrators are outside the local-user threat model.
    Existing directories are inspected, never silently re-permissioned.
    """
    import re
    c, w, adv, kernel = _windows_api()
    adv.GetFileSecurityW.argtypes = [w.LPCWSTR, w.DWORD, c.c_void_p, w.DWORD, c.POINTER(w.DWORD)]
    adv.GetFileSecurityW.restype = w.BOOL
    adv.ConvertSecurityDescriptorToStringSecurityDescriptorW.argtypes = [c.c_void_p, w.DWORD, w.DWORD, c.POINTER(w.LPWSTR), c.POINTER(w.DWORD)]
    adv.ConvertSecurityDescriptorToStringSecurityDescriptorW.restype = w.BOOL
    needed = w.DWORD()
    adv.GetFileSecurityW(str(path), 4, None, 0, c.byref(needed))
    buf = c.create_string_buffer(needed.value)
    if not adv.GetFileSecurityW(str(path), 4, buf, needed, c.byref(needed)):
        raise c.WinError(c.get_last_error())
    text = w.LPWSTR()
    if not adv.ConvertSecurityDescriptorToStringSecurityDescriptorW(buf, 1, 4, c.byref(text), None):
        raise c.WinError(c.get_last_error())
    try:
        descriptor = text.value
    finally:
        kernel.LocalFree(c.cast(text, c.c_void_p))
    # whoami returns identity metadata only; no credentials or shell execution.
    sid = _windows_user_sid()
    allowed = {'OW', 'CO', 'SY', 'BA', sid}
    aces = re.findall(r'\(([^()]*)\)', descriptor)
    if not aces or any(len(a.split(';')) != 6 or a.split(';')[0] != 'A' or a.split(';')[5] not in allowed for a in aces):
        raise PermissionError('Windows database directory must grant access only to its owner, SYSTEM and administrators; choose a private directory.')


@lru_cache(maxsize=1)
def _windows_user_sid():
    import csv
    import subprocess
    return list(csv.reader(subprocess.check_output(['whoami', '/user', '/fo', 'csv', '/nh'], text=True).splitlines()))[0][1]


from contextlib import contextmanager


@contextmanager
def private_temporary_directory(*, prefix='aletheia-'):
    """Owned scratch directory, private at creation even on Python 3.11 Windows."""
    import tempfile
    if os.name != 'nt':
        with tempfile.TemporaryDirectory(prefix=prefix) as directory:
            yield directory
        return
    import secrets
    import shutil
    directory=None
    for _ in range(100):
        candidate=Path(tempfile.gettempdir())/(prefix+secrets.token_hex(16))
        try:
            _windows_create_private_directory(candidate)
        except FileExistsError:
            continue
        directory=candidate
        break
    if directory is None:
        raise FileExistsError('Could not reserve a unique private scratch directory.')
    try:
        yield str(directory)
    finally:
        shutil.rmtree(directory)


def prepare_database_path(path: Path) -> None:
    """Check sidecar inheritance before any database bytes are written."""
    parent=path.parent
    if os.name!='nt':
        parent.mkdir(parents=True,exist_ok=True)
        return
    def mkdir(directory):
        if directory.exists():
            return
        mkdir(directory.parent)
        try:
            _windows_create_private_directory(directory)
        except FileExistsError:
            pass
    mkdir(parent)
    require_windows_private_directory(parent)
    if path.is_symlink():
        raise PermissionError('Windows private database paths cannot be symbolic links.')
    for suffix in ('','-wal','-shm','-journal'):
        artifact=Path(str(path)+suffix)
        if artifact.exists():
            require_windows_private_directory(artifact)


def _windows_create_private_directory(path: Path) -> None:
    c,w,adv,kernel=_windows_api()
    class Attributes(c.Structure):
        _fields_=[('length',w.DWORD),('descriptor',c.c_void_p),('inherit',w.BOOL)]
    sd=c.c_void_p()
    if not adv.ConvertStringSecurityDescriptorToSecurityDescriptorW('D:P(A;OICI;FA;;;OW)(A;OICI;FA;;;SY)',1,c.byref(sd),None):
        raise c.WinError(c.get_last_error())
    kernel.CreateDirectoryW.argtypes=[w.LPCWSTR,c.POINTER(Attributes)]
    kernel.CreateDirectoryW.restype=w.BOOL
    try:
        attrs=Attributes(c.sizeof(Attributes),sd,False)
        if not kernel.CreateDirectoryW(str(path),c.byref(attrs)):
            error=c.get_last_error()
            if error in (80,183):
                raise FileExistsError(str(path))
            raise c.WinError(error)
    finally:
        kernel.LocalFree(sd)
