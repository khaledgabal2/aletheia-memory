"""Bounded storage-capacity, multi-process socket and sustained lifecycle probes.

The campaign runner must own the host resource lock. Synthetic databases only.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import threading
import time
import traceback

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from aletheia import Memory
from aletheia.client import AletheiaClient
from aletheia.models import ServiceConfig
from aletheia.service.http import AletheiaDaemon


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--seconds', type=int, default=120)
    args = parser.parse_args()
    if not 120 <= args.seconds <= 3600:
        parser.error('--seconds must be between 120 and 3600')
    args.output.mkdir(parents=True, exist_ok=False)
    rows = []
    def case(name, fn):
        start = time.monotonic()
        try:
            row = {'name': name, 'status': 'passed', 'detail': fn()}
        except Exception:
            row = {'name': name, 'status': 'failed', 'error': traceback.format_exc()}
        row['seconds'] = round(time.monotonic() - start, 3)
        rows.append(row)
        (args.output / 'cases.json').write_text(json.dumps(rows, indent=2))
        print(json.dumps(row), flush=True)
    def capacity():
        with closing(Memory.open(str(args.output / 'capacity.db'), namespace='pressure/storage')) as m:
            db = m.store.connection
            pages = db.execute('PRAGMA page_count').fetchone()[0]
            db.execute(f'PRAGMA max_page_count={pages}')
            before = len(m.list_claims(namespace=m.namespace))
            try:
                m.remember(memory_type='fact', subject='capacity', predicate='records', object='bounded capacity canary ' * 50000)
            except sqlite3.DatabaseError as error:
                assert error.sqlite_errorcode == sqlite3.SQLITE_FULL, error
            else:
                raise AssertionError('Capacity-limited write unexpectedly succeeded')
            assert db.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
            assert len(m.list_claims(namespace=m.namespace)) == before
            db.execute(f'PRAGMA max_page_count={pages + 4096}')
            claim = m.remember(memory_type='fact', subject='capacity', predicate='records', object='recovered capacity')
            assert m.retrieve(m.namespace, 'recovered')[0].claim_id == claim.id
        with closing(Memory.open(str(args.output / 'capacity.db'), namespace='pressure/storage')) as reopened:
            assert reopened.read_claim(claim.id).object == 'recovered capacity'
        return {'failure': 'SQLITE_FULL', 'integrity': 'ok', 'subsequent_write_and_reopen': True,
                'limitation': 'SQLite page capacity, not physical filesystem exhaustion'}
    case('sqlite_capacity_failure_and_recovery', capacity)
    config = ServiceConfig(db_path=str(args.output / 'service.db'), auto_migrate=True, port=0,
        advertise_local=False, local_pairing_enabled=False, rate_limit_enabled=False)
    daemon = AletheiaDaemon(config)
    host, port = daemon.start()
    thread = threading.Thread(target=daemon.httpd.serve_forever, daemon=True)
    thread.start()
    ns = 'pressure/reliability'
    try:
        auth = daemon.service.auth
        client = auth.create_client(name='synthetic pressure agent', client_type='test')
        _, agent_token = auth.create_token(client_id=client.id, namespace_grants=[ns], privacy_ceiling='personal',
            capabilities=['memory:read', 'memory:context', 'memory:write_candidate', 'memory:feedback'])
        operator = auth.create_client(name='synthetic review operator', client_type='test')
        _, reviewer_token = auth.create_token(client_id=operator.id, namespace_grants=[ns], privacy_ceiling='personal',
            capabilities=['memory:read', 'memory:review', 'memory:audit'])
        url = f'http://{host}:{port}'
        m = daemon.service.memory
        for index in range(32):
            m.remember(namespace=ns, memory_type='fact', subject=f'worker-{index}', predicate='records', object='socketpressuremarker')
        def processes():
            code = '''import json,os,time
from urllib.request import Request,urlopen
started=time.monotonic()
for i in range(50):
 request=Request(os.environ['PRESSURE_URL']+'/v1/retrieve',data=json.dumps({'namespace':'pressure/reliability','query':'socketpressuremarker','limit':20}).encode(),headers={'Content-Type':'application/json','Authorization':'Bearer '+os.environ['PRESSURE_TOKEN']},method='POST')
 with urlopen(request,timeout=10) as response:
  rows=json.load(response)['data']
 assert len(rows)==20 and len({row['claim_id'] for row in rows})==20
print(json.dumps({'requests':50,'seconds':time.monotonic()-started}))
'''
            env = {**os.environ, 'PRESSURE_URL': url, 'PRESSURE_TOKEN': agent_token}
            def worker(index):
                result = subprocess.run([sys.executable, '-c', code], env=env, capture_output=True, text=True, timeout=90)
                assert result.returncode == 0, f'Worker {index} failed: {result.stderr}'
                return json.loads(result.stdout)
            with ThreadPoolExecutor(max_workers=8) as pool:
                results = list(pool.map(worker, range(8)))
            assert sum(row['requests'] for row in results) == 400
            return {'processes': 8, 'requests': 400, 'worker_results': results}
        case('http_eight_processes_400_real_retrievals', processes)
        def soak():
            agent, reviewer = AletheiaClient(url, agent_token), AletheiaClient(url, reviewer_token)
            deadline = time.monotonic() + args.seconds
            cycles, reads = 0, 0
            while time.monotonic() < deadline:
                if cycles < 5000:
                    marker = f'soakmarker{cycles}'
                    created = agent.remember_candidate(namespace=ns, memory_type='fact', subject=f'cycle-{cycles}',
                        predicate='observes', object=marker, evidence_text=f'cycle-{cycles} observes {marker}',
                        idempotency_key=f'cycle-create-{cycles}')
                    assert all(row['object'] != marker for row in agent.retrieve(namespace=ns, query=marker))
                    candidate = reviewer.get_candidate_for_review(created['candidate']['id'])
                    arguments = dict(action='promote', reason='Synthetic source checked by separate operator',
                        expected_revision=candidate['revision'], idempotency_key=f'cycle-review-{cycles}')
                    receipt = reviewer.review_candidate(candidate['id'], **arguments)
                    assert reviewer.review_candidate(candidate['id'], **arguments)['operation_id'] == receipt['operation_id']
                    claim_id = receipt['claim_id']
                    assert agent.retrieve(namespace=ns, query=marker)[0]['claim_id'] == claim_id
                    before = m.read_claim(claim_id).confidence_base
                    agent.feedback(namespace=ns, target_id=claim_id, signal='wrong', strength=0)
                    assert m.read_claim(claim_id).confidence_base == before and m.read_claim(claim_id).status == 'active'
                    context = agent.context_pack(namespace=ns, query=marker, token_budget=128, record_usage=True)
                    assert marker in context['markdown']
                    cycles += 1
                    if cycles % 50 == 0:
                        (args.output / 'soak-progress.json').write_text(json.dumps({'cycles': cycles,
                            'seconds_remaining': max(0, deadline - time.monotonic())}))
                else:
                    assert len(agent.retrieve(namespace=ns, query='socketpressuremarker', limit=20)) == 20
                    reads += 1
                time.sleep(.05)
            assert cycles >= 200
            assert m.store.connection.execute('SELECT count(*) FROM claims WHERE namespace = ?', (ns,)).fetchone()[0] == 32 + cycles
            assert m.store.connection.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
            return {'lifecycle_cycles': cycles, 'extra_reads': reads, 'duration_seconds': args.seconds,
                    'lifecycle': 'candidate -> invisible to trusted recall -> guarded operator approval -> idempotent replay -> recall -> zero feedback -> context usage'}
        case('sustained_review_recall_feedback_soak', soak)
    finally:
        daemon.shutdown()
        thread.join(timeout=5)
        (args.output / 'cleanup.json').write_text(json.dumps({'stopped': not thread.is_alive()}))
    return int(any(row['status'] != 'passed' for row in rows))


if __name__ == '__main__':
    raise SystemExit(main())
