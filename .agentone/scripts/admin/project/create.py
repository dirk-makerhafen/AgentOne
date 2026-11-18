"""Create a new project."""
from __future__ import annotations
from pathlib import Path


def create(_session: Any, name: str, path: str | None = None, description: str = "", manifest_in_workspace: bool = False, **kwargs) -> tuple[bool, dict]:
    """
    Create a new project.
    
    Args:
        name: Project name (required, globally unique)
        path: Optional filesystem path for the project root
        description: Optional description
        manifest_in_workspace: If True and path is a workspace, put manifests in workspace
    
    Returns:
        A tuple of (success, result).
        On success, result contains:
            - status: "success"
            - project: dict with project info
        On error, result contains:
            - status: "error"
            - message: str
    """
    from server.models.project import Project
    from server.models.workspace import WorkspaceModel
    
    if not name or not name.strip():
        return (False, {"status": "error", "message": "Project name is required"})
    
    name = name.strip()
    
    if Project.objects.filter(name=name).exists():
        return (False, {"status": "error", "message": f"Project '{name}' already exists"})
    
    try:
        project_kwargs = {"name": name, "description": description or ""}
        
        if path:
            path_obj = Path(path).resolve()
            if not path_obj.exists():
                return (False, {"status": "error", "message": f"Path does not exist: {path}"})
            project_kwargs["path"] = path_obj.as_posix()
        
        project = Project.objects.create(**project_kwargs)
        
        if path and manifest_in_workspace:
            workspace = WorkspaceModel.objects.filter(path=path_obj.as_posix()).first()
            if workspace:
                workspace.parent_project = project
                workspace.save(update_fields=["parent_project"])
        
        # Create .agentone directory structure
        agentone_dir = project.get_agentone_dir()
        agentone_dir.mkdir(parents=True, exist_ok=True)
        (agentone_dir / "agents").mkdir(exist_ok=True)
        (agentone_dir / "scripts").mkdir(exist_ok=True)
        (agentone_dir / "skills").mkdir(exist_ok=True)
        (agentone_dir / "streams").mkdir(exist_ok=True)
        (agentone_dir / "sets").mkdir(exist_ok=True)
        (agentone_dir / "dashboard").mkdir(exist_ok=True)
        
        project.refresh_from_disk()
        
    except Exception as e:
        return (False, {"status": "error", "message": f"Failed to create project: {e}"})
    
    return (True, {
        "status": "success",
        "project": {
            "pk": project.pk,
            "name": project.name,
            "path": project.path,
            "agentone_dir": project.agentone_dir,
            "description": project.description or "",
        }
    })


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