"""Bounded child memory pressure and an isolated macOS disk-full filesystem.

Caller owns the shared validation lock. Never fill the host filesystem. The
disk image is 64 MiB and is always detached; only synthetic memory is used.
"""
import argparse
import errno
import json
import os
from pathlib import Path
import platform
import sqlite3
import subprocess
import sys
import traceback

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from aletheia import Memory


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    scope = parser.add_mutually_exclusive_group()
    scope.add_argument('--only-memory', action='store_true')
    scope.add_argument('--disk-only', action='store_true')
    args = parser.parse_args()
    args.output = args.output.resolve()
    args.output.mkdir(parents=True, exist_ok=False)
    rows = []
    def case(name, operation):
        try:
            result = {'name': name, 'status': 'passed', 'detail': operation()}
        except Exception:
            result = {'name': name, 'status': 'failed', 'error': traceback.format_exc()}
        rows.append(result)
        (args.output / 'cases.json').write_text(json.dumps(rows, indent=2))
        print(json.dumps(result), flush=True)

    def memory_pressure():
        code = '''import json,resource,sys
from aletheia import Memory
m=Memory.open(sys.argv[1],namespace='pressure/memory')
m.remember(memory_type='fact',subject='before',predicate='records',object='before pressure')
old=resource.getrlimit(resource.RLIMIT_AS)
blocks=[]
observed=False
try:
 resource.setrlimit(resource.RLIMIT_AS,(256*1024*1024,old[1]))
 try:
  for i in range(8): blocks.append(bytearray(32*1024*1024))
 except MemoryError: observed=True
finally:
 blocks.clear()
 resource.setrlimit(resource.RLIMIT_AS,old)
assert observed,'Memory limit was not enforced; do not count an unsupported host as passed'
m.remember(memory_type='fact',subject='after',predicate='records',object='after pressure')
assert len(m.list_claims(namespace=m.namespace))==2
assert m.store.connection.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
m.close()
m=Memory.open(sys.argv[1],namespace='pressure/memory')
assert len(m.list_claims(namespace=m.namespace))==2
m.close()
print(json.dumps({'memory_error_observed':observed,'bounded_allocation_mib':256,'post_failure_write_reopen_integrity':True,'scope':'Python allocation failure; not every SQLite/crypto allocation point'}))
'''
        result = subprocess.run([sys.executable, '-c', code, str(args.output / 'memory.db')],
            capture_output=True, text=True, timeout=60)
        (args.output / 'memory-child.log').write_text(result.stdout + result.stderr)
        assert result.returncode == 0, result.stderr
        return json.loads(result.stdout)
    if not args.disk_only:
        case('bounded_child_memory_failure_and_recovery', memory_pressure)

    def disk_full():
        if platform.system() != 'Darwin':
            raise RuntimeError('This disk-image probe requires macOS hdiutil; use native equivalent elsewhere')
        image = args.output / 'bounded.dmg'
        mount = args.output / 'mount'
        mount.mkdir(mode=0o700)
        log = args.output / 'disk-image.log'
        def run(*command):
            result = subprocess.run(command, capture_output=True, text=True, timeout=60)
            with log.open('a') as stream:
                stream.write(json.dumps(list(command)) + '\n' + result.stdout + result.stderr)
            assert result.returncode == 0, result.stderr
        run('hdiutil', 'create', '-size', '64m', '-fs', 'HFS+', '-volname', 'AletheiaSyntheticPressure', str(image))
        attached = False
        m = None
        try:
            run('hdiutil', 'attach', '-nobrowse', '-mountpoint', str(mount), str(image))
            attached = True
            m = Memory.open(str(mount / 'memory.db'), namespace='pressure/filesystem')
            original = m.remember(memory_type='fact', subject='before', predicate='records', object='before disk pressure')
            full = False
            written = 0
            with (mount / 'filler').open('wb', buffering=0) as stream:
                try:
                    for _ in range(160):
                        written += stream.write(b'x' * (512 * 1024))
                    os.fsync(stream.fileno())
                except OSError as error:
                    assert error.errno == errno.ENOSPC, error
                    full = True
            assert full, 'Bounded image did not become full; host filesystem was never a target'
            try:
                m.remember(memory_type='fact', subject='refused', predicate='records', object='refused canary ' * 100000)
            except sqlite3.DatabaseError as error:
                failure = {'kind': type(error).__name__, 'sqlite_errorcode': error.sqlite_errorcode, 'message': str(error)}
                assert error.sqlite_errorcode == sqlite3.SQLITE_FULL, failure
            else:
                raise AssertionError('Large write unexpectedly succeeded on full image')
            (mount / 'filler').unlink()
            assert m.store.connection.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
            assert [row.id for row in m.list_claims(namespace=m.namespace)] == [original.id]
            m.remember(memory_type='fact', subject='after', predicate='records', object='after disk pressure')
            m.close()
            m = Memory.open(str(mount / 'memory.db'), namespace='pressure/filesystem')
            assert len(m.list_claims(namespace=m.namespace)) == 2
            assert m.store.connection.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
            return {'image_mib': 64, 'filler_bytes': written, 'os_error': 'ENOSPC',
                    'database_failure': failure, 'rollback_integrity_write_reopen': True}
        finally:
            if m is not None:
                m.close()
            if attached:
                run('hdiutil', 'detach', str(mount))
                (args.output / 'detached.json').write_text(json.dumps({'detached': True, 'mount': str(mount)}))
    if not args.only_memory:
        case('isolated_filesystem_full_and_database_recovery', disk_full)
    return int(any(row['status'] != 'passed' for row in rows))


if __name__ == '__main__':
    raise SystemExit(main())
