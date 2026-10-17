"""Adversarial synthetic cases; machine-readable per-case receipts and retained DBs."""
from __future__ import annotations
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import math
import subprocess
from pathlib import Path
import statistics
import sys
import time
import traceback

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from aletheia import Memory
from aletheia.core.memory import CANDIDATE_MEMORY_TYPES, FEEDBACK_SIGNALS, RESOLUTION_STRATEGIES


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    receipts = []
    def case(name, fn):
        start = time.monotonic()
        memory = Memory.open(str(args.output / (name + '.db')), namespace='pressure/main')
        try:
            detail = fn(memory)
            item = dict(name=name, status='passed', detail=detail)
        except Exception:
            item = dict(name=name, status='failed', error=traceback.format_exc())
        finally:
            memory.close()
        item['seconds'] = round(time.monotonic() - start, 3)
        receipts.append(item)
        (args.output / 'cases.json').write_text(json.dumps(receipts, indent=2, default=str))
        print(json.dumps(item, default=str), flush=True)
    def remember(m, **kw):
        values = dict(namespace='pressure/main', memory_type='fact', subject='fixture',
                      predicate='records', object='synthetic needle', confidence=.8)
        values.update(kw)
        return m.remember(**values)
    def types(m):
        checked = sorted(CANDIDATE_MEMORY_TYPES | {'fact', 'project', 'session', 'reflection', 'custom_pressure_type'})
        for kind in checked:
            claim = remember(m, memory_type=kind, subject=kind, object='typeprobe ' + kind)
            assert any(r.claim_id == claim.id for r in m.retrieve('pressure/main', 'typeprobe', memory_types=[kind]))
            assert m.explain_claim(claim.id).evidence
        return checked
    case('all_memory_types', types)
    for signal in sorted(FEEDBACK_SIGNALS):
        def feedback(m, signal=signal):
            claim = remember(m)
            record = m.feedback(claim.id, signal=signal, namespace='pressure/main', note='synthetic evaluation')
            assert record.signal == signal
            confidence = m.compute_confidence(claim.id)
            return str(confidence)
        case('feedback_' + signal, feedback)
    def assistant_loop(m):
        claim = remember(m)
        for _ in range(100):
            record = m.feedback(claim.id, signal='confirmed', source='assistant', namespace='pressure/main')
            assert record.strength <= .05
        return str(m.compute_confidence(claim.id))
    case('assistant_feedback_loop_100', assistant_loop)
    def zero_strength(m):
        observations = []
        for signal in sorted(FEEDBACK_SIGNALS):
            claim = remember(m, subject='zero_' + signal, confidence=.5)
            before = m.compute_confidence(claim.id)
            m.feedback(claim.id, namespace='pressure/main', signal=signal, strength=0)
            after = m.compute_confidence(claim.id, at_time=before.computed_at)
            observations.append({'signal': signal, 'before_factor': before.feedback_factor,
                                 'after_factor': after.feedback_factor,
                                 'before_status': claim.status, 'after_status': m.read_claim(claim.id).status})
        assert all(r['before_factor'] == r['after_factor'] and r['before_status'] == r['after_status']
                   for r in observations), observations
        return observations
    case('zero_strength_feedback_is_inert', zero_strength)
    for strategy in sorted(RESOLUTION_STRATEGIES):
        def conflict(m, strategy=strategy):
            first = remember(m, memory_type='preference', predicate='prefers_editor', object='Vim')
            second = remember(m, memory_type='preference', predicate='prefers_editor', object='Emacs')
            m.detect_conflicts(namespace='pressure/main')
            families = m.list_conflicts(namespace='pressure/main')
            assert families, 'Incompatible preferences produced no conflict'
            family = families[0]
            options = dict(strategy=strategy, note='Synthetic operator review')
            if strategy == 'manual':
                options['active_claim_id'] = second.id
            if strategy == 'context_scope':
                options['scoped_claims'] = [
                    {'claim_id': first.id, 'scope_type': 'contextual', 'applies_when': 'architecture'},
                    {'claim_id': second.id, 'scope_type': 'contextual', 'applies_when': 'progress'}]
            if strategy == 'time_scope':
                options['scoped_claims'] = [
                    {'claim_id': first.id, 'scope_type': 'temporal', 'valid_to': '2026-01-01T00:00:00Z'},
                    {'claim_id': second.id, 'scope_type': 'temporal', 'valid_from': '2026-01-01T00:00:00Z'}]
            resolution = m.resolve_conflict(family.id, **options)
            if strategy == 'mark_unresolved':
                assert m.read_conflict(family.id).status == 'unresolved'
            else:
                assert m.read_conflict(family.id).status == 'resolved'
            if strategy in {'context_scope', 'time_scope'}:
                assert all(m.list_claim_scopes(claim.id) for claim in [first, second])
            elif strategy != 'mark_unresolved':
                statuses = [m.read_claim(claim.id).status for claim in [first, second]]
                assert statuses.count('active') == 1
                assert ('rejected' if strategy == 'reject_weak_claims' else 'superseded') in statuses
            return {'resolution': str(resolution), 'claims': [m.read_claim(c.id).status for c in [first, second]]}
        case('conflict_' + strategy, conflict)
    def namespace(m):
        remember(m, namespace='pressure/private', object='canary_secret_7284')
        for query in ['canary_secret_7284', '*', '', '" OR 1=1 --']:
            assert not m.retrieve('pressure/main', query)
        return 'No cross-namespace results for literal, empty, wildcard or SQL-like queries'
    case('namespace_adversarial_queries', namespace)
    def input_edges(m):
        values = ['中文记忆 café مرحبا 🧠', 'quote \' " ; DROP TABLE claims; --',
                  'line one\nline two\tend', 'x' * 100000]
        for index, value in enumerate(values):
            claim = remember(m, subject=f'edge{index}', object=value)
            assert m.read_claim(claim.id).object == value
        return {'roundtripped': len(values), 'largest_characters': 100000}
    case('unicode_sql_long_payloads', input_edges)
    def load(m):
        latencies = []
        for i in range(5000):
            remember(m, subject=f'entity{i}', object=f'pressuretoken item{i}')
        for _ in range(100):
            start = time.perf_counter()
            hits = m.retrieve('pressure/main', 'pressuretoken', limit=20)
            latencies.append(time.perf_counter() - start)
            assert len(hits) == 20
            assert len({r.claim_id for r in hits}) == 20
        return {'claims': 5000, 'queries': 100, 'median_seconds': statistics.median(latencies),
                'max_seconds': max(latencies)}
    case('bulk_5000_retrieval_100', load)
    def concurrent(m):
        path = str(args.output / 'concurrent_connections.db')
        seed = Memory.open(path)
        seed.close()
        def worker(number):
            own = Memory.open(path, namespace='pressure/main')
            try:
                for i in range(25):
                    remember(own, subject=f'worker{number}_{i}', object='concurrentmarker')
                return 25
            finally:
                own.close()
        with ThreadPoolExecutor(max_workers=4) as pool:
            assert sum(pool.map(worker, range(4))) == 100
        check = Memory.open(path)
        try:
            assert len(check.list_claims(namespace='pressure/main', limit=200)) == 100
        finally:
            check.close()
        return 'Four independent connections; 100 writes persisted'
    case('concurrent_writers_4x25', concurrent)
    def nonfinite(m):
        accepted = []
        for value in [float('nan'), float('inf'), -float('inf')]:
            try:
                claim = remember(m, subject=str(value), confidence=value)
            except Exception as error:
                # Persist rejection class for inspection rather than assuming a specific validator.
                accepted.append({'input': str(value), 'rejected': type(error).__name__})
            else:
                assert math.isfinite(claim.confidence_base), 'Non-finite confidence persisted'
                accepted.append({'input': str(value), 'normalized': claim.confidence_base})
        return accepted
    case('nonfinite_confidence', nonfinite)
    def invalid_budgets(m):
        claim = remember(m)
        observations = []
        for value in [float('nan'), float('inf'), -1, True, '100']:
            try:
                pack = m.context_pack('pressure/main', 'synthetic', token_budget=value)
            except Exception as error:
                observations.append({'input': str(value), 'rejected': type(error).__name__})
            else:
                observations.append({'input': str(value), 'included': len(pack.items())})
        assert all('rejected' in row for row in observations), observations
        return observations
    case('invalid_context_budgets', invalid_budgets)
    def missing_scope(m):
        for obj in ['Vim', 'Emacs']:
            remember(m, memory_type='preference', predicate='prefers_editor', object=obj)
        conflict = m.list_conflicts(namespace='pressure/main')[0]
        try:
            m.resolve_conflict(conflict.id, strategy='context_scope', note='No actual scope supplied')
        except Exception as error:
            return {'rejected': type(error).__name__}
        assert m.read_conflict(conflict.id).status == 'unresolved', 'Conflict marked resolved without any supplied scopes'
    case('context_resolution_without_scopes', missing_scope)
    def crash_rollback(m):
        path = str(args.output / 'crash_target.db')
        seed = Memory.open(path)
        seed.close()
        code = '''import os,sys
from aletheia import Memory
m=Memory.open(sys.argv[1])
with m.store.transaction():
 m.remember(namespace="pressure/main",memory_type="fact",subject="crash",predicate="records",object="uncommittedcanary")
 os._exit(7)
'''
        result = subprocess.run([sys.executable, '-c', code, path], timeout=30)
        assert result.returncode == 7
        reopened = Memory.open(path)
        try:
            assert reopened.store.connection.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
            assert not reopened.list_claims(namespace='pressure/main')
            assert not reopened.retrieve('pressure/main', 'uncommittedcanary')
        finally:
            reopened.close()
        return 'Abrupt process exit inside a write transaction preserves integrity and rolls back claims'
    case('process_crash_transaction_rollback', crash_rollback)
    return 1 if any(item['status'] == 'failed' for item in receipts) else 0


if __name__ == '__main__':
    raise SystemExit(main())
