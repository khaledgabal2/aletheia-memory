"""Map measured line coverage to public method bodies, excluding declarations.

An observed body is execution evidence only, never a semantic qualification.
CLI subprocesses are outside the single-process coverage collection.
"""
import argparse
import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--coverage', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    measured = json.loads(args.coverage.read_text())
    report = {'totals': measured['totals'], 'scope': __doc__, 'classes': {}}
    for name in ['aletheia/core/memory.py', 'aletheia/client.py', 'aletheia/service/mcp.py']:
        source = ast.parse((ROOT / name).read_text())
        data = measured['files'].get(name, {})
        executed = set(data.get('executed_lines', []))
        missing = set(data.get('missing_lines', []))
        for cls in (node for node in source.body if isinstance(node, ast.ClassDef)):
            methods = {}
            for method in cls.body:
                if not isinstance(method, (ast.FunctionDef, ast.AsyncFunctionDef)) or method.name.startswith('_'):
                    continue
                # Exclude decorators/signature/docstring: only measured executable
                # body lines count. Nested definitions are rare in these facades.
                body = list(method.body)
                if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) and isinstance(body[0].value.value, str):
                    body.pop(0)
                lines = {line for statement in body for line in range(statement.lineno, statement.end_lineno + 1)}
                seen, unseen = sorted(lines & executed), sorted(lines & missing)
                methods[method.name] = {'body_observed': bool(seen), 'executed_lines': len(seen),
                    'missing_lines': unseen, 'line': method.lineno}
            if methods:
                report['classes'][cls.name] = {'path': name, 'methods': methods,
                    'public_methods': len(methods), 'bodies_observed': sum(row['body_observed'] for row in methods.values()),
                    'unobserved_methods': [key for key, row in methods.items() if not row['body_observed']]}
    args.output.write_text(json.dumps(report, indent=2))
    print(json.dumps({'totals': report['totals'], 'classes': {key: {k: v for k, v in value.items() if k != 'methods'} for key, value in report['classes'].items()}}, indent=2))


if __name__ == '__main__':
    main()
