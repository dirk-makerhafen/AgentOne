"""Workspace collection tools for the workspaces_assistant agent.

Workspaces are global entities (no project FK), so these tools are NOT
project-scoped: they see every workspace on the instance. Listing the
collection, creating top-level workspaces, and collection health belong
here; working inside ONE workspace (sub-workspaces, rename, chats)
belongs to the bound ``workspace_assistant``. Every tool returns a
``(bool, dict)`` tuple.
"""
from __future__ import annotations

import os
from typing import Any, Optional

from runtime.session.session import Session


def _norm(path: str) -> str:
    """Normalize a path for prefix comparison (symlinks resolved)."""
    try:
        return os.path.realpath(path or "").rstrip(os.sep)
    except Exception:
        return os.path.normpath(path or "").rstrip(os.sep)


def _workspace_info(ws, all_paths: dict[int, str]) -> dict[str, Any]:
    mine = all_paths.get(ws.pk, "")
    nested = any(
        other != ws.pk and all_paths.get(other, "") and mine.startswith(all_paths[other] + os.sep)
        for other in all_paths
    )
    return {
        "workspace_pk": ws.pk,
        "name": ws.name or ws.path,
        "path": ws.path,
        "description": ws.description or "",
        "color": getattr(ws, "color", "") or "",
        "top_level": not nested,
    }


def _all_workspaces():
    from server.models.workspace import WorkspaceModel

    return list(WorkspaceModel.objects.all().order_by("name"))


def list_workspaces(_session: Session) -> tuple[bool, dict[str, Any]]:
    """List ALL workspaces on the instance, ordered by name.

    Each entry flags whether it is top-level or nested inside another
    workspace's directory.

    Returns:
        ``(True, {"status": "success", "workspaces": [...], "count": int})``
        or ``(False, {"status": "error", "message": ...})``.
    """
    try:
        all_ws = _all_workspaces()
    except Exception as e:
        return False, {"status": "error", "message": f"Could not list workspaces: {e}"}
    paths = {ws.pk: _norm(ws.path) for ws in all_ws}
    return True, {
        "status": "success",
        "workspaces": [_workspace_info(ws, paths) for ws in all_ws],
        "count": len(all_ws),
    }


def create_workspace(
    _session: Session,
    name: str,
    path: str,
    description: str = "",
    color: Optional[str] = None,
) -> tuple[bool, dict[str, Any]]:
    """Create a new top-level workspace for an existing directory tree.

    The directory is created when missing. Unlike the bound
    ``workspace_assistant`` (which only creates sub-workspaces inside its
    managed workspace), this creates a workspace anywhere. Organizing
    inside ONE workspace afterwards belongs to ``workspace_assistant``.

    Args:
        name: Display name for the new workspace (required).
        path: Directory for the new workspace (required).
        description: Optional short description.
        color: Optional #rrggbb accent color.

    Returns:
        ``(True, {"status": "success", "created": bool, workspace...})``
        (``created`` is False when a workspace for that path already
        existed), or ``(False, {"status": "error", "message": ...})``.
    """
    from server.models.workspace import WorkspaceModel, validate_workspace_color

    name = (name or "").strip()
    if not name:
        return False, {"status": "error", "message": "A name is required."}
    if not (path or "").strip():
        return False, {"status": "error", "message": "A path is required."}
    if color is not None:
        try:
            validate_workspace_color(color)
        except Exception:
            return False, {"status": "error", "message": "Color must be a #rrggbb hex string."}
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
    if created:
        if color is not None:
            ws.color = color
            try:
                ws.save(update_fields=["color", "updated_at"])
            except Exception:
                pass
    info = {
        "workspace_pk": ws.pk,
        "name": ws.name or ws.path,
        "path": ws.path,
        "description": ws.description or "",
        "color": getattr(ws, "color", "") or "",
    }
    info.update({"status": "success", "created": created})
    return True, info


def workspaces_stats(_session: Session) -> tuple[bool, dict[str, Any]]:
    """Count workspaces on the instance: total, top-level, and nested.

    Returns:
        ``(True, {"status": "success", "total": int, "top_level": int,
        "nested": int})`` or ``(False, {"status": "error", ...})``.
    """
    try:
        all_ws = _all_workspaces()
    except Exception as e:
        return False, {"status": "error", "message": f"Could not list workspaces: {e}"}
    paths = {ws.pk: _norm(ws.path) for ws in all_ws}
    nested = sum(
        1 for ws in all_ws
        if any(
            other != ws.pk and paths.get(other, "") and paths[ws.pk].startswith(paths[other] + os.sep)
            for other in paths
        )
    )
    return True, {
        "status": "success",
        "total": len(all_ws),
        "top_level": len(all_ws) - nested,
        "nested": nested,
    }
