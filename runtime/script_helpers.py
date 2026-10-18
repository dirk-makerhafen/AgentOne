"""Shared helpers for internal-assistant script tools.

Single source for the row builders used by the singular/plural assistant
scripts. All Django imports are deferred (script modules load via
importlib; this module stays side-effect free).
"""
from __future__ import annotations

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
