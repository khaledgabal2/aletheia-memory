"""Exercise every CLI leaf's help in a real installed subprocess, without writes.

This qualifies parsing/discoverability and side-effect-free help. Positive
command workflows are covered separately by the milestone and recovery harness.
"""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from aletheia.cli.main import build_parser


def leaves(parser, prefix=()):
    actions = [action for action in parser._actions if isinstance(action, argparse._SubParsersAction)]
    if not actions:
        return [prefix]
    return [leaf for action in actions for name, child in action.choices.items() for leaf in leaves(child, (*prefix, name))]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--python', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output = args.output.resolve()
    args.output.mkdir(parents=True, exist_ok=False)
    working = args.output / 'empty-working-directory'
    working.mkdir()
    rows = []
    interpreter = str(args.python.absolute())  # Preserve venv, not its resolved base symlink.
    for index, command in enumerate(leaves(build_parser())):
        started = time.monotonic()
        result = subprocess.run([interpreter, '-I', '-m', 'aletheia.cli.main', *command, '--help'],
            cwd=working, capture_output=True, text=True, timeout=30)
        log = f'{index:03d}-help.log'
        (args.output / log).write_text(result.stdout + result.stderr)
        rows.append({'command': list(command), 'returncode': result.returncode, 'log': log,
            'seconds': round(time.monotonic() - started, 3),
            'passed': result.returncode == 0 and 'usage:' in result.stdout.lower() and not list(working.iterdir())})
        (args.output / 'commands.json').write_text(json.dumps(rows, indent=2))
    summary = {'scope': __doc__, 'commands': len(rows), 'passed': sum(row['passed'] for row in rows),
               'working_directory_unchanged': not list(working.iterdir())}
    (args.output / 'summary.json').write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))
    return int(any(not row['passed'] for row in rows))


if __name__ == '__main__':
    raise SystemExit(main())
