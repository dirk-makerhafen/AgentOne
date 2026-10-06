"""
Session-private storage — per-session isolated folders.

Each agent session gets a private folder at::

    <SESSIONS_BASE>/<session_pk>/

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

import os
import shutil
from pathlib import Path


def get_sessions_base() -> Path:
    """Return the sessions base directory (``~/.agentone/sessions`` by default).

    Reads the ``AGENTONE_SESSIONS_DIR`` Django setting when configured,
    so operators can point it elsewhere via ``config/settings_local.py``
    and tests can redirect it.  Pure path computation, no I/O.
    """
    try:
        from django.conf import settings as _settings

        configured = getattr(_settings, "AGENTONE_SESSIONS_DIR", None)
        if configured:
            return Path(os.path.expanduser(str(configured)))
    except Exception:  # pylint: disable=broad-exception-caught
        # Settings not configured (e.g. bare import) — fall through.
        pass
    return Path(os.path.expanduser("~/.agentone/sessions"))


def session_dir(session_pk: int | str) -> Path:
    """Return the private folder path for *session_pk* (pure, no I/O)."""
    return get_sessions_base() / str(session_pk)


def ensure_session_dir(session_pk: int | str) -> Path:
    """Create the private folder for *session_pk* if missing and return it.

    Idempotent (``mkdir(parents=True, exist_ok=True)``).  New folders get
    mode ``0o700`` so other OS users cannot list them.
    """
    folder = session_dir(session_pk)
    folder.mkdir(parents=True, exist_ok=True)
    try:
        folder.chmod(0o700)
    except OSError:
        pass
    return folder


def parse_session_pk(target: Path | str) -> str | None:
    """Return the ``<session_pk>`` path segment if *target* is inside the
    sessions base, else *None*.

    Both sides are resolved (symlinks expanded, ``..`` collapsed) before the
    containment check, so a symlink pointing into another session's folder is
    attributed to that session, not to the link's own folder.
    """
    base = get_sessions_base()
    try:
        base_resolved = base.expanduser().resolve()
    except OSError:
        base_resolved = base.expanduser()
    try:
        resolved = Path(target).expanduser().resolve()
    except OSError:
        resolved = Path(target).expanduser()
    try:
        rel = resolved.relative_to(base_resolved)
    except ValueError:
        return None
    if not rel.parts:
        return ""  # target IS the base dir itself
    return rel.parts[0]


def cleanup_orphaned_session_folders() -> int:
    """Remove session folders whose DB row no longer exists.

    Only folders named by an integer pk with no matching ``SessionModel``
    row are removed.  Archived/inactive sessions are kept forever.
    Non-numeric entries are ignored.  Returns the number removed.
    """
    base = get_sessions_base()
    if not base.exists():
        return 0
    removed = 0
    for entry in sorted(base.iterdir()):
        if not entry.is_dir() or entry.is_symlink():
            continue
        try:
            pk = int(entry.name)
        except ValueError:
            continue
        try:
            from server.models.sessions.session import SessionModel

            exists = SessionModel.objects.filter(pk=pk).exists()
        except Exception:  # pylint: disable=broad-exception-caught
            continue
        if not exists:
            shutil.rmtree(entry, ignore_errors=True)
            removed += 1
    return removed
