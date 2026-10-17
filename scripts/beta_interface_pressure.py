"""Loopback HTTP/SDK load, idempotency, and actual CLI stdio wire probes."""
import argparse
import asyncio
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import subprocess
import sys
import time
import traceback

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from aletheia.client import AletheiaClient, AsyncAletheiaClient
from scripts.v1_4_phase0 import local_service, request, NAMESPACE


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    rows = []
    def case(name, fn):
        start = time.monotonic()
        try:
            item = {'name': name, 'status': 'passed', 'detail': fn()}
        except Exception:
            item = {'name': name, 'status': 'failed', 'error': traceback.format_exc()}
        item['seconds'] = round(time.monotonic() - start, 3)
        rows.append(item)
        (args.output / 'cases.json').write_text(json.dumps(rows, indent=2, default=str))
        print(json.dumps(item, default=str), flush=True)
    with local_service(str(args.output)) as (service, url, tokens):
        document = request(url, 'GET', '/v1/openapi.json')['body']['data']
        (args.output / 'openapi.json').write_text(json.dumps(document, indent=2))
        def reads():
            def one(_):
                client = AletheiaClient(url, tokens['agent'])
                return client.current_principal()['supported_profiles']
            with ThreadPoolExecutor(max_workers=8) as pool:
                values = list(pool.map(one, range(100)))
            assert all('agent-onboarding-v1' in v for v in values)
            return '100 authenticated reads through 8 client workers'
        case('http_sync_sdk_concurrent_100', reads)
        def async_reads():
            async def run():
                client = AsyncAletheiaClient(url, tokens['agent'])
                result = await asyncio.gather(*(client.health() for _ in range(100)))
                assert len(result) == 100
            asyncio.run(run())
            return '100 async SDK health calls'
        case('http_async_sdk_concurrent_100', async_reads)
        def idempotency():
            payload = dict(namespace=NAMESPACE, memory_type='preference', subject='user',
                           predicate='prefers', object='idempotentmarker', evidence_text='User prefers idempotentmarker.')
            def one(_):
                return AletheiaClient(url, tokens['agent']).remember_candidate(
                    idempotency_key='pressure-same-operation', **payload)
            with ThreadPoolExecutor(max_workers=8) as pool:
                results = list(pool.map(one, range(32)))
            candidates = service.memory.list_candidates(NAMESPACE)
            assert len(candidates) == 1, f'Repeated operation created {len(candidates)} candidates'
            assert len({json.dumps(r, sort_keys=True) for r in results}) == 1
            return '32 concurrent retries produce one identical candidate result'
        case('http_candidate_idempotency_32', idempotency)
        def unauthorized():
            before = len(service.memory.list_candidates(NAMESPACE))
            for namespace in [NAMESPACE, 'other/private']:
                response = request(url, 'POST', '/v1/remember', token=tokens['reader'], payload={
                    'namespace': namespace, 'memory_type': 'fact', 'subject': 'attacker',
                    'predicate': 'writes', 'object': 'deniedmarker', 'write_mode': 'active'})
                assert response['status'] == 403, response['status']
            assert len(service.memory.list_candidates(NAMESPACE)) == before
            return 'Read-only token cannot perform active writes or namespace escapes'
        case('http_denied_mutations', unauthorized)
    command = [sys.executable, '-m', 'aletheia.cli.main', 'mcp', '--db',
               str(args.output / 'stdio.db'), '--namespace', 'pressure/stdio', '--mode', 'read_only']
    def stdio_custom():
        result = subprocess.run(command, input=json.dumps({'tool': 'memory_search', 'arguments': {'query': 'synthetic'}}) + '\n',
                                capture_output=True, text=True, timeout=45)
        (args.output / 'stdio-custom.log').write_text(result.stdout + result.stderr)
        messages = [json.loads(line) for line in result.stdout.splitlines()]
        assert result.returncode == 0 and any(row.get('ok') is True for row in messages), messages
        return {'messages': len(messages), 'protocol': 'custom line-delimited tool/arguments'}
    case('cli_stdio_custom_protocol', stdio_custom)
    def stdio_default():
        default = list(command)
        default[default.index('--namespace') + 1] = 'user/default'
        result = subprocess.run(default, input=json.dumps({'tool': 'memory_search', 'arguments': {'query': 'synthetic'}}) + '\n',
                                capture_output=True, text=True, timeout=45)
        (args.output / 'stdio-default.log').write_text(result.stdout + result.stderr)
        messages = [json.loads(line) for line in result.stdout.splitlines()]
        assert result.returncode == 0 and any(row.get('ok') is True for row in messages), messages[-1:]
        return 'Default namespace succeeds with the same read-only tool'
    case('cli_stdio_default_namespace_control', stdio_default)
    def stdio_mcp():
        wire = {'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {
            'protocolVersion': '2025-06-18', 'capabilities': {},
            'clientInfo': {'name': 'beta-pressure', 'version': '1'}}}
        result = subprocess.run(command, input=json.dumps(wire) + '\n',
                                capture_output=True, text=True, timeout=45)
        (args.output / 'stdio-jsonrpc.log').write_text(result.stdout + result.stderr)
        messages = [json.loads(line) for line in result.stdout.splitlines()]
        assert any(row.get('jsonrpc') == '2.0' and row.get('id') == 1 and 'result' in row for row in messages), messages
        return 'MCP initialize handshake succeeded'
    case('cli_stdio_mcp_initialize', stdio_mcp)
    return int(any(row['status'] == 'failed' for row in rows))


if __name__ == '__main__':
    raise SystemExit(main())
