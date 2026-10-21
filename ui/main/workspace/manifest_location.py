"""Workspace agentone-directory location helpers.

A workspace's manifests live in one of three places:

* ``inline`` — inside the workspace folder (``<workspace>/.agentone``);
* ``project`` — under the owning project's agentone tree
  (``<project agentone>/workspaces/<name>``);
* ``user`` — under the AgentOne home (``~/.agentone/workspaces/<name>``).

The legacy ``central`` value meant "project when owned, user otherwise"; it
is still accepted for rows written before the split, but the UI exposes the
project and user locations as separate options.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

STORAGE_NONE = "none"
STORAGE_INLINE = "inline"
STORAGE_PROJECT = "project"
STORAGE_USER = "user"
STORAGE_CENTRAL = "central"  # legacy: project when owned, user otherwise
STORAGES = (STORAGE_INLINE, STORAGE_PROJECT, STORAGE_USER)


def _workspace_key(workspace: Any) -> str:
    """Return the directory-name key for *workspace*."""
    name = (getattr(workspace, "name", "") or "").strip()
    if name:
        return name
    return Path(getattr(workspace, "path", "") or "").name or "unnamed"


def _workspace_project(workspace: Any) -> Any | None:
    """Return the owning project, unwrapping runtime/model wrappers."""
    project = getattr(workspace, "parent_project", None)
    if project is not None:
        return project
    model = getattr(workspace, "model", None)
    return getattr(model, "parent_project", None) if model is not None else None


def storage_options() -> list[dict]:
    """Return the ``<select>`` options for the manifest-location picker."""
    return [
        {"value": STORAGE_INLINE,
         "label": "In workspace dir (<workspace>/.agentone)"},
        {"value": STORAGE_PROJECT,
         "label": "In project (<project agentone>/workspaces/<name>)"},
        {"value": STORAGE_USER,
         "label": "In user dir (~/.agentone/workspaces/<name>)"},
    ]


def inline_manifest_dir(ws_path: str) -> Path:
    return Path(ws_path) / ".agentone"


def project_workspace_manifest_dir(workspace: Any) -> Path | None:
    """Return the project-owned manifest dir, or ``None`` without a project."""
    from runtime.paths import central_workspace_dir

    project = _workspace_project(workspace)
    if project is None:
        return None
    return central_workspace_dir(_workspace_key(workspace), project=project)


def user_manifest_dir(workspace: Any) -> Path:
    """Return the user-home manifest dir (``~/.agentone/workspaces/<name>``)."""
    from runtime.paths import central_workspace_dir

    return central_workspace_dir(_workspace_key(workspace))


def central_manifest_dir(workspace: Any) -> Path:
    """Return the legacy central location (project when owned, else user)."""
    return project_workspace_manifest_dir(workspace) or user_manifest_dir(workspace)


def detect_storage(workspace: Any) -> str:
    """Return the storage mode implied by a workspace's stored ``agentone_dir``."""
    stored = str(
        getattr(workspace, "agentone_dir", "")
        or getattr(workspace, "manifest_dir", "")
        or ""
    ).strip()
    project_dir = project_workspace_manifest_dir(workspace)
    user_dir = user_manifest_dir(workspace)
    if not stored:
        return STORAGE_PROJECT if project_dir is not None else STORAGE_USER
    try:
        stored_p = Path(stored)
        if stored_p == inline_manifest_dir(getattr(workspace, "path", "") or ""):
            return STORAGE_INLINE
        if project_dir is not None and stored_p == project_dir:
            return STORAGE_PROJECT
        if stored_p == user_dir:
            return STORAGE_USER
        ws_path = str(getattr(workspace, "path", "") or "")
        if ws_path and str(stored_p).startswith(str(Path(ws_path))):
            return STORAGE_INLINE
        if project_dir is not None:
            try:
                project = _workspace_project(workspace)
                project_root = project.get_agentone_dir()
                if str(stored_p).startswith(str(project_root)):
                    return STORAGE_PROJECT
            except Exception:  # pylint: disable=broad-exception-caught
                pass
    except Exception:  # pylint: disable=broad-exception-caught
        pass
    return STORAGE_PROJECT if project_dir is not None else STORAGE_USER


def gitignore_has_agentone(ws_path: str) -> bool:
    """Return True when ``<ws_path>/.gitignore`` already ignores ``.agentone/``."""
    if not ws_path:
        return False
    gi = Path(ws_path) / ".gitignore"
    try:
        if not gi.exists():
            return False
        return ".agentone/" in gi.read_text(encoding="utf-8").splitlines()
    except OSError:
        return False


def ensure_manifest_dir(workspace: Any, storage: str, ws_path: str,
                        gitignore: bool = False) -> str:
    """Create the agentone dir for *storage*; return its path.

    ``none`` returns ``""``. Inline storage optionally appends ``.agentone/``
    to the workspace's ``.gitignore``. Never raises on filesystem errors —
    returns ``""`` so the caller can leave the workspace unmanaged.
    """
    if storage == STORAGE_NONE:
        return ""
    if storage == STORAGE_INLINE:
        manifest = inline_manifest_dir(ws_path)
        try:
            manifest.mkdir(parents=True, exist_ok=True)
        except OSError:
            return ""
        if gitignore:
            _add_gitignore_entry(Path(ws_path))
        return manifest.as_posix()
    if storage == STORAGE_PROJECT:
        manifest = project_workspace_manifest_dir(workspace) or user_manifest_dir(workspace)
    elif storage == STORAGE_CENTRAL:
        manifest = central_manifest_dir(workspace)
    else:
        manifest = user_manifest_dir(workspace)
    try:
        manifest.mkdir(parents=True, exist_ok=True)
    except OSError:
        return ""
    return manifest.as_posix()


def _add_gitignore_entry(ws_path: Path) -> None:
    gi = ws_path / ".gitignore"
    try:
        existing = gi.read_text(encoding="utf-8") if gi.exists() else ""
        if ".agentone/" not in existing.splitlines():
            with gi.open("a", encoding="utf-8") as f:
                if existing and not existing.endswith("\n"):
                    f.write("\n")
                f.write(".agentone/\n")
    except OSError:
        pass
