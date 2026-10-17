"""Bounded fresh-process CLI readiness measurements; never invokes a model."""
import argparse
import json
import math
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
from urllib.request import urlopen
from urllib.error import URLError


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--samples', type=int, default=5)
    args = p.parse_args()
    if not 3 <= args.samples <= 20:
        p.error('samples must be between 3 and 20')
    args.output.mkdir(parents=True, exist_ok=False)
    if os.name == 'nt':
        from aletheia.storage.private_files import windows_private_directory
        windows_private_directory(args.output)
    rows = []
    # Explicit supported profile, avoiding unsupported Windows local pairing.
    targets = {'new_database': {'p95': 45, 'maximum': 60}, 'current_database': {'p95': 15, 'maximum': 30}}
    for index in range(args.samples):
        db = args.output / f'sample-{index}.db'
        for profile, limits in targets.items():
            with socket.socket() as sock:
                sock.bind(('127.0.0.1', 0))
                port = sock.getsockname()[1]
            command = [sys.executable, '-m', 'aletheia.cli.main', 'serve', '--db', str(db.resolve()),
                       '--port', str(port), '--auto-migrate', '--no-advertise', '--no-local-pairing']
            started = time.monotonic()
            ready = False
            with (args.output / f'{index}-{profile}.log').open('w') as log:
                process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT)
                try:
                    while time.monotonic() - started < limits['maximum'] and process.poll() is None:
                        try:
                            with urlopen(f'http://127.0.0.1:{port}/v1/ready', timeout=.5) as response:
                                body = json.load(response)
                            if body.get('data', {}).get('ready') is True:
                                ready = True
                                break
                        except (URLError, TimeoutError, ConnectionError):
                            pass
                        time.sleep(.025)
                    rows.append({'profile': profile, 'sample': index, 'seconds': time.monotonic()-started,
                                 'ready': ready, 'child_exit': process.poll()})
                finally:
                    process.terminate()
                    try:
                        process.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=5)
            (args.output / 'progress.json').write_text(json.dumps(rows, indent=2))
    results = {}
    for profile, limits in targets.items():
        values = sorted(r['seconds'] for r in rows if r['profile'] == profile)
        p95 = values[math.ceil(.95 * len(values))-1]
        results[profile] = {'p95_seconds': p95, 'maximum_seconds': max(values), 'targets_seconds': limits,
                            'passed': all(r['ready'] for r in rows if r['profile'] == profile)
                            and p95 <= limits['p95'] and max(values) <= limits['maximum']}
    receipt = {'status': 'passed' if all(r['passed'] for r in results.values()) else 'failed',
               'samples': rows, 'results': results, 'scope': 'Fresh Python processes, loopback /v1/ready, auth enabled; no advertisement/pairing, worker, model load or OS cache eviction.'}
    (args.output / 'receipt.json').write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt))
    return 0 if receipt['status'] == 'passed' else 1

if __name__ == '__main__':
    raise SystemExit(main())
