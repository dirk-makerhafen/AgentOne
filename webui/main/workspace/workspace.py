"""Workspace helpers shared by the (legacy) UI and tests.

Only the pure helpers live here now; the  view class has been removed.
"""
from __future__ import annotations

import os

from typing import TYPE_CHECKING


def norm_workspace_path(path: str) -> str:
    """Normalize a workspace path for prefix comparison (symlinks resolved)."""
    try:
        return os.path.realpath(path or "").rstrip(os.sep)
    except Exception:
        return os.path.normpath(path or "").rstrip(os.sep)


def workspace_parent_map(workspaces: list) -> dict[int, int | None]:
    """Map each workspace pk to its parent pk (longest path-prefix wins).

    Items need ``pk`` and ``path`` attributes.  Workspaces with no
    containing workspace map to None.
    """
    normed = {ws.pk: norm_workspace_path(ws.path) for ws in workspaces}
    parent_of: dict[int, int | None] = {}
    for ws in workspaces:
        best: int | None = None
        best_len = -1
        mine = normed[ws.pk]
        for other in workspaces:
            if other.pk == ws.pk:
                continue
            theirs = normed[other.pk]
            if not theirs or theirs == os.sep:
                continue
            if mine != theirs and mine.startswith(theirs + os.sep) and len(theirs) > best_len:
                best, best_len = other.pk, len(theirs)
        parent_of[ws.pk] = best
    return parent_of


def current_session_workspace_pk(main_view) -> int | None:
    """Workspace pk bound to the current chat session, if any.

    Scans the open tabs for a session subject (the selected tab first)
    so the ACTIVE badge survives while the overview or a detail tab is
    selected.  Never raises — returns None when nothing matches.
    """
    try:
        selected = main_view.selected_tab_view
        rest = [v for v in getattr(main_view, "open_tabs", {}).values() if v is not selected]
        tabs = ([selected] if selected is not None else []) + rest
    except Exception:
        return None
    for tab in tabs:
        subj = getattr(tab, "subject", None)
        if subj is None:
            continue
        try:
            from server.models import SessionModel

            if isinstance(subj, SessionModel):
                sv = getattr(subj, "latest_session_version", None)
                ws_id = getattr(sv, "workspace_id", None)
                if ws_id:
                    return ws_id
        except Exception:
            continue
    return None


def workspace_card_data(ws) -> dict:
    """Card info dict for a workspace (sessions/agents counts, no raise)."""
    try:
        from server.models.sessions.session_version import SessionVersionModel

        versions = SessionVersionModel.objects.filter(workspace=ws)
        sessions = versions.count()
        agents = versions.values_list("agent__name", flat=True).distinct().count()
    except Exception:
        sessions, agents = 0, 0
    return {
        "pk": ws.pk,
        "name": ws.name or ws.path,
        "path": ws.path,
        "description": ws.description or "",
        "color": getattr(ws, "color", "") or "",
        "session_count": sessions,
        "agent_count": agents,
    }


def related_chat_data(session) -> dict:
    """Row info dict for a session bound to a workspace (no raise)."""
    try:
        from server.models.enums.session_enums import SessionType

        type_label = dict(SessionType.choices).get(
            session.session_type, session.session_type or ""
        )
    except Exception:
        type_label = ""
    return {
        "pk": session.pk,
        "name": session.name or f"Session {session.pk}",
        "type_label": type_label,
        "is_active": bool(getattr(session, "is_active", False)),
        "turn_count": getattr(session, "turn_count", 0) or 0,
    }