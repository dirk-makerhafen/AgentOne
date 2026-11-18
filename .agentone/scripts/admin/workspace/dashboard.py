"""Get or update a workspace's dashboard."""
from __future__ import annotations
from pathlib import Path


def dashboard(_session: Any, workspace_pk: int | None = None, content: str | None = None, **kwargs) -> tuple[bool, dict]:
    """
    Get or update a workspace's dashboard.
    
    If content is provided, writes it to the dashboard.
    If omitted, reads current content.
    
    Returns:
        A tuple of (success, result).
        On success, result contains:
            - status: "success"
            - content: str (when reading)
            - path: str
            - message: str (when writing)
        On error, result contains:
            - status: "error"
            - message: str
    """
    from server.models.workspace import WorkspaceModel
    
    target_workspace = _get_scope_workspace(_session)
    if workspace_pk:
        try:
            target_workspace = WorkspaceModel.objects.get(pk=workspace_pk)
        except WorkspaceModel.DoesNotExist:
            return (False, {"status": "error", "message": f"Workspace {workspace_pk} not found"})
    
    if not target_workspace:
        return (False, {"status": "error", "message": "No workspace in scope and no workspace_pk provided"})
    
    project = _get_scope_project(_session)
    if project and target_workspace.parent_project != project:
        if target_workspace.parent_project is not None:
            return (False, {"status": "error", "message": "Workspace not in current project scope"})
    
    dashboard_path = target_workspace.get_agentone_dir() / "dashboard" / "index.md"
    
    try:
        if content is not None:
            dashboard_path.parent.mkdir(parents=True, exist_ok=True)
            dashboard_path.write_text(content)
            return (True, {"status": "success", "message": "Dashboard updated", "path": dashboard_path.as_posix()})
        else:
            if dashboard_path.exists():
                content = dashboard_path.read_text()
                return (True, {"status": "success", "content": content, "path": dashboard_path.as_posix()})
            else:
                return (True, {"status": "success", "content": "", "path": dashboard_path.as_posix()})
    except Exception as e:
        return (False, {"status": "error", "message": f"Failed to access dashboard: {e}"})


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


def _get_scope_workspace(session: Any) -> Any | None:
    return _session_workspace(session)