"""Central filesystem layout for AgentOne (single source of truth).

Manifest scopes (DB-canonical, most-specific wins)::

    global    <AGENTONE_ROOT>/                       (repo checkout .agentone/)
    user      ~/.agentone/{agents,skills,scripts,cronjobs}/
    project   <manifest_dir>/                        (DB Project.manifest_dir,
                                                     legacy fallback <path>/.agentone)
    workspace <manifest_dir>/                        (DB Workspace.manifest_dir,
                                                     loaded under parent_project)

Derived state under ``~/.agentone/`` (never manifests, re-creatable except
where noted)::

    sessions/<pk>/     per-session scratch (kept for archived, orphans swept)
    runtime/<ver>/     versioned extracts (1h GC, re-extractable)
    install/           content-addressed git repos (re-syncable)
    upstream/ staging/ upstream clones + merged staging (re-syncable)
    browser/           daemon token/profiles (DURABLE — back up)
    projects/<n>/      central project manifest dirs (DB-canonical content)
    workspaces/<n>/    central workspace manifest dirs (DB-canonical content)

``project.md`` / ``projects.yaml`` / ``workspace.md`` files are deprecated:
metadata lives in the DB. Loaders warn-and-ignore leftovers.
"""

from __future__ import annotations

import os
from pathlib import Path


def _expand(value: str | os.PathLike | None, default: str) -> Path:
    if value:
        return Path(os.path.expanduser(str(value)))
    return Path(os.path.expanduser(default))


def agentone_home() -> Path:
    """Return ``~/.agentone`` (overridable via ``AGENTONE_HOME`` env)."""
    return _expand(os.environ.get("AGENTONE_HOME", "").strip(), "~/.agentone")


def agentone_root() -> Path:
    """Return the global manifest root (repo ``.agentone/``).

    Prefers the ``AGENTONE_ROOT`` Django setting when configured, else
    ``AGENTONE_ROOT`` env, else ``<cwd>/.agentone`` resolved from this file.
    Pure path computation, no I/O.
    """
    try:
        from django.conf import settings as _settings

        configured = getattr(_settings, "AGENTONE_ROOT", None)
        if configured:
            return Path(str(configured))
    except Exception:  # settings not configured (bare import)
        pass
    env = os.environ.get("AGENTONE_ROOT", "").strip()
    if env:
        return Path(os.path.expanduser(env))
    return Path(__file__).resolve().parent.parent / ".agentone"


def sessions_base() -> Path:
    """Return the sessions base (``~/.agentone/sessions`` by default)."""
    try:
        from django.conf import settings as _settings

        configured = getattr(_settings, "AGENTONE_SESSIONS_DIR", None)
        if configured:
            return Path(os.path.expanduser(str(configured)))
    except Exception:
        pass
    return agentone_home() / "sessions"


def runtime_base() -> Path:
    return agentone_home() / "runtime"


def install_base() -> Path:
    return agentone_home() / "install"


def upstream_base() -> Path:
    return agentone_home() / "upstream"


def staging_base() -> Path:
    return agentone_home() / "staging"


def browser_base() -> Path:
    """Return the browser base (``AGENTONE_BROWSER_DIR`` env wins)."""
    configured = os.environ.get("AGENTONE_BROWSER_DIR", "").strip()
    if configured:
        return Path(os.path.expanduser(configured))
    return agentone_home() / "browser"


def user_scope_dir() -> Path:
    """Return ``~/.agentone`` (root of the user manifest scope)."""
    return agentone_home()


def user_agents_dir() -> Path:
    return agentone_home() / "agents"


def user_skills_dir() -> Path:
    return agentone_home() / "skills"


def user_scripts_dir() -> Path:
    return agentone_home() / "scripts"


def user_cronjobs_dir() -> Path:
    return agentone_home() / "cronjobs"


def central_projects_base() -> Path:
    return agentone_home() / "projects"


def central_workspaces_base() -> Path:
    return agentone_home() / "workspaces"


def central_project_dir(name: str) -> Path:
    safe = str(name).strip().replace(" ", "_").replace("/", "_")
    return central_projects_base() / safe


def central_workspace_dir(name: str) -> Path:
    safe = str(name).strip().replace(" ", "_").replace("/", "_")
    return central_workspaces_base() / safe


def ensure_private_dir(path: Path, mode: int = 0o700) -> Path:
    """Create *path* (and parents) with private mode; return it."""
    path.mkdir(parents=True, exist_ok=True)
    try:
        path.chmod(mode)
    except OSError:
        pass
    return path


def project_manifest_dir(project) -> Path:
    """Return the manifest (``.agentone``) dir for a Project row.

    Prefers ``project.manifest_dir`` when set, else legacy fallbacks:
    ``<path>/.agentone`` if that exists, else ``<path>`` itself when the
    path already looks like a manifest dir, else ``<path>/.agentone``.
    """
    explicit = str(getattr(project, "manifest_dir", "") or "").strip()
    if explicit:
        return Path(os.path.expanduser(explicit))
    base = str(getattr(project, "path", "") or "").strip()
    if not base:
        return central_project_dir(getattr(project, "name", "unnamed"))
    p = Path(os.path.expanduser(base))
    if p.name == ".agentone" and p.is_dir():
        return p
    legacy = p / ".agentone"
    if legacy.is_dir():
        return legacy
    # Default for rows created before manifest_dir existed.
    return legacy


def workspace_manifest_dir(workspace) -> Path | None:
    """Return the manifest dir for a Workspace row, or None if unmanaged."""
    explicit = str(getattr(workspace, "manifest_dir", "") or "").strip()
    if explicit:
        return Path(os.path.expanduser(explicit))
    return None
