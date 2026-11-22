"""Projects admin_tool dispatcher."""
from __future__ import annotations

from typing import Any

from admin_common import _err, _ok, _scope_project, _project_for


def _as_bool(value: Any, default: bool = True) -> bool:
    """LLM calls may send booleans as strings; treat them consistently."""
    if value is None:
        return default
    if isinstance(value, str):
        return value.strip().lower() not in ("", "0", "false", "no", "off", "none")
    return bool(value)


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

        project, error = _project_for(
            _session,
            kwargs.get("project_pk"),
            kwargs.get("project_name") or kwargs.get("name"),
        )
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

        from runtime.paths import central_project_dir, ensure_private_dir
        from server.models.project import Project
        from server.models.workspace import WorkspaceModel

        name = str(kwargs.get("name") or "").strip()
        if not name:
            return _err("Project name is required")
        if Project.objects.filter(name=name).exists():
            return _err(f"Project '{name}' already exists")
        # ``path`` is the canonical kwarg; ``project_path`` is accepted for
        # callers porting from the old global scripts/projects tool.
        raw_path = str(kwargs.get("path") or kwargs.get("project_path") or "").strip()
        path_obj = Path(raw_path).expanduser().resolve() if raw_path else None
        details: list = []
        try:
            if path_obj is not None:
                path_obj.mkdir(parents=True, exist_ok=True)

            project = Project.objects.create(
                name=name, description=str(kwargs.get("description") or "").strip(),
            )
            # Place the manifest tree before creating the workspace: its default
            # agentone_dir is derived from the owning project.
            manifest = (
                path_obj / ".agentone"
                if path_obj is not None and _as_bool(kwargs.get("manifest_in_workspace"), True)
                else central_project_dir(name)
            )
            ensure_private_dir(manifest)
            for sub in ("agents", "scripts", "skills", "streams", "sets", "dashboard"):
                (manifest / sub).mkdir(exist_ok=True)
            project.atomic_update(agentone_dir=manifest.as_posix())

            if path_obj is not None:
                workspace = WorkspaceModel.objects.filter(path=path_obj.as_posix()).first()
                if workspace is None:
                    workspace = WorkspaceModel.objects.create(
                        name=str(kwargs.get("workspace_name") or f"{name} project root"),
                        path=path_obj.as_posix(),
                        description="project root directory",
                        parent_project=project,
                    )
                elif workspace.parent_project_id is None:
                    workspace.atomic_update(parent_project=project)
                project.atomic_update(main_workspace=workspace)

            project.refresh_from_disk(details=details)
            project.refresh_from_db()
        except Exception as e:  # pylint: disable=broad-exception-caught
            return _err(f"Failed to create project: {e}")
        return _ok(project=_project_info(project), details=details)

    if action == "reload":
        project, error = _project_for(
            _session,
            kwargs.get("project_pk"),
            kwargs.get("project_name") or kwargs.get("name"),
        )
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
        project, error = _project_for(
            _session,
            kwargs.get("project_pk"),
            kwargs.get("project_name") or kwargs.get("name"),
        )
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
