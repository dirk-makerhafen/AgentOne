"""List all workspaces in current scope."""
from __future__ import annotations


def list_workspaces(_session: Any, include_nested: bool = True, **kwargs) -> tuple[bool, dict]:
    """
    List all workspaces in the current scope.

    In a project-scoped session: shows that project's workspaces.
    In a global session: shows all global workspaces.

    Args:
        include_nested: Include sub-workspaces (default: True)
        (Note: nesting is determined by path prefix, not a parent_workspace FK)

    Returns:
        A tuple of (success, result).
        On success, result contains:
            - status: "success"
            - workspaces: list of workspace dicts
        On error, result contains:
            - status: "error"
            - message: str
    """
    from server.models.workspace import WorkspaceModel
    from pathlib import Path

    project = _get_scope_project(_session)
    current_workspace = _get_scope_workspace(_session)

    try:
        if project:
            workspaces_qs = WorkspaceModel.objects.filter(parent_project=project)
        else:
            workspaces_qs = WorkspaceModel.objects.filter(parent_project__isnull=True)

        # Get all workspaces and compute nesting via path
        all_workspaces = list(workspaces_qs.order_by("name"))
        workspaces = []
        for w in all_workspaces:
            # Check if this workspace is nested under another in the same scope
            is_nested = False
            parent_workspace_pk = None
            for other in all_workspaces:
                if other.pk != w.pk and w.path.startswith(other.path.rstrip("/") + "/"):
                    is_nested = True
                    parent_workspace_pk = other.pk
                    break

            if not include_nested and is_nested:
                continue

            # Count active sessions via session versions
            session_count = 0
            try:
                for sv in w.related_session_versions.all():
                    if sv.session and sv.session.is_active:
                        session_count += 1
            except Exception:
                pass

            workspaces.append({
                "pk": w.pk,
                "name": w.name or "",
                "path": w.path or "",
                "description": w.description or "",
                "is_nested": is_nested,
                "parent_workspace_pk": parent_workspace_pk,
                "is_current": w.pk == current_workspace.pk if current_workspace else False,
                "session_count": session_count,
            })
    except Exception as e:
        return (False, {"status": "error", "message": f"Failed to list workspaces: {e}"})

    return (True, {"status": "success", "workspaces": workspaces})


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