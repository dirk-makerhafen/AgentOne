"""Workspace manifest-location helpers (inline vs central ``.agentone``).

A workspace's manifests live either inside the workspace folder
(``<workspace>/.agentone``, *inline*) or under the central home
(``~/.agentone/workspaces/<name>``, *central*), or the workspace is left
unmanaged (*none*). Shared by the create form and the inline edit form so
both resolve and persist ``manifest_dir`` identically.
"""
from __future__ import annotations

from pathlib import Path

STORAGE_NONE = "none"
STORAGE_INLINE = "inline"
STORAGE_CENTRAL = "central"
STORAGES = (STORAGE_INLINE, STORAGE_CENTRAL)


def storage_options() -> list[dict]:
    """Return the ``<select>`` options for the manifest-location picker."""
    return [
        {"value": STORAGE_INLINE,
         "label": "In workspace dir (<workspace>/.agentone)"},
        {"value": STORAGE_CENTRAL,
         "label": "Centralized (project or ~/.agentone/workspaces/<name>)"},
    ]


def inline_manifest_dir(ws_path: str) -> Path:
    return Path(ws_path) / ".agentone"


def central_manifest_dir(workspace) -> Path:
    from runtime.paths import central_workspace_dir, project_manifest_dir

    key = (getattr(workspace, "name", "") or "").strip() or Path(
        getattr(workspace, "path", "") or ""
    ).name
    project = getattr(workspace, "parent_project", None)
    try:
        model = getattr(workspace, "model", None)
        if project is None and model is not None:
            project = getattr(model, "parent_project", None)
    except Exception:  # pylint: disable=broad-exception-caught
        pass
    return central_workspace_dir(key, project=project)


def detect_storage(workspace) -> str:
    """Return the storage mode implied by a workspace's stored ``manifest_dir``."""
    stored = str(getattr(workspace, "agentone_dir", "") or getattr(workspace, "manifest_dir", "") or "").strip()
    if not stored:
        return STORAGE_CENTRAL
    try:
        stored_p = Path(stored)
        if stored_p == central_manifest_dir(workspace):
            return STORAGE_CENTRAL
        if stored_p == inline_manifest_dir(getattr(workspace, "path", "") or ""):
            return STORAGE_INLINE
        ws_path = str(getattr(workspace, "path", "") or "")
        if ws_path and str(stored_p).startswith(str(Path(ws_path))):
            return STORAGE_INLINE
    except Exception:  # pylint: disable=broad-exception-caught
        pass
    return STORAGE_CENTRAL


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


def ensure_manifest_dir(workspace, storage: str, ws_path: str,
                        gitignore: bool = False) -> str:
    """Create the manifest dir for *storage*; return its path (``""`` for none).

    For *inline* storage optionally appends ``.agentone/`` to the
    workspace's ``.gitignore``. Never raises on filesystem errors — returns
    ``""`` so the caller can leave the workspace unmanaged.
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
    manifest = central_manifest_dir(workspace)
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
