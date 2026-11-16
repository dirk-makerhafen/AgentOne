"""Shared primary-workspace picker logic for the project create/edit forms.

The picker is a ``<select>`` whose value is one of:

* ``""``       — no primary workspace (manifests stored centrally)
* ``"<pk>"``   — an existing :class:`WorkspaceModel` primary key
* ``"new"``    — create/reuse a workspace from a folder path

Both the create view and the inline project edit view use these helpers so
selecting an existing workspace by path never spawns a duplicate row.
"""
from __future__ import annotations

from pathlib import Path


def workspace_options(project=None) -> list[dict]:
    """Return picker options for *project* (its own workspaces listed first).

    Each option is ``{"value": "<pk>", "label": "<name> — <path>"}``. Errors
    (e.g. DB unavailable) degrade to an empty list.
    """
    try:
        from server.models.workspace import WorkspaceModel

        rows = list(WorkspaceModel.objects.all())
    except Exception:  # pylint: disable=broad-exception-caught
        return []

    project_pk = getattr(project, "pk", None)

    def _sort_key(ws):
        owner = getattr(ws, "parent_project", None)
        owned = 0 if (project_pk is not None and getattr(owner, "pk", None) == project_pk) else 1
        return (owned, (ws.name or ws.path or "").lower())

    options: list[dict] = []
    for ws in sorted(rows, key=_sort_key):
        label = ws.name or ws.path or f"Workspace {ws.pk}"
        if ws.path and ws.path != label:
            label = f"{label} — {ws.path}"
        owner = getattr(ws, "parent_project", None)
        if owner is not None and getattr(owner, "pk", None) != project_pk:
            label = f"{label}  ({owner.name})"
        options.append({"value": str(ws.pk), "label": label})
    return options


def resolve_primary_workspace(ref, new_path, project, project_name):
    """Resolve a picker selection to a workspace row.

    Returns ``(workspace_or_None, error_message_or_None)``. When *ref* is
    ``"new"`` an existing workspace with the same path is reused instead of
    creating a duplicate.
    """
    from server.models.workspace import WorkspaceModel

    ref = (ref or "").strip()
    if ref == "":
        return None, None

    if ref == "new":
        path = (new_path or "").strip()
        if not path:
            return None, "Enter a folder path for the new workspace."
        ws_dir = Path(path).expanduser()
        try:
            ws_dir.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            return None, f"Cannot create workspace folder {path}: {e}"
        target = ws_dir.as_posix()
        existing = WorkspaceModel.objects.filter(path=target).first()
        if existing is not None:
            _adopt(existing, project)
            return existing, None
        try:
            ws = WorkspaceModel.objects.create(
                name=f"{project_name} project root",
                path=target,
                description="project root directory",
                parent_project=project,
            )
            return ws, None
        except Exception as e:  # pylint: disable=broad-exception-caught
            return None, f"Failed to create workspace: {e}"

    try:
        pk = int(ref)
    except (TypeError, ValueError):
        return None, "Invalid workspace selection."
    ws = WorkspaceModel.objects.filter(pk=pk).first()
    if ws is None:
        return None, "Selected workspace no longer exists."
    _adopt(ws, project)
    return ws, None


def _adopt(ws, project) -> None:
    """Attach an unowned workspace to *project* (never steal another's)."""
    from server.models.workspace import WorkspaceModel

    if project is not None and ws.parent_project_id is None:
        WorkspaceModel.objects.filter(pk=ws.pk).update(parent_project=project)
        ws.parent_project = project
