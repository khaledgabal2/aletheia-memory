"""Optional pytest plugin: record route/status coverage without payloads or IDs.

Enable with -p scripts.beta_http_coverage and ALETHEIA_BETA_HTTP_COVERAGE.
In-process and threaded socket handlers count; independent subprocesses do not.
Observed requests establish interface execution, not correctness for every input.
"""
from collections import Counter
from functools import wraps
import json
import os
from pathlib import Path
import re
import threading
from urllib.parse import urlsplit

_counts = Counter()
_lock = threading.Lock()
_original = None
_routes = []


def pytest_configure(config):
    global _original, _routes
    from aletheia.service.http import AletheiaService, openapi_schema
    for template, operations in openapi_schema()['paths'].items():
        pattern = re.escape(template)
        pattern = re.sub(r'\\\{[^}]+\\\}', '[^/]+', pattern)
        for method in operations:
            if method.lower() in {'get', 'post', 'put', 'patch', 'delete', 'head', 'options'}:
                _routes.append((method.upper(), template, re.compile('^' + pattern + '$')))
    _routes.sort(key=lambda row: ('{' in row[1], row[1]))
    _original = AletheiaService.handle_http
    @wraps(_original)
    def observed(self, *args, **kwargs):
        method, path = kwargs.get('method', ''), urlsplit(kwargs.get('path', '')).path
        match = next((template for verb, template, pattern in _routes if method == verb and pattern.fullmatch(path)), None)
        status = 'raised'
        try:
            result = _original(self, *args, **kwargs)
            status = str(result[0])
            return result
        finally:
            with _lock:
                _counts[(method, match, status)] += 1
    AletheiaService.handle_http = observed


def pytest_sessionfinish(session, exitstatus):
    from aletheia.service.http import AletheiaService
    if _original is not None:
        AletheiaService.handle_http = _original
    destination = os.environ.get('ALETHEIA_BETA_HTTP_COVERAGE')
    if not destination:
        return
    rows = []
    for method, template, _ in _routes:
        counts = {status: count for (verb, route, status), count in _counts.items() if verb == method and route == template}
        rows.append({'method': method, 'template': template, 'requests': sum(counts.values()), 'statuses': counts})
    Path(destination).write_text(json.dumps({'scope': __doc__, 'pytest_exitstatus': int(exitstatus),
        'declared_operations': len(rows), 'observed_operations': sum(bool(row['requests']) for row in rows),
        'unmatched_requests': sum(count for (_, route, _), count in _counts.items() if route is None),
        'operations': rows}, indent=2))
