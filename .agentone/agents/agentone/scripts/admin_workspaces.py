"""Workspaces admin_tool dispatcher."""
from __future__ import annotations

from typing import Any

from admin_common import _err, _ok, _scope_project, _scope_workspace, _project_for, _workspace_for


def _workspace_paths(workspaces: list) -> dict[int, str]:
    """Normalised path by pk, for path-nesting checks."""
    from pathlib import Path

    return {ws.pk: Path(ws.path).resolve().as_posix() for ws in workspaces}


def _is_nested(workspace: Any, paths: dict[int, str]) -> bool:
    mine = paths.get(workspace.pk, "")
    return any(
        other != workspace.pk and paths.get(other, "") and mine.startswith(paths[other].rstrip("/") + "/")
        for other in paths
    )


def _workspace_info(workspace: Any, paths: dict[int, str], current: Any = None,
                    session_counts: dict[int, int] | None = None) -> dict[str, Any]:
    parent_pk = None
    for other, path in paths.items():
        if other != workspace.pk and path and paths.get(workspace.pk, "").startswith(path.rstrip("/") + "/"):
            parent_pk = other
            break
    return {
        "pk": workspace.pk,
        "name": workspace.name or "",
        "path": workspace.path or "",
        "description": workspace.description or "",
        "is_nested": parent_pk is not None,
        "parent_workspace_pk": parent_pk,
        "is_current": current is not None and workspace.pk == current.pk,
        "session_count": (session_counts or {}).get(workspace.pk, 0),
    }


def _scoped_workspaces(session: Any) -> list:
    from server.models.workspace import WorkspaceModel

    project = _scope_project(session)
    if project is not None:
        return list(WorkspaceModel.objects.filter(parent_project=project).order_by("name"))
    return list(WorkspaceModel.objects.filter(parent_project__isnull=True).order_by("name"))


def _session_counts() -> dict[int, int]:
    from django.db.models import Count

    from server.models.sessions.session import SessionModel

    counts: dict[int, int] = {}
    try:
        rows = (
            SessionModel.objects.filter(latest_session_version__workspace__isnull=False)
            .values("latest_session_version__workspace")
            .annotate(n=Count("pk"))
        )
        for row in rows:
            counts[row["latest_session_version__workspace"]] = row["n"]
    except Exception:  # pylint: disable=broad-exception-caught
        pass
    return counts


def _workspaces(_session: Any, action: str, kwargs: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
    from server.models.workspace import WorkspaceModel

    if action == "list":
        try:
            all_ws = _scoped_workspaces(_session)
            paths = _workspace_paths(all_ws)
            counts = _session_counts()
            workspaces = [
                _workspace_info(ws, paths, _scope_workspace(_session), counts)
                for ws in all_ws
            ]
            if not kwargs.get("include_nested", True):
                workspaces = [ws for ws in workspaces if not ws["is_nested"]]
        except Exception as e:  # pylint: disable=broad-exception-caught
            return _err(f"Failed to list workspaces: {e}")
        return _ok(workspaces=workspaces)

    if action == "stats":
        try:
            all_ws = _scoped_workspaces(_session)
            paths = _workspace_paths(all_ws)
            nested = sum(1 for ws in all_ws if _is_nested(ws, paths))
            project = _scope_project(_session)
            stats = {
                "total": len(all_ws),
                "top_level": len(all_ws) - nested,
                "nested": nested,
                "scope": "project" if project else "global",
                "project_name": project.name if project else None,
            }
        except Exception as e:  # pylint: disable=broad-exception-caught
            return _err(f"Failed to get workspace stats: {e}")
        return _ok(stats=stats)

    if action == "details":
        from pathlib import Path

        workspace, error = _workspace_for(
            _session,
            kwargs.get("workspace_pk"),
            kwargs.get("workspace_name") or kwargs.get("name"),
        )
        if error:
            return _err(error)
        try:
            project = _scope_project(_session)
            siblings = _scoped_workspaces(_session)
            paths = _workspace_paths(siblings)
            subworkspaces = [
                {"pk": w.pk, "name": w.name or "", "path": w.path or "", "description": w.description or ""}
                for w in siblings
                if w.pk != workspace.pk
                and paths.get(w.pk, "").startswith(paths.get(workspace.pk, "").rstrip("/") + "/")
            ]
            sessions = []
            for sv in workspace.related_session_versions.all():
                sess = sv.session
                if sess and sess.is_active:
                    sessions.append({
                        "pk": sess.pk,
                        "agent_name": sv.agent.name if sv.agent else "unknown",
                        "description": sess.description or "",
                    })
            scoped_agents: list[dict[str, Any]] = []
            scoped_skills: list[dict[str, Any]] = []
            scoped_crons: list[dict[str, Any]] = []
            if project is not None:
                from runtime.agents.agents import Agents
                from runtime.cron.crons import Cronjobs
                from runtime.skill.skills import Skills

                for s in Skills(parent_workspace=workspace).all():
                    scoped_skills.append({
                        "pk": s.pk,
                        "name": s.name,
                        "description": s.latest_skill_version.description if s.latest_skill_version else "",
                    })
                for a in Agents(parent_workspace=workspace).all():
                    version = a.latest_agent_version
                    scoped_agents.append({
                        "pk": a.pk, "name": a.name,
                        "description": version.description if version else "",
                        "visibility": version.visibility if version else "",
                    })
                for c in Cronjobs(parent_workspace=workspace).all():
                    scoped_crons.append({
                        "pk": c.pk, "name": c.name, "schedule": c.schedule,
                        "agent_name": c.agent_name, "is_active": c.is_active,
                    })
        except Exception as e:  # pylint: disable=broad-exception-caught
            return _err(f"Failed to get workspace details: {e}")
        info = _workspace_info(workspace, paths)
        return _ok(
            workspace=info,
            subworkspaces=subworkspaces,
            sessions=sessions,
            skills=scoped_skills,
            agents=scoped_agents,
            cronjobs=scoped_crons,
        )

    if action == "create":
        from pathlib import Path

        name = str(kwargs.get("name") or "").strip()
        path = str(kwargs.get("path") or "").strip()
        if not name:
            return _err("Workspace name is required")
        if not path:
            return _err("Workspace path is required")
        path_obj = Path(path).resolve()
        if not path_obj.is_dir():
            return _err(f"Path does not exist or is not a directory: {path}")
        project = _scope_project(_session)
        existing = WorkspaceModel.objects.filter(path=path_obj.as_posix()).first()
        if existing:
            if project is not None and existing.parent_project is None:
                existing.parent_project = project
                existing.save(update_fields=["parent_project"])
            return _err(f"Workspace already exists at this path: {existing.name}")
        parent_pk = kwargs.get("parent_workspace_pk")
        if parent_pk:
            parent = WorkspaceModel.objects.filter(pk=parent_pk).first()
            if parent is None:
                return _err(f"Parent workspace {parent_pk} not found")
            if project is not None and parent.parent_project not in (None, project):
                return _err("Parent workspace is outside the current project scope")
            if not path_obj.is_relative_to(Path(parent.path).resolve()):
                return _err("Workspace path must be inside the parent workspace path")
        try:
            workspace = WorkspaceModel.objects.create(
                name=name,
                path=path_obj.as_posix(),
                description=kwargs.get("description") or "",
                parent_project=project,
            )
            agentone_dir = workspace.get_agentone_dir()
            agentone_dir.mkdir(parents=True, exist_ok=True)
            (agentone_dir / "dashboard").mkdir(exist_ok=True)
        except Exception as e:  # pylint: disable=broad-exception-caught
            return _err(f"Failed to create workspace: {e}")
        paths = _workspace_paths(_scoped_workspaces(_session))
        info = _workspace_info(workspace, paths)
        info.pop("session_count", None)
        return _ok(workspace=info)

    if action == "rename":
        workspace, error = _workspace_for(_session, kwargs.get("workspace_pk"), kwargs.get("workspace_name"))
        if error:
            return _err(error)
        name = str(kwargs.get("name") or "").strip()
        if not name:
            return _err("New name is required")
        try:
            workspace.name = name
            workspace.save(update_fields=["name"])
        except Exception as e:  # pylint: disable=broad-exception-caught
            return _err(f"Failed to rename workspace: {e}")
        return _ok(workspace={"pk": workspace.pk, "name": workspace.name, "path": workspace.path})

    if action == "update":
        workspace, error = _workspace_for(_session, kwargs.get("workspace_pk"), kwargs.get("workspace_name"))
        if error:
            return _err(error)
        description = kwargs.get("description")
        if description is None:
            return _err("Nothing to change; pass description")
        try:
            workspace.description = description
            workspace.save(update_fields=["description"])
        except Exception as e:  # pylint: disable=broad-exception-caught
            return _err(f"Failed to update workspace: {e}")
        return _ok(workspace={"pk": workspace.pk, "name": workspace.name,
                              "path": workspace.path, "description": workspace.description or ""})

    if action == "dashboard":
        workspace, error = _workspace_for(
            _session,
            kwargs.get("workspace_pk"),
            kwargs.get("workspace_name") or kwargs.get("name"),
        )
        if error:
            return _err(error)
        dashboard_path = workspace.get_agentone_dir() / "dashboard" / "index.md"
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

    if action == "create_chat":
        from datetime import datetime

        from server.models.agents.agent import AgentModel
        from server.models.enums.session_enums import SessionType
        from server.models.sessions.session import SessionModel
        from server.models.sessions.session_version import SessionVersionModel

        workspace, error = _workspace_for(
            _session,
            kwargs.get("workspace_pk"),
            kwargs.get("workspace_name") or kwargs.get("name"),
        )
        if error:
            return _err(error)
        agent_name = str(kwargs.get("agent_name") or "general-chat")
        agent = AgentModel.objects.filter(name=agent_name).first()
        if agent is None:
            return _err(f"Agent '{agent_name}' not found")
        title = kwargs.get("title") or f"{workspace.name or 'chat'} - {agent_name} - {datetime.now():%Y-%m-%d %H:%M}"
        try:
            session = SessionModel.objects.create(
                name=title,
                parent_project=_scope_project(_session),
                session_type=SessionType.SESSION,
                is_active=True,
            )
            SessionVersionModel.objects.create(
                session=session, agent=agent, workspace=workspace,
                version_number=0, description=title,
            )
            session.latest_session_version = session.related_session_versions.first()
            session.save(update_fields=["latest_session_version"])
        except Exception as e:  # pylint: disable=broad-exception-caught
            return _err(f"Failed to create chat session: {e}")
        return _ok(session={"pk": session.pk, "name": session.name or title,
                            "agent": agent_name, "workspace": workspace.name or workspace.path})

    return _err(f"Unknown action '{action}' for scope 'workspaces'")
