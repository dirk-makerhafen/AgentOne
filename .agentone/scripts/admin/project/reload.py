"""Reload a project's manifests from disk."""
from __future__ import annotations


def reload(_session: Any, project_pk: int | None = None, **kwargs) -> tuple[bool, dict]:
    """
    Reload a project's manifests from disk.
    
    If project_pk is not provided, reloads the current session's project.
    
    Returns:
        A tuple of (success, result).
        On success, result contains:
            - status: "success"
            - details: list of reload details
        On error, result contains:
            - status: "error"
            - message: str
    """
    from server.models.project import Project
    
    target_project = _get_scope_project(_session)
    
    if project_pk:
        try:
            target_project = Project.objects.get(pk=project_pk)
        except Project.DoesNotExist:
            return (False, {"status": "error", "message": f"Project {project_pk} not found"})
    
    if not target_project:
        return (False, {"status": "error", "message": "No project in scope and no project_pk provided"})
    
    try:
        details: list = []
        target_project.refresh_from_disk(details=details)
        target_project.refresh_from_db()
    except Exception as e:
        return (False, {"status": "error", "message": f"Failed to reload project: {e}"})
    
    return (True, {"status": "success", "details": details})


def _session_project(session: Any) -> Any | None:
    return session.get_project()


def _session_workspace(session: Any) -> Any | None:
    try:
        return session.workspace
    except Exception:
        return None


def _get_workspace_project(workspace: Any) -> Any | None:
    try:
        return workspace.parent_project
    except Exception:
        return None


def _get_scope_project(session: Any) -> Any | None:
    project = _session_project(session)
    if project:
        return project
    workspace = _session_workspace(session)
    if workspace:
        return _get_workspace_project(workspace)
    return None