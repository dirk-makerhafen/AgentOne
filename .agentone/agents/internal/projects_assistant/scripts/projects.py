"""Project collection tools for the projects_assistant agent.

Projects are global entities, so these tools are NOT project-scoped:
they see every registered project. Describing one project in depth and
collection health belong here; creating/listing/reloading projects reuses
the global ``projects.*`` tools (composed in the agent's tool list);
administering ONE project's ``.agentone/`` directory belongs to
``project_assistant`` (via ``call_assistant``). Every tool returns a
``(bool, dict)`` tuple.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from runtime.session.session import Session


def _project_counts(project) -> dict[str, int]:
    """Count the records owned by one project (best effort per model)."""
    from runtime.project.project import Project as ProjectScope

    try:
        return ProjectScope(project).counts()
    except Exception:
        return {}


def _project_workspaces(project) -> list[dict[str, str]]:
    """Workspaces linked to the project (DB-canonical via parent_project FK)."""
    try:
        from runtime.workspace.workspaces import Workspaces

        return [
            {"name": w.name or "", "path": w.path or ""}
            for w in Workspaces(parent_project=project).all()
        ]
    except Exception:
        return []


def _resolve_project(_session: Session, name: str):
    """Find one project by name, defaulting to the session's project."""
    from server.models.project import Project

    name = (name or "").strip()
    if not name:
        project = _session.get_project()
        if project is None:
            return False, {"status": "error", "message": "No project name given and this session belongs to no project."}
        return True, project
    project = Project.objects.filter(name=name).first()
    if project is None:
        return False, {"status": "error", "message": f"No project named '{name}'."}
    return True, project


def project_details(_session: Session, name: str = "") -> tuple[bool, dict[str, Any]]:
    """Show ONE project in depth: record, path, declared workspaces, and owned-record counts.

    Defaults to the calling session's project when no name is given —
    use this to answer "what lives in this project?".

    Args:
        name: Project name (optional; defaults to the session's project).

    Returns:
        ``(True, {"status": "success", project..., "counts": {...},
        "workspaces": [...]})`` or ``(False, {"status": "error", ...})``.
    """
    ok, project = _resolve_project(_session, name)
    if not ok:
        return False, project
    try:
        path_exists = Path(project.path).is_dir() if project.path else False
    except Exception:
        path_exists = False
    return True, {
        "status": "success",
        "id": project.pk,
        "name": project.name,
        "description": project.description or "",
        "path": project.path or "",
        "path_exists": path_exists,
        "counts": _project_counts(project),
        "workspaces": _project_workspaces(project),
    }


def projects_stats(_session: Session) -> tuple[bool, dict[str, Any]]:
    """Report health for EVERY registered project: owned-record counts each.

    Marks the calling session's project as current. Use this for the
    cross-project overview ("which project holds what?").

    Returns:
        ``(True, {"status": "success", "projects": [...], "count": int})``
        or ``(False, {"status": "error", "message": ...})``.
    """
    from server.models.project import Project

    try:
        all_projects = list(Project.objects.all().order_by("name"))
    except Exception as e:
        return False, {"status": "error", "message": f"Could not list projects: {e}"}
    current = _session.get_project()
    current_pk = current.pk if current is not None else None
    rows = []
    for project in all_projects:
        rows.append({
            "id": project.pk,
            "name": project.name,
            "path": project.path or "",
            "current": project.pk == current_pk,
            "counts": _project_counts(project),
        })
    return True, {"status": "success", "projects": rows, "count": len(rows)}
