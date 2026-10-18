"""Single-cron-job tools for the cronjob_assistant agent.

All tools are bound and take the job's ``name``: they describe, tune,
pause/resume, and report the run history of ONE cron job in the calling
session's project scope (global jobs when unbound). Collection operations
(list, create, archive, scope stats) belong to ``cronjobs_assistant``.
Every tool returns a ``(bool, dict)`` tuple.
"""
from __future__ import annotations

from typing import Any, Optional

from runtime.session.session import Session


def _scoped_jobs(_session: Session, include_archived: bool = False):
    """Cronjobs in the session's project scope, ordered by name."""
    from runtime.cron.crons import Cronjobs

    qs = Cronjobs(parent_project=_session.get_project()).all()
    if not include_archived:
        qs = qs.filter(is_archived=False)
    return qs


def _resolve(_session: Session, name: str, include_archived: bool = True):
    """Find one cron job by name in scope. Returns ``(True, job)`` or ``(False, error)``."""
    name = (name or "").strip()
    if not name:
        return False, {"status": "error", "message": "A cron job name is required."}
    matches = list(_scoped_jobs(_session, include_archived=include_archived).filter(name=name))
    if not matches:
        return False, {"status": "error", "message": f"No cron job named '{name}' in this project scope."}
    if len(matches) > 1:
        return False, {
            "status": "error",
            "message": f"Multiple cron jobs named '{name}'. This should not happen — report their ids.",
            "ids": [j.pk for j in matches],
        }
    return True, matches[0]


def _message_text(job) -> str:
    try:
        return job.message.content if job.message else ""
    except Exception:
        return ""


def _cron_info(job) -> dict[str, Any]:
    try:
        agent_name = job.agent.name if job.agent_id and job.agent else None
    except Exception:
        agent_name = None
    try:
        workspace_name = job.workspace.name if job.workspace_id and job.workspace else None
    except Exception:
        workspace_name = None
    return {
        "id": job.pk,
        "name": job.name,
        "description": job.description or "",
        "schedule": job.schedule,
        "is_active": bool(job.is_active),
        "is_archived": bool(job.is_archived),
        "agent": agent_name,
        "workspace": workspace_name,
        "session_mode": job.session_mode or "new",
        "session_name": job.session_name or "",
        "function_type": job.function_type or "",
        "function_name": job.function_name or "",
        "message": _message_text(job),
        "last_run_at": job.last_run_at.isoformat() if job.last_run_at else None,
        "next_run_at": job.next_run_at.isoformat() if job.next_run_at else None,
        "last_status": job.last_status or "",
        "total_runs": job.total_runs or 0,
    }


def _resolve_agent(agent_name: str):
    """Find an AgentModel by name. Returns ``(agent, error)``."""
    from server.models.agents.agent import AgentModel

    if not (agent_name or "").strip():
        return None, None
    agent = AgentModel.objects.filter(name=agent_name.strip()).first()
    if agent is None:
        return None, f"No agent named '{agent_name}'. Use get_available_agents to list them."
    return agent, None


def _validate_schedule(schedule: str):
    """Validate a schedule string. Returns ``(next_run, error)``."""
    from runtime.cron.execute import compute_next_run

    schedule = (schedule or "").strip()
    if not schedule:
        return None, "A schedule is required (e.g. '0 9 * * *', '@daily', 'every 30m')."
    try:
        nxt = compute_next_run(schedule)
    except Exception:
        nxt = None
    if nxt is None:
        return None, (
            f"Invalid schedule '{schedule}'. Use standard cron ('min hour day month weekday', "
            "e.g. '0 9 * * 1-5'), a shorthand ('@hourly', '@daily', '@weekly'), "
            "or 'every N min|hour' (e.g. 'every 30m')."
        )
    return nxt, None


def cronjob_details(_session: Session, name: str) -> tuple[bool, dict[str, Any]]:
    """Show the full configuration of one cron job in your scope.

    Includes schedule, agent, session mode, function target, the full
    message text, and run tracking (last/next run, status, total runs).

    Args:
        name: Name of the cron job (required).

    Returns:
        ``(True, {"status": "success", job...})`` or
        ``(False, {"status": "error", "message": ...})``.
    """
    ok, job = _resolve(_session, name)
    if not ok:
        return False, job
    info = _cron_info(job)
    info["status"] = "success"
    return True, info


def edit_cronjob(
    _session: Session,
    name: str,
    schedule: Optional[str] = None,
    agent_name: Optional[str] = None,
    message: Optional[str] = None,
    description: Optional[str] = None,
    session_mode: Optional[str] = None,
    session_name: Optional[str] = None,
    function_type: Optional[str] = None,
    function_name: Optional[str] = None,
    workspace_name: Optional[str] = None,
) -> tuple[bool, dict[str, Any]]:
    """Edit one cron job in your managed project scope.

    Only the arguments you pass are changed. Pass ``message=""`` to clear
    the message, ``workspace_name=""`` to unbind the workspace. The
    ``.md`` file is rewritten so reloads keep the change.

    Args:
        name: Name of the cron job (required).
        schedule: New schedule (validated; recomputes next run).
        agent_name: New agent for each run.
        message: New message text (or JSON args for function targets).
        description: New description.
        session_mode: 'new' or 'existing'.
        session_name: Session name for 'existing' mode.
        function_type: '', 'task', 'tool' or 'command'.
        function_name: Task/tool/command name.
        workspace_name: Workspace name, or "" to unbind.

    Returns:
        ``(True, {"status": "success", "changed": [...], job...})`` or
        ``(False, {"status": "error", "message": ...})``.
    """
    from server.models.content import GenericContent
    from server.models.workspace import WorkspaceModel
    from runtime.cron.file_io import write_cron_file

    ok, job = _resolve(_session, name)
    if not ok:
        return False, job
    changed: list[str] = []
    if schedule is not None:
        nxt, error = _validate_schedule(schedule)
        if error:
            return False, {"status": "error", "message": error}
        job.schedule = schedule.strip()
        job.next_run_at = nxt
        changed.append("schedule")
    if agent_name is not None:
        agent, error = _resolve_agent(agent_name)
        if error:
            return False, {"status": "error", "message": error}
        job.agent = agent
        changed.append("agent")
    if message is not None:
        job.message = GenericContent.from_text(message) if message else None
        changed.append("message")
    if description is not None:
        job.description = description or ""
        changed.append("description")
    if session_mode is not None:
        mode = (session_mode or "new").strip()
        if mode not in ("new", "existing"):
            return False, {"status": "error", "message": "session_mode must be 'new' or 'existing'."}
        job.session_mode = mode
        changed.append("session_mode")
    if session_name is not None:
        job.session_name = session_name or ""
        changed.append("session_name")
    if function_type is not None:
        ftype = (function_type or "").strip()
        if ftype not in ("", "task", "tool", "command"):
            return False, {"status": "error", "message": "function_type must be '', 'task', 'tool' or 'command'."}
        job.function_type = ftype
        changed.append("function_type")
    if function_name is not None:
        job.function_name = function_name or ""
        changed.append("function_name")
    if workspace_name is not None:
        if (workspace_name or "").strip():
            ws = WorkspaceModel.objects.filter(name=workspace_name.strip()).first()
            if ws is None:
                return False, {"status": "error", "message": f"No workspace named '{workspace_name}'."}
            job.workspace = ws
        else:
            job.workspace = None
        changed.append("workspace")
    if not changed:
        return False, {"status": "error", "message": "Nothing to change."}
    try:
        job.save()
        write_cron_file(job)
    except Exception as e:
        return False, {"status": "error", "message": f"Could not save cron job: {e}"}
    info = _cron_info(job)
    info.update({"status": "success", "changed": changed})
    return True, info


def set_cronjob_active(_session: Session, name: str, is_active: bool = True) -> tuple[bool, dict[str, Any]]:
    """Enable or pause one cron job without deleting it.

    A paused job keeps its configuration and history; the scheduler
    simply skips it until re-enabled. The ``.md`` file is updated too.

    Args:
        name: Name of the cron job (required).
        is_active: True to enable, False to pause.

    Returns:
        ``(True, {"status": "success", job...})`` or
        ``(False, {"status": "error", "message": ...})``.
    """
    from runtime.cron.file_io import write_cron_file

    ok, job = _resolve(_session, name)
    if not ok:
        return False, job
    job.is_active = bool(is_active)
    try:
        job.save(update_fields=["is_active", "updated_at"])
        write_cron_file(job)
    except Exception as e:
        return False, {"status": "error", "message": f"Could not update cron job: {e}"}
    info = _cron_info(job)
    info.update({"status": "success"})
    return True, info


def cronjob_runs(_session: Session, name: str, limit: int = 20) -> tuple[bool, dict[str, Any]]:
    """Show recent executions of one cron job, newest first.

    Each entry carries the dispatch status and timestamp — use this to
    judge whether the job is healthy, stuck, or failing. Same source as
    the History tab in the cron panel.

    Args:
        name: Name of the cron job (required).
        limit: Max entries to return (1-100, default 20).

    Returns:
        ``(True, {"status": "success", "name": str, "runs": [...],
        "total_runs": int, "last_status": str})`` or
        ``(False, {"status": "error", "message": ...})``.
    """
    from server.models.tasks.agent_task_call import AgentTaskCall

    ok, job = _resolve(_session, name)
    if not ok:
        return False, job
    try:
        limit = max(1, min(int(limit or 20), 100))
    except (TypeError, ValueError):
        return False, {"status": "error", "message": "limit must be a number."}
    try:
        calls = list(
            AgentTaskCall.objects.filter(cronjob=job)
            .select_related("session")
            .order_by("-pk")[:limit]
        )
    except Exception as e:
        return False, {"status": "error", "message": f"Could not read run history: {e}"}
    runs = []
    for call in calls:
        try:
            session_name = call.session.name if call.session_id else None
        except Exception:
            session_name = None
        try:
            created = call.created_at.isoformat() if call.created_at else None
        except Exception:
            created = None
        runs.append({
            "id": call.pk,
            "status": call.status,
            "created_at": created,
            "session_pk": call.session_id,
            "session": session_name,
        })
    return True, {
        "status": "success",
        "name": job.name,
        "runs": runs,
        "returned": len(runs),
        "total_runs": job.total_runs or 0,
        "last_status": job.last_status or "",
        "last_run_at": job.last_run_at.isoformat() if job.last_run_at else None,
        "next_run_at": job.next_run_at.isoformat() if job.next_run_at else None,
    }


def refresh_from_disk(_session: Session, name: str) -> tuple[bool, dict[str, Any]]:
    """Reload ONE cron job from disk.

    Use after editing the job's manifest file on disk.

    Args:
        name: Name of the cron job (required).

    Returns:
        ``(True, {"status": "success", "job": str, "details": [...]})``
        or ``(False, {"status": "error", "message": ...})``.
    """
    ok, job = _resolve(_session, name)
    if not ok:
        return False, job
    details: list[dict[str, Any]] = []
    try:
        job.refresh_from_disk(details=details)
    except Exception as e:
        return False, {"status": "error", "message": f"Could not refresh cron job from disk: {e}"}
    return True, {
        "status": "success",
        "job": job.name,
        "details": details,
    }
