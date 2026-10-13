"""Filesystem layout for the browser daemon.

Everything lives under ``~/.agentone/browser/`` (overridable via the
``AGENTONE_BROWSER_DIR`` environment variable, so tests can redirect it)::

    ~/.agentone/browser/
        token                    0600 bearer token for the local HTTP API
        state.json               pid + port of the running daemon
        start.lock               flock, serializes lazy daemon starts
        nav-audit.jsonl          one JSON line per navigation (audit trail)
        profiles/
            s<root_session_pk>/      session-scoped profile (default)
                launch_options.json  Camoufox identity — persisted, not redrawn
                user_data/           Firefox profile (cookies, logins, storage)
            named-<slug>/            opt-in durable profile, shared by name
            clean-<uuid>/            ephemeral throwaway profile

This base dir is intentionally outside ``~/.agentone/runtime/`` (which is
garbage-collected) and outside session-private storage, so browser profiles
outlive worker restarts and are not swept with a versioned runtime folder.
"""

from __future__ import annotations

import os
import re
import secrets
import stat
from pathlib import Path

BROWSER_DIR_ENV = "AGENTONE_BROWSER_DIR"

#: Profile key grammar.  ``session``/``named`` keys are reusable (they are
#: re-entered on daemon restart), ``clean`` keys are single-use.
_KEY_RE = re.compile(r"^(?:s(?P<session>[0-9]{1,18})|named-[a-z0-9][a-z0-9_-]{0,48}|clean-[0-9a-f]{32})$")


def browser_base() -> Path:
    """Return the browser base directory (pure, no I/O)."""
    try:
        from runtime.paths import browser_base as _central_browser_base

        return _central_browser_base()
    except Exception:
        configured = os.environ.get(BROWSER_DIR_ENV, "").strip()
        base = Path(os.path.expanduser(configured)) if configured else Path.home() / ".agentone" / "browser"
        return base


def profiles_base() -> Path:
    return browser_base() / "profiles"


def profile_dir(key: str) -> Path:
    """Return the directory for *key*.  Validates the key (no traversal)."""
    if not _KEY_RE.match(key):
        raise ValueError(f"invalid browser profile key: {key!r}")
    return profiles_base() / key


def launch_options_path(key: str) -> Path:
    return profile_dir(key) / "launch_options.json"


def user_data_dir(key: str) -> Path:
    return profile_dir(key) / "user_data"


def token_path() -> Path:
    return browser_base() / "token"


def state_path() -> Path:
    return browser_base() / "state.json"


def start_lock_path() -> Path:
    return browser_base() / "start.lock"


def audit_log_path() -> Path:
    return browser_base() / "nav-audit.jsonl"


def ensure_private_dir(path: Path) -> Path:
    """Create *path* (and parents) with mode ``0700``; return it."""
    try:
        from runtime.paths import ensure_private_dir as _ensure_private

        return _ensure_private(path, 0o700)
    except Exception:
        path.mkdir(parents=True, exist_ok=True)
        try:
            path.chmod(stat.S_IRWXU)  # 0o700
        except OSError:
            pass
        return path


def read_token() -> str | None:
    """Return the daemon bearer token, creating it on first use."""
    path = token_path()
    if path.exists():
        try:
            token = path.read_text(encoding="utf-8").strip()
            if token:
                return token
        except OSError:
            return None
    ensure_private_dir(browser_base())
    token = secrets.token_urlsafe(32)
    tmp = path.with_suffix(".tmp")
    # Write-then-rename so a concurrent reader never sees a half-written token.
    tmp.write_text(token + "\n", encoding="utf-8")
    try:
        tmp.chmod(stat.S_IRUSR | stat.S_IWUSR)  # 0o600
    except OSError:
        pass
    os.replace(tmp, path)
    return token


def session_profile_key(root_session_pk: int) -> str:
    """Profile key for a session-scoped (default) browser."""
    return f"s{int(root_session_pk)}"


def named_profile_key(name: str) -> str:
    """Profile key for an opt-in named durable profile (``profile="github"``)."""
    slug = re.sub(r"[^a-z0-9_-]+", "-", str(name).strip().lower()).strip("-_")
    if not slug:
        raise ValueError(f"invalid browser profile name: {name!r}")
    return f"named-{slug[:48]}"


def clean_profile_key() -> str:
    """Profile key for a fresh throwaway identity."""
    return f"clean-{secrets.token_hex(16)}"
