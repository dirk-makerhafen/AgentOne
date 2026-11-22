"""Cross-platform advisory file locks.

POSIX uses ``fcntl.flock``; Windows uses ``msvcrt.locking``.  On platforms
with neither, an ``O_EXCL`` lock file with stale detection is used as a
last resort.  Locks are *machine-local*, which is what daemon/lock-file
serialization needs — these are not distributed locks.

The Windows path is deliberately non-blocking with an explicit deadline:
``msvcrt.LK_LOCK`` only retries for a few seconds, which is shorter than a
cold browser daemon start.
"""

from __future__ import annotations

import os
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

try:  # POSIX
    import fcntl
except ImportError:  # pragma: no cover - Windows
    fcntl = None
try:  # Windows
    import msvcrt
except ImportError:  # pragma: no cover - POSIX
    msvcrt = None


class FileLockTimeout(RuntimeError):
    """The lock was still held when the deadline expired."""


def _wait_for(deadline: float, poll_interval: float, message: str) -> None:
    if time.monotonic() >= deadline:
        raise FileLockTimeout(message)
    time.sleep(min(poll_interval, max(0.0, deadline - time.monotonic())))


@contextmanager
def file_lock(path: str | Path, *, timeout: float = 30.0,
              poll_interval: float = 0.1) -> Iterator[Path]:
    """Hold an exclusive lock on *path*, waiting at most *timeout* seconds.

    The file is created if missing and never removed: removal would let a
    second process create a fresh inode while the first still holds the old
    one.  Raises :class:`FileLockTimeout` if the lock stays contended.
    """
    lock_path = Path(path)
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    message = f"Timed out waiting for file lock {lock_path}"

    if fcntl is not None:
        handle = lock_path.open("a+b")
        try:
            deadline = time.monotonic() + timeout
            while True:
                try:
                    fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except OSError:
                    _wait_for(deadline, poll_interval, message)
            yield lock_path
        finally:
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            finally:
                handle.close()
        return

    if msvcrt is not None:  # pragma: no cover - exercised on Windows only
        # msvcrt.locking() locks *bytes*; the file must be at least one byte
        # long or the call fails with EINVAL.
        handle = lock_path.open("a+b")
        handle.seek(0, os.SEEK_END)
        if handle.tell() == 0:
            handle.write(b"\0")
            handle.flush()
        try:
            deadline = time.monotonic() + timeout
            while True:
                handle.seek(0)
                try:
                    msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                    break
                except OSError:
                    _wait_for(deadline, poll_interval, message)
            yield lock_path
        finally:
            try:
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            finally:
                handle.close()
        return

    # pragma: no cover - only relevant on exotic platforms
    acquired = False
    deadline = time.monotonic() + timeout
    while True:
        try:
            if lock_path.exists() and time.time() - lock_path.stat().st_mtime > 3600:
                lock_path.unlink(missing_ok=True)
            descriptor = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except OSError:
            _wait_for(deadline, poll_interval, message)
            continue
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(str(os.getpid()))
        acquired = True
        break
    if not acquired:
        raise FileLockTimeout(message)
    try:
        yield lock_path
    finally:
        lock_path.unlink(missing_ok=True)
