"""Cross-process lock that keeps updates from running concurrently.

The OS lock is released automatically when the process dies, so a killed worker
cannot leave the installation permanently "locked".  It is machine-local,
which is correct: an update operates on a local checkout and its local DB.
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path
from time import time

from runtime.paths import run_base

try:  # POSIX
    import fcntl
except ImportError:  # pragma: no cover - Windows
    fcntl = None
try:  # Windows
    import msvcrt
except ImportError:  # pragma: no cover - POSIX
    msvcrt = None


class UpdateLockError(RuntimeError):
    """Another update is already in progress."""


def _fallback_acquire(path: Path, stale_after: int = 3600):
    """Last-resort O_EXCL lock for platforms without advisory file locks."""
    try:
        if path.exists() and time() - path.stat().st_mtime < stale_after:
            return None
        descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except OSError:
        return None
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        handle.write(str(os.getpid()))
    return path


@contextmanager
def update_lock(path=None):
    """Serialize updates; raise :class:`UpdateLockError` if one is running."""
    base = run_base() if path is None else Path(path)
    base.mkdir(parents=True, exist_ok=True)
    lock_path = base / "agentone-update.lock"

    if fcntl is not None:
        handle = lock_path.open("a+")
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            handle.close()
            raise UpdateLockError("Another AgentOne update is already running.") from exc
        try:
            handle.seek(0)
            handle.truncate()
            handle.write(str(os.getpid()))
            handle.flush()
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            handle.close()
        return

    if msvcrt is not None:  # pragma: no cover - exercised on Windows only
        handle = lock_path.open("a+")
        handle.seek(0)
        try:
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError as exc:
            handle.close()
            raise UpdateLockError("Another AgentOne update is already running.") from exc
        try:
            yield
        finally:
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            handle.close()
        return

    acquired = _fallback_acquire(lock_path)
    if acquired is None:
        raise UpdateLockError("Another AgentOne update is already running.")
    try:
        yield
    finally:
        acquired.unlink(missing_ok=True)
