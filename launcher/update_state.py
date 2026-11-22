"""Cache-backed state for UI-triggered updates.

Runs are short-lived operational state, not domain data, so they live in the
existing Redis cache instead of adding a migration.  The newest run id is kept
under a second key so the System page can show either an in-progress job or the
result of the last one.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from django.core.cache import cache

_KEY_PREFIX = "agentone:update:run:"
_CURRENT_KEY = "agentone:update:current"
_QUEUE_KEY = "agentone:update:queued"
_TTL = 24 * 60 * 60
_MAX_LOG_LINES = 300
#: A run still marked "running" after this long lost its worker; stop polling.
_STALE_AFTER = 60 * 60


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _get(key):
    try:
        return cache.get(key)
    except Exception:  # pylint: disable=broad-exception-caught
        return None


def _set(key, value, ttl=_TTL):
    try:
        cache.set(key, value, ttl)
    except Exception:  # pylint: disable=broad-exception-caught
        pass


def reserve_queue() -> bool:
    """Atomically reserve the single UI update slot (fails open without Redis)."""
    try:
        return bool(cache.add(_QUEUE_KEY, "1", 300))
    except Exception:  # pylint: disable=broad-exception-caught
        return True


def release_queue():
    try:
        cache.delete(_QUEUE_KEY)
    except Exception:  # pylint: disable=broad-exception-caught
        pass


def is_stale_run(run: dict | None) -> bool:
    if not run or run.get("status") != "running":
        return False
    try:
        started = datetime.fromisoformat(run.get("started_at", ""))
    except (TypeError, ValueError):
        return True
    if started.tzinfo is None:
        started = started.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - started).total_seconds() > _STALE_AFTER


def reconcile_stale_run() -> dict | None:
    """Mark a lost run as failed so the UI stops polling forever."""
    run = current_run()
    if not is_stale_run(run):
        return None
    return finish_run(
        run["id"],
        "failed",
        error="Update worker stopped responding; the run is considered failed.",
    )


def start_run(version_before: str) -> dict:
    run = {
        "id": uuid.uuid4().hex[:12],
        "status": "running",
        "version_before": version_before,
        "version_after": "",
        "started_at": _now(),
        "finished_at": "",
        "error": "",
        "result": {},
        "logs": [],
    }
    _set(_KEY_PREFIX + run["id"], run)
    _set(_CURRENT_KEY, run["id"])
    return dict(run)


def get_run(run_id: str) -> dict | None:
    run = _get(_KEY_PREFIX + str(run_id))
    return dict(run) if isinstance(run, dict) else None


def current_run() -> dict | None:
    run_id = _get(_CURRENT_KEY)
    if not run_id:
        return None
    return get_run(str(run_id))


def append_log(run_id: str, message: str, level: str = "info"):
    run = get_run(run_id)
    if not run:
        return
    run.setdefault("logs", []).append({"time": _now(), "level": level, "message": str(message)})
    if len(run["logs"]) > _MAX_LOG_LINES:
        run["logs"] = run["logs"][-_MAX_LOG_LINES:]
    _set(_KEY_PREFIX + str(run_id), run)


def finish_run(run_id: str, status: str, *, result: dict | None = None, error: str = "") -> dict | None:
    run = get_run(run_id)
    if not run:
        return None
    run["status"] = status
    run["finished_at"] = _now()
    run["error"] = str(error or "")
    run["result"] = result or {}
    if result and result.get("after"):
        run["version_after"] = result["after"]
    _set(_KEY_PREFIX + str(run_id), run)
    _set(_CURRENT_KEY, run_id)
    return dict(run)
