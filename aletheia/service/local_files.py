"""Owner-only local protocol files. Never exposed as a general HTTP file API."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import stat
import tempfile


def private_directory(path: Path) -> Path:
    if not path.is_absolute():
        raise ValueError("Local protocol directories must be absolute.")
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    info = path.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
        raise ValueError("Local protocol directory must be owned by this user with mode 0700.")
    return path


def identity_directory(db_path: str, root: str | None = None) -> Path:
    if db_path == ":memory:":
        raise ValueError("Local pairing requires a persistent database.")
    database = Path(db_path).expanduser().resolve(strict=True)
    info = database.stat()
    if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid():
        raise ValueError("Local pairing requires a database file owned by this user.")
    base = Path(root or os.environ.get("ALETHEIA_IDENTITY_DIR") or Path.home() / ".aletheia/local-identities")
    private_directory(base)
    identity = hashlib.sha256(f"{database}\0{info.st_dev}\0{info.st_ino}".encode()).hexdigest()[:32]
    return private_directory(base / identity)


def read_private(path: Path, limit: int = 16384) -> bytes:
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077 or info.st_size > limit:
            raise ValueError("Invalid local protocol file ownership, permissions, or size.")
        with os.fdopen(descriptor, "rb", closefd=False) as stream:
            data = stream.read(limit + 1)
        if len(data) > limit:
            raise ValueError("Local protocol file exceeds its size limit.")
        return data
    finally:
        os.close(descriptor)


def write_private(path: Path, data: bytes) -> None:
    descriptor, temporary = tempfile.mkstemp(prefix=".pending-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)
