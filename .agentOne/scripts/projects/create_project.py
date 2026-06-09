from __future__ import annotations

from pathlib import Path

import yaml
from django.conf import settings


def create_project(
    project_path: str,
    name: str,
    description: str = "",
    workspaces: list | None = None,
) -> tuple[bool, dict]:
    '''
    Create a new project directory with ``.agentone/project.md`` and
    register it in ``.agentone/projects.yaml``.

    Does NOT create an ``.agentone/`` directory — that is created lazily
    by the projectmanager when project-specific agents or configs are added.

    After creating the files, runs ``reload_all`` to sync into the database.

    Args:
        project_path: Absolute path for the new project root directory.
        name: Short unique name for the project.
        description: Optional project description.
        workspaces: Optional list of workspace dicts, each with:
            - name: str (required)
            - path: str (required, absolute or relative to project root)
            - description: str (optional)

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

    frontmatter_data: dict = {"name": name}
    if workspaces:
        frontmatter_data["workspaces"] = workspaces

    project_md_lines = [
        "---",
        yaml.dump(frontmatter_data, default_flow_style=False).strip(),
        "---",
    ]
    if description:
        project_md_lines.append("")
        project_md_lines.append(description.strip())

    project_md_path = agentone_dir / "project.md"
    project_md_path.write_text("\n".join(project_md_lines) + "\n", encoding="utf-8")

    projects_yaml = Path(settings.BASE_DIR) / ".agentone" / "projects.yaml"
    try:
        if projects_yaml.exists():
            existing = yaml.safe_load(projects_yaml.read_text(encoding="utf-8")) or []
        else:
            existing = []
    except Exception as e:
        return (False, {"status": "error", "message": f"Failed to read projects.yaml: {e}"})

    if project_path not in existing:
        existing.append(project_path)

    try:
        projects_yaml.write_text(
            yaml.dump(existing, default_flow_style=False),
            encoding="utf-8",
        )
    except OSError as e:
        return (False, {"status": "error", "message": f"Failed to write projects.yaml: {e}"})

    try:
        from django.core.management import call_command
        call_command("reload_all", project_path)
    except Exception as e:
        return (True, {"status": "created_not_synced", "path": project_path, "name": name,
                       "message": f"Project files created but reload_all failed: {e}"})

    return (True, {"status": "success", "path": project_path, "name": name})
