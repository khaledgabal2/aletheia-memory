"""Inventory public surfaces and static test references; not runtime coverage."""
import argparse
import ast
import inspect
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from aletheia import Memory
from aletheia.cli.main import build_parser
from aletheia.service.http import openapi_schema
from aletheia.service.mcp import McpToolRegistry


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    calls = {}
    sources = {}
    for path in sorted((ROOT / 'tests').glob('test_*.py')):
        source = path.read_text()
        sources[str(path.relative_to(ROOT))] = source
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                calls.setdefault(node.func.attr, set()).add(f'{path.relative_to(ROOT)}:{node.lineno}')
    methods = {name: {'signature': str(inspect.signature(method)),
                      'static_test_references': sorted(calls.get(name, []))}
               for name, method in inspect.getmembers(Memory, callable) if not name.startswith('_')}
    def leaves(parser, prefix=()):
        actions = [a for a in parser._actions if isinstance(a, argparse._SubParsersAction)]
        if not actions:
            return [' '.join(prefix)]
        return [leaf for action in actions for name, child in action.choices.items()
                for leaf in leaves(child, (*prefix, name))]
    commands = leaves(build_parser())
    schema = openapi_schema()
    routes = []
    for path, operations in schema['paths'].items():
        for method in operations:
            if method.lower() not in {'get', 'post', 'put', 'patch', 'delete', 'options', 'head'}:
                continue
            routes.append({'method': method.upper(), 'path': path,
                           'literal_path_test_files': [name for name, source in sources.items() if path in source]})
    tools = McpToolRegistry.tools(None)
    report = {'limitation': 'Static names/literal paths can miss dynamic calls and do not prove tested semantics or execution.',
              'counts': {'python_methods': len(methods), 'cli_leaf_commands': len(commands),
                         'http_operations': len(routes), 'mcp_tools': len(tools)},
              'python': methods, 'cli': commands, 'http': routes,
              'mcp': [{'name': t.name, 'capability': t.required_capability, 'schema': t.input_schema,
                       'literal_name_test_files': [name for name, source in sources.items() if t.name in source]}
                      for t in tools]}
    args.output.write_text(json.dumps(report, indent=2))
    print(json.dumps(report['counts']))
    print('Methods without direct static test references:', ', '.join(name for name, data in methods.items()
                                                                     if not data['static_test_references']))


if __name__ == '__main__':
    main()
