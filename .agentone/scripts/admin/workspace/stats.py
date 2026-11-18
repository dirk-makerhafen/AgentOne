"""Get workspace collection statistics."""
from __future__ import annotations


def stats(_session: Any, **kwargs) -> tuple[bool, dict]:
    """
    Get workspace collection statistics.

    Returns:
        A tuple of (success, result).
        On success, result contains:
            - status: "success"
            - stats: dict with total, top_level, nested counts
        On error, result contains:
            - status: "error"
            - message: str
    """
    from server.models.workspace import WorkspaceModel
    from pathlib import Path

    project = _get_scope_project(_session)

    try:
        if project:
            workspaces_qs = WorkspaceModel.objects.filter(parent_project=project)
        else:
            workspaces_qs = WorkspaceModel.objects.filter(parent_project__isnull=True)

        # Compute nesting via path
        all_workspaces = list(workspaces_qs)
        total = len(all_workspaces)
        top_level = 0
        for w in all_workspaces:
            is_nested = False
            for other in all_workspaces:
                if other.pk != w.pk and w.path.startswith(other.path.rstrip("/") + "/"):
                    is_nested = True
                    break
            if not is_nested:
                top_level += 1
        nested = total - top_level

        stats = {
            "total": total,
            "top_level": top_level,
            "nested": nested,
            "scope": "project" if project else "global",
            "project_name": project.name if project else None,
        }
    except Exception as e:
        return (False, {"status": "error", "message": f"Failed to get workspace stats: {e}"})

    return (True, {"status": "success", "stats": stats})


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