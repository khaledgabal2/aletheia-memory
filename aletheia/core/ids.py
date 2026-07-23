"""Identifier helpers."""

from __future__ import annotations

import hashlib
import uuid


def stable_event_id(
    namespace: str,
    source_type: str,
    content: str,
    source_uri: str | None = None,
    session_id: str | None = None,
) -> str:
    """Create a stable evidence ID for identical evidence input."""

    payload = "\0".join(
        [
            namespace,
            session_id or "",
            source_type,
            source_uri or "",
            content,
        ]
    )
    return "evt_" + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:20]


def content_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:20]}"

