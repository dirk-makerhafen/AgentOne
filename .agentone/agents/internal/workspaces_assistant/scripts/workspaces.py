"""Workspace collection tools for the workspaces_assistant agent.

The collection is scoped exactly like every other plural assistant: a
project-bound session sees that project's workspaces, an unbound session
sees the global collection. Listing, creating project/global workspaces,
and collection health belong here; working inside ONE workspace
(sub-workspaces, rename, chats) belongs to the bound
``workspace_assistant``. Every tool returns a ``(bool, dict)`` tuple.
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


def _session_counts() -> dict[int, int]:
    """Map workspace pk to bound session count (single grouped query)."""
    from django.db.models import Count

    from server.models.sessions.session import SessionModel

    counts: dict[int, int] = {}
    try:
        rows = (
            SessionModel.objects.filter(latest_session_version__workspace__isnull=False)
            .values("latest_session_version__workspace")
            .annotate(n=Count("pk"))
        )
        for row in rows:
            counts[row["latest_session_version__workspace"]] = row["n"]
    except Exception:
        pass
    return counts


def _scope_project(_session: Session):
    """Return the project that scopes the collection (None means global).

    Sessions bound to a project-owned workspace inherit that project even
    when ``parent_project`` was not stamped on the session.
    """
    try:
        project = _session.get_project()
    except Exception:  # pylint: disable=broad-exception-caught
        project = None
    if project is not None:
        return project
    try:
        workspace = _session.workspace
        return getattr(workspace, "parent_project", None)
    except Exception:  # pylint: disable=broad-exception-caught
        return None


def _scoped_workspaces(_session: Session) -> list:
    """Return workspaces in the session's scope, ordered by name."""
    from runtime.workspace.workspaces import Workspaces

    return list(Workspaces(parent_project=_scope_project(_session)).all())


def _workspace_info(ws, all_paths: dict[int, str], session_counts: dict[int, int] | None = None) -> dict[str, Any]:
    mine = all_paths.get(ws.pk, "")
    nested = any(
        other != ws.pk and all_paths.get(other, "") and mine.startswith(all_paths[other] + os.sep)
        for other in all_paths
    )
    try:
        project = ws.parent_project
    except Exception:  # pylint: disable=broad-exception-caught
        project = None
    return {
        "workspace_pk": ws.pk,
        "name": ws.name or ws.path,
        "path": ws.path,
        "description": ws.description or "",
        "color": getattr(ws, "color", "") or "",
        "project": (project.name if project is not None else ""),
        "project_pk": (project.pk if project is not None else None),
        "top_level": not nested,
        "session_count": (session_counts or {}).get(ws.pk, 0),
    }


def _scope_label(project) -> str:
    """Return a short human scope label for tool results."""
    if project is None:
        return "global"
    try:
        name = (getattr(project, "name", "") or "").strip()
    except Exception:  # pylint: disable=broad-exception-caught
        name = ""
    return f"project {name}" if name else f"project #{getattr(project, 'pk', '?')}"


def list_workspaces(_session: Session) -> tuple[bool, dict[str, Any]]:
    """List the workspaces in your scope, ordered by name.

    A project-bound session lists that project's workspaces; an unbound
    session lists the global collection. Each entry flags whether it is
    top-level or nested inside another workspace *within this scope*.

    Returns:
        ``(True, {"status": "success", "workspaces": [...], "count": int,
        "scope": str})``
        or ``(False, {"status": "error", "message": ...})``.
    """
    project = _scope_project(_session)
    try:
        all_ws = _scoped_workspaces(_session)
    except Exception as e:
        return False, {"status": "error", "message": f"Could not list workspaces: {e}"}
    paths = {ws.pk: _norm(ws.path) for ws in all_ws}
    counts = _session_counts()
    return True, {
        "status": "success",
        "workspaces": [_workspace_info(ws, paths, counts) for ws in all_ws],
        "count": len(all_ws),
        "scope": _scope_label(project),
    }


def create_workspace(
    _session: Session,
    name: str,
    path: str,
    description: str = "",
    color: Optional[str] = None,
) -> tuple[bool, dict[str, Any]]:
    """Create a new workspace in your scope for an existing directory tree.

    The directory is created when missing. In a project-bound session the
    new workspace is owned by that project (and appears in the project's
    workspace list); an unbound session creates a global workspace. Unlike
    the bound ``workspace_assistant`` (which only creates sub-workspaces
    inside its managed workspace), this creates a top-level workspace.
    Organizing inside ONE workspace afterwards belongs to
    ``workspace_assistant``.

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
    project = _scope_project(_session)
    full = _norm(path)
    try:
        os.makedirs(full, exist_ok=True)
    except Exception as e:
        return False, {"status": "error", "message": f"Could not create directory '{full}': {e}"}
    try:
        ws = WorkspaceModel.objects.filter(path=full).order_by("pk").first()
        created = ws is None
        if created:
            ws = WorkspaceModel.objects.create(
                path=full,
                name=name,
                description=description or "",
                parent_project=project,
            )
    except Exception as e:
        return False, {"status": "error", "message": f"Could not create workspace: {e}"}
    adopted = False
    if not created and project is not None and ws.parent_project_id is None:
        ws.parent_project = project
        try:
            ws.save(update_fields=["parent_project"])
            adopted = True
        except Exception:  # pylint: disable=broad-exception-caught
            pass
    if created and color is not None:
        ws.color = color
        try:
            ws.save(update_fields=["color", "updated_at"])
        except Exception:  # pylint: disable=broad-exception-caught
            pass
    try:
        scoped = _scoped_workspaces(_session)
    except Exception:  # pylint: disable=broad-exception-caught
        scoped = []
    if ws.pk not in {item.pk for item in scoped}:
        scoped.append(ws)
    paths = {item.pk: _norm(item.path) for item in scoped}
    info = _workspace_info(ws, paths, _session_counts())
    info.update({
        "status": "success",
        "created": created,
        "adopted": adopted,
        "scope": _scope_label(project),
    })
    return True, info


def workspaces_stats(_session: Session) -> tuple[bool, dict[str, Any]]:
    """Count workspaces in your scope: total, top-level, and nested.

    Returns:
        ``(True, {"status": "success", "total": int, "top_level": int,
        "nested": int, "scope": str})`` or ``(False, {"status": "error", ...})``.
    """
    project = _scope_project(_session)
    try:
        all_ws = _scoped_workspaces(_session)
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
        "scope": _scope_label(project),
    }
