"""Single-agent tools for the agent_assistant agent.

All tools are bound and take the agent's ``name`` (globally unique):
they describe ONE agent's effective configuration, report its usage
(sessions, cron jobs, work items), and list its version history.
Collection operations (list, stats) belong to ``agents_assistant``.
Every tool returns a ``(bool, dict)`` tuple.
"""
from __future__ import annotations

from typing import Any

from runtime.session.session import Session

#: Description chars returned by describe_agent; agent bodies can be very
#: long, so the remainder is cut with a marker rather than flooding context.
DESCRIPTION_LIMIT = 3000


def _resolve_agent(agent_name: str):
    """Find an AgentModel by name (globally unique)."""
    from server.models.agents.agent import AgentModel

    name = (agent_name or "").strip()
    if not name:
        return False, {"status": "error", "message": "An agent name is required."}
    agent = AgentModel.objects.filter(name=name).first()
    if agent is None:
        return False, {"status": "error", "message": f"No agent named '{name}'. Use agents_assistant to list them."}
    return True, agent


def _version_info(version) -> dict[str, Any]:
    tools: list[str] = []
    tasks: list[str] = []
    commands: list[str] = []
    try:
        for tdv in version.task_versions.all().select_related("task_definition"):
            try:
                tname = tdv.task_definition.name
            except Exception:
                continue
            if tdv.task_type == "TOOL":
                tools.append(tname)
            elif tdv.task_type == "COMMAND":
                commands.append(tname)
            else:
                tasks.append(tname)
    except Exception:
        pass
    skills: list[str] = []
    try:
        for sv in version.skill_versions.all().select_related("skill"):
            try:
                skills.append(sv.skill.name)
            except Exception:
                continue
    except Exception:
        pass
    subagents: list[str] = []
    try:
        for sub in version.subagent_versions.all().select_related("agent"):
            try:
                subagents.append(sub.agent.name)
            except Exception:
                continue
    except Exception:
        pass
    try:
        extends = list(version.extends_agent_names or [])
    except Exception:
        extends = []
    try:
        hooks = len(version.hooks or [])
    except Exception:
        hooks = 0
    return {
        "version_number": version.version_number,
        "visibility": version.visibility,
        "extends": extends,
        "tools": sorted(set(tools)),
        "tasks": sorted(set(tasks)),
        "commands": sorted(set(commands)),
        "skills": sorted(set(skills)),
        "subagents": sorted(set(subagents)),
        "hooks": hooks,
        "commit": version.commit or "",
        "hash": version.hash or "",
    }


def describe_agent(_session: Session, name: str) -> tuple[bool, dict[str, Any]]:
    """Show ONE agent's effective configuration: the resolved tool/task/
    command/skill/subagent sets on its latest version, plus visibility,
    extends chain, and version identity.

    Args:
        name: Name of the agent (required, globally unique).

    Returns:
        ``(True, {"status": "success", agent...})`` or
        ``(False, {"status": "error", "message": ...})``.
    """
    ok, agent = _resolve_agent(name)
    if not ok:
        return False, agent
    version = agent.latest_agent_version
    if version is None:
        return False, {"status": "error", "message": f"Agent '{agent.name}' has no version yet."}
    try:
        parent_project = agent.parent_project.name if agent.parent_project else None
    except Exception:
        parent_project = None
    try:
        parent_agent = agent.parent_agent.name if agent.parent_agent else None
    except Exception:
        parent_agent = None
    description = version.description or ""
    truncated = len(description) > DESCRIPTION_LIMIT
    info = _version_info(version)
    info.update({
        "status": "success",
        "name": agent.name,
        "project": parent_project,
        "parent_agent": parent_agent,
        "description": description[:DESCRIPTION_LIMIT] + ("…[truncated]" if truncated else ""),
        "description_truncated": truncated,
        "version_count": agent.related_agent_versions.count(),
    })
    return True, info


def agent_usage(_session: Session, name: str, limit: int = 10) -> tuple[bool, dict[str, Any]]:
    """Report how ONE agent is used: session count plus recent sessions,
    cron jobs targeting it, and assigned work items by status.

    Args:
        name: Name of the agent (required).
        limit: Max recent sessions to detail (1-50, default 10).

    Returns:
        ``(True, {"status": "success", "agent": str, "sessions_total": int,
        "recent_sessions": [...], "cronjobs": [...], "workitems_by_status": {...}}})``
        or ``(False, {"status": "error", "message": ...})``.
    """
    from server.models.cron import Cronjob
    from server.models.sessions.session import SessionModel
    from server.models.workitems.work_item import WorkItem

    ok, agent = _resolve_agent(name)
    if not ok:
        return False, agent
    try:
        limit = max(1, min(int(limit or 10), 50))
    except (TypeError, ValueError):
        return False, {"status": "error", "message": "limit must be a number."}
    try:
        sessions = list(
            SessionModel.objects.filter(latest_session_version__agent=agent).order_by("-created_at")[:limit]
        )
        sessions_total = SessionModel.objects.filter(latest_session_version__agent=agent).count()
    except Exception as e:
        return False, {"status": "error", "message": f"Could not read agent sessions: {e}"}
    recent = []
    for s in sessions:
        try:
            created = s.created_at.isoformat() if s.created_at else None
        except Exception:
            created = None
        recent.append({
            "session_pk": s.pk,
            "name": s.name or f"Session {s.pk}",
            "created_at": created,
            "is_active": bool(getattr(s, "is_active", False)),
        })
    try:
        cronjobs = [
            {"name": c.name, "is_active": bool(c.is_active), "schedule": c.schedule}
            for c in Cronjob.objects.filter(agent=agent).order_by("name")
        ]
    except Exception:
        cronjobs = []
    by_status: dict[str, int] = {}
    try:
        for item in WorkItem.objects.filter(assigned_agent=agent):
            by_status[item.status] = by_status.get(item.status, 0) + 1
    except Exception:
        pass
    return True, {
        "status": "success",
        "agent": agent.name,
        "sessions_total": sessions_total,
        "recent_sessions": recent,
        "cronjobs": cronjobs,
        "workitems_by_status": by_status,
    }


def agent_versions(_session: Session, name: str, limit: int = 20) -> tuple[bool, dict[str, Any]]:
    """List ONE agent's version history, newest first.

    Args:
        name: Name of the agent (required).
        limit: Max versions to return (1-100, default 20).

    Returns:
        ``(True, {"status": "success", "agent": str, "versions": [...]})``
        or ``(False, {"status": "error", "message": ...})``.
    """
    ok, agent = _resolve_agent(name)
    if not ok:
        return False, agent
    try:
        limit = max(1, min(int(limit or 20), 100))
    except (TypeError, ValueError):
        return False, {"status": "error", "message": "limit must be a number."}
    try:
        versions = list(agent.related_agent_versions.all().order_by("-version_number")[:limit])
        total = agent.related_agent_versions.count()
    except Exception as e:
        return False, {"status": "error", "message": f"Could not read agent versions: {e}"}
    rows = []
    for v in versions:
        try:
            created = v.created_at.isoformat() if v.created_at else None
        except Exception:
            created = None
        rows.append({
            "version_number": v.version_number,
            "visibility": v.visibility,
            "created_at": created,
            "commit": (v.commit or "")[:12],
        })
    return True, {"status": "success", "agent": agent.name, "versions": rows, "total": total}
