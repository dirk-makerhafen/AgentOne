"""Single-agent tools for the agent_assistant agent.

All tools are bound to the calling session's workspace: the
agent_assistant session runs with its workspace set to the folder holding
that agent's ``agent.md`` (see ``Agent.get_assistant_session``), so the
agent is resolved from the workspace path — tools take NO agent name.
They report its usage (sessions, cron jobs, work items), list its
version history, and list its child skills, subagents, and targeted
cron jobs. Reading and editing the ``agent.md`` itself is done
with the filesystem tools, not with a describe tool.
Collection operations (list, stats) belong to ``agents_assistant``.
Every tool returns a ``(bool, dict)`` tuple.
"""
from __future__ import annotations

import os
from typing import Any

from runtime.script_helpers import agent_row, cron_row, normalize_dir, skill_row
from runtime.session.session import Session


def _resolve_agent(_session: Session):
    """Find the agent whose manifest folder is this session's workspace.

    Returns ``(True, agent)`` or ``(False, error_dict)``.
    """
    from server.models.agents.agent import AgentModel

    workspace = None
    try:
        workspace = _session.workspace
    except Exception:
        workspace = None
    ws_path = normalize_dir(getattr(workspace, "path", None))
    if not ws_path:
        return False, {
            "status": "error",
            "message": (
                "This assistant session is not bound to an agent folder "
                "(no workspace). Open the assistant from an agent instead."
            ),
        }
    agent = AgentModel.objects.filter(manifest_dir=ws_path).first()
    if agent is None:
        # Fall back to realpath comparison (symlinked home dirs, etc.).
        try:
            real = os.path.realpath(ws_path)
        except Exception:
            real = ""
        if real:
            for cand in AgentModel.objects.exclude(manifest_dir=""):
                try:
                    if os.path.realpath(cand.manifest_dir or "") == real:
                        agent = cand
                        break
                except Exception:
                    continue
    if agent is None:
        return False, {
            "status": "error",
            "message": (
                f"No agent found for this session's workspace '{ws_path}'. "
                "Open the assistant from an agent instead."
            ),
        }
    return True, agent


def agent_usage(_session: Session, limit: int = 10) -> tuple[bool, dict[str, Any]]:
    """Report how THIS agent is used: session count plus recent sessions,
    cron jobs targeting it, and assigned work items by status.

    The agent is the one whose manifest folder is this session's
    workspace — no name argument.

    Args:
        limit: Max recent sessions to detail (1-50, default 10).

    Returns:
        ``(True, {"status": "success", "agent": str, "sessions_total": int,
        "recent_sessions": [...], "cronjobs": [...], "workitems_by_status": {...}}})``
        or ``(False, {"status": "error", "message": ...})``.
    """
    from server.models.cron import Cronjob
    from server.models.sessions.session import SessionModel
    from server.models.workitems.work_item import WorkItem

    ok, agent = _resolve_agent(_session)
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


def agent_versions(_session: Session, limit: int = 20) -> tuple[bool, dict[str, Any]]:
    """List THIS agent's version history, newest first.

    The agent is the one whose manifest folder is this session's
    workspace — no name argument.

    Args:
        limit: Max versions to return (1-100, default 20).

    Returns:
        ``(True, {"status": "success", "agent": str, "versions": [...]})``
        or ``(False, {"status": "error", "message": ...})``.
    """
    ok, agent = _resolve_agent(_session)
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


def list_skills(_session: Session) -> tuple[bool, dict[str, Any]]:
    """List THIS agent's child skills, ordered by name.

    The agent is the one whose manifest folder is this session's
    workspace — no name argument. Base path ``<agent_dir>/skills/``.

    Returns:
        ``(True, {"status": "success", "agent": str, "skills": [...],
        "count": int, "scope": str})`` or
        ``(False, {"status": "error", "message": ...})``.
    """
    from runtime.skill.skills import Skills

    ok, agent = _resolve_agent(_session)
    if not ok:
        return False, agent
    try:
        skills = list(Skills(parent_agent=agent).all().order_by("name"))
    except Exception as e:
        return False, {"status": "error", "message": f"Could not list agent skills: {e}"}
    return True, {
        "status": "success",
        "agent": agent.name,
        "skills": [skill_row(s) for s in skills],
        "count": len(skills),
        "scope": f"{normalize_dir(agent.manifest_dir)}/skills/",
    }


def list_agents(_session: Session) -> tuple[bool, dict[str, Any]]:
    """List THIS agent's subagents, ordered by name.

    The agent is the one whose manifest folder is this session's
    workspace — no name argument. Base path ``<agent_dir>/agents/``.

    Returns:
        ``(True, {"status": "success", "agent": str, "agents": [...],
        "count": int, "scope": str})`` or
        ``(False, {"status": "error", "message": ...})``.
    """
    from runtime.agents.agents import Agents

    ok, agent = _resolve_agent(_session)
    if not ok:
        return False, agent
    try:
        subagents = list(Agents(parent_agent=agent).all().order_by("name"))
    except Exception as e:
        return False, {"status": "error", "message": f"Could not list subagents: {e}"}
    return True, {
        "status": "success",
        "agent": agent.name,
        "agents": [agent_row(a) for a in subagents],
        "count": len(subagents),
        "scope": f"{normalize_dir(agent.manifest_dir)}/agents/",
    }


def list_cronjobs(_session: Session, include_archived: bool = False) -> tuple[bool, dict[str, Any]]:
    """List the cron jobs targeting THIS agent, ordered by name.

    The agent is the one whose manifest folder is this session's
    workspace — no name argument. Scope is the targeting relation (jobs
    pointing at this agent), not a directory on disk.

    Args:
        include_archived: Also list archived jobs (default False).

    Returns:
        ``(True, {"status": "success", "agent": str, "cronjobs": [...],
        "count": int, "scope": str})`` or
        ``(False, {"status": "error", "message": ...})``.
    """
    from server.models.cron import Cronjob

    ok, agent = _resolve_agent(_session)
    if not ok:
        return False, agent
    try:
        queryset = Cronjob.objects.filter(agent=agent)
        if not include_archived:
            queryset = queryset.filter(is_archived=False)
        jobs = list(queryset.order_by("name"))
    except Exception as e:
        return False, {"status": "error", "message": f"Could not list agent cron jobs: {e}"}
    return True, {
        "status": "success",
        "agent": agent.name,
        "cronjobs": [cron_row(j) for j in jobs],
        "count": len(jobs),
        "scope": f"{normalize_dir(agent.manifest_dir)}/cronjobs/",
    }


def agent_details(_session: Session) -> tuple[bool, dict[str, Any]]:
    """Show THIS agent's key details in one call: identity, version,
    usage totals, and children counts.

    The agent is the one whose manifest folder is this session's
    workspace — no name argument. This returns what the file alone
    cannot: version identity, live session/usage totals, and children
    counts. Use `agent_usage` / `agent_versions` / `list_*` for the
    full breakdowns.

    Returns:
        ``(True, {"status": "success", details...})`` or
        ``(False, {"status": "error", "message": ...})``.
    """
    from server.models.cron import Cronjob
    from server.models.sessions.session import SessionModel
    from runtime.agents.agents import Agents
    from runtime.skill.skills import Skills

    ok, agent = _resolve_agent(_session)
    if not ok:
        return False, agent
    version = agent.latest_agent_version
    try:
        parent_project = agent.parent_project.name if agent.parent_project else None
    except Exception:
        parent_project = None
    try:
        parent_agent = agent.parent_agent.name if agent.parent_agent else None
    except Exception:
        parent_agent = None
    try:
        sessions_total = SessionModel.objects.filter(
            latest_session_version__agent=agent
        ).count()
    except Exception:
        sessions_total = 0
    try:
        skills_count = Skills(parent_agent=agent).all().count()
    except Exception:
        skills_count = 0
    try:
        subagents_count = Agents(parent_agent=agent).all().count()
    except Exception:
        subagents_count = 0
    try:
        cronjobs_count = Cronjob.objects.filter(
            agent=agent, is_archived=False
        ).count()
    except Exception:
        cronjobs_count = 0
    return True, {
        "status": "success",
        "name": agent.name,
        "path": agent.manifest_dir or "",
        "project": parent_project,
        "parent_agent": parent_agent,
        "kind": "subagent" if parent_agent else "root",
        "visibility": version.visibility if version is not None else None,
        "version_number": version.version_number if version is not None else 0,
        "version_count": agent.related_agent_versions.count(),
        "sessions_total": sessions_total,
        "skills_count": skills_count,
        "subagents_count": subagents_count,
        "cronjobs_count": cronjobs_count,
        "scope": f"{normalize_dir(agent.manifest_dir)}/",
    }


def refresh_from_disk(_session: Session) -> tuple[bool, dict[str, Any]]:
    """Reload THIS agent (and its child scripts/skills/subagents) from disk.

    Use after editing the agent's ``agent.md`` or sibling files on disk.
    The agent is the one whose manifest folder is this session's
    workspace.

    Returns:
        ``(True, {"status": "success", "agent": str, "details": [...]})``
        or ``(False, {"status": "error", "message": ...})``.
    """
    ok, agent = _resolve_agent(_session)
    if not ok:
        return False, agent
    details: list[dict[str, Any]] = []
    try:
        agent.refresh_from_disk(details=details)
    except Exception as e:
        return False, {"status": "error", "message": f"Could not refresh agent from disk: {e}"}
    return True, {
        "status": "success",
        "agent": agent.name,
        "details": details,
    }
