"""Single source of truth for the AgentOne checkout's virtualenv.

``install.py`` creates ``venv/``, but a forgotten ``source venv/bin/activate``
used to make ``server run``, service installs and self-updates fall back to a
system Python with a different Django version.  Every entry point resolves its
interpreter through this module instead.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Set before re-exec so a broken venv cannot cause an endless exec loop.
REEXEC_MARKER = "AGENTONE_VENV_REEXEC"
# Escape hatch for tooling that deliberately wants the calling interpreter.
SKIP_REEXEC_ENV = "AGENTONE_SKIP_VENV_REEXEC"

_VENV_DIRS = ("venv", ".venv")


def repo_root() -> Path:
    """The directory containing manage.py (this module lives in launcher/)."""
    return Path(__file__).resolve().parents[1]


def venv_python(root: Path | str | None = None) -> Path | None:
    """Return the venv interpreter for *root*, or None if there is no venv."""
    base = Path(root) if root is not None else repo_root()
    candidates = [
        base / directory / "Scripts" / "python.exe"
        for directory in _VENV_DIRS
    ] + [
        base / directory / "bin" / "python"
        for directory in _VENV_DIRS
    ]
    return next((candidate for candidate in candidates if candidate.is_file()), None)


def in_venv() -> bool:
    """Whether this interpreter is already inside a virtual environment."""
    return bool(getattr(sys, "prefix", None)) and sys.prefix != getattr(
        sys, "base_prefix", sys.prefix
    )


def current_python(root: Path | str | None = None) -> str:
    """Interpreter to use for child processes (venv when available)."""
    python = venv_python(root)
    return str(python) if python else sys.executable


def scripts_dir(root: Path | str | None = None) -> Path | None:
    """The venv's Scripts/bin directory, if a venv exists."""
    python = venv_python(root)
    return python.parent if python else None


def prepend_scripts_to_path(root: Path | str | None = None) -> None:
    """Put the venv's Scripts/bin directory first on PATH (idempotent)."""
    directory = scripts_dir(root)
    if directory is None:
        return
    current = os.environ.get("PATH", "")
    parts = current.split(os.pathsep)
    if str(directory) not in parts:
        os.environ["PATH"] = (
            f"{directory}{os.pathsep}{current}" if current else str(directory)
        )


def ensure_venv(root: Path | str | None = None) -> bool:
    """Re-exec this process under the checkout's venv interpreter if needed.

    Returns True when this process is already running from a venv (or when no
    venv exists and the caller is deliberately using the current interpreter).
    Called by manage.py before Django is imported, so *every* management
    command -- setup, run, update, service install -- gets the same Python.
    """
    python = venv_python(root)
    if python is None:
        return False
    if in_venv():
        prepend_scripts_to_path(root)
        return True
    if os.environ.get(SKIP_REEXEC_ENV):
        return False
    marker = str(python)
    if os.environ.get(REEXEC_MARKER) == marker:
        return False

    env = os.environ.copy()
    env[REEXEC_MARKER] = marker
    env["VIRTUAL_ENV"] = str(python.parent.parent)
    env.pop("PYTHONHOME", None)
    scripts = str(python.parent)
    current_path = env.get("PATH", "")
    if scripts not in current_path.split(os.pathsep):
        env["PATH"] = f"{scripts}{os.pathsep}{current_path}" if current_path else scripts

    script = os.path.abspath(sys.argv[0])
    try:
        os.execve(str(python), [str(python), script, *sys.argv[1:]], env)
    except OSError as exc:
        print(
            f"WARNING: could not restart with {python} ({exc}); "
            f"using {sys.executable} instead.",
            file=sys.stderr,
        )
        return False
    return True  # pragma: no cover - execve replaces this process
