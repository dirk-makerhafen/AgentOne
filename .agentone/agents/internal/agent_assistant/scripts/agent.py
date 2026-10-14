"""Single-agent tools for the agent_assistant agent.

All tools are bound to the calling session's workspace: the
agent_assistant session runs with its workspace set to the folder holding
that agent's ``agent.md`` (see ``Agent.get_assistant_session``), so the
agent is resolved from the workspace path — tools take NO agent name.
They report its usage (sessions, cron jobs, work items) and list its
version history. Reading and editing the ``agent.md`` itself is done
with the filesystem tools, not with a describe tool.
Collection operations (list, stats) belong to ``agents_assistant``.
Every tool returns a ``(bool, dict)`` tuple.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from runtime.session.session import Session


def _normalize_dir(value: Any) -> str:
    """Normalize a directory path for comparison (no I/O)."""
    try:
        text = str(value or "").strip()
        if not text:
            return ""
        return Path(text).expanduser().as_posix().rstrip("/") or ""
    except Exception:
        return ""


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
    ws_path = _normalize_dir(getattr(workspace, "path", None))
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
