"""
Worker-independent sleep-guard manager for local AI on macOS laptops.

``caffeinate`` state cannot live in a Celery worker — prefork workers execute
``call_llm`` in *whatever* process is free, so a per-process reference count
(PID / refcount in module globals) is scattered and unreliable.  Instead the
guard is owned by a single manager that runs on the 60-second recovery
scheduler:

* :func:`manage_sleep_guard` reconciles the *desired* state once per minute:
  keep a single ``caffeinate -dimsu`` running while local models have been
  used within the ``sleep_guard_release_delay_minutes`` grace window **and**
  power conditions allow it (AC, or battery >= ``min_battery_pct_for_caffeinate``).
* The guard process is tracked by a pidfile (``~/.agentone/sleep_guard.pid``),
  and its pin is validated via ``ps`` so a recycled PID is never killed.

The low-battery *pause* gate (parking local calls) is independent and lives
in ``runtime.power`` / ``call_llm``; this module only decides keep-awake.
"""

from __future__ import annotations

import os
import shutil
import signal
import subprocess
import sys
import threading
from pathlib import Path

from runtime.power import caffeinate_allowed
from runtime.settings.settings import (
    get_prevent_sleep_when_local_ai,
    get_sleep_guard_release_delay_minutes,
)

#: Where the running ``caffeinate`` process id is persisted so any worker —
#: or the UI process — can find and stop it.
PID_FILE = Path.home() / ".agentone" / "sleep_guard.pid"

#: Serializes spawn/kill/read within a single process; pidfile writes are
#: atomic enough for the (already serialized) 60s recovery cadence.
_LOCK = threading.Lock()


def desired_state(recent_activity: bool) -> tuple[bool, str]:
    """Whether the sleep guard *should* be running right now.

    ``recent_activity`` is decided by the caller (a DB query here,
    a mock in tests) so this stays pure and testable.
    """
    if sys.platform != "darwin":
        return False, "not macOS"
    if not get_prevent_sleep_when_local_ai():
        return False, "preference disabled"
    if not caffeinate_allowed():
        return False, "battery too low"
    if not recent_activity:
        return False, "no recent local activity"
    return True, "local activity in grace window"


def has_recent_local_activity(minutes: int | None = None) -> bool:
    """Whether a local model produced a Response within the grace window.

    Uses ``sleep_guard_release_delay_minutes`` when *minutes* is omitted.  A
    window of 0 disables the guard entirely (release immediately).
    """
    from datetime import timedelta

    from django.utils import timezone

    window = minutes if minutes is not None else get_sleep_guard_release_delay_minutes()
    if window <= 0:
        return False
    from django.db.models import Q
    from server.models.queries.response import Response

    threshold = timezone.now() - timedelta(minutes=window)
    return Response.objects.filter(
        created_at__gte=threshold,
    ).filter(
        Q(aimodel__self_hosted=True) | Q(aimodel__is_cloud=False),
    ).exists()


# ---------------------------------------------------------------------------
# Pidfile / process helpers
# ---------------------------------------------------------------------------


def _read_pid() -> int | None:
    try:
        return int(PID_FILE.read_text().strip())
    except Exception:
        return None


def _write_pid(pid: int) -> None:
    try:
        PID_FILE.parent.mkdir(parents=True, exist_ok=True)
        PID_FILE.write_text(str(pid))
    except Exception:
        pass


def _clear_pid() -> None:
    try:
        PID_FILE.unlink(missing_ok=True)
    except Exception:
        pass


def _is_caffeinate_process(pid: int) -> bool:
    """True only if the given pid is a live ``caffeinate`` process."""
    try:
        proc = subprocess.run(
            ["ps", "-p", str(pid), "-o", "comm="],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except Exception:
        return False
    return "caffeinate" in (proc.stdout or "").strip()


def guard_is_active() -> bool:
    """Whether a managed ``caffeinate`` is currently running."""
    pid = _read_pid()
    if pid is None:
        return False
    return _is_caffeinate_process(pid)


def _spawn_caffeinate() -> bool:
    binary = shutil.which("caffeinate")
    if not binary:
        return False
    try:
        proc = subprocess.Popen(
            [binary, "-dimsu"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        return False
    _write_pid(proc.pid)
    return True


def _stop_caffeinate() -> bool:
    pid = _read_pid()
    if pid is None:
        return False
    if _is_caffeinate_process(pid):
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    _clear_pid()
    return True


# ---------------------------------------------------------------------------
# Public reconciliation API
# ---------------------------------------------------------------------------


def manage_sleep_guard() -> dict:
    """Reconcile the guard with recent activity + power state. Call on the 60s
    recovery pass (and at startup). Returns a status dict for logging/tests.
    """
    with _LOCK:
        has_recent = has_recent_local_activity()
        on, reason = desired_state(has_recent)
        active = guard_is_active()

        if on and not active:
            started = _spawn_caffeinate()
            state = "started" if started else "start_failed"
        elif (not on) and active:
            _stop_caffeinate()
            state = "stopped"
        elif on and active:
            state = "running"
        else:
            state = "off"
        return {"state": state, "reason": reason, "active": on, "pid": _read_pid()}
