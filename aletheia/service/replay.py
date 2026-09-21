"""Bind cached mutation receipts to their original authority and live sources."""
from contextlib import contextmanager
from contextvars import ContextVar
import json

from aletheia.core.ids import content_hash
from aletheia.service.errors import forbidden

_current = ContextVar("aletheia_receipt_access", default=None)


def authority(context):
    return content_hash(json.dumps({"capabilities": sorted(context.capabilities),
        "grants": sorted(context.namespace_grants), "privacy": context.privacy_ceiling}, sort_keys=True))


def record_source(kind, value):
    current = _current.get()
    if current is not None:
        current.sources.add((kind, value))


def record_target(kind, item):
    current = _current.get()
    if current is not None:
        current.targets[(kind, item.id)] = (item.namespace, getattr(item, "project_id", None))


def record_provider(requested, source_task, privacy_level):
    current = _current.get()
    if current is not None and isinstance(requested, str) and isinstance(privacy_level, str):
        current.providers.add((requested, source_task, privacy_level))


class ReceiptAccess:
    def __init__(self, context):
        self.authority = authority(context)
        self.sources = set()
        self.targets = {}
        self.providers = set()

    @contextmanager
    def capture(self):
        token = _current.set(self)
        try:
            yield
        finally:
            _current.reset(token)

    def payload(self):
        return {"version": 1, "authority": self.authority, "sources": sorted(self.sources),
                "targets": [[kind, value, *scope] for (kind, value), scope in sorted(self.targets.items())],
                "providers": sorted(self.providers)}


def validate(service, context, receipt):
    from aletheia.service.operations import OperationAccess
    if not receipt or receipt.get("version") != 1 or receipt.get("authority") != authority(context):
        raise forbidden("Cached result is unavailable under the current access policy; the operation was not repeated.")
    access = OperationAccess(service, context)
    if any(not access.allowed(kind, value) for kind, value in receipt["sources"]):
        raise forbidden("Cached result sources are unavailable under the current access policy; the operation was not repeated.")
    for kind, value, namespace, project in receipt["targets"]:
        item = access.target(kind, value, namespace=namespace)
        if getattr(item, "project_id", None) != project:
            raise forbidden("Cached result scope changed; the operation was not repeated.")
    for requested, source_task, privacy_level in receipt["providers"]:
        access.provider(requested, source_task=source_task, privacy_level=privacy_level)
