"""DB-backed agent reads for the AgentOne admin_tool dispatcher.

Agents are defined by ``agent.md`` manifests, but the database is the live
view of them. This module only *inspects* that view. Creating or editing an
agent (or its tools) is a filesystem manifest edit followed by a framework
reload — never a state-changing action on this tool.
"""
from __future__ import annotations

from typing import Any

from admin_common import _err, _ok, _scope_project


def _scoped_agents(session: Any):
    """Global agents plus the session project's own agents, ordered by name."""
    from runtime.agents.agents import Agents
    return Agents(parent_project=session.get_project()).all()


def _agent_info(agent: Any) -> dict[str, Any]:
    version = agent.latest_agent_version
    try:
        project_name = agent.parent_project.name if agent.parent_project else None
    except Exception:  # pylint: disable=broad-exception-caught
        project_name = None
    try:
        parent_name = agent.parent_agent.name if agent.parent_agent else None
    except Exception:  # pylint: disable=broad-exception-caught
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


def _resolve_agent(session: Any, name: Any):
    """Find one agent by name in scope. Returns ``(agent, error)``."""
    name = str(name or "").strip()
    if not name:
        return None, "An agent name is required (kwargs: name)."
    matches = list(_scoped_agents(session).filter(name=name))
    if not matches:
        return None, f"No agent named '{name}' in this scope."
    project = _scope_project(session)
    if len(matches) > 1 and project is not None:
        local = [a for a in matches if getattr(a, "parent_project_id", None) == project.pk]
        if local:
            return local[0], None
    return matches[0], None


def _agents(session: Any, action: str, kwargs: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
    if action == "list":
        try:
            agents = list(_scoped_agents(session))
        except Exception as e:  # pylint: disable=broad-exception-caught
            return _err(f"Could not list agents: {e}")
        project = session.get_project()
        scope = f"global + project {project.name}" if project is not None else "global"
        return _ok(agents=[_agent_info(a) for a in agents], count=len(agents), scope=scope)

    if action == "stats":
        try:
            agents = list(_scoped_agents(session))
        except Exception as e:  # pylint: disable=broad-exception-caught
            return _err(f"Could not list agents: {e}")
        by_visibility: dict[str, int] = {}
        roots = 0
        for agent in agents:
            info = _agent_info(agent)
            visibility = info["visibility"] or "unset"
            by_visibility[visibility] = by_visibility.get(visibility, 0) + 1
            if info["kind"] == "root":
                roots += 1
        return _ok(
            total=len(agents), by_visibility=by_visibility,
            roots=roots, subagents=len(agents) - roots,
        )

    if action == "details":
        agent, error = _resolve_agent(session, kwargs.get("name"))
        if error:
            return _err(error)
        from runtime.agents.agents import Agents
        from runtime.skill.skills import Skills
        from server.models.cron import Cronjob
        from server.models.sessions.session import SessionModel

        info = _agent_info(agent)
        try:
            sessions_total = SessionModel.objects.filter(
                latest_session_version__agent=agent
            ).count()
        except Exception:  # pylint: disable=broad-exception-caught
            sessions_total = 0
        try:
            skills_count = Skills(parent_agent=agent).all().count()
        except Exception:  # pylint: disable=broad-exception-caught
            skills_count = 0
        try:
            subagents_count = Agents(parent_agent=agent).all().count()
        except Exception:  # pylint: disable=broad-exception-caught
            subagents_count = 0
        try:
            cronjobs_count = Cronjob.objects.filter(agent=agent, is_archived=False).count()
        except Exception:  # pylint: disable=broad-exception-caught
            cronjobs_count = 0
        return _ok(
            **info,
            version_count=agent.related_agent_versions.count(),
            sessions_total=sessions_total,
            skills_count=skills_count,
            subagents_count=subagents_count,
            cronjobs_count=cronjobs_count,
        )

    return _err(f"Unknown action '{action}' for scope 'agents'")
