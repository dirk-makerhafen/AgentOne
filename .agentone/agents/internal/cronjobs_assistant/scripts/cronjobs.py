"""Cron collection tools for the cronjobs_assistant agent.

All tools are bound: the managed scope is the calling session's project
(global jobs when unbound). Listing, creating, archiving, and scope
health belong here; working on ONE job (describe, tune, pause, runs)
belongs to ``cronjob_assistant``. Every tool returns a ``(bool, dict)``
tuple.

Writes go to the database AND to the ``.agentone/cronjobs/<name>.md`` file
(via ``runtime.cron.file_io``), mirroring what the UI does — otherwise the
next manifest reload would archive the DB-only record.
"""
from __future__ import annotations

from typing import Any

from runtime.session.session import Session


def _scoped_jobs(_session: Session, include_archived: bool = False):
    """Cronjobs in the session's project scope, ordered by name."""
    from runtime.cron.crons import Cronjobs

    qs = Cronjobs(parent_project=_session.get_project()).all()
    if not include_archived:
        qs = qs.filter(is_archived=False)
    return qs


def _cron_info(job) -> dict[str, Any]:
    try:
        agent_name = job.agent.name if job.agent_id and job.agent else None
    except Exception:
        agent_name = None
    try:
        workspace_name = job.workspace.name if job.workspace_id and job.workspace else None
    except Exception:
        workspace_name = None
    try:
        message_text = job.message.content if job.message else ""
    except Exception:
        message_text = ""
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
        "message": message_text,
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


def list_cronjobs(_session: Session, include_archived: bool = False) -> tuple[bool, dict[str, Any]]:
    """List the cron jobs in your managed project scope, ordered by name.

    A session bound to a project sees that project's jobs; a session with
    no project sees the global jobs.

    Args:
        include_archived: When true, also return archived jobs.

    Returns:
        ``(True, {"status": "success", "jobs": [...], "count": int})`` or
        ``(False, {"status": "error", "message": ...})``.
    """
    try:
        jobs = list(_scoped_jobs(_session, include_archived=include_archived))
    except Exception as e:
        return False, {"status": "error", "message": f"Could not list cron jobs: {e}"}
    return True, {"status": "success", "jobs": [_cron_info(j) for j in jobs], "count": len(jobs)}


def create_cronjob(
    _session: Session,
    name: str,
    schedule: str,
    agent_name: str,
    message: str = "",
    description: str = "",
    session_mode: str = "new",
    session_name: str = "",
    function_type: str = "",
    function_name: str = "",
    workspace_name: str = "",
) -> tuple[bool, dict[str, Any]]:
    """Create a new cron job in your managed project scope.

    The job starts active immediately and is written to the database and
    to its ``.agentone/cronjobs/<name>.md`` file, so manifest reloads
    keep it. For tuning one job afterwards, see ``cronjob_assistant``.

    Args:
        name: Unique job name in this scope (required).
        schedule: Cron expression (required) — standard cron
            ('0 9 * * *'), shorthand ('@daily', '@hourly'), or
            'every N min|hour' ('every 30m').
        agent_name: Agent to run on each tick (required).
        message: Message text sent each run (or JSON args when a function
            target is set).
        description: Optional short description.
        session_mode: 'new' (fresh session each run) or 'existing'
            (reuse the named session).
        session_name: Session name for 'existing' mode.
        function_type: '' (send message), 'task', 'tool' or 'command'.
        function_name: Name of the task/tool/command to execute.
        workspace_name: Optional workspace to bind runs to.

    Returns:
        ``(True, {"status": "success", job...})`` or
        ``(False, {"status": "error", "message": ...})``.
    """
    from server.models.content import GenericContent
    from server.models.cron import Cronjob
    from server.models.workspace import WorkspaceModel
    from runtime.cron.file_io import write_cron_file

    name = (name or "").strip()
    if not name:
        return False, {"status": "error", "message": "A name is required."}
    nxt, error = _validate_schedule(schedule)
    if error:
        return False, {"status": "error", "message": error}
    agent, error = _resolve_agent(agent_name)
    if error:
        return False, {"status": "error", "message": error}
    if agent is None:
        return False, {"status": "error", "message": "An agent name is required."}
    session_mode = (session_mode or "new").strip()
    if session_mode not in ("new", "existing"):
        return False, {"status": "error", "message": "session_mode must be 'new' or 'existing'."}
    function_type = (function_type or "").strip()
    if function_type not in ("", "task", "tool", "command"):
        return False, {"status": "error", "message": "function_type must be '', 'task', 'tool' or 'command'."}

    workspace = None
    if (workspace_name or "").strip():
        workspace = WorkspaceModel.objects.filter(name=workspace_name.strip()).first()
        if workspace is None:
            return False, {"status": "error", "message": f"No workspace named '{workspace_name}'."}

    project = _session.get_project()
    qs = Cronjob.objects.filter(name=name)
    qs = qs.filter(parent_project=project) if project is not None else qs.filter(parent_project__isnull=True)
    if qs.exists():
        return False, {"status": "error", "message": f"A cron job named '{name}' already exists in this scope."}

    try:
        job = Cronjob.objects.create(
            name=name,
            description=description or "",
            schedule=schedule.strip(),
            is_active=True,
            is_archived=False,
            agent=agent,
            parent_project=project,
            workspace=workspace,
            session_mode=session_mode,
            session_name=session_name or "",
            message=GenericContent.from_text(message) if message else None,
            function_type=function_type,
            function_name=function_name or "",
            next_run_at=nxt,
        )
    except Exception as e:
        return False, {"status": "error", "message": f"Could not create cron job: {e}"}
    try:
        write_cron_file(job)
    except Exception as e:
        return False, {
            "status": "error",
            "message": f"Created cron job {job.pk} but could not write its .md file: {e}",
        }
    try:
        from runtime.cron.file_io import cron_file_path

        Cronjob.objects.filter(pk=job.pk).update(
            manifest_dir=cron_file_path(job.name, project).parent.as_posix()
        )
    except Exception:
        pass
    info = _cron_info(job)
    info.update({"status": "success"})
    return True, info


def cronjobs_stats(_session: Session) -> tuple[bool, dict[str, Any]]:
    """Count the cron jobs in your managed project scope by state.

    Reports active, paused, and archived jobs, total recorded runs, and
    the next upcoming run — the collection health overview.

    Returns:
        ``(True, {"status": "success", "total": int, "active": int,
        "paused": int, "archived": int, "total_runs": int,
        "next_run": {...} or None})`` or
        ``(False, {"status": "error", "message": ...})``.
    """
    try:
        jobs = list(_scoped_jobs(_session, include_archived=True))
    except Exception as e:
        return False, {"status": "error", "message": f"Could not list cron jobs: {e}"}
    active = sum(1 for j in jobs if j.is_active and not j.is_archived)
    paused = sum(1 for j in jobs if not j.is_active and not j.is_archived)
    archived = sum(1 for j in jobs if j.is_archived)
    total_runs = sum(j.total_runs or 0 for j in jobs)
    upcoming = [j for j in jobs if j.is_active and not j.is_archived and j.next_run_at]
    upcoming.sort(key=lambda j: j.next_run_at)
    nxt = None
    if upcoming:
        first = upcoming[0]
        nxt = {"name": first.name, "next_run_at": first.next_run_at.isoformat()}
    return True, {
        "status": "success",
        "total": len(jobs),
        "active": active,
        "paused": paused,
        "archived": archived,
        "total_runs": total_runs,
        "next_run": nxt,
    }


def set_cronjob_archived(_session: Session, name: str, archived: bool = True) -> tuple[bool, dict[str, Any]]:
    """Archive or restore a cron job in your managed project scope.

    Archiving hides the job from the default views but preserves its
    tracking data (run count, last run). The ``.md`` file is removed on
    archive (a missing file means archived) and rewritten on restore.

    Args:
        name: Name of the cron job (required).
        archived: True to archive, False to restore.

    Returns:
        ``(True, {"status": "success", job...})`` or
        ``(False, {"status": "error", "message": ...})``.
    """
    from runtime.cron.file_io import delete_cron_file, write_cron_file

    name = (name or "").strip()
    if not name:
        return False, {"status": "error", "message": "A cron job name is required."}
    matches = list(_scoped_jobs(_session, include_archived=True).filter(name=name))
    if not matches:
        return False, {"status": "error", "message": f"No cron job named '{name}' in this project scope."}
    job = matches[0]
    job.is_archived = bool(archived)
    try:
        job.save(update_fields=["is_archived", "updated_at"])
        if archived:
            delete_cron_file(job.name, job.parent_project)
        else:
            write_cron_file(job)
    except Exception as e:
        return False, {"status": "error", "message": f"Could not update cron job: {e}"}
    info = _cron_info(job)
    info.update({"status": "success"})
    return True, info


def refresh_from_disk(_session: Session) -> tuple[bool, dict[str, Any]]:
    """Reload all cron jobs visible in the managed scope from disk."""
    from pathlib import Path

    from runtime.paths import agentone_home, agentone_root
    from registry.loader.load_cron_manifest import load_cron_manifest
    from registry.install_repo import InstallRepo

    project = _session.get_project()
    details: list[dict[str, Any]] = []
    errors: list[str] = []
    roots: list[tuple[Path, Any, InstallRepo]] = []
    if project is not None:
        md = project.get_agentone_dir()
        roots.append((md, project, InstallRepo.for_project(project.name, source_root=md)))
    else:
        roots.append((agentone_root(), None, InstallRepo.for_global(source_root=agentone_root())))
        roots.append((agentone_home(), None, InstallRepo.for_user(source_root=agentone_home())))

    for root, proj, repo in roots:
        crons_dir = root / "cronjobs"
        if not crons_dir.is_dir():
            continue
        try:
            repo.sync()
        except Exception as e:  # pylint: disable=broad-exception-caught
            errors.append(f"sync {root}: {e}")
            continue
        seen: set[str] = set()
        for cron_md in sorted(crons_dir.glob("*.md")):
            try:
                load_cron_manifest(cron_md, install_repo=repo, parent_project=proj, seen_names=seen, details=details)
            except Exception as e:  # pylint: disable=broad-exception-caught
                errors.append(f"{cron_md}: {e}")

    return (len(errors) == 0, {
        "status": "success" if not errors else "partial",
        "details": details,
        "errors": errors,
    })
