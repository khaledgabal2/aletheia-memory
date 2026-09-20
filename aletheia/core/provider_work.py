"""Suspend service snapshots before provider work, then replay with fresh checks.

Embedded calls are unchanged. A service route uses a request-local transcript:
its database work rolls back before a missing provider result is requested.
Replaying the route consumes cached results only for exactly the same inputs.
"""
from contextlib import contextmanager
from contextvars import ContextVar
from copy import deepcopy
from functools import wraps
import json


_current = ContextVar("aletheia_provider_work", default=None)


class ProviderInputsChanged(Exception):
    pass


class ProviderWorkNeeded(BaseException):
    # Internal control flow must cross provider error handlers without being
    # converted into a failed model output. SQLite transaction managers still
    # roll back on BaseException before the service executes the work.
    def __init__(self, key, operation):
        self.key, self.operation = key, operation


class ProviderWork:
    def __init__(self):
        self.results = {}
        self.transcript = []
        self.position = 0
        self.claimed_jobs = None

    @staticmethod
    def current():
        return _current.get()

    @contextmanager
    def snapshot(self):
        self.position = 0
        token = _current.set(self)
        try:
            yield
            if self.position != len(self.transcript):
                raise ProviderInputsChanged("Provider inputs changed while the request was running.")
        finally:
            _current.reset(token)

    def request(self, key, operation):
        if self.position < len(self.transcript):
            if self.transcript[self.position] != key:
                raise ProviderInputsChanged("Provider inputs changed while the request was running.")
        else:
            self.transcript.append(key)
        self.position += 1
        if key not in self.results:
            raise ProviderWorkNeeded(key, operation)
        return self.results[key]

    def perform(self, needed):
        # Called after both the service lock and SQLite transaction have exited.
        self.results[needed.key] = needed.operation()


def deferred_factory(factory):
    @wraps(factory)
    def construct(*args, **kwargs):
        work = _current.get()
        if work is None:
            return factory(*args, **kwargs)
        key = (factory, json.dumps([args, kwargs], sort_keys=True))
        engine = work.request(key, lambda: factory(*args, **kwargs))
        return _Provider(engine, work, key)
    return construct


class _Provider:
    def __init__(self, engine, work, key):
        self._engine, self._work, self._key = engine, work, key

    def __getattr__(self, name):
        value = getattr(self._engine, name)
        if name not in {"complete_json", "embed_texts"} or not callable(value):
            return value
        def invoke(*args, **kwargs):
            key = (self._key, name, json.dumps([args, kwargs], sort_keys=True))
            return deepcopy(self._work.request(key, lambda: value(*args, **kwargs)))
        return invoke
