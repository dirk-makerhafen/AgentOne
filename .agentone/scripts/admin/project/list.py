"""List all projects in current scope."""
from __future__ import annotations

from django.db.models import Q


def list_projects(_session: Any, **kwargs) -> tuple[bool, dict]:
    """
    List all projects visible in the current scope.
    
    In a project-scoped session: shows that project plus global projects.
    In a global session: shows only global projects.
    
    Returns:
        A tuple of (success, result).
        On success, result contains:
            - status: "success"
            - projects: list of dicts, each with:
                - pk: int
                - name: str
                - path: str
                - agentone_dir: str
                - description: str
                - is_current: bool
        On error, result contains:
            - status: "error"
            - message: str
    """
    from server.models.project import Project
    
    project = _get_scope_project(_session)
    
    try:
        # All projects are top-level; no parent_project on Project model
        projects_qs = Project.objects.all().order_by("name")
        
        projects = [
            {
                "pk": p.pk,
                "name": p.name,
                "path": p.path,
                "agentone_dir": p.agentone_dir,
                "description": p.description or "",
                "is_current": p.pk == project.pk if project else False,
            }
            for p in projects_qs
        ]
    except Exception as e:
        return (False, {"status": "error", "message": f"Failed to list projects: {e}"})
    
    return (True, {"status": "success", "projects": projects})


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