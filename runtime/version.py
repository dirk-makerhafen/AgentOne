"""Version and update metadata for the running AgentOne installation.

The displayed version is derived from git (``git describe --tags --always
--dirty``) with the checked-in ``VERSION`` file as a fallback for source
drops that have no ``.git`` directory.  All git calls are best-effort: the
Settings page must still render when git is missing or Redis is down.
"""

from __future__ import annotations

import re
import subprocess
import time
from pathlib import Path

from django.conf import settings
from django.core.cache import cache

_VERSION_TAG = re.compile(r"^v?\d+\.\d+")
_LOCAL_CACHE_KEY = "agentone:version:local"
_REMOTE_CACHE_KEY = "agentone:version:remote"
_LOCAL_TTL = 120
_REMOTE_TTL = 300

# When Redis is unavailable the Django cache raises; keep a short-lived
# in-process copy so a single page render does not spawn a dozen git processes.
_FALLBACK: dict[str, tuple[object, float]] = {}


def _cache_get(key):
    try:
        return cache.get(key)
    except Exception:  # pylint: disable=broad-exception-caught
        entry = _FALLBACK.get(key)
        if entry and entry[1] > time.monotonic():
            return entry[0]
        return None


def _cache_set(key, value, ttl):
    try:
        cache.set(key, value, ttl)
    except Exception:  # pylint: disable=broad-exception-caught
        _FALLBACK[key] = (value, time.monotonic() + ttl)


def _cache_delete(*keys):
    try:
        cache.delete_many(list(keys))
    except Exception:  # pylint: disable=broad-exception-caught
        pass
    for key in keys:
        _FALLBACK.pop(key, None)


def repo_path(path=None) -> Path:
    """Resolve the installation root (defaults to ``settings.BASE_DIR``)."""
    return Path(path or getattr(settings, "BASE_DIR", Path.cwd())).resolve()


def _git(args, root: Path, timeout: int = 10):
    try:
        proc = subprocess.run(
            ["git", *args],
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout.strip()


def _release(root: Path) -> str:
    version_file = root / "VERSION"
    try:
        return version_file.read_text(encoding="utf-8").strip()
    except OSError:
        return str(getattr(settings, "AGENTONE_VERSION", "") or "").strip()


def get_version_info(path=None, refresh: bool = False) -> dict:
    """Return local version, commit and branch information.

    Keys: ``version``, ``release``, ``describe``, ``commit``,
    ``short_commit``, ``branch``, ``dirty``, ``is_git``, ``source``.
    """
    if not refresh:
        cached = _cache_get(_LOCAL_CACHE_KEY)
        if isinstance(cached, dict):
            return dict(cached)

    root = repo_path(path)
    release = _release(root)
    is_git = (root / ".git").exists()
    describe = _git(["describe", "--tags", "--always", "--dirty"], root) or ""
    commit = _git(["rev-parse", "HEAD"], root) or ""
    short_commit = _git(["rev-parse", "--short", "HEAD"], root) or ""
    branch = _git(["rev-parse", "--abbrev-ref", "HEAD"], root) or ""
    dirty = bool(_git(["status", "--porcelain"], root)) if is_git else False

    if _VERSION_TAG.match(describe):
        # A real release tag wins over the VERSION file.
        version = describe[1:] if describe.startswith("v") else describe
    elif release and short_commit:
        version = f"{release}+{short_commit}" + ("-dirty" if dirty else "")
    elif release:
        version = release
    else:
        version = describe or "unknown"

    info = {
        "version": version,
        "release": release,
        "describe": describe,
        "commit": commit,
        "short_commit": short_commit,
        "branch": branch,
        "dirty": dirty,
        "is_git": is_git,
        "source": "git" if is_git else "file",
    }
    _cache_set(_LOCAL_CACHE_KEY, info, _LOCAL_TTL)
    return info


def get_remote_commit(path=None, refresh: bool = False) -> str:
    """Return the current remote tip for the checked-out branch.

    Page renders use the cached value only.  ``refresh=True`` (the explicit
    "Check for updates" button / ``--check``) fetches the branch first so the
    local remote-tracking ref — and therefore the behind count — is current.
    ``git ls-remote`` is the fallback when a fetch is not possible.
    """
    if not getattr(settings, "AGENTONE_UPDATE_CHECK_ENABLED", True):
        return ""
    cached = _cache_get(_REMOTE_CACHE_KEY)
    if isinstance(cached, str) and not refresh:
        return cached
    if not refresh:
        return ""

    root = repo_path(path)
    branch = _git(["rev-parse", "--abbrev-ref", "HEAD"], root) or "main"
    _git(["fetch", "--quiet", "origin", branch], root, timeout=10)
    sha = _git(["rev-parse", f"origin/{branch}"], root) or ""

    if not sha:
        remote = _git(["ls-remote", "--exit-code", "--heads", "origin", branch], root, timeout=8) or ""
        if not remote:
            remote = _git(["ls-remote", "--exit-code", "origin", "HEAD"], root, timeout=8) or ""
        sha = remote.split()[0] if remote else ""

    _cache_set(_REMOTE_CACHE_KEY, sha, _REMOTE_TTL)
    return sha


def update_status(path=None, refresh: bool = False) -> dict:
    """Combine local and remote data for the Settings → System update card.

    ``available`` means the remote-tracking ref is genuinely ahead of HEAD;
    a locally ahead checkout is not reported as an available update.
    """
    local = get_version_info(path, refresh=refresh)
    remote = get_remote_commit(path, refresh=refresh)
    behind = 0
    if local["is_git"] and local["branch"] and local["branch"] != "HEAD":
        count = _git(
            ["rev-list", "--count", f"HEAD..origin/{local['branch']}"],
            repo_path(path),
            timeout=5,
        )
        if count and count.isdigit():
            behind = int(count)
    return {
        **local,
        "remote_commit": remote,
        "remote_short_commit": remote[:7] if remote else "",
        "behind": behind,
        "available": bool(remote and behind > 0),
    }


def clear_version_cache():
    """Drop cached metadata after a pull changed HEAD."""
    _cache_delete(_LOCAL_CACHE_KEY, _REMOTE_CACHE_KEY)
