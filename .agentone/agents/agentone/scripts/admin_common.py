"""Shared helpers for the AgentOne admin_tool dispatchers."""
from __future__ import annotations

from typing import Any

def _normalize(value: Any) -> str:
    return str(value or "").strip().lower().replace("-", "_").replace(" ", "_")


def _ok(**data: Any) -> tuple[bool, dict[str, Any]]:
    return True, {"status": "success", **data}


def _err(message: str, **data: Any) -> tuple[bool, dict[str, Any]]:
    return False, {"status": "error", "message": message, **data}


# ---------------------------------------------------------------------------
# Shared session/scope helpers
# ---------------------------------------------------------------------------

def _scope_project(session: Any) -> Any | None:
    """Project that scopes this session (None = global)."""
    try:
        project = session.get_project()
    except Exception:  # pylint: disable=broad-exception-caught
        project = None
    if project is not None:
        return project
    workspace = _scope_workspace(session)
    return getattr(workspace, "parent_project", None) if workspace is not None else None


def _scope_workspace(session: Any) -> Any | None:
    try:
        return session.workspace
    except Exception:  # pylint: disable=broad-exception-caught
        return None


def _project_for(session: Any, pk: Any = None):
    """Return ``(project, error)`` — pk overrides the session scope."""
    from server.models.project import Project

    if pk:
        try:
            return Project.objects.get(pk=pk), None
        except Project.DoesNotExist:
            return None, f"Project {pk} not found"
    project = _scope_project(session)
    if project is None:
        return None, "No project in scope; pass project_pk"
    return project, None


def _workspace_for(session: Any, pk: Any = None):
    """Return ``(workspace, error)`` with a scope check for an explicit pk."""
    from server.models.workspace import WorkspaceModel

    workspace = _scope_workspace(session)
    if pk:
        try:
            workspace = WorkspaceModel.objects.get(pk=pk)
        except WorkspaceModel.DoesNotExist:
            return None, f"Workspace {pk} not found"
    if workspace is None:
        return None, "No workspace in scope; pass workspace_pk"
    project = _scope_project(session)
    if project is not None and workspace.parent_project is not None and workspace.parent_project != project:
        return None, "Workspace is outside the current project scope"
    return workspace, None


def _default_reload_folder(session: Any) -> str:
    """Best-effort root containing ``.agentone/`` for this session's scope.

    Callers that edited a different tree (e.g. global manifests from a
    project-scoped session) should pass ``folder=`` explicitly.
    """
    from pathlib import Path

    project = _scope_project(session)
    path = getattr(project, "path", None) if project is not None else None
    if path:
        return str(Path(path).resolve())
    workspace = _scope_workspace(session)
    path = getattr(workspace, "path", None) if workspace is not None else None
    if path:
        return str(Path(path).resolve())
    return str(Path.cwd())
