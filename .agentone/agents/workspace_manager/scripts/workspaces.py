"""Workspace management tools for the workspace_manager agent.

All tools are bound: the managed workspace is the workspace of the calling
session. Sub-workspace paths must stay inside the managed workspace
directory. Every tool returns a ``(bool, dict)`` tuple.
"""
from __future__ import annotations

import os
from typing import Any

from runtime.session.session import Session


def _norm(path: str) -> str:
    """Normalize a path for prefix comparison (symlinks resolved)."""
    try:
        return os.path.realpath(path or "").rstrip(os.sep)
    except Exception:
        return os.path.normpath(path or "").rstrip(os.sep)


def _is_within(path: str, parent: str) -> bool:
    """True when *path* is strictly inside *parent*."""
    mine, theirs = _norm(path), _norm(parent)
    return bool(theirs) and mine != theirs and mine.startswith(theirs + os.sep)


def _managed_workspace(_session: Session):
    """Workspace the calling session is bound to (None when unbound)."""
    try:
        return _session.workspace
    except Exception:
        return None


def _workspace_info(ws) -> dict[str, Any]:
    return {
        "workspace_pk": ws.pk,
        "name": ws.name or ws.path,
        "path": ws.path,
        "description": ws.description or "",
        "color": getattr(ws, "color", "") or "",
    }


def _resolve_target(_session: Session, workspace_name: str = ""):
    """Resolve the tool target: the managed workspace, or a sub-workspace.

    Returns ``(True, workspace)`` or ``(False, error_dict)``.
    """
    from server.models.workspace import WorkspaceModel

    managed = _managed_workspace(_session)
    if managed is None:
        return False, {"status": "error", "message": "Your session is not bound to a workspace."}
    name = (workspace_name or "").strip()
    if not name:
        return True, managed
    candidates = [
        ws for ws in WorkspaceModel.objects.all()
        if (ws.name or "") == name and _is_within(ws.path, managed.path)
    ]
    if not candidates:
        return False, {
            "status": "error",
            "message": f"No sub-workspace named '{name}' inside '{managed.name}'.",
        }
    if len(candidates) > 1:
        return False, {
            "status": "error",
            "message": f"Multiple sub-workspaces named '{name}'. Tell the user to pick one by path.",
            "paths": [ws.path for ws in candidates],
        }
    return True, candidates[0]


def list_subworkspaces(_session: Session) -> tuple[bool, dict[str, Any]]:
    """List the direct sub-workspaces of your managed workspace.

    A sub-workspace is any workspace whose directory lives inside the
    managed workspace directory (longest path-prefix wins for nesting).

    Args:
        (none besides _session, which is bound automatically).

    Returns:
        ``(True, {"status": "success", "workspace": {...managed...},
        "subworkspaces": [{workspace_pk, name, path, description, color}]})``
        sorted by name, or ``(False, {"status": "error", "message": ...})``.
    """
    from server.models.workspace import WorkspaceModel

    managed = _managed_workspace(_session)
    if managed is None:
        return False, {"status": "error", "message": "Your session is not bound to a workspace."}
    try:
        all_ws = list(WorkspaceModel.objects.all())
    except Exception as e:
        return False, {"status": "error", "message": f"Could not list workspaces: {e}"}
    normed = {ws.pk: _norm(ws.path) for ws in all_ws}
    mine = normed.get(managed.pk, "")
    children = []
    for ws in all_ws:
        if ws.pk == managed.pk:
            continue
        theirs = normed.get(ws.pk, "")
        if not theirs or theirs == os.sep or not mine:
            continue
        if theirs.startswith(mine + os.sep):
            # Direct child: no other workspace in between.
            in_between = any(
                other.pk not in (managed.pk, ws.pk)
                and normed.get(other.pk, "")
                and theirs.startswith(normed[other.pk] + os.sep)
                and normed[other.pk].startswith(mine + os.sep)
                for other in all_ws
            )
            if not in_between:
                children.append(ws)
    children.sort(key=lambda w: (w.name or "").lower())
    return True, {
        "status": "success",
        "workspace": _workspace_info(managed),
        "subworkspaces": [_workspace_info(ws) for ws in children],
    }


def create_subworkspace(
    _session: Session, name: str, path: str, description: str = ""
) -> tuple[bool, dict[str, Any]]:
    """Create a new sub-workspace inside your managed workspace.

    The directory is created when missing. The path must be strictly
    inside the managed workspace directory.

    Args:
        name: Display name for the new sub-workspace (required).
        path: Directory for the new sub-workspace (required, must be
            inside the managed workspace directory).
        description: Optional short description.

    Returns:
        ``(True, {"status": "success", "created": bool, subworkspace...})``
        (``created`` is False when a workspace for that path already
        existed), or ``(False, {"status": "error", "message": ...})``.
    """
    from server.models.workspace import WorkspaceModel

    managed = _managed_workspace(_session)
    if managed is None:
        return False, {"status": "error", "message": "Your session is not bound to a workspace."}
    name = (name or "").strip()
    if not name:
        return False, {"status": "error", "message": "A name is required."}
    if not (path or "").strip():
        return False, {"status": "error", "message": "A path is required."}
    if not _is_within(path, managed.path):
        return False, {
            "status": "error",
            "message": f"Path must be inside the managed workspace '{managed.path}'.",
        }
    full = _norm(path)
    try:
        os.makedirs(full, exist_ok=True)
    except Exception as e:
        return False, {"status": "error", "message": f"Could not create directory '{full}': {e}"}
    try:
        ws, created = WorkspaceModel.objects.get_or_create(
            path=full,
            defaults={"name": name, "description": description or ""},
        )
    except Exception as e:
        return False, {"status": "error", "message": f"Could not create workspace: {e}"}
    info = _workspace_info(ws)
    info.update({"status": "success", "created": created})
    return True, info


def edit_workspace(
    _session: Session,
    description: str | None = None,
    color: str | None = None,
    path: str | None = None,
    workspace_name: str = "",
) -> tuple[bool, dict[str, Any]]:
    """Edit the description, color or path of the managed workspace or one of its sub-workspaces.

    Only the arguments you pass are changed. To rename, use
    ``rename_workspace`` instead.

    Args:
        description: New description (optional).
        color: New accent color as a #rrggbb hex string (optional).
        path: New directory (optional, must exist; sub-workspaces must
            stay inside the managed workspace directory).
        workspace_name: Name of a sub-workspace to edit instead of the
            managed workspace itself (optional).

    Returns:
        ``(True, {"status": "success", workspace...})`` or
        ``(False, {"status": "error", "message": ...})``.
    """
    from server.models.workspace import validate_workspace_color

    ok, target = _resolve_target(_session, workspace_name)
    if not ok:
        return False, target
    managed = _managed_workspace(_session)
    changed: list[str] = []
    if description is not None:
        target.description = description or ""
        changed.append("description")
    if color is not None:
        try:
            validate_workspace_color(color)
        except Exception:
            return False, {"status": "error", "message": "Color must be a #rrggbb hex string."}
        target.color = color
        changed.append("color")
    if path is not None:
        new_path = (path or "").strip()
        if not new_path or not os.path.isdir(new_path):
            return False, {"status": "error", "message": "Path must be an existing directory."}
        if target.pk != managed.pk and not _is_within(new_path, managed.path):
            return False, {
                "status": "error",
                "message": f"Path must stay inside the managed workspace '{managed.path}'.",
            }
        target.path = _norm(new_path)
        changed.append("path")
    if not changed:
        return False, {"status": "error", "message": "Nothing to change."}
    try:
        target.save()
    except Exception as e:
        return False, {"status": "error", "message": f"Could not save workspace: {e}"}
    info = _workspace_info(target)
    info.update({"status": "success", "changed": changed})
    return True, info


def rename_workspace(
    _session: Session, new_name: str, workspace_name: str = ""
) -> tuple[bool, dict[str, Any]]:
    """Rename the managed workspace or one of its sub-workspaces.

    Confirm the new name with the user first when they did not state it
    explicitly.

    Args:
        new_name: New display name (required, must not be empty).
        workspace_name: Name of a sub-workspace to rename instead of the
            managed workspace itself (optional).

    Returns:
        ``(True, {"status": "success", "old_name": ..., workspace...})`` or
        ``(False, {"status": "error", "message": ...})``.
    """
    ok, target = _resolve_target(_session, workspace_name)
    if not ok:
        return False, target
    new_name = (new_name or "").strip()
    if not new_name:
        return False, {"status": "error", "message": "A new name is required."}
    old_name = target.name
    target.name = new_name
    try:
        target.save(update_fields=["name", "updated_at"])
    except Exception as e:
        return False, {"status": "error", "message": f"Could not rename workspace: {e}"}
    info = _workspace_info(target)
    info.update({"status": "success", "old_name": old_name})
    return True, info


def list_sessions(_session: Session) -> tuple[bool, dict[str, Any]]:
    """List the chat sessions bound to your managed workspace, newest first.

    Args:
        (none besides _session, which is bound automatically).

    Returns:
        ``(True, {"status": "success", "sessions": [{session_pk, name,
        agent, type, is_active, turn_count}]})`` or
        ``(False, {"status": "error", "message": ...})``.
    """
    from server.models.enums.session_enums import SessionType
    from server.models.sessions.session import SessionModel

    managed = _managed_workspace(_session)
    if managed is None:
        return False, {"status": "error", "message": "Your session is not bound to a workspace."}
    try:
        sessions = (
            SessionModel.objects.filter(
                latest_session_version__workspace=managed,
                session_type__in=[SessionType.SESSION],
            )
            .select_related("latest_session_version__agent")
            .order_by("-created_at")
        )
        rows = []
        for s in sessions:
            try:
                agent_name = s.latest_session_version.agent.name
            except Exception:
                agent_name = ""
            rows.append({
                "session_pk": s.pk,
                "name": s.name or f"Session {s.pk}",
                "agent": agent_name,
                "type": s.session_type or "",
                "is_active": bool(getattr(s, "is_active", False)),
                "turn_count": getattr(s, "turn_count", 0) or 0,
            })
    except Exception as e:
        return False, {"status": "error", "message": f"Could not list sessions: {e}"}
    return True, {"status": "success", "sessions": rows}


def create_chat(
    _session: Session, agent_name: str, name: str = "", description: str = ""
) -> tuple[bool, dict[str, Any]]:
    """Create a new normal chat session in your managed workspace.

    The new session uses the requested agent and starts empty — the user
    opens it from the workspace page or the chat list and starts talking.
    Always tell the user the chat's name so they can find it.

    Args:
        agent_name: Name of the agent for the new chat (required,
            e.g. "AgentOne").
        name: Display name for the new chat (optional; auto-generated
            from workspace and agent when omitted).
        description: Optional description for the new chat.

    Returns:
        ``(True, {"status": "success", "session_pk": int, "name": str,
        "agent": str})`` or ``(False, {"status": "error", "message": ...})``.
    """
    from server.models.agents.agent import AgentModel
    from server.models.sessions.session import SessionModel

    managed = _managed_workspace(_session)
    if managed is None:
        return False, {"status": "error", "message": "Your session is not bound to a workspace."}
    agent_name = (agent_name or "").strip()
    if not agent_name:
        return False, {"status": "error", "message": "An agent name is required."}
    try:
        agent = AgentModel.objects.get(name=agent_name)
    except AgentModel.DoesNotExist:
        names = list(
            AgentModel.objects.filter(parent_agent__isnull=True).values_list("name", flat=True)
        )
        return False, {
            "status": "error",
            "message": f"No agent named '{agent_name}'.",
            "available_agents": names,
        }
    except Exception as e:
        return False, {"status": "error", "message": f"Could not look up agent: {e}"}
    if agent.latest_agent_version is None:
        return False, {"status": "error", "message": f"Agent '{agent_name}' has no version yet."}
    name = (name or "").strip()
    try:
        if not name:
            base = f"{managed.name or 'workspace'}-{agent.name}"
            name, i = base, 1
            while SessionModel.objects.filter(name=name).exists():
                i += 1
                name = f"{base}-{i}"
        elif SessionModel.objects.filter(name=name).exists():
            return False, {"status": "error", "message": f"A chat named '{name}' already exists."}
        session_version = agent.latest_agent_version.get_or_create_session(
            name=name,
            display_name=name,
            description=description or "",
            workspace=managed,
        )
    except Exception as e:
        return False, {"status": "error", "message": f"Could not create chat: {e}"}
    return True, {
        "status": "success",
        "session_pk": session_version.session.pk,
        "name": name,
        "agent": agent.name,
    }
