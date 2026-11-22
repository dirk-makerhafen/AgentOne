"""Tool-side client for the browser daemon.

Responsibilities: authenticate to the local daemon, start it on demand if it
is not already running, and dispatch one action.  Kept dependency-free (stdlib
``urllib``) and synchronous — the tool itself runs synchronously in the
Celery worker via ``BoundTask.call()``.

On-demand start is serialized with a cross-platform lock on ``start.lock`` so
N workers racing for the first browser of the morning end up with one daemon.
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from runtime.browser import paths
from runtime.file_lock import file_lock

#: Generous — first start also validates Camoufox imports.
START_WAIT_SECONDS = 60.0
#: Must exceed the daemon's REQUEST_TIMEOUT backstop.
CALL_TIMEOUT = 200.0


class ClientError(RuntimeError):
    """Daemon unreachable, or the daemon returned an error."""


def _read_state() -> dict | None:
    path = paths.state_path()
    if not path.exists():
        return None
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return state if isinstance(state, dict) and isinstance(state.get("port"), int) else None


def _pid_alive(pid: Any) -> bool:
    """Check liveness without signalling the process.

    ``os.kill(pid, 0)`` is a no-op on POSIX but calls ``TerminateProcess`` on
    Windows — using it there would kill the daemon we are probing.
    """
    if not isinstance(pid, int) or pid <= 0:
        return False
    try:
        import psutil  # pylint: disable=import-outside-toplevel
    except ImportError:  # pragma: no cover - psutil is a hard requirement
        if sys.platform == "win32":
            # Never signal on Windows; the caller also checks daemon health.
            return True
        try:
            import os  # pylint: disable=import-outside-toplevel

            os.kill(pid, 0)
        except OSError:
            return False
        return True
    return psutil.pid_exists(pid)


def _request(url: str, payload: dict | None, timeout: float) -> dict:
    token = paths.read_token() or ""
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = urllib.request.Request(url, data=data, method="POST" if data else "GET")
    request.add_header("Authorization", f"Bearer {token}")
    if data:
        request.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310 - loopback
        return json.loads(response.read() or b"{}")


def _healthy(port: int, timeout: float = 3.0) -> bool:
    try:
        reply = _request(f"http://127.0.0.1:{port}/health", None, timeout)
    except (urllib.error.URLError, OSError, ValueError):
        return False
    return bool(reply.get("ok"))


def _spawn_daemon() -> None:
    """Launch a detached daemon process (its stdout/stderr go to the base dir)."""
    paths.ensure_private_dir(paths.browser_base())
    log_path = paths.browser_base() / "daemon.log"
    log = open(log_path, "ab", buffering=0)  # pylint: disable=consider-using-with
    kwargs: dict[str, Any] = {
        "stdout": log,
        "stderr": log,
        "stdin": subprocess.DEVNULL,
        "cwd": str(Path(__file__).resolve().parents[2]),
        "close_fds": True,
    }
    if sys.platform == "win32":
        # start_new_session is POSIX-only; without these flags the daemon
        # dies together with the Celery worker that spawned it.
        kwargs["creationflags"] = (
            getattr(subprocess, "DETACHED_PROCESS", 0)
            | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
            | getattr(subprocess, "CREATE_NO_WINDOW", 0)
        )
    else:
        kwargs["start_new_session"] = True
    subprocess.Popen(  # pylint: disable=consider-using-with
        [sys.executable, "-m", "runtime.browser.daemon"], **kwargs
    )


def ensure_daemon() -> int:
    """Return a healthy daemon port, starting the daemon if needed."""
    state = _read_state()
    if state and _pid_alive(state.get("pid")) and _healthy(state["port"]):
        return int(state["port"])

    paths.ensure_private_dir(paths.browser_base())
    lock_path = paths.start_lock_path()
    with file_lock(lock_path, timeout=START_WAIT_SECONDS + 10):
        # Re-check under the lock: another worker may have won the race.
        state = _read_state()
        if state and _pid_alive(state.get("pid")) and _healthy(state["port"]):
            return int(state["port"])

        # A stale state file means the daemon died — clear it before start.
        paths.state_path().unlink(missing_ok=True)
        _spawn_daemon()

        deadline = time.time() + START_WAIT_SECONDS
        while time.time() < deadline:
            state = _read_state()
            if state and _pid_alive(state.get("pid")) and _healthy(state["port"], timeout=2.0):
                return int(state["port"])
            time.sleep(0.5)
    raise ClientError(
        f"browser daemon did not become ready within {int(START_WAIT_SECONDS)}s; "
        f"see {paths.browser_base() / 'daemon.log'}"
    )


def call(action: str, scope: dict, params: dict | None = None, *, timeout: float = CALL_TIMEOUT) -> dict:
    """Dispatch *action* to the daemon and return the result payload.

    Raises :class:`ClientError` on transport failure or a daemon-side error.
    """
    port = ensure_daemon()
    payload = {"action": action, "scope": scope, "params": params or {}}
    try:
        reply = _request(f"http://127.0.0.1:{port}/action", payload, timeout)
    except (urllib.error.URLError, OSError, ValueError) as exc:
        raise ClientError(f"browser daemon unreachable: {exc}") from exc
    if not reply.get("ok"):
        raise ClientError(str(reply.get("error") or "unknown browser error"))
    return reply


def probe_status() -> dict | None:
    """Status of an already-running daemon, or ``None`` if it is not running.

    Never starts the daemon — use :func:`status` when on-demand startup is
    wanted.  Lets ``server browser status``/``stop`` stay read-only.
    """
    state = _read_state()
    if not state or not _pid_alive(state.get("pid")):
        return None
    if not _healthy(state["port"]):
        return None
    try:
        return call("status", {})
    except ClientError:
        return None


def status() -> dict:
    """Daemon status (bindings, pages, config echo), starting it if needed."""
    return call("status", {})
