"""
Session-private storage — per-session isolated folders.

Each agent session gets a private folder.  The location depends on the
session's scope:

* workspace session: ``<workspace agentone dir>/sessions/<agent name>/<pk>/``
* project session (no workspace): ``<project agentone dir>/sessions/<agent name>/<pk>/``
* global session (neither): ``<AGENTONE_SESSIONS_DIR>/<agent name>/<pk>/``
  (defaults to ``~/.agentone/sessions/<agent name>/<pk>/``).

Default ``SESSIONS_BASE`` is ``~/.agentone/sessions`` (overridable via the
``AGENTONE_SESSIONS_DIR`` Django setting, see ``config/settings.py`` and
``config/settings_local.example.py``).

The folder is for scratch files, temporary memory, ad-hoc prompts/tools,
intermediate results, generated scripts and other session-specific artifacts.
Isolation is enforced by the filesystem guardrail
(``runtime/workspace_access.py``): a session may read/write its own folder
but never another session's folder.

Creation is lazy — use :func:`ensure_session_dir` on first use, never
eagerly at session creation.  Archived sessions (``is_archived=True``) are
kept forever; only folders whose DB row is gone (hard delete) are removed
by :func:`cleanup_orphaned_session_folders`.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any


from runtime.paths import ensure_private_dir, sessions_base as _sessions_base


def _safe_segment(name: Any) -> str:
    return str(name or "").strip().strip("/") or "unnamed"


def get_sessions_base() -> Path:
    """Return the global sessions base directory (``~/.agentone/sessions`` by default)."""
    return _sessions_base()


# ---------------------------------------------------------------------------
# Context resolution helpers
# ---------------------------------------------------------------------------


def _extract_pk(obj: Any) -> Any:
    if isinstance(obj, (int, str, Path)):
        if isinstance(obj, Path):
            return obj.name
        return obj
    pk = getattr(obj, "pk", None)
    if pk is not None:
        return pk
    model = getattr(obj, "model", None)
    if model is not None:
        pk = getattr(model, "pk", None)
        if pk is not None:
            return pk
    for attr in ("session_pk", "id"):
        pk = getattr(obj, attr, None)
        if pk is not None:
            return pk
    return obj


def _workspace_of(obj: Any) -> Any | None:
    if isinstance(obj, (int, str, Path)):
        return None
    ws = getattr(obj, "workspace", None)
    if callable(ws):
        try:
            ws = ws()
        except Exception:  # pylint: disable=broad-exception-caught
            ws = None
    if ws is None:
        model = getattr(obj, "model", None)
        if model is not None:
            try:
                version = getattr(model, "latest_session_version", None)
                if version is not None:
                    ws = getattr(version, "workspace", None)
            except Exception:  # pylint: disable=broad-exception-caught
                pass
    return ws


def _project_of(obj: Any, ws: Any | None) -> Any | None:
    if isinstance(obj, (int, str, Path)):
        return None
    proj = getattr(obj, "parent_project", None)
    if proj is None:
        gp = getattr(obj, "get_project", None)
        if callable(gp):
            try:
                proj = gp()
            except Exception:  # pylint: disable=broad-exception-caught
                proj = None
    if proj is None:
        model = getattr(obj, "model", None)
        if model is not None:
            proj = getattr(model, "parent_project", None)
    if proj is None and ws is not None:
        proj = getattr(ws, "parent_project", None)
    return proj


def _agent_name_of(obj: Any) -> str:
    if isinstance(obj, (int, str, Path)):
        return "agent"
    name = getattr(obj, "agent_name", None)
    if name:
        return _safe_segment(name)
    agent = getattr(obj, "agent", None)
    if callable(agent):
        try:
            agent = agent()
        except Exception:  # pylint: disable=broad-exception-caught
            agent = None
    if agent is not None:
        name = getattr(agent, "name", None)
        if name is None:
            am = getattr(agent, "model", None)
            if am is not None:
                name = getattr(am, "name", None)
        if name:
            return _safe_segment(name)
    model = getattr(obj, "model", None)
    if model is not None:
        try:
            version = getattr(model, "latest_session_version", None)
            if version is not None:
                agent = getattr(version, "agent", None)
                if agent is not None:
                    name = getattr(agent, "name", None)
                    if name is None:
                        am = getattr(agent, "model", None)
                        if am is not None:
                            name = getattr(am, "name", None)
                    if name:
                        return _safe_segment(name)
        except Exception:  # pylint: disable=broad-exception-caught
            pass
    return "agent"


def _agentone_dir(ws: Any | None, proj: Any | None) -> Path:
    if ws is not None:
        md = getattr(ws, "manifest_dir", None)
        if callable(md):
            try:
                md = md()
            except Exception:  # pylint: disable=broad-exception-caught
                md = None
        md = str(md or "").strip()
        if md:
            return Path(md).expanduser()
        wproj = getattr(ws, "parent_project", None)
        if wproj is not None:
            from runtime.paths import project_manifest_dir

            return project_manifest_dir(wproj)
    if proj is not None:
        from runtime.paths import project_manifest_dir

        return project_manifest_dir(proj)
    from runtime.paths import agentone_home

    return agentone_home()


def session_dir(session_or_pk: Any, *args: Any, **kwargs: Any) -> Path:
    """Return the private folder path for *session_or_pk* (pure, no I/O).

    Accepts an int/str pk, a ``SessionModel``, a runtime ``Session``, or any
    object exposing ``.model`` / ``.workspace`` / ``.parent_project`` /
    ``.agent``.  Optional keyword overrides: ``agent_name``, ``workspace``,
    ``project``.
    """
    agent_name = kwargs.pop("agent_name", None)
    workspace = kwargs.pop("workspace", None)
    project = kwargs.pop("project", None)

    # Primitive pk: try to resolve full context from the DB first.
    if isinstance(session_or_pk, (int, str)) and workspace is None and project is None and agent_name is None:
        try:
            from server.models.sessions.session import SessionModel

            obj = SessionModel.objects.get(pk=int(session_or_pk))
            return session_dir(obj)
        except Exception:  # pylint: disable=broad-exception-caught
            pass

    if workspace is None:
        workspace = _workspace_of(session_or_pk)
    if project is None:
        project = _project_of(session_or_pk, workspace)
    if agent_name is None:
        agent_name = _agent_name_of(session_or_pk)
    else:
        agent_name = _safe_segment(agent_name)

    pk = _extract_pk(session_or_pk)

    # Global scope (no workspace / no project): honour AGENTONE_SESSIONS_DIR.
    if workspace is None and project is None:
        from runtime.paths import sessions_base

        sessions_base_dir = sessions_base()
    else:
        base = _agentone_dir(workspace, project)
        sessions_base_dir = base / "sessions"

    return sessions_base_dir / str(agent_name) / str(pk)


def ensure_session_dir(session_or_pk: Any, *args: Any, **kwargs: Any) -> Path:
    """Create the private folder for *session_or_pk* if missing and return it."""
    folder = session_dir(session_or_pk, *args, **kwargs)
    return ensure_private_dir(folder, 0o700)


def parse_session_pk(target: Path | str) -> str | None:
    """Return the ``<session_pk>`` path segment if *target* is inside a
    session-private storage tree, else *None*.

    Handles both the legacy layout (``<base>/<pk>/...``) and the new layout
    (``<base>/<agent>/<pk>/...``).  Returns ``""`` when *target* is a
    sessions base directory itself.
    """
    try:
        resolved = Path(target).expanduser().resolve()
    except OSError:
        resolved = Path(target).expanduser()
    parts = resolved.parts

    # Find the last "sessions" segment.
    idx = None
    for i in range(len(parts) - 1, -1, -1):
        if parts[i] == "sessions":
            idx = i
            break
    if idx is None:
        # Fall back to the configured global base containment check.
        base = get_sessions_base()
        try:
            base_resolved = base.expanduser().resolve()
        except OSError:
            base_resolved = base.expanduser()
        try:
            rel = resolved.relative_to(base_resolved)
        except ValueError:
            return None
        if not rel.parts:
            return ""
        # legacy: first segment is pk
        return rel.parts[0]
    rest = parts[idx + 1:]
    if not rest:
        return ""
    if rest[0].isdigit():
        return rest[0]
    if len(rest) >= 2 and rest[1].isdigit():
        return rest[1]
    return None


def cleanup_orphaned_session_folders() -> int:
    """Remove session folders whose DB row no longer exists.

    Handles both the legacy flat layout (``<base>/<pk>``) and the new nested
    layout (``<base>/<agent>/<pk>``).  Only folders named by an integer pk
    with no matching ``SessionModel`` row are removed.  Archived/inactive
    sessions are kept forever.  Non-numeric entries are ignored.  Returns the
    number removed.
    """
    base = get_sessions_base()
    if not base.exists():
        return 0
    removed = 0
    try:
        from server.models.sessions.session import SessionModel
    except Exception:  # pylint: disable=broad-exception-caught
        return 0

    def _exists(pk: int) -> bool:
        try:
            return SessionModel.objects.filter(pk=pk).exists()
        except Exception:  # pylint: disable=broad-exception-caught
            return True

    # Flat legacy entries: <base>/<pk>
    for entry in sorted(base.iterdir()):
        if not entry.is_dir() or entry.is_symlink():
            continue
        try:
            pk = int(entry.name)
        except ValueError:
            # Agent-named directory: <base>/<agent>/<pk>
            if entry.is_dir():
                for pk_entry in sorted(entry.iterdir()):
                    if not pk_entry.is_dir() or pk_entry.is_symlink():
                        continue
                    try:
                        pk2 = int(pk_entry.name)
                    except ValueError:
                        continue
                    if not _exists(pk2):
                        shutil.rmtree(pk_entry, ignore_errors=True)
                        removed += 1
            continue
        if not _exists(pk):
            shutil.rmtree(entry, ignore_errors=True)
            removed += 1
    return removed
