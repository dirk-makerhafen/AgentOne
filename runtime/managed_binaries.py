"""Managed helper binaries for persistent terminals.

On POSIX, AgentOne uses the system ``tmux`` binary.  On native Windows the
backend is `psmux <https://github.com/psmux/psmux>`_: a self-contained Rust
build that installs a ``tmux.exe`` alias and speaks the tmux CLI/control
protocol, so libtmux keeps working unchanged.

psmux is distributed as a portable zip.  We download a pinned, SHA-256
verified release into ``~/.agentone/var/bin`` instead of running an installer:
no admin rights, no PATH edits, and `server update` never touches it.  The
managed path can be overridden with ``AGENTONE_TMUX_BINARY``; Git Bash can be
overridden with ``AGENTONE_BASH``.

This module deliberately stays standard-library only — ``install.py`` imports
it before the repo's dependencies are installed.
"""
from __future__ import annotations

import hashlib
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
import zipfile
from pathlib import Path

from runtime.file_lock import FileLockTimeout, file_lock
from runtime.paths import bin_dir

__all__ = [
    "ManagedBinaryError",
    "PSMUX_VERSION",
    "bin_dir",
    "ensure_tmux",
    "managed_bin_dir",
    "managed_tmux_path",
    "resolve_bash",
    "resolve_tmux_binary",
]

PSMUX_VERSION = "3.4.0"
_PSMUX_TAG = f"v{PSMUX_VERSION}"
_PSMUX_ZIP_SHA256 = {
    # sha256 of the release zip (from the GitHub releases API), not of the
    # extracted binary. Bump together with PSMUX_VERSION.
    "x64": "a66b6be7c13c6fa0dc3660a267b9e34eaa91a4eb7f07fbd55a0468018bd0f721",
    "arm64": "b123398e3b37408032bc268b4da6e7a6eab5b56461e0c3414914513a57a7a5cf",
    "x86": "b1d5f037befaa4dca94280bf0559531d9bbbc2d03e66cbb4f47961f82a8fc0c1",
}
_DOWNLOAD_TIMEOUT = 60
_FAILURE_MARKER = ".tmux.download.failed"
_FAILURE_TTL = 3600  # Don't retry a failed download on every tool call.

managed_bin_dir = bin_dir


class ManagedBinaryError(RuntimeError):
    """A managed binary could not be prepared."""


def managed_tmux_path() -> Path:
    """Return the managed tmux/psmux executable path (may not exist yet)."""
    return bin_dir() / ("tmux.exe" if os.name == "nt" else "tmux")


def _psmux_asset() -> tuple[str, str]:
    machine = platform.machine().lower().replace("-", "_")
    if machine in ("x86_64", "amd64"):
        arch = "x64"
    elif machine in ("aarch64", "arm64"):
        arch = "arm64"
    elif machine in ("x86", "i386", "i686"):
        arch = "x86"
    else:
        raise ManagedBinaryError(f"Unsupported Windows architecture for psmux: {platform.machine()!r}")
    asset = f"psmux-{_PSMUX_TAG}-windows-{arch}.zip"
    url = f"https://github.com/psmux/psmux/releases/download/{_PSMUX_TAG}/{asset}"
    return url, _PSMUX_ZIP_SHA256[arch]


def _download(url: str, destination: Path, sha256: str) -> None:
    hasher = hashlib.sha256()
    try:
        with urllib.request.urlopen(url, timeout=_DOWNLOAD_TIMEOUT) as response:
            with destination.open("wb") as handle:
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    hasher.update(chunk)
                    handle.write(chunk)
    except OSError as exc:
        raise ManagedBinaryError(f"Could not download psmux from {url}: {exc}") from exc
    actual = hasher.hexdigest()
    if actual != sha256:
        destination.unlink(missing_ok=True)
        raise ManagedBinaryError(f"psmux checksum mismatch (expected {sha256}, got {actual})")


def _tmux_member(archive: Path) -> str:
    with zipfile.ZipFile(archive) as zipped:
        for name in zipped.namelist():
            if Path(name).name.lower() == "tmux.exe":
                return name
    raise ManagedBinaryError("psmux archive does not contain tmux.exe")


def _download_failed_recently() -> bool:
    marker = bin_dir() / _FAILURE_MARKER
    try:
        return time.time() - marker.stat().st_mtime < _FAILURE_TTL
    except OSError:
        return False


def _mark_download_failed(exc: Exception) -> None:
    marker = bin_dir() / _FAILURE_MARKER
    try:
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text(f"{type(exc).__name__}: {exc}\n", encoding="utf-8")
    except OSError:
        pass


def ensure_tmux(*, force: bool = False) -> Path | None:
    """Download psmux into ``~/.agentone/var/bin`` and return its path.

    No-op on POSIX (the system tmux is used there). Failures raise
    :class:`ManagedBinaryError`; callers that can degrade gracefully should
    catch it. A per-host file lock keeps concurrent workers/installers from
    downloading the same release twice.
    """
    target = managed_tmux_path()
    if target.is_file() and not force:
        return target
    if sys.platform != "win32":
        return None

    url, digest = _psmux_asset()
    try:
        bin_dir().mkdir(parents=True, exist_ok=True)
        with file_lock(bin_dir() / ".tmux.download.lock", timeout=120):
            if target.is_file() and not force:
                return target
            # Keep the staging directory on the same filesystem so os.replace()
            # is atomic on Windows too.
            with tempfile.TemporaryDirectory(prefix="agentone-psmux-", dir=str(bin_dir())) as temp:
                temp_path = Path(temp)
                archive = temp_path / "psmux.zip"
                _download(url, archive, digest)
                member = _tmux_member(archive)
                staged = temp_path / target.name
                with zipfile.ZipFile(archive) as zipped, zipped.open(member) as source:
                    with staged.open("wb") as destination:
                        shutil.copyfileobj(source, destination)
                os.replace(staged, target)
    except (ManagedBinaryError, FileLockTimeout, OSError, zipfile.BadZipFile) as exc:
        _mark_download_failed(exc)
        if isinstance(exc, ManagedBinaryError):
            raise
        raise ManagedBinaryError(f"Could not install psmux: {exc}") from exc

    (bin_dir() / _FAILURE_MARKER).unlink(missing_ok=True)
    return target


def resolve_tmux_binary(*, auto_install: bool = True) -> str | None:
    """Return an executable tmux/psmux binary path, or ``None``.

    Resolution order: ``AGENTONE_TMUX_BINARY``, managed
    ``~/.agentone/var/bin/tmux[.exe]``, PATH (``tmux``, ``psmux``, ``pmux``),
    then an automatic psmux download on Windows.
    """
    override = os.environ.get("AGENTONE_TMUX_BINARY", "").strip()
    if override:
        path = Path(os.path.expanduser(override))
        if path.is_file():
            return str(path)
        return shutil.which(override)

    managed = managed_tmux_path()
    if managed.is_file():
        return str(managed)
    for name in ("tmux", "psmux", "pmux"):
        found = shutil.which(name)
        if found:
            return found

    if auto_install and sys.platform == "win32" and not _download_failed_recently():
        try:
            installed = ensure_tmux()
        except ManagedBinaryError:
            return None
        if installed is not None:
            return str(installed)
    return None


def resolve_bash() -> str | None:
    """Return a POSIX shell suitable for terminal commands, or ``None``.

    AgentOne's terminal sentinel uses ``$?`` and POSIX command syntax, so on
    Windows we prefer Git Bash over pwsh/cmd. Git for Windows is already an
    installer prerequisite; bash.exe usually lives outside PATH, so derive it
    from ``git --exec-path`` and the standard install locations.
    """
    override = os.environ.get("AGENTONE_BASH", "").strip()
    if override:
        path = Path(os.path.expanduser(override))
        if path.is_file():
            return str(path)
        return shutil.which(override)

    found = shutil.which("bash") or shutil.which("bash.exe")
    if found:
        return found
    if sys.platform != "win32":
        return None

    candidates: list[Path] = []
    git = shutil.which("git") or shutil.which("git.exe")
    if git:
        try:
            result = subprocess.run(
                [git, "--exec-path"],
                capture_output=True,
                text=True,
                timeout=10,
                check=True,
            )
            exec_path = Path(result.stdout.strip())
            if result.stdout.strip():
                for parent in (exec_path, *list(exec_path.parents)[:5]):
                    candidates.append(parent / "bin" / "bash.exe")
                    candidates.append(parent / "usr" / "bin" / "bash.exe")
        except (OSError, subprocess.SubprocessError, ValueError):
            pass

    roots = [Path(r"C:\Program Files\Git"), Path(r"C:\Program Files (x86)\Git")]
    local_appdata = os.environ.get("LOCALAPPDATA", "").strip()
    if local_appdata:
        roots.append(Path(local_appdata) / "Programs" / "Git")
    for root in roots:
        candidates.append(root / "bin" / "bash.exe")
        candidates.append(root / "usr" / "bin" / "bash.exe")

    for candidate in dict.fromkeys(candidates):
        if candidate.is_file():
            return str(candidate)
    return None
