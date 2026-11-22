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
        _cleanup_orphaned_session_folders,
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
        _cleanup_orphaned_session_folders,
        _ensure_agentone_home_workspace,
        _timeout_active_runs,
        _cancel_duplicate_queries,
        _clear_stale_compaction_flags,
        _fail_ancient_parked_calls,
        _recover_stuck_calls,
        _resolve_stuck_waiting_runs,
        _recover_stale_queries_startup,
        _release_queued_calls,
        _cleanup_orphaned_terminals,
    ):
        try:
            pass_()
        except Exception as e:
            print(f"[startup-cleanup] error in {pass_.__name__}: {e}")


def _clear_stale_compaction_flags() -> None:
    """Close compaction fences left behind by a worker crash/restart.

    The normal release happens in ``CallScheduler._on_taskcall_ended``.  A
    process that died mid-compaction cannot run that hook; here we drop any
    flag whose owning ``compact_turn`` call no longer exists or has ended.
    """
    from runtime.session.compaction_guard import compaction_state
    from server.models.sessions.session import SessionModel

    session_ids = SessionModel.objects.filter(is_compacting=True).values_list("pk", flat=True)
    for session_id in session_ids:
        try:
            compaction_state(session_id)
        except Exception as e:  # pylint: disable=broad-exception-caught
            print(f"[startup-cleanup] error clearing compaction flag for {session_id}: {e}")


def _ensure_agentone_home_workspace() -> None:
    """Ensure the single AgentOne home workspace exists (idempotent).

    Formerly this pass also minted a workspace per collection (agents,
    skills, cronjobs). All assistant sessions now bind to AgentOne home,
    the project's primary workspace, or an explicitly selected workspace —
    so only the home row is needed.
    """
    from runtime.workspace.workspaces import Workspaces

    Workspaces.agentone_home_workspace()


def _recover_stale_queries_startup() -> None:
    """Startup variant: restart every ACTIVE/WAITING query, ignoring liveness."""
    from server.tasks.recovery_scheduler import _recover_stale_queries

    _recover_stale_queries(startup=True)


def _cleanup_orphaned_terminals() -> None:
    """Kill tmux sessions with no live TerminalSession row (reboot leftovers)."""
    from runtime.terminal import cleanup_orphans

    cleaned = cleanup_orphans()
    if cleaned:
        print(f"[startup-cleanup] removed {cleaned} orphaned terminal(s)")


def _recover_active_queries(*args, **kwargs):
    from server.tasks.recovery_scheduler import _recover_stale_queries

    kwargs.setdefault("startup", True)
    return _recover_stale_queries(*args, **kwargs)


def _recover_stale_queries(*args, **kwargs):
    # Startup context: be aggressive by default.
    from server.tasks.recovery_scheduler import _recover_stale_queries as _rsq

    if not (args or kwargs):
        kwargs = dict(kwargs)
        kwargs.setdefault("startup", True)
    return _rsq(*args, **kwargs)
