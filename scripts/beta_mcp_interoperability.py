"""Exercise Aletheia stdio with the independently maintained official MCP SDK.

Run from an isolated environment with mcp==1.30.0. No Aletheia import is used
by the client; --server-python selects the installed artifact under test.
"""
import argparse
import asyncio
from importlib.metadata import version
import json
from pathlib import Path
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def run(args):
    # Keep the venv entrypoint: resolving its symlink selects the base Python
    # and silently discards the installed artifact's site-packages.
    params = StdioServerParameters(command=str(args.server_python.absolute()), args=[
        '-I', '-m', 'aletheia.cli.main', 'mcp', '--db', str(args.output / 'memory.db'),
        '--namespace', 'evaluation/official-sdk', '--mode', 'read_write_candidate'])
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as client:
            initialized = await client.initialize()
            assert initialized.capabilities.tools is not None
            tools = await client.list_tools()
            names = {tool.name for tool in tools.tools}
            assert {'memory_search', 'memory_remember', 'memory_context_pack'} <= names
            for tool in tools.tools:
                assert tool.inputSchema['type'] == 'object'
            arguments = dict(memory_type='fact', subject='synthetic sdk', predicate='observes',
                object='officialsdkcanary', evidence_text='Synthetic sdk observes officialsdkcanary.')
            created = await client.call_tool('memory_remember', arguments)
            assert not created.isError
            result = await client.call_tool('memory_search', {'query': 'officialsdkcanary'})
            assert not result.isError
            assert json.loads(result.content[0].text) == []
            active = await client.call_tool('memory_remember', {**arguments, 'write_mode': 'active'})
            escaped = await client.call_tool('memory_search', {'query': 'canary', 'namespace': 'private/other'})
            assert active.isError and escaped.isError
            await client.send_ping()
            return {'sdk_version': version('mcp'), 'protocol_version': initialized.protocolVersion,
                    'server': initialized.serverInfo.model_dump(), 'listed_tools': sorted(names),
                    'candidate_write': True, 'candidate_excluded_from_recall': True,
                    'active_write_denied': True, 'namespace_escape_denied': True, 'ping': True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--server-python', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output = args.output.resolve()
    args.output.mkdir(parents=True, exist_ok=False)
    receipt = asyncio.run(run(args))
    (args.output / 'receipt.json').write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt))


if __name__ == '__main__':
    main()
