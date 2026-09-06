"""Version 1 local advertisements; untrusted, expiring discovery hints only."""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
import threading
import time
import uuid

from .local_files import private_directory, write_private


def valid_label(value: str) -> bool:
    return (isinstance(value, str) and 1 <= len(value) <= 60 and value == value.strip()
            and not any(ord(c) < 32 or 127 <= ord(c) <= 159 or 0x202a <= ord(c) <= 0x202e
                        or 0x2066 <= ord(c) <= 0x2069 for c in value))


class LocalAdvertisement:
    def __init__(self, *, port: int, service_identity: str, label: str, directory: str | None = None):
        if not 1024 <= port <= 65535 or not valid_label(label):
            raise ValueError("Use a local port and a service name of 1–60 characters.")
        self.directory = Path(directory or os.environ.get("ALETHEIA_DISCOVERY_DIR") or Path.home() / ".aletheia/desktop-discovery")
        self.identifier = str(uuid.uuid4())
        self.path = self.directory / f"{self.identifier}.json"
        self.record = {"format_version": 1, "registration_id": self.identifier, "label": label,
                       "port": port, "service_identity": service_identity}
        self.stop = threading.Event()
        self.thread: threading.Thread | None = None

    def renew(self) -> None:
        if self.stop.is_set():
            return
        private_directory(self.directory)
        write_private(self.path, json.dumps({**self.record, "expires_at_ms": int(time.time() * 1000) + 30000}).encode())
        if self.stop.is_set():
            self.path.unlink(missing_ok=True)

    def start(self) -> None:
        self.renew()
        def run():
            while not self.stop.wait(10):
                try:
                    self.renew()
                except (OSError, ValueError):
                    logging.getLogger(__name__).warning("Local advertisement renewal failed; its lease will expire.")
        self.thread = threading.Thread(target=run, name="aletheia-advertisement", daemon=True)
        self.thread.start()

    def close(self) -> None:
        self.stop.set()
        if self.thread and self.thread is not threading.current_thread():
            self.thread.join(timeout=2)
        self.path.unlink(missing_ok=True)
