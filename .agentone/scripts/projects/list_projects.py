from __future__ import annotations


def list_projects() -> tuple[bool, dict]:
    '''
    List all registered projects (DB-canonical).

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
    try:
        from server.models.project import Project

        projects = [
            {"path": p.path, "name": p.name, "description": p.description or ""}
            for p in Project.objects.all().order_by("name")
        ]
    except Exception as e:
        return (False, {"status": "error", "message": f"Failed to list projects: {e}"})

    return (True, {"status": "success", "projects": projects})
