"""Get or update a project's dashboard."""
from __future__ import annotations
from pathlib import Path


def dashboard(_session: Any, project_pk: int | None = None, content: str | None = None, **kwargs) -> tuple[bool, dict]:
    """
    Get or update a project's dashboard.
    
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
    from server.models.project import Project
    
    target_project = _get_scope_project(_session)
    
    if project_pk:
        try:
            target_project = Project.objects.get(pk=project_pk)
        except Project.DoesNotExist:
            return (False, {"status": "error", "message": f"Project {project_pk} not found"})
    
    if not target_project:
        return (False, {"status": "error", "message": "No project in scope and no project_pk provided"})
    
    dashboard_path = target_project.get_agentone_dir() / "dashboard" / "index.md"
    
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