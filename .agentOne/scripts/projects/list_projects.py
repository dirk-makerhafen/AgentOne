from __future__ import annotations

from pathlib import Path

import frontmatter
import yaml
from django.conf import settings


def list_projects() -> tuple[bool, dict]:
    '''
    List all registered projects.

    Reads `.agentone/projects.yaml` and returns each project's path,
    name, and description.

    Returns:
        A tuple of (success, result).
        On success, result contains:
            - status: "success"
            - projects: list of dicts, each with:
                - path: str
                - name: str
                - description: str
        On error, result contains:
            - status: "error"
            - message: str
    '''
    projects_yaml = Path(settings.BASE_DIR) / ".agentone" / "projects.yaml"
    if not projects_yaml.exists():
        return (True, {"projects": []})

    try:
        with open(projects_yaml) as f:
            raw = f.read()
        paths: list[str] = yaml.safe_load(raw) or []
    except Exception as e:
        return (False, {"status": "error", "message": f"Failed to read projects.yaml: {e}"})

    projects = []
    for p in paths:
        project_md = Path(p) / ".agentone" / "project.md"
        name = Path(p).name
        description = ""
        if project_md.exists():
            try:
                post = frontmatter.loads(project_md.read_text(encoding="utf-8"))
                name = post.get("name") or name
                description = (post.content or "").strip()
            except Exception:
                pass
        projects.append({"path": p, "name": name, "description": description})

    return (True, {"status": "success", "projects": projects})
