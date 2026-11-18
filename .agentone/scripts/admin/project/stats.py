"""Get cross-project statistics."""
from __future__ import annotations


def stats(_session: Any, **kwargs) -> tuple[bool, dict]:
    """
    Get cross-project statistics including agent, skill, cronjob, workspace, and workitem counts.
    
    Returns:
        A tuple of (success, result).
        On success, result contains:
            - status: "success"
            - stats: list of dicts per project with counts
        On error, result contains:
            - status: "error"
            - message: str
    """
    from server.models.project import Project
    from server.models.agents.agent import AgentModel
    from server.models.skills.skill import SkillModel
    from server.models.cron import Cronjob as CronJobModel
    from server.models.workspace import WorkspaceModel
    from server.models.workitems.work_item import WorkItem as WorkItemModel
    from django.db.models import Q
    
    project = _get_scope_project(_session)
    
    try:
        projects_qs = Project.objects.all()
        
        stats = []
        for p in projects_qs.order_by("name"):
            stats.append({
                "project": {"pk": p.pk, "name": p.name, "path": p.path},
                "agents": AgentModel.objects.filter(parent_project=p).count(),
                "skills": SkillModel.objects.filter(parent_project=p).count(),
                "cronjobs": CronJobModel.objects.filter(parent_project=p).count(),
                "workspaces": WorkspaceModel.objects.filter(parent_project=p).count(),
                "workitems": WorkItemModel.objects.filter(project=p).count(),
                "is_current": p.pk == project.pk if project else False,
            })
    except Exception as e:
        return (False, {"status": "error", "message": f"Failed to get project stats: {e}"})
    
    return (True, {"status": "success", "stats": stats})


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