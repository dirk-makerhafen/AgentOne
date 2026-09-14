"""
One-time startup cleanup task, split out of ``recovery_scheduler``.

Runs the recovery passes immediately so orphaned state left over from a
previous run (lost Celery messages, ACTIVE_QUEUED calls, QUEUED runs,
stale runtime folders) is cleaned up right away instead of waiting for a
recovery pass.  Dispatched once at startup by ``python3 manage.py server run``
(``launcher/management/commands/server.py``).
"""

from __future__ import annotations

from celery import shared_task


@shared_task(name="tasks.startup_cleanup")
def startup_cleanup() -> None:
    """One-time startup cleanup — called when the server starts.

    Runs the recovery passes immediately so orphaned state left over from a
    previous run (lost Celery messages, ACTIVE_QUEUED calls, QUEUED runs) is
    recovered right away instead of waiting up to 60s for the recovery pass.
    """
    from server.tasks.recovery_scheduler import (
        _cancel_duplicate_queries,
        _cleanup_stale_runtime_folders,
        _fail_ancient_parked_calls,
        _recover_stale_queries,
        _recover_stuck_calls,
        _release_queued_calls,
        _resolve_stuck_waiting_runs,
        _timeout_active_runs,
    )

    for pass_ in (
        _cleanup_stale_runtime_folders,
        _timeout_active_runs,
        _cancel_duplicate_queries,
        _fail_ancient_parked_calls,
        _recover_stuck_calls,
        _resolve_stuck_waiting_runs,
        _recover_stale_queries,
        _release_queued_calls,
    ):
        try:
            pass_()
        except Exception as e:
            print(f"[startup-cleanup] error in {pass_.__name__}: {e}")