"""Retain assertion locations that historical scorecards reduce to empty strings."""
import argparse
import json
from pathlib import Path
import runpy
import sys
import traceback


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--script', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    path = args.script.resolve()
    filename = str(path)
    events = []
    def trace(frame, event, value):
        if frame.f_code.co_filename != filename:
            return None
        if event == 'exception':
            kind, error, tb = value
            if issubclass(kind, (AssertionError, ValueError, RuntimeError)):
                entry = {'function': frame.f_code.co_name, 'line': frame.f_lineno,
                         'error': ''.join(traceback.format_exception(kind, error, tb))}
                if entry not in events:
                    events.append(entry)
        return trace
    sys.argv = [str(path)]
    sys.settrace(trace)
    try:
        runpy.run_path(str(path), run_name='__main__')
    except SystemExit as error:
        status = int(error.code or 0)
    else:
        status = 0
    finally:
        sys.settrace(None)
        args.output.write_text(json.dumps(events, indent=2))
    return status


if __name__ == '__main__':
    raise SystemExit(main())
