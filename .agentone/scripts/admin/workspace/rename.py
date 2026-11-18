"""Rename a workspace."""
from __future__ import annotations


def rename(_session: Any, workspace_pk: int, name: str, **kwargs) -> tuple[bool, dict]:
    """
    Rename a workspace.
    
    Args:
        workspace_pk: Workspace primary key
        name: New name
    
    Returns:
        A tuple of (success, result).
        On success, result contains:
            - status: "success"
            - workspace: dict with updated workspace info
        On error, result contains:
            - status: "error"
            - message: str
    """
    from server.models.workspace import WorkspaceModel
    
    if not name or not name.strip():
        return (False, {"status": "error", "message": "New name is required"})
    
    project = _get_scope_project(_session)
    name = name.strip()
    
    try:
        workspace = WorkspaceModel.objects.get(pk=workspace_pk)
    except WorkspaceModel.DoesNotExist:
        return (False, {"status": "error", "message": f"Workspace {workspace_pk} not found"})
    
    if project and workspace.parent_project != project:
        if workspace.parent_project is not None:
            return (False, {"status": "error", "message": "Workspace not in current project scope"})
    
    try:
        workspace.name = name
        workspace.save(update_fields=["name"])
    except Exception as e:
        return (False, {"status": "error", "message": f"Failed to rename workspace: {e}"})
    
    return (True, {
        "status": "success",
        "workspace": {
            "pk": workspace.pk,
            "name": workspace.name,
            "path": workspace.path,
        }
    })


def _session_project(session: Any) -> Any | None:
    return session.get_project()


def _session_workspace(session: Any) -> Any | None:
    try:
        return session.workspace
    except Exception:
        return None


def _get_scope_project(session: Any) -> Any | None:
    project = _session_project(session)
    if project:
        return project
    workspace = _session_workspace(session)
    if workspace:
        try:
            return workspace.parent_project
        except Exception:
            return None
    return None