"""Get detailed information about a workspace."""
from __future__ import annotations


def details(_session: Any, workspace_pk: int | None = None, **kwargs) -> tuple[bool, dict]:
    """
    Get detailed information about a specific workspace.

    If workspace_pk is not provided, uses the current session's workspace.

    Returns:
        A tuple of (success, result).
        On success, result contains:
            - status: "success"
            - workspace: dict with workspace info
            - subworkspaces: list of child workspaces
            - sessions: list of active sessions
            - skills: list of skills in scope
            - agents: list of agents in scope
            - cronjobs: list of cronjobs in scope
        On error, result contains:
            - status: "error"
            - message: str
    """
    from server.models.workspace import WorkspaceModel
    from server.models.agents.agent import AgentModel
    from server.models.skills.skill import SkillModel
    from server.models.cron import Cronjob as CronJobModel
    from server.models.workitems.work_item import WorkItem as WorkItemModel
    from server.models.sessions.session import SessionModel
    from pathlib import Path

    current_workspace = _get_scope_workspace(_session)
    project = _get_scope_project(_session)

    target_workspace = current_workspace
    if workspace_pk:
        try:
            target_workspace = WorkspaceModel.objects.get(pk=workspace_pk)
        except WorkspaceModel.DoesNotExist:
            return (False, {"status": "error", "message": f"Workspace {workspace_pk} not found"})

    if not target_workspace:
        return (False, {"status": "error", "message": "No workspace in scope and no workspace_pk provided"})

    if project and target_workspace.parent_project != project:
        if target_workspace.parent_project is not None:
            return (False, {"status": "error", "message": "Workspace not in current project scope"})

    try:
        # Find subworkspaces via path prefix
        subworkspaces = []
        target_path = target_workspace.path.rstrip("/") + "/"
        for w in WorkspaceModel.objects.filter(parent_project=target_workspace.parent_project):
            if w.pk != target_workspace.pk and w.path.startswith(target_path):
                subworkspaces.append({
                    "pk": w.pk,
                    "name": w.name or "",
                    "path": w.path or "",
                    "description": w.description or "",
                })

        sessions = []
        for sv in target_workspace.related_session_versions.all():
            s = sv.session
            if s and s.is_active:
                sessions.append({
                    "pk": s.pk,
                    "agent_name": sv.agent.name if sv.agent else "unknown",
                    "is_active": s.is_active,
                    "description": s.description or "",
                })

        ws_project = target_workspace.parent_project

        skills = []
        if ws_project:
            from runtime.skill.skills import Skills
            skills_rt = Skills(parent_workspace=target_workspace)
            for s in skills_rt.all():
                desc = s.latest_skill_version.description if s.latest_skill_version else ""
                skills.append({
                    "pk": s.pk,
                    "name": s.name,
                    "description": desc or "",
                })

        agents = []
        if ws_project:
            from runtime.agents.agents import Agents
            agents_rt = Agents(parent_workspace=target_workspace)
            for a in agents_rt.all():
                desc = a.latest_agent_version.description if a.latest_agent_version else ""
                agents.append({
                    "pk": a.pk,
                    "name": a.name,
                    "description": desc or "",
                    "visibility": a.latest_agent_version.visibility if a.latest_agent_version else "",
                })

        cronjobs = []
        if ws_project:
            from runtime.cron.crons import Cronjobs
            cronjobs_rt = Cronjobs(parent_workspace=target_workspace)
            for c in cronjobs_rt.all():
                cronjobs.append({
                    "pk": c.pk,
                    "name": c.name,
                    "schedule": c.schedule,
                    "agent_name": c.agent_name,
                    "is_active": c.is_active,
                })

    except Exception as e:
        return (False, {"status": "error", "message": f"Failed to get workspace details: {e}"})

    # Determine if this workspace is nested
    is_nested = False
    parent_workspace_pk = None
    if target_workspace.parent_project:
        for w in WorkspaceModel.objects.filter(parent_project=target_workspace.parent_project):
            if w.pk != target_workspace.pk and target_workspace.path.startswith(w.path.rstrip("/") + "/"):
                is_nested = True
                parent_workspace_pk = w.pk
                break

    return (True, {
        "status": "success",
        "workspace": {
            "pk": target_workspace.pk,
            "name": target_workspace.name or "",
            "path": target_workspace.path or "",
            "description": target_workspace.description or "",
            "is_nested": is_nested,
            "parent_workspace_pk": parent_workspace_pk,
        },
        "subworkspaces": subworkspaces,
        "sessions": sessions,
        "skills": skills,
        "agents": agents,
        "cronjobs": cronjobs,
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


def _get_scope_workspace(session: Any) -> Any | None:
    return _session_workspace(session)