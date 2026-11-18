"""Projects admin_tool dispatcher."""
from __future__ import annotations

from typing import Any

from admin_common import _err, _ok, _scope_project, _project_for


def _project_info(project: Any, current: Any = None) -> dict[str, Any]:
    return {
        "pk": project.pk,
        "name": project.name,
        "path": project.path,
        "agentone_dir": project.agentone_dir,
        "description": project.description or "",
        "is_current": current is not None and project.pk == current.pk,
    }


def _projects(_session: Any, action: str, kwargs: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
    from server.models.project import Project

    if action == "list":
        try:
            current = _scope_project(_session)
            projects = [_project_info(p, current) for p in Project.objects.all().order_by("name")]
        except Exception as e:  # pylint: disable=broad-exception-caught
            return _err(f"Failed to list projects: {e}")
        return _ok(projects=projects)

    if action == "stats":
        from server.models.agents.agent import AgentModel
        from server.models.cron import Cronjob
        from server.models.skills.skill import SkillModel
        from server.models.workitems.work_item import WorkItem
        from server.models.workspace import WorkspaceModel

        try:
            current = _scope_project(_session)
            rows = []
            for project in Project.objects.all().order_by("name"):
                rows.append({
                    "project": {"pk": project.pk, "name": project.name, "path": project.path},
                    "agents": AgentModel.objects.filter(parent_project=project).count(),
                    "skills": SkillModel.objects.filter(parent_project=project).count(),
                    "cronjobs": Cronjob.objects.filter(parent_project=project).count(),
                    "workspaces": WorkspaceModel.objects.filter(parent_project=project).count(),
                    "workitems": WorkItem.objects.filter(project=project).count(),
                    "is_current": current is not None and project.pk == current.pk,
                })
        except Exception as e:  # pylint: disable=broad-exception-caught
            return _err(f"Failed to get project stats: {e}")
        return _ok(stats=rows)

    if action == "details":
        from server.models.agents.agent import AgentModel
        from server.models.cron import Cronjob
        from server.models.skills.skill import SkillModel
        from server.models.workitems.work_item import WorkItem
        from server.models.workspace import WorkspaceModel

        project, error = _project_for(_session, kwargs.get("project_pk"))
        if error:
            return _err(error)
        try:
            agents = [
                {"pk": a.pk, "name": a.name, "description": a.description or "",
                 "visibility": a.visibility,
                 "latest_version": a.latest_agent_version.version_number if a.latest_agent_version else None}
                for a in AgentModel.objects.filter(parent_project=project).select_related("latest_agent_version")
            ]
            skills = [
                {"pk": s.pk, "name": s.name, "description": s.description or ""}
                for s in SkillModel.objects.filter(parent_project=project)
            ]
            cronjobs = [
                {"pk": c.pk, "name": c.name, "schedule": c.schedule,
                 "agent_name": c.agent_name, "is_active": c.is_active, "is_archived": c.is_archived}
                for c in Cronjob.objects.filter(parent_project=project)
            ]
            workspaces = [
                {"pk": w.pk, "name": w.name, "path": w.path, "description": w.description or ""}
                for w in WorkspaceModel.objects.filter(parent_project=project)
            ]
            workitems = [
                {"pk": wi.pk, "title": wi.title, "status": wi.status,
                 "assigned_agent": wi.assigned_agent}
                for wi in WorkItem.objects.filter(project=project)
            ]
        except Exception as e:  # pylint: disable=broad-exception-caught
            return _err(f"Failed to get project details: {e}")
        return _ok(
            project=_project_info(project), agents=agents, skills=skills,
            cronjobs=cronjobs, workspaces=workspaces, workitems=workitems,
        )

    if action == "create":
        from pathlib import Path

        from server.models.project import Project
        from server.models.workspace import WorkspaceModel

        name = str(kwargs.get("name") or "").strip()
        if not name:
            return _err("Project name is required")
        if Project.objects.filter(name=name).exists():
            return _err(f"Project '{name}' already exists")
        path = kwargs.get("path")
        try:
            values: dict[str, Any] = {"name": name, "description": kwargs.get("description") or ""}
            path_obj = None
            if path:
                path_obj = Path(path).resolve()
                if not path_obj.exists():
                    return _err(f"Path does not exist: {path}")
                values["path"] = path_obj.as_posix()
            project = Project.objects.create(**values)

            if path_obj and kwargs.get("manifest_in_workspace"):
                workspace = WorkspaceModel.objects.filter(path=path_obj.as_posix()).first()
                if workspace:
                    workspace.parent_project = project
                    workspace.save(update_fields=["parent_project"])

            agentone_dir = project.get_agentone_dir()
            agentone_dir.mkdir(parents=True, exist_ok=True)
            for sub in ("agents", "scripts", "skills", "streams", "sets", "dashboard"):
                (agentone_dir / sub).mkdir(exist_ok=True)
            project.refresh_from_disk()
        except Exception as e:  # pylint: disable=broad-exception-caught
            return _err(f"Failed to create project: {e}")
        return _ok(project=_project_info(project))

    if action == "reload":
        project, error = _project_for(_session, kwargs.get("project_pk"))
        if error:
            return _err(error)
        try:
            details: list = []
            project.refresh_from_disk(details=details)
            project.refresh_from_db()
        except Exception as e:  # pylint: disable=broad-exception-caught
            return _err(f"Failed to reload project: {e}")
        return _ok(project=_project_info(project), details=details)

    if action == "dashboard":
        project, error = _project_for(_session, kwargs.get("project_pk"))
        if error:
            return _err(error)
        dashboard_path = project.get_agentone_dir() / "dashboard" / "index.md"
        content = kwargs.get("content")
        try:
            if content is not None:
                dashboard_path.parent.mkdir(parents=True, exist_ok=True)
                dashboard_path.write_text(content)
                return _ok(message="Dashboard updated", path=dashboard_path.as_posix())
            existing = dashboard_path.read_text() if dashboard_path.exists() else ""
            return _ok(content=existing, path=dashboard_path.as_posix())
        except Exception as e:  # pylint: disable=broad-exception-caught
            return _err(f"Failed to access dashboard: {e}")

    return _err(f"Unknown action '{action}' for scope 'projects'")
