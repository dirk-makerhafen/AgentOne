"""Create a new workspace."""
from __future__ import annotations
from pathlib import Path


def create(_session: Any, name: str, path: str, description: str = "", parent_workspace_pk: int | None = None, **kwargs) -> tuple[bool, dict]:
    """
    Create a new workspace.

    Args:
        name: Workspace name (required)
        path: Filesystem path (must be an existing directory)
        description: Optional description
        parent_workspace_pk: Optional parent workspace for nesting (validated by path)

    Returns:
        A tuple of (success, result).
        On success, result contains:
            - status: "success"
            - workspace: dict with workspace info
        On error, result contains:
            - status: "error"
            - message: str
    """
    from server.models.workspace import WorkspaceModel
    from server.models.project import Project

    if not name or not name.strip():
        return (False, {"status": "error", "message": "Workspace name is required"})
    if not path or not path.strip():
        return (False, {"status": "error", "message": "Workspace path is required"})

    name = name.strip()
    path_obj = Path(path).resolve()

    if not path_obj.exists() or not path_obj.is_dir():
        return (False, {"status": "error", "message": f"Path does not exist or is not a directory: {path}"})

    project = _get_scope_project(_session)

    existing = WorkspaceModel.objects.filter(path=path_obj.as_posix()).first()
    if existing:
        if project and existing.parent_project is None:
            existing.parent_project = project
            existing.save(update_fields=["parent_project"])
        return (False, {"status": "error", "message": f"Workspace already exists at this path: {existing.name}"})

    # Validate parent workspace if provided (by path, not FK)
    if parent_workspace_pk:
        try:
            parent_workspace = WorkspaceModel.objects.get(pk=parent_workspace_pk)
            if project and parent_workspace.parent_project != project:
                if parent_workspace.parent_project is not None:
                    return (False, {"status": "error", "message": "Parent workspace not in current project scope"})
            parent_path = Path(parent_workspace.path).resolve()
            if not path_obj.is_relative_to(parent_path):
                return (False, {"status": "error", "message": "Workspace path must be inside parent workspace path"})
        except WorkspaceModel.DoesNotExist:
            return (False, {"status": "error", "message": f"Parent workspace {parent_workspace_pk} not found"})

    try:
        workspace = WorkspaceModel.objects.create(
            name=name,
            path=path_obj.as_posix(),
            description=description or "",
            parent_project=project,
        )

        agentone_dir = workspace.get_agentone_dir()
        agentone_dir.mkdir(parents=True, exist_ok=True)
        (agentone_dir / "dashboard").mkdir(exist_ok=True)

    except Exception as e:
        return (False, {"status": "error", "message": f"Failed to create workspace: {e}"})

    # Determine if nested by path
    is_nested = False
    if project:
        for w in WorkspaceModel.objects.filter(parent_project=project):
            if w.pk != workspace.pk and workspace.path.startswith(w.path.rstrip("/") + "/"):
                is_nested = True
                break

    return (True, {
        "status": "success",
        "workspace": {
            "pk": workspace.pk,
            "name": workspace.name,
            "path": workspace.path,
            "description": workspace.description or "",
            "is_nested": is_nested,
        }
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