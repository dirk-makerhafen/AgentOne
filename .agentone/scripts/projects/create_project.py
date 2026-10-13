from __future__ import annotations

from pathlib import Path


def create_project(
    project_path: str,
    name: str,
    description: str = "",
) -> tuple[bool, dict]:
    '''
    Create a new project (DB-canonical; no ``project.md`` / ``projects.yaml``).

    Creates the ``.agentone/`` manifest dir, a ``Project`` row
    (``storage=inline_project``) with its default workspace row, then loads
    the scope into the database.

    Args:
        project_path: Absolute path for the new project root directory.
        name: Short unique name for the project.
        description: Optional project description.

    Returns:
        A tuple of (success, result).
        On success, result contains:
            - status: "success"
            - path: str
            - name: str
        On error, result contains:
            - status: "error"
            - message: str
    '''
    root = Path(project_path)
    agentone_dir = root / ".agentone"

    try:
        agentone_dir.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        return (False, {"status": "error", "message": f"Cannot create directory {project_path}: {e}"})

    try:
        from server.models.project import Project
        from server.models.workspace import WorkspaceModel

        proj, _ = Project.objects.get_or_create(
            name=name,
            defaults={
                "path": project_path,
                "description": description.strip(),
                "manifest_dir": agentone_dir.as_posix(),
                "storage": "inline_project",
            },
        )
        ws, ws_created = WorkspaceModel.objects.get_or_create(
            name=f"{name} project root",
            defaults={
                "path": project_path,
                "description": "project root directory",
                "parent_project": proj,
            },
        )
        if ws.parent_project_id is None and ws_created is False:
            WorkspaceModel.objects.filter(pk=ws.pk).update(parent_project=proj)
        if proj.main_workspace_id is None:
            Project.objects.filter(pk=proj.pk).update(main_workspace=ws)
    except Exception as e:
        return (False, {"status": "error", "message": f"Failed to create project row: {e}"})

    try:
        from registry.loader.load_project_folder import load_project_folder

        load_project_folder(project_path)
    except Exception as e:
        return (True, {"status": "created_not_synced", "path": project_path, "name": name,
                       "message": f"Project created but sync failed: {e}"})

    return (True, {"status": "success", "path": project_path, "name": name})
