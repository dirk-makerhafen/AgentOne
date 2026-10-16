"""Shared helpers for internal-assistant script tools.

Single source for session-scope resolution, row builders, and markdown
renderers used by the singular/plural assistant scripts (see plan.md:
list-item shapes + list conventions). All Django imports are deferred
(script modules load via importlib; this module stays side-effect free).
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any


def normalize_dir(value: Any) -> str:
    """Normalize a directory path for comparison (no I/O)."""
    try:
        text = str(value or "").strip()
        if not text:
            return ""
        return Path(text).expanduser().as_posix().rstrip("/") or ""
    except Exception:
        return ""


def session_workspace(_session: Any) -> Any:
    """Return the workspace a session is bound to, or *None* when unbound."""
    try:
        return _session.workspace
    except Exception:
        return None


def unbound_error(kind: str) -> dict:
    """Standard error when an assistant session is not bound to its item."""
    return {
        "status": "error",
        "message": (
            f"This assistant session is not bound to {kind} "
            "(no workspace). Open the assistant from its item instead."
        ),
    }


def not_found_error(kind: str, path: str) -> dict:
    """Standard error when no item matches the session workspace."""
    return {
        "status": "error",
        "message": (
            f"No {kind} found for this session's workspace '{path}'. "
            "Open the assistant from its item instead."
        ),
    }


def _version_of(model: Any, attr: str) -> Any:
    try:
        return getattr(model, attr)
    except Exception:
        return None


def agent_row(agent: Any) -> dict[str, Any]:
    """Row dict for one agent (agent_list_item fields)."""
    version = _version_of(agent, "latest_agent_version")
    try:
        project_name = agent.parent_project.name if agent.parent_project else None
    except Exception:
        project_name = None
    try:
        parent_name = agent.parent_agent.name if agent.parent_agent else None
    except Exception:
        parent_name = None
    return {
        "name": agent.name,
        "path": getattr(agent, "manifest_dir", "") or "",
        "project": project_name,
        "parent_agent": parent_name,
        "kind": "subagent" if parent_name else "root",
        "visibility": version.visibility if version is not None else None,
        "version_number": version.version_number if version is not None else 0,
    }


def skill_row(skill: Any) -> dict[str, Any]:
    """Row dict for one skill (skill_list_item fields)."""
    version = _version_of(skill, "latest_skill_version")
    try:
        project_name = skill.parent_project.name if skill.parent_project else None
    except Exception:
        project_name = None
    return {
        "id": skill.pk,
        "name": skill.name,
        "project": project_name,
        "description": (version.description if version is not None else "") or "",
        "path": (version.path if version is not None else "") or "",
        "manifest_dir": getattr(skill, "manifest_dir", "") or "",
        "version_number": version.version_number if version is not None else 0,
    }


def cron_row(job: Any) -> dict[str, Any]:
    """Row dict for one cron job (cronjob_list_item fields + run tracking)."""
    try:
        agent_name = job.agent.name if job.agent_id and job.agent else None
    except Exception:
        agent_name = None
    try:
        workspace_name = job.workspace.name if job.workspace_id and job.workspace else None
    except Exception:
        workspace_name = None
    try:
        message = job.message.content if job.message else ""
    except Exception:
        message = ""
    return {
        "id": job.pk,
        "name": job.name,
        "path": getattr(job, "manifest_dir", "") or "",
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
        "message": message,
        "last_run_at": job.last_run_at.isoformat() if job.last_run_at else None,
        "next_run_at": job.next_run_at.isoformat() if job.next_run_at else None,
        "last_status": job.last_status or "",
        "total_runs": job.total_runs or 0,
    }


def workspace_row(workspace: Any, session_count: int = 0) -> dict[str, Any]:
    """Row dict for one workspace (workspace_list_item fields)."""
    return {
        "workspace_pk": workspace.pk,
        "name": workspace.name or workspace.path,
        "path": workspace.path,
        "description": workspace.description or "",
        "color": getattr(workspace, "color", "") or "",
        "session_count": session_count,
    }


def workitem_row(item: Any) -> dict[str, Any]:
    """Row dict for one work item (workitem_list_item fields)."""
    try:
        assignee = item.assigned_agent.name if item.assigned_agent else None
    except Exception:
        assignee = None
    return {
        "id": item.pk,
        "title": item.title,
        "status": item.status,
        "priority": item.priority,
        "assigned_agent": assignee,
    }


def project_row(project: Any) -> dict[str, Any]:
    """Row dict for one project (project_list_item fields)."""
    return {
        "name": project.name,
        "path": getattr(project, "path", "") or "",
    }


def agent_list_item(agent_model: Any) -> str:
    """One markdown row for an agent (agent_list_item shape)."""
    row = agent_row(agent_model)
    return f"- **{row['name']}** (v{row['version_number']}, {row['visibility'] or 'unset'}) — {row['path'] or '?'}"


def skill_list_item(skill_model: Any) -> str:
    """One markdown row for a skill (skill_list_item shape)."""
    row = skill_row(skill_model)
    return f"- **{row['name']}** (v{row['version_number']}) — {row['description']} [{row['manifest_dir'] or '?'}]"


def project_list_item(project: Any) -> str:
    """One markdown row for a project (project_list_item shape)."""
    from server.models.sessions.session import SessionModel
    from server.models.workspace import WorkspaceModel

    session_count = SessionModel.objects.filter(parent_project=project).count()
    workspace_names = ", ".join(
        WorkspaceModel.objects.filter(parent_project=project)
        .order_by("name")
        .values_list("name", flat=True)
    ) or "(none)"
    row = project_row(project)
    return f"- **{row['name']}** — {row['path']} ({session_count} sessions; workspaces: {workspace_names})"


def cronjob_list_item(job: Any) -> str:
    """One markdown row for a cron job (cronjob_list_item shape)."""
    row = cron_row(job)
    state = "active" if row["is_active"] else "paused"
    return f"- **{row['name']}** ({row['schedule']}, {state}) — {row['description']} [{row['path'] or '?'}]"


def workspace_list_item(workspace_model: Any) -> str:
    """One markdown row for a workspace (workspace_list_item shape)."""
    from server.models.sessions.session import SessionModel

    session_count = SessionModel.objects.filter(
        latest_session_version__workspace=workspace_model
    ).count()
    row = workspace_row(workspace_model, session_count)
    return f"- **{row['name']}** — {row['path']} ({row['session_count']} sessions)"


def workitem_list_item(item: Any) -> str:
    """One markdown row for a work item (workitem_list_item shape)."""
    row = workitem_row(item)
    text = f"- #{row['id']} **{row['title']}** ({row['status']}, priority {row['priority']})"
    if row["assigned_agent"]:
        text += f" — assigned: {row['assigned_agent']}"
    return text


def as_markdown_list(models: Any, item_fn: Any) -> str:
    """Render every model with item_fn, one markdown row per line."""
    rows = [item_fn(model) for model in models]
    return "\n".join(rows) if rows else "(none)"


def _realpath(value: str) -> str:
    try:
        return os.path.realpath(value or "")
    except Exception:
        return ""


def match_manifest_dir(queryset: Any, ws_path: str) -> list:
    """Return rows whose manifest_dir matches *ws_path*.

    Exact match first; realpath comparison as fallback (symlinked home
    dirs). *queryset* is the model manager's queryset (unfiltered).
    """
    matches = list(queryset.filter(manifest_dir=ws_path))
    if not matches and ws_path:
        real = _realpath(ws_path)
        if real:
            for cand in queryset.exclude(manifest_dir=""):
                try:
                    if _realpath(cand.manifest_dir or "") == real:
                        matches.append(cand)
                except Exception:
                    continue
    return matches
