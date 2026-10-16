"""Single-project list tools for the project_assistant agent.

All tools are bound to the calling session's project: they list the
manifest-owned children of that project — its agents, skills, and cron
jobs — ordered by name. The project is the calling session's project
(``_session.get_project()``); an unbound session has no manifest-owned
children and gets an error. Every tool returns a ``(bool, dict)`` tuple.
"""
from __future__ import annotations

from typing import Any

from runtime.script_helpers import (
    agent_row,
    cron_row,
    skill_row,
    unbound_error,
)
from runtime.session.session import Session


def _resolve_project(_session: Session):
    """Find the session's project. Returns ``(True, project)`` or ``(False, error)``."""
    project = _session.get_project()
    if project is None:
        return False, unbound_error("a project scope")
    return True, project


def list_agents(_session: Session) -> tuple[bool, dict[str, Any]]:
    """List THIS project's agents, ordered by name.

    The project is the calling session's project — no name argument.
    Base path ``<project>/.agentone/agents/``.

    Returns:
        ``(True, {"status": "success", "project": str, "agents": [...],
        "count": int, "scope": str})`` or
        ``(False, {"status": "error", "message": ...})``.
    """
    from runtime.agents.agents import Agents

    ok, project = _resolve_project(_session)
    if not ok:
        return False, project
    try:
        agents = list(Agents(parent_project=project).all().order_by("name"))
    except Exception as e:
        return False, {"status": "error", "message": f"Could not list project agents: {e}"}
    return True, {
        "status": "success",
        "project": project.name,
        "agents": [agent_row(a) for a in agents],
        "count": len(agents),
        "scope": f"{project.path}/.agentone/agents/",
    }


def list_skills(_session: Session) -> tuple[bool, dict[str, Any]]:
    """List THIS project's skills, ordered by name.

    The project is the calling session's project — no name argument.
    Base path ``<project>/.agentone/skills/``.

    Returns:
        ``(True, {"status": "success", "project": str, "skills": [...],
        "count": int, "scope": str})`` or
        ``(False, {"status": "error", "message": ...})``.
    """
    from runtime.skill.skills import Skills

    ok, project = _resolve_project(_session)
    if not ok:
        return False, project
    try:
        skills = list(Skills(parent_project=project).all().order_by("name"))
    except Exception as e:
        return False, {"status": "error", "message": f"Could not list project skills: {e}"}
    return True, {
        "status": "success",
        "project": project.name,
        "skills": [skill_row(s) for s in skills],
        "count": len(skills),
        "scope": f"{project.path}/.agentone/skills/",
    }


def list_cronjobs(_session: Session, include_archived: bool = False) -> tuple[bool, dict[str, Any]]:
    """List THIS project's cron jobs, ordered by name.

    The project is the calling session's project — no name argument.
    Base path ``<project>/.agentone/cronjobs/``.

    Args:
        include_archived: Also list archived jobs (default False).

    Returns:
        ``(True, {"status": "success", "project": str, "cronjobs": [...],
        "count": int, "scope": str})`` or
        ``(False, {"status": "error", "message": ...})``.
    """
    from runtime.cron.crons import Cronjobs

    ok, project = _resolve_project(_session)
    if not ok:
        return False, project
    try:
        queryset = Cronjobs(parent_project=project).all()
        if not include_archived:
            queryset = queryset.filter(is_archived=False)
        jobs = list(queryset.order_by("name"))
    except Exception as e:
        return False, {"status": "error", "message": f"Could not list project cron jobs: {e}"}
    return True, {
        "status": "success",
        "project": project.name,
        "cronjobs": [cron_row(j) for j in jobs],
        "count": len(jobs),
        "scope": f"{project.path}/.agentone/cronjobs/",
    }
