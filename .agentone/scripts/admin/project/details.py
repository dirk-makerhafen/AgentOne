"""Get detailed information about a project."""
from __future__ import annotations


def details(_session: Any, project_pk: int | None = None, **kwargs) -> tuple[bool, dict]:
    """
    Get detailed information about a specific project.
    
    If project_pk is not provided, uses the current session's project.
    
    Returns:
        A tuple of (success, result).
        On success, result contains:
            - status: "success"
            - project: dict with project info
            - agents: list of owned agents
            - skills: list of owned skills
            - cronjobs: list of owned cronjobs
            - workspaces: list of owned workspaces
            - workitems: list of owned workitems
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
    
    target_project = _get_scope_project(_session)
    
    if project_pk:
        try:
            target_project = Project.objects.get(pk=project_pk)
        except Project.DoesNotExist:
            return (False, {"status": "error", "message": f"Project {project_pk} not found"})
    
    if not target_project:
        return (False, {"status": "error", "message": "No project in scope and no project_pk provided"})
    
    try:
        agents = [
            {
                "pk": a.pk,
                "name": a.name,
                "description": a.description or "",
                "visibility": a.visibility,
                "latest_version": a.latest_agent_version.version_number if a.latest_agent_version else None,
            }
            for a in AgentModel.objects.filter(parent_project=target_project).select_related("latest_agent_version")
        ]
        
        skills = [
            {
                "pk": s.pk,
                "name": s.name,
                "description": s.description or "",
            }
            for s in SkillModel.objects.filter(parent_project=target_project)
        ]
        
        cronjobs = [
            {
                "pk": c.pk,
                "name": c.name,
                "schedule": c.schedule,
                "agent_name": c.agent_name,
                "is_active": c.is_active,
                "is_archived": c.is_archived,
            }
            for c in CronJobModel.objects.filter(parent_project=target_project)
        ]
        
        workspaces = [
            {
                "pk": w.pk,
                "name": w.name,
                "path": w.path,
                "description": w.description or "",
            }
            for w in WorkspaceModel.objects.filter(parent_project=target_project)
        ]
        
        workitems = [
            {
                "pk": wi.pk,
                "title": wi.title,
                "status": wi.status,
                "assigned_agent": wi.assigned_agent,
            }
            for wi in WorkItemModel.objects.filter(project=target_project)
        ]
        
    except Exception as e:
        return (False, {"status": "error", "message": f"Failed to get project details: {e}"})
    
    return (True, {
        "status": "success",
        "project": {
            "pk": target_project.pk,
            "name": target_project.name,
            "path": target_project.path,
            "agentone_dir": target_project.agentone_dir,
            "description": target_project.description or "",
        },
        "agents": agents,
        "skills": skills,
        "cronjobs": cronjobs,
        "workspaces": workspaces,
        "workitems": workitems,
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