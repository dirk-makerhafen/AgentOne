from __future__ import annotations

from pathlib import Path


def create_project(
    name: str,
    project_path: str = "",
    description: str = "",
    manifest_in_workspace: bool = True,
) -> tuple[bool, dict]:
    '''
    Create a new project (DB-canonical; no ``project.md`` / ``projects.yaml``).

    A project only needs a ``name``. If ``project_path`` is given it is used
    as the project's primary workspace folder: a ``Workspace`` row is created
    and linked as the project's ``main_workspace``. The manifest tree
    (``.agentone/``) is stored either inside that workspace
    (``manifest_in_workspace=True``, the default) or centrally under
    ``~/.agentone/projects/<name>/`` otherwise. With no ``project_path`` the
    manifest always lives in the central location.

    Args:
        name: Short unique name for the project.
        project_path: Optional absolute path of the project's primary
            workspace folder in the filesystem.
        description: Optional project description.
        manifest_in_workspace: When a workspace folder is given, store the
            manifest tree inside it instead of the central location.

    Returns:
        A tuple of (success, result).
        On success, result contains:
            - status: "success"
            - name: str
            - path: str (primary workspace folder, or "")
            - manifest_dir: str
        On error, result contains:
            - status: "error"
            - message: str
    '''
    from runtime.paths import central_project_dir, ensure_private_dir
    from server.models.project import Project
    from server.models.workspace import WorkspaceModel

    description = (description or "").strip()
    workspace_path = (project_path or "").strip()

    try:
        proj, _ = Project.objects.get_or_create(
            name=name, defaults={"description": description},
        )
    except Exception as e:
        return (False, {"status": "error", "message": f"Failed to create project row: {e}"})

    updates: dict = {}
    if description:
        updates["description"] = description

    if workspace_path:
        ws_dir = Path(workspace_path).expanduser()
        try:
            ws_dir.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            return (False, {"status": "error", "message": f"Cannot create folder {workspace_path}: {e}"})
        try:
            ws, ws_created = WorkspaceModel.objects.get_or_create(
                name=f"{name} project root",
                defaults={
                    "path": ws_dir.as_posix(),
                    "description": "project root directory",
                    "parent_project": proj,
                },
            )
            if not ws_created and ws.parent_project_id is None:
                WorkspaceModel.objects.filter(pk=ws.pk).update(parent_project=proj)
        except Exception as e:
            return (False, {"status": "error", "message": f"Failed to create workspace row: {e}"})
        updates["main_workspace"] = ws
        if manifest_in_workspace:
            manifest = ws_dir / ".agentone"
            updates["storage"] = "inline_project"
        else:
            manifest = central_project_dir(name)
            updates["storage"] = "central"
    else:
        manifest = central_project_dir(name)
        updates["storage"] = "central"

    try:
        ensure_private_dir(manifest)
        updates["agentone_dir"] = manifest.as_posix()
        Project.objects.filter(pk=proj.pk).update(**updates)
        proj.refresh_from_db()
    except Exception as e:
        return (False, {"status": "error", "message": f"Failed to save project: {e}"})

    try:
        from registry.loader.load_project_folder import load_scope_dir

        load_scope_dir(manifest, proj)
    except Exception as e:
        return (True, {"status": "created_not_synced", "name": name,
                       "path": proj.path,
                        "manifest_dir": updates["agentone_dir"],
                       "message": f"Project created but sync failed: {e}"})

    return (True, {"status": "success", "name": name,
                   "path": proj.path,
                    "manifest_dir": updates["agentone_dir"]})
