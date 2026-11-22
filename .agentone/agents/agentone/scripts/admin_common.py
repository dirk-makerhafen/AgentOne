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


def _by_name(model: Any, value: Any) -> tuple[Any | None, str | None]:
    """Resolve a row by id or exact (then unambiguous partial) name.

    Used when the session binding cannot identify the intended target — e.g.
    a rightbar chat bound to AgentOne home but asked about a named project.
    """
    text = str(value or "").strip()
    if not text:
        return None, None
    if text.isdigit():
        row = model.objects.filter(pk=int(text)).first()
        if row is not None:
            return row, None
    row = model.objects.filter(name__iexact=text).first()
    if row is not None:
        return row, None
    matches = list(model.objects.filter(name__icontains=text)[:5])
    if len(matches) == 1:
        return matches[0], None
    if len(matches) > 1:
        names = ", ".join(str(match.name) for match in matches)
        return None, f"'{text}' is ambiguous; use an id. Matches: {names}"
    return None, f"{model.__name__} '{text}' not found"


def _project_for(session: Any, pk: Any = None, name: Any = None):
    """Return ``(project, error)`` — explicit id/name beats session scope."""
    from server.models.project import Project

    if pk:
        try:
            return Project.objects.get(pk=pk), None
        except Project.DoesNotExist:
            return None, f"Project {pk} not found"
    if name:
        row, error = _by_name(Project, name)
        if error:
            return None, error
        if row is not None:
            return row, None
    project = _scope_project(session)
    if project is None:
        return None, "No project in scope; pass project_pk or project_name"
    return project, None


def _scope_project_for(session: Any, kwargs: dict[str, Any] | None = None):
    """Return ``(project, error)`` for a read scope.

    Read-only scopes (agents, skills) used to be able only to infer the
    project from the session, which a rightbar chat bound to AgentOne home
    cannot express. Explicit ``project_pk`` / ``project_name`` now win.
    """
    values = kwargs or {}
    if values.get("project_pk") or values.get("project_name"):
        return _project_for(session, values.get("project_pk"), values.get("project_name"))
    return _scope_project(session), None


def _workspace_for(session: Any, pk: Any = None, name: Any = None):
    """Return ``(workspace, error)`` — explicit id/name beats session scope.

    The session binding is a fallback, not a fence: an explicit id or name is
    a deliberate target and may sit outside the inferred project scope. That
    is exactly the case the one-time session context hint warns about.
    """
    from server.models.workspace import WorkspaceModel

    if pk:
        try:
            return WorkspaceModel.objects.get(pk=pk), None
        except WorkspaceModel.DoesNotExist:
            return None, f"Workspace {pk} not found"
    if name:
        row, error = _by_name(WorkspaceModel, name)
        if error:
            return None, error
        if row is not None:
            return row, None
    workspace = _scope_workspace(session)
    if workspace is None:
        return None, "No workspace in scope; pass workspace_pk or workspace_name"
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
