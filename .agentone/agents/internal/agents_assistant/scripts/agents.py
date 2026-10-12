"""Agent collection tools for the agents_assistant agent.

All tools are bound: the managed scope is the global agents plus the
calling session's project agents (agent names are globally unique, so
single-agent work never needs disambiguation). Listing the collection
and collection health belong here; working on ONE agent (describe,
usage, versions) belongs to ``agent_assistant``. Creating or editing
agent manifests belongs to ``project_assistant``. Every tool returns a
``(bool, dict)`` tuple.
"""
from __future__ import annotations

from typing import Any

from django.db.models import Q

from runtime.session.session import Session


def _session_project(_session: Session) -> Any:
    """Return the project this session belongs to, or ``None`` for global."""
    model = getattr(_session, "model", None)
    return getattr(model, "parent_project", None) if model else None


def _scoped_agents(_session: Session):
    """Global agents plus the session project's own agents, ordered by name."""
    from server.models.agents.agent import AgentModel

    project = _session_project(_session)
    qs = AgentModel.objects.all()
    if project is not None:
        qs = qs.filter(Q(parent_project=project) | Q(parent_project__isnull=True))
    else:
        qs = qs.filter(parent_project__isnull=True)
    return qs.select_related(
        "latest_agent_version", "parent_project", "parent_agent"
    ).order_by("name")


def _agent_info(agent) -> dict[str, Any]:
    version = agent.latest_agent_version
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
        "project": project_name,
        "parent_agent": parent_name,
        "kind": "subagent" if parent_name else "root",
        "visibility": version.visibility if version is not None else None,
        "version_number": version.version_number if version is not None else 0,
    }


def list_agents(_session: Session) -> tuple[bool, dict[str, Any]]:
    """List the agents visible in your managed scope, ordered by name.

    Global agents are visible everywhere; project agents only in their
    own project scope. Each entry flags root vs subagent and visibility.

    Returns:
        ``(True, {"status": "success", "agents": [...], "count": int})`` or
        ``(False, {"status": "error", "message": ...})``.
    """
    try:
        agents = list(_scoped_agents(_session))
    except Exception as e:
        return False, {"status": "error", "message": f"Could not list agents: {e}"}
    return True, {"status": "success", "agents": [_agent_info(a) for a in agents], "count": len(agents)}


def agents_stats(_session: Session) -> tuple[bool, dict[str, Any]]:
    """Count the agents in your managed scope: by visibility and by kind.

    Returns:
        ``(True, {"status": "success", "total": int,
        "by_visibility": {...}, "roots": int, "subagents": int})`` or
        ``(False, {"status": "error", "message": ...})``.
    """
    try:
        agents = list(_scoped_agents(_session))
    except Exception as e:
        return False, {"status": "error", "message": f"Could not list agents: {e}"}
    by_visibility: dict[str, int] = {}
    roots = 0
    for agent in agents:
        info = _agent_info(agent)
        vis = info["visibility"] or "unset"
        by_visibility[vis] = by_visibility.get(vis, 0) + 1
        if info["kind"] == "root":
            roots += 1
    return True, {
        "status": "success",
        "total": len(agents),
        "by_visibility": by_visibility,
        "roots": roots,
        "subagents": len(agents) - roots,
    }
