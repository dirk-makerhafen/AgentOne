"""Central filesystem layout for AgentOne (single source of truth).

Scope roots are self-contained.  Each scope owns its manifests, memory tree
and a ``var/`` subtree for runtime state::

    global    <AGENTONE_ROOT>/                       (repo checkout .agentone/)
    user      ~/.agentone/                           (agents/, skills/, …)
    project   <manifest_dir>/                        (Project.get_agentone_dir())
    workspace <manifest_dir>/                        (WorkspaceModel.get_agentone_dir())

Inside every scope directory::

    agents/ skills/ scripts/ cronjobs/ dashboard/ memory/   manifests + memory
    var/sessions/<agent>/<pk>/    session scratch (0700, never versioned)
    var/log/                      scope logs (terminals, …)
    var/run/                      scope pids/locks
    var/cache/runtime/<ver>/      versioned extracts (1h GC, re-extractable)
    var/cache/upstream/           upstream clones (re-syncable)
    var/cache/staging/            merged staging (re-syncable)

The home directory additionally owns machine-wide state.  Install repos are
the one family that stays central (keyed by scope) because they are derived,
content-addressed by tree SHA, and referenced by DB rows::

    ~/.agentone/
    ├── config.yaml               user/machine settings
    ├── secrets/                  0600 credentials (never synced)
    ├── agents/ skills/ scripts/ cronjobs/ memory/
    ├── projects/<n>/             project scopes
    ├── workspaces/<n>/           workspace scopes
    └── var/
        ├── install/              global/, user/, projects/<pk>/, workspaces/<pk>/
        ├── browser/              Camoufox profiles, token, audit (DURABLE)
        ├── sessions/             global/user-scope session scratch
        ├── log/                  global/user-scope + machine logs
        ├── run/                  global/user-scope + machine pids/locks
        └── cache/                runtime/, upstream/, staging/

``project.md`` / ``projects.yaml`` / ``workspace.md`` files are deprecated:
metadata lives in the DB. Loaders warn-and-ignore leftovers.

All location decisions live here.  Do not recompute ``~/.agentone/...`` paths
elsewhere; use :class:`ScopeRef` for per-scope paths.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any


def _expand(value: str | os.PathLike | None, default: str) -> Path:
    if value:
        return Path(os.path.expanduser(str(value)))
    return Path(os.path.expanduser(default))


# ---------------------------------------------------------------------------
# Home / scope roots
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Machine-wide home containers
# ---------------------------------------------------------------------------


def var_base() -> Path:
    """Return ``~/.agentone/var`` (machine + global/user scope state)."""
    return agentone_home() / "var"


def secrets_dir() -> Path:
    """Return ``~/.agentone/secrets`` (0600 credentials)."""
    return agentone_home() / "secrets"


def log_base() -> Path:
    """Return the machine/global-scope log directory."""
    return var_base() / "log"


def run_base() -> Path:
    """Return the machine/global-scope pid/lock directory."""
    return var_base() / "run"


def cache_base() -> Path:
    """Return the machine/global-scope cache directory."""
    return var_base() / "cache"


def runtime_base() -> Path:
    """Return the global/user-scope runtime extract cache."""
    return cache_base() / "runtime"


def install_base() -> Path:
    """Return ``~/.agentone/var/install`` (machine-wide, keyed by scope)."""
    return var_base() / "install"


def upstream_base() -> Path:
    """Return the global/user-scope upstream clone cache."""
    return cache_base() / "upstream"


def staging_base() -> Path:
    """Return the global/user-scope merged-staging cache."""
    return cache_base() / "staging"


def browser_base() -> Path:
    """Return the browser base (``AGENTONE_BROWSER_DIR`` env wins).

    Falls back to the pre-``var/`` location while a layout migration has not
    run yet, so durable Camoufox profiles keep working across the upgrade.
    """
    configured = os.environ.get("AGENTONE_BROWSER_DIR", "").strip()
    if configured:
        return Path(os.path.expanduser(configured))
    new = var_base() / "browser"
    legacy = agentone_home() / "browser"
    if new.exists() or not legacy.exists():
        return new
    return legacy


def sessions_base() -> Path:
    """Return the sessions base (``~/.agentone/var/sessions`` by default)."""
    try:
        from django.conf import settings as _settings

        configured = getattr(_settings, "AGENTONE_SESSIONS_DIR", None)
        if configured:
            return Path(os.path.expanduser(str(configured)))
    except Exception:
        pass
    new = var_base() / "sessions"
    legacy = agentone_home() / "sessions"
    if new.exists() or not legacy.exists():
        return new
    return legacy


# ---------------------------------------------------------------------------
# Legacy (pre-var/) locations — used for one-shot migration + read fallbacks
# ---------------------------------------------------------------------------


def legacy_install_base() -> Path:
    return agentone_home() / "install"


def legacy_runtime_base() -> Path:
    return agentone_home() / "runtime"


def legacy_upstream_base() -> Path:
    return agentone_home() / "upstream"


def legacy_staging_base() -> Path:
    return agentone_home() / "staging"


def legacy_sessions_base() -> Path:
    return agentone_home() / "sessions"


def legacy_log_base() -> Path:
    return agentone_home() / "terminals"


def legacy_pid_file() -> Path:
    return agentone_home() / "sleep_guard.pid"


# ---------------------------------------------------------------------------
# User-scope manifest dirs (unchanged paths: ~/.agentone/{agents,skills,…})
# ---------------------------------------------------------------------------


def user_agents_dir() -> Path:
    return agentone_home() / "agents"


def user_skills_dir() -> Path:
    return agentone_home() / "skills"


def user_scripts_dir() -> Path:
    return agentone_home() / "scripts"


def user_cronjobs_dir() -> Path:
    return agentone_home() / "cronjobs"


def user_memory_dir() -> Path:
    return agentone_home() / "memory"


def _safe_segment(name: str) -> str:
    """Return *name* trimmed for use as a single path segment."""
    return str(name or "").strip().strip("/") or "unnamed"


# ---------------------------------------------------------------------------
# ScopeRef — one object decides every per-scope path
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ScopeRef:
    """A manifest scope and all of its derived paths.

    ``kind`` is ``global`` | ``user`` | ``project`` | ``workspace``.  ``key``
    is the stable filesystem identity used for install repos (``global``,
    ``user``, or the DB pk).  ``manifest_dir`` is where agents/skills/scripts/
    cronjobs/memory live.
    """

    kind: str
    key: str
    name: str
    manifest_dir: Path

    # -- constructors -------------------------------------------------

    @classmethod
    def global_scope(cls) -> "ScopeRef":
        return cls("global", "global", "global", agentone_root())

    @classmethod
    def user_scope(cls) -> "ScopeRef":
        return cls("user", "user", "user", agentone_home())

    @classmethod
    def for_project(cls, project: Any) -> "ScopeRef":
        name = str(getattr(project, "name", "") or "unnamed")
        pk = getattr(project, "pk", None)
        key = str(pk) if pk is not None else _safe_segment(name)
        try:
            manifest_dir = Path(project.get_agentone_dir()).expanduser()
        except Exception:  # pylint: disable=broad-exception-caught
            manifest_dir = central_project_dir(name)
        return cls("project", key, name, manifest_dir)

    @classmethod
    def for_workspace(cls, workspace: Any) -> "ScopeRef":
        name = str(getattr(workspace, "name", "") or "unnamed")
        pk = getattr(workspace, "pk", None)
        key = str(pk) if pk is not None else _safe_segment(name)
        try:
            manifest_dir = Path(workspace.get_agentone_dir()).expanduser()
        except Exception:  # pylint: disable=broad-exception-caught
            manifest_dir = central_workspace_dir(name)
        return cls("workspace", key, name, manifest_dir)

    @classmethod
    def for_manifest(cls, project: Any = None, agent: Any = None) -> "ScopeRef":
        """Best-effort scope for a loaded manifest.

        Prefers the owning project (directly or via the agent).  Global and
        user manifests share the home ``var/`` tree, so they resolve to the
        global scope when no project is known.
        """
        if project is None and agent is not None:
            project = getattr(agent, "parent_project", None)
        if project is not None:
            return cls.for_project(project)
        return cls.global_scope()

    # -- paths --------------------------------------------------------

    def var_dir(self) -> Path:
        """Return this scope's ``var/`` directory.

        Global and user scopes share ``~/.agentone/var``; project and
        workspace scopes own ``<manifest_dir>/var``.
        """
        if self.kind in ("global", "user"):
            return var_base()
        return self.manifest_dir / "var"

    def sessions_dir(self) -> Path:
        return self.var_dir() / "sessions"

    def log_dir(self) -> Path:
        return self.var_dir() / "log"

    def run_dir(self) -> Path:
        return self.var_dir() / "run"

    def cache_dir(self) -> Path:
        return self.var_dir() / "cache"

    def runtime_dir(self) -> Path:
        return self.cache_dir() / "runtime"

    def upstream_dir(self) -> Path:
        return self.cache_dir() / "upstream"

    def staging_dir(self) -> Path:
        return self.cache_dir() / "staging"

    def new_install_repo_path(self) -> Path:
        """Return the canonical (current-layout) install repo path."""
        if self.kind == "global":
            return install_base() / "global"
        if self.kind == "user":
            return install_base() / "user"
        if self.kind == "workspace":
            return install_base() / "workspaces" / self.key
        return install_base() / "projects" / self.key

    def legacy_install_repo_path(self) -> Path:
        """Return the pre-``var/`` install repo path for this scope."""
        if self.kind in ("global", "user"):
            return legacy_install_base() / self.kind
        prefix = "workspace" if self.kind == "workspace" else "project"
        safe = str(self.name or "").strip().replace(" ", "_").replace("/", "_") or "unnamed"
        return legacy_install_base() / f"{prefix}_{safe}"

    def install_repo_path(self) -> Path:
        """Return the install git repo for this scope (machine-wide).

        New layout lives under ``~/.agentone/var/install/``.  Before a
        migration has run, an existing legacy repo (``project_<name>``) is
        reused so pinned tree SHAs stay resolvable.
        """
        new = self.new_install_repo_path()
        if new.exists():
            return new
        legacy = self.legacy_install_repo_path()
        if legacy.exists():
            return legacy
        return new


def scope_for_project(project: Any) -> ScopeRef:
    return ScopeRef.for_project(project)


def scope_for_workspace(workspace: Any) -> ScopeRef:
    return ScopeRef.for_workspace(workspace)


# ---------------------------------------------------------------------------
# Manifest source dirs (``manifest_dir`` stored on the model wins)
# ---------------------------------------------------------------------------


def agent_source_dir(name: str, project: Any = None) -> Path:
    """Return the conventional source dir for an agent manifest (no I/O).

    Project-owned agents live under the project manifest's ``agents/``
    tree; global ones under ``~/.agentone/agents/``. Pure computation —
    the directory may not exist (e.g. repo-scoped agents).
    """
    safe = _safe_segment(name)
    if project is not None:
        try:
            return project.get_agentone_dir() / "agents" / safe
        except Exception:  # pylint: disable=broad-exception-caught
            pass
    return user_agents_dir() / safe


def skill_source_dir(name: str, project: Any = None) -> Path:
    """Return the conventional source dir for a skill manifest (no I/O).

    Same layout rules as :func:`agent_source_dir` with ``skills/``.
    """
    safe = _safe_segment(name)
    if project is not None:
        try:
            return project.get_agentone_dir() / "skills" / safe
        except Exception:  # pylint: disable=broad-exception-caught
            pass
    return user_skills_dir() / safe


def model_manifest_dir(model: Any, kind: str, name: str = "", project: Any = None) -> Path:
    """Return the source directory for an agent/skill manifest (no I/O).

    Prefers the stored ``manifest_dir`` field (set by the loader); falls
    back to the conventional layout for the *kind* (``agent`` | ``skill``).
    Projects and workspaces resolve through ``get_agentone_dir()``;
    cronjobs resolve through ``runtime.cron.file_io`` (import cycle if
    done here).
    """
    stored = str(getattr(model, "manifest_dir", "") or "").strip()
    if stored:
        return Path(os.path.expanduser(stored))
    if kind == "skill":
        return skill_source_dir(name or getattr(model, "name", ""), project)
    return agent_source_dir(name or getattr(model, "name", ""), project)


# ---------------------------------------------------------------------------
# Central project / workspace manifest dirs
# ---------------------------------------------------------------------------


def central_projects_base() -> Path:
    return agentone_home() / "projects"


def central_workspaces_base() -> Path:
    return agentone_home() / "workspaces"


def central_project_dir(name: str) -> Path:
    safe = str(name).strip().replace(" ", "_").replace("/", "_")
    return central_projects_base() / safe


def central_workspace_dir(name: str, project: Any = None) -> Path:
    safe = str(name).strip().replace(" ", "_").replace("/", "_") or "unnamed"
    if project is not None:
        try:
            return project.get_agentone_dir() / "workspaces" / safe
        except Exception:  # pylint: disable=broad-exception-caught
            pass
    return central_workspaces_base() / safe


def ensure_private_dir(path: Path, mode: int = 0o700) -> Path:
    """Create *path* (and parents) with private mode; return it."""
    path.mkdir(parents=True, exist_ok=True)
    try:
        path.chmod(mode)
    except OSError:
        pass
    return path
