"""Cronjobs admin_tool dispatcher."""
from __future__ import annotations

from typing import Any

from admin_common import _err, _ok, _scope_project


def _scoped_jobs(session: Any, include_archived: bool = False):
    from runtime.cron.crons import Cronjobs

    queryset = Cronjobs(parent_project=_scope_project(session)).all()
    if not include_archived:
        queryset = queryset.filter(is_archived=False)
    return queryset


def _cron_info(job: Any) -> dict[str, Any]:
    def _name(attr: str) -> str | None:
        try:
            obj = getattr(job, attr)
            return obj.name if obj else None
        except Exception:  # pylint: disable=broad-exception-caught
            return None

    try:
        message = job.message.content if job.message else ""
    except Exception:  # pylint: disable=broad-exception-caught
        message = ""
    return {
        "id": job.pk,
        "name": job.name,
        "description": job.description or "",
        "schedule": job.schedule,
        "is_active": bool(job.is_active),
        "is_archived": bool(job.is_archived),
        "agent": _name("agent"),
        "workspace": _name("workspace"),
        "session_mode": job.session_mode or "new",
        "session_name": job.session_name or "",
        "function_type": job.function_type or "",
        "function_name": job.function_name or "",
        "message": message,
        "last_run_at": job.last_run_at.isoformat() if job.last_run_at else None,
        "next_run_at": job.next_run_at.isoformat() if job.next_run_at else None,
        "last_status": job.last_status or "",
        "total_runs": job.total_runs or 0,
    }


def _cron_result(job: Any, **extra: Any) -> tuple[bool, dict[str, Any]]:
    info = _cron_info(job)
    info.update(extra)
    return _ok(**info)


def _validate_schedule(schedule: Any):
    from runtime.cron.execute import compute_next_run

    schedule = str(schedule or "").strip()
    if not schedule:
        return None, "A schedule is required (e.g. '0 9 * * *', '@daily', 'every 30m')."
    try:
        next_run = compute_next_run(schedule)
    except Exception:  # pylint: disable=broad-exception-caught
        next_run = None
    if next_run is None:
        return None, (
            f"Invalid schedule '{schedule}'. Use standard cron ('min hour day month weekday', "
            "e.g. '0 9 * * 1-5'), a shorthand ('@hourly', '@daily', '@weekly'), "
            "or 'every N min|hour' (e.g. 'every 30m')."
        )
    return next_run, None


def _cron_agent(agent_name: Any):
    from server.models.agents.agent import AgentModel

    name = str(agent_name or "").strip()
    if not name:
        return None, "An agent_name is required."
    agent = AgentModel.objects.filter(name=name).first()
    if agent is None:
        return None, f"No agent named '{name}'."
    return agent, None


def _cron_workspace(workspace_name: Any):
    from server.models.workspace import WorkspaceModel

    name = str(workspace_name or "").strip()
    if not name:
        return None, None
    workspace = WorkspaceModel.objects.filter(name=name).first()
    if workspace is None:
        return None, f"No workspace named '{name}'."
    return workspace, None


def _resolve_job(session: Any, kwargs: dict[str, Any]):
    """Return ``(job, error)``; job lookup by ``name`` or ``pk``."""
    pk = kwargs.get("pk") or kwargs.get("cronjob_pk") or kwargs.get("job_pk")
    name = str(kwargs.get("name") or "").strip()
    jobs = _scoped_jobs(session, include_archived=True)
    if pk:
        job = jobs.filter(pk=pk).first()
        if job is None:
            return None, f"Cron job {pk} not found in this scope."
        return job, None
    if not name:
        return None, "A cron job 'name' (or 'pk') is required."
    matches = list(jobs.filter(name=name))
    if not matches:
        return None, f"No cron job named '{name}' in this scope."
    if len(matches) > 1:
        return None, f"Multiple cron jobs named '{name}': ids {[j.pk for j in matches]}"
    return matches[0], None


_CRON_EDIT_FIELDS = (
    "schedule", "agent_name", "message", "description", "session_mode",
    "session_name", "function_type", "function_name", "workspace_name",
)


def _apply_cron_fields(job: Any, kwargs: dict[str, Any], creating: bool = False):
    """Validate and apply cron fields. Returns ``(changed, error)``."""
    from runtime.cron.content import build_cron_message

    changed: list[str] = []
    message_changed = creating

    if creating or "schedule" in kwargs:
        next_run, error = _validate_schedule(kwargs.get("schedule"))
        if error:
            return None, error
        job.schedule = str(kwargs["schedule"]).strip()
        job.next_run_at = next_run
        changed.append("schedule")

    if creating or "agent_name" in kwargs:
        agent, error = _cron_agent(kwargs.get("agent_name"))
        if error:
            return None, error
        job.agent = agent
        changed.append("agent")

    if creating or "description" in kwargs:
        job.description = str(kwargs.get("description") or "")
        changed.append("description")

    if creating or "session_mode" in kwargs:
        mode = str(kwargs.get("session_mode") or "new").strip()
        if mode not in ("new", "existing"):
            return None, "session_mode must be 'new' or 'existing'."
        job.session_mode = mode
        changed.append("session_mode")

    if creating or "session_name" in kwargs:
        job.session_name = str(kwargs.get("session_name") or "")
        changed.append("session_name")

    if creating or "function_type" in kwargs:
        ftype = str(kwargs.get("function_type") or "").strip()
        if ftype not in ("", "task", "tool", "command"):
            return None, "function_type must be '', 'task', 'tool' or 'command'."
        if ftype != (job.function_type or ""):
            job.function_type = ftype
            message_changed = True
        changed.append("function_type")

    if creating or "function_name" in kwargs:
        job.function_name = str(kwargs.get("function_name") or "")
        changed.append("function_name")

    if job.function_type and not (job.function_name or "").strip():
        return None, "function_name is required when function_type is set."

    if creating or "workspace_name" in kwargs:
        if "workspace_name" in kwargs or creating:
            workspace, error = _cron_workspace(kwargs.get("workspace_name"))
            if error:
                return None, error
            job.workspace = workspace
            changed.append("workspace")

    if creating or "message" in kwargs:
        message_changed = True

    if message_changed:
        current = ""
        if not creating and job.message:
            try:
                current = job.message.get() or ""
            except Exception:  # pylint: disable=broad-exception-caught
                current = ""
        raw = kwargs.get("message") if "message" in kwargs else current
        try:
            job.message = build_cron_message(raw or "", job.function_type or "")
        except ValueError as exc:
            return None, str(exc)
        if not creating:
            changed.append("message")

    return changed, None


def _cronjobs(_session: Any, action: str, kwargs: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
    if action == "list":
        try:
            jobs = list(_scoped_jobs(_session, include_archived=bool(kwargs.get("include_archived"))))
        except Exception as e:  # pylint: disable=broad-exception-caught
            return _err(f"Could not list cron jobs: {e}")
        return _ok(jobs=[_cron_info(job) for job in jobs], count=len(jobs))

    if action == "stats":
        try:
            jobs = list(_scoped_jobs(_session, include_archived=True))
        except Exception as e:  # pylint: disable=broad-exception-caught
            return _err(f"Could not list cron jobs: {e}")
        active = sum(1 for j in jobs if j.is_active and not j.is_archived)
        paused = sum(1 for j in jobs if not j.is_active and not j.is_archived)
        archived = sum(1 for j in jobs if j.is_archived)
        upcoming = sorted(
            (j for j in jobs if j.is_active and not j.is_archived and j.next_run_at),
            key=lambda j: j.next_run_at,
        )
        nxt = None
        if upcoming:
            nxt = {"name": upcoming[0].name, "next_run_at": upcoming[0].next_run_at.isoformat()}
        return _ok(
            total=len(jobs), active=active, paused=paused, archived=archived,
            total_runs=sum(j.total_runs or 0 for j in jobs), next_run=nxt,
        )

    if action == "details":
        job, error = _resolve_job(_session, kwargs)
        if error:
            return _err(error)
        return _cron_result(job)

    if action == "create":
        from server.models.cron import Cronjob

        name = str(kwargs.get("name") or "").strip()
        if not name:
            return _err("A cron job name is required.")
        duplicate = _scoped_jobs(_session, include_archived=True).filter(name=name)
        if duplicate.exists():
            return _err(f"A cron job named '{name}' already exists in this scope.")
        job = Cronjob(
            name=name,
            is_active=True,
            is_archived=False,
            parent_project=_scope_project(_session),
        )
        changed, error = _apply_cron_fields(job, kwargs, creating=True)
        if error:
            return _err(error)
        try:
            job.save()
        except Exception as e:  # pylint: disable=broad-exception-caught
            return _err(f"Could not create cron job: {e}")
        return _cron_result(job, changed=changed)

    if action == "update":
        job, error = _resolve_job(_session, kwargs)
        if error:
            return _err(error)
        supplied = [field for field in _CRON_EDIT_FIELDS if field in kwargs]
        if not supplied:
            return _err("Nothing to change; pass at least one cron field")
        changed, error = _apply_cron_fields(job, kwargs)
        if error:
            return _err(error)
        try:
            job.save()
        except Exception as e:  # pylint: disable=broad-exception-caught
            return _err(f"Could not update cron job: {e}")
        return _cron_result(job, changed=changed)

    if action == "set_active":
        job, error = _resolve_job(_session, kwargs)
        if error:
            return _err(error)
        job.is_active = bool(kwargs.get("is_active", True))
        try:
            job.save(update_fields=["is_active", "updated_at"])
        except Exception as e:  # pylint: disable=broad-exception-caught
            return _err(f"Could not update cron job: {e}")
        return _cron_result(job)

    if action == "set_archived":
        job, error = _resolve_job(_session, kwargs)
        if error:
            return _err(error)
        job.is_archived = bool(kwargs.get("archived", True))
        try:
            job.save(update_fields=["is_archived", "updated_at"])
        except Exception as e:  # pylint: disable=broad-exception-caught
            return _err(f"Could not update cron job: {e}")
        return _cron_result(job)

    if action == "runs":
        from server.models.tasks.agent_task_call import AgentTaskCall

        job, error = _resolve_job(_session, kwargs)
        if error:
            return _err(error)
        try:
            limit = max(1, min(int(kwargs.get("limit") or 20), 100))
        except (TypeError, ValueError):
            return _err("limit must be a number.")
        try:
            calls = list(
                AgentTaskCall.objects.filter(cronjob=job)
                .select_related("session")
                .order_by("-pk")[:limit]
            )
        except Exception as e:  # pylint: disable=broad-exception-caught
            return _err(f"Could not read run history: {e}")
        runs = []
        for call in calls:
            try:
                session_name = call.session.name if call.session_id else None
            except Exception:  # pylint: disable=broad-exception-caught
                session_name = None
            runs.append({
                "id": call.pk,
                "status": call.status,
                "created_at": call.created_at.isoformat() if call.created_at else None,
                "session_pk": call.session_id,
                "session": session_name,
            })
        return _ok(
            name=job.name, runs=runs, returned=len(runs),
            total_runs=job.total_runs or 0, last_status=job.last_status or "",
            last_run_at=job.last_run_at.isoformat() if job.last_run_at else None,
            next_run_at=job.next_run_at.isoformat() if job.next_run_at else None,
        )

    return _err(f"Unknown action '{action}' for scope 'cronjobs'")

