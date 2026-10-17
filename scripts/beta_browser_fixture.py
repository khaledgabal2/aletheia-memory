"""Five-minute disposable UI fixture; holds the existing shared lock until cleanup."""
import argparse
import contextlib
import fcntl
import io
import json
import os
from pathlib import Path
import signal
import stat
import sys
import threading

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from aletheia.cli.main import main as cli_main
from aletheia.models import ServiceConfig
from aletheia.service.http import AletheiaDaemon
from scripts.v1_4_read_contract import browser_server
from scripts.v1_4_review_contract import seed
from scripts.v1_4_phase0 import NAMESPACE


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    os.chmod(args.output, 0o700)
    descriptor = os.open(f'/private/tmp/ultron-local-validation-{os.getuid()}.lock', os.O_RDWR | os.O_NOFOLLOW)
    info = os.fstat(descriptor)
    assert stat.S_ISREG(info.st_mode) and info.st_uid == os.getuid() and not info.st_mode & 0o077
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        os.close(descriptor)
        print('resource_deferred; no fixture started', flush=True)
        return 75
    stop = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    daemon = AletheiaDaemon(ServiceConfig(db_path=str(args.output / 'ui.db'), port=0, auto_migrate=True,
        console_enabled=True, rate_limit_enabled=False, advertise_local=False, local_pairing_enabled=False))
    # Console trace/integrity actions write operational domain tables. Keep
    # them separate from the read contract's strict unchanged-table baseline.
    console_daemon = AletheiaDaemon(ServiceConfig(db_path=str(args.output / 'console.db'), port=0, auto_migrate=True,
        console_enabled=True, rate_limit_enabled=False, advertise_local=False, local_pairing_enabled=False))
    proxies, threads = [], []
    try:
        host, port = daemon.start()
        thread = threading.Thread(target=daemon.httpd.serve_forever, daemon=True)
        thread.start()
        threads.append(thread)
        url = f'http://{host}:{port}'
        console_host, console_port = console_daemon.start()
        console_thread = threading.Thread(target=console_daemon.httpd.serve_forever, daemon=True)
        console_thread.start()
        threads.append(console_thread)
        console_daemon.service.memory.remember(namespace=NAMESPACE, memory_type='preference', subject='demo',
            predicate='prefers', object='careful architecture notes', confidence=.95)
        memory = daemon.service.memory
        claim = memory.remember(namespace=NAMESPACE, memory_type='preference', subject='demo', predicate='prefers',
                                object='careful architecture notes', confidence=.95)
        first = seed(memory, 'User prefers careful architecture notes.')
        second = seed(memory, 'User prefers compact review summaries.')
        manifest = {'console': f'http://{console_host}:{console_port}/console', 'namespace': NAMESPACE, 'pid': os.getpid()}
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            assert cli_main(['console', 'login-token', '--db', str(args.output / 'console.db'), '--namespace', NAMESPACE]) == 0
        manifest['synthetic_login_token'] = json.loads(buffer.getvalue())['login_token']
        for kind, candidates in [('read', ()), ('review', (first, second))]:
            proxy = browser_server(daemon.service, url, claim, review_candidates=candidates)
            proxies.append(proxy)
            thread = threading.Thread(target=proxy.serve_forever, daemon=True)
            thread.start()
            threads.append(thread)
            manifest[kind] = f'http://127.0.0.1:{proxy.server_port}/'
        (args.output / 'fixture.json').write_text(json.dumps(manifest, indent=2))
        print(json.dumps({key: value for key, value in manifest.items() if key != 'synthetic_login_token'}), flush=True)
        stop.wait(300)
    finally:
        for proxy in proxies:
            proxy.shutdown()
            proxy.server_close()
        daemon.shutdown()
        console_daemon.shutdown()
        for thread in threads:
            thread.join(timeout=5)
        os.close(descriptor)
        (args.output / 'cleanup.json').write_text(json.dumps({'stopped': True, 'pid': os.getpid()}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
