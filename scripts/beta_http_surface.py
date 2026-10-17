"""Real-socket refusal/empty-state contracts for every declared HTTP operation.

Positive domain semantics are qualified by the workflow tests, not this sweep.
Missing-object IDs and an empty namespace deliberately exercise error envelopes;
no request uses caller data or external providers. Only status/code are retained.
"""
import argparse
import json
import os
from pathlib import Path
import re
import sys
import threading
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from aletheia.models import ServiceConfig
from aletheia.service.http import AletheiaDaemon, openapi_schema


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output = args.output.resolve()
    args.output.mkdir(parents=True, exist_ok=False)
    daemon = AletheiaDaemon(ServiceConfig(db_path=str(args.output / 'http.db'), port=0, auto_migrate=True,
        rate_limit_enabled=False, advertise_local=False, console_enabled=True,
        local_pairing_enabled=os.name == 'posix', identity_directory=str(args.output / 'identities')))
    rows = []
    try:
        host, port = daemon.start()
        thread = threading.Thread(target=daemon.httpd.serve_forever, daemon=True)
        thread.start()
        m = daemon.service.memory
        retained = m.remember(namespace='pressure/retained', memory_type='fact', subject='synthetic',
            predicate='retains', object='untouched canary', privacy_level='public')
        operator = daemon.service.auth.create_client(name='Synthetic HTTP route operator', client_type='test')
        _, token = daemon.service.auth.create_token(client_id=operator.id, namespace_grants=['*'],
            capabilities=['memory:admin'], privacy_ceiling='secret')
        for index, (template, operations) in enumerate(openapi_schema()['paths'].items()):
            for method, operation in operations.items():
                if method not in {'get', 'post', 'put', 'patch', 'delete', 'head', 'options'}:
                    continue
                path = re.sub(r'\{[^}]+\}', 'missing-synthetic-object', template)
                query = {item['name']: 'pressure/empty' if item['name'] == 'namespace' else 'missing-synthetic-value'
                         for item in operation.get('parameters', []) if item.get('in') == 'query' and (item.get('required') or item.get('name') == 'namespace')}
                if query:
                    path += '?' + urlencode(query)
                payload = {'namespace': 'pressure/empty', 'provider': 'mock',
                    'output_path': str(args.output / f'output-{index}-{method}'),
                    'output_dir': str(args.output / f'docs-{index}-{method}'),
                    'target_db_path': str(args.output / f'restore-{index}-{method}.db'),
                    'backup_path': str(args.output / 'missing-backup.alet'),
                    'input_path': str(args.output / 'missing-input.alet'),
                    'path': str(args.output / 'missing-plugin'), 'service_url': None}
                body = None if method in {'get', 'head'} else json.dumps(payload).encode()
                request = Request(f'http://{host}:{port}' + path, data=body, method=method.upper(),
                    headers={'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json'})
                try:
                    response = urlopen(request, timeout=60)
                except HTTPError as error:
                    response = error
                with response:
                    raw = response.read()
                    content_type = response.headers.get('Content-Type', '')
                    try:
                        envelope = json.loads(raw)
                    except ValueError:
                        envelope = None
                    status = response.status
                code = ((envelope or {}).get('error') or {}).get('code') if isinstance(envelope, dict) else None
                valid = isinstance(envelope, dict) and ('data' in envelope or 'openapi' in envelope if status < 400 else bool(code))
                if template == '/v1/metrics' and method == 'get' and status == 200:
                    valid = bool(raw) and 'text/plain' in content_type
                if template == '/console' and status == 200:
                    valid = 'text/html' in content_type and b'Aletheia Console' in raw
                if template == '/console/assets/app.css' and status == 200:
                    valid = bool(raw) and 'text/css' in content_type
                row = {'method': method.upper(), 'template': template, 'status': status, 'error_code': code,
                       'content_type': content_type, 'envelope_valid': valid,
                       'passed': valid and (status < 500 or os.name != 'posix' and code == 'pairing_unavailable')}
                rows.append(row)
                (args.output / 'operations.json').write_text(json.dumps(rows, indent=2))
        assert m.read_claim(retained.id).object == retained.object
        assert m.store.connection.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
        summary = {'scope': __doc__, 'operations': len(rows), 'passed': sum(row['passed'] for row in rows),
                   'server_errors': [row for row in rows if not row['passed']], 'retained_namespace_unchanged': True}
        (args.output / 'summary.json').write_text(json.dumps(summary, indent=2))
        print(json.dumps(summary, indent=2))
        return int(any(not row['passed'] for row in rows))
    finally:
        daemon.shutdown()
        if 'thread' in locals():
            thread.join(timeout=5)


if __name__ == '__main__':
    raise SystemExit(main())
