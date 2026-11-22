#!/usr/bin/env python3
"""Cross-platform AgentOne bootstrap installer.

Self-contained on purpose: it runs *before* the repository and its dependencies
exist, so it uses only the standard library.  It can be run as a file from a
checkout or piped straight from GitHub::

    curl -fsSL https://raw.githubusercontent.com/dirk-makerhafen/AgentOne/main/install.py | python3 -
    # Windows PowerShell:
    #   irm https://raw.githubusercontent.com/dirk-makerhafen/AgentOne/main/install.py | python -

Environment overrides:
    AGENTONE_REPO_URL   repository to clone (default: HTTPS GitHub URL)
    AGENTONE_BRANCH     branch to check out (default: main)
    AGENTONE_DIR        target directory (default: ./AgentOne)

Flags:
    --dir DIR           target directory
    --branch BRANCH     branch to check out
    --skip-setup        do not run `manage.py server setup`
    --skip-browser      do not download the Camoufox browser build
    --skip-terminal-binaries
                        do not download psmux (Windows) for terminal_* tools
    --with-browser      deprecated no-op (the browser is installed by default)
"""

from __future__ import annotations

import argparse
import os
import shutil
import socket
import subprocess
import sys
import venv
from pathlib import Path

REPO_URL = os.environ.get("AGENTONE_REPO_URL", "https://github.com/dirk-makerhafen/AgentOne.git")
DEFAULT_BRANCH = os.environ.get("AGENTONE_BRANCH", "main")
DEFAULT_DIR = os.environ.get("AGENTONE_DIR", "")
MIN_PYTHON = (3, 10)
REDIS_HOST = "127.0.0.1"
REDIS_PORT = 6379


class InstallError(RuntimeError):
    """A fatal installation failure with a user-facing message."""


def info(message: str) -> None:
    print(f"==> {message}", flush=True)


def note(message: str) -> None:
    print(f"NOTE: {message}", file=sys.stderr, flush=True)


def _quote(path: Path) -> str:
    text = str(path)
    return f'"{text}"' if " " in text else text


def _run(args, *, cwd: Path | None = None, capture: bool = False) -> str:
    """Run a command with an argument list (never a shell)."""
    command = [str(part) for part in args]
    try:
        result = subprocess.run(
            command,
            cwd=str(cwd) if cwd else None,
            check=True,
            text=True,
            capture_output=capture,
        )
    except FileNotFoundError as exc:
        raise InstallError(f"Command not found: {command[0]}") from exc
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or "").strip()
        suffix = f": {detail}" if detail else ""
        raise InstallError(f"{' '.join(command)} failed (exit {exc.returncode}){suffix}") from exc
    return (result.stdout or "").strip()


def is_git_checkout(path: Path) -> bool:
    return (path / ".git").exists()


def venv_python(root: Path) -> Path:
    """Path to the interpreter inside the checkout's virtual environment."""
    if sys.platform == "win32":
        return root / "venv" / "Scripts" / "python.exe"
    return root / "venv" / "bin" / "python"


def ensure_venv(root: Path) -> Path:
    python = venv_python(root)
    if python.exists():
        info(f"Using existing virtual environment: {python.parent.parent}")
        return python

    info("Creating virtual environment")
    try:
        venv.EnvBuilder(with_pip=True).create(root / "venv")
    except (OSError, subprocess.CalledProcessError) as exc:
        raise InstallError(
            f"Could not create a virtual environment: {exc}. "
            "On Debian/Ubuntu install the python3-venv package first."
        ) from exc

    if not python.exists():
        raise InstallError(f"Virtual environment was created but {python} is missing.")
    return python


def clone_repo(target: Path, branch: str) -> None:
    if is_git_checkout(target):
        info(f"Using existing checkout: {target}")
        return
    if target.exists() and any(target.iterdir()):
        raise InstallError(f"Target directory is not empty and is not a git checkout: {target}")

    info(f"Cloning {REPO_URL} ({branch}) into {target}")
    _run(["git", "clone", "--branch", branch, REPO_URL, str(target)])
    if not is_git_checkout(target):
        raise InstallError(f"git clone reported success but {target} is not a checkout.")


def redis_reachable() -> bool:
    try:
        with socket.create_connection((REDIS_HOST, REDIS_PORT), timeout=0.5):
            return True
    except OSError:
        return False


def check_redis() -> None:
    if redis_reachable():
        return
    if shutil.which("redis-server"):
        note("Redis is installed but not responding on 127.0.0.1:6379.")
    else:
        note("Redis was not found. Install and start it before running AgentOne.")


def prepare_terminal_bins(target: Path) -> None:
    """Prefetch psmux and locate Git Bash on Windows (never fatal)."""
    if sys.platform != "win32":
        return
    sys.path.insert(0, str(target))
    try:
        from runtime.managed_binaries import ensure_tmux, resolve_bash  # pylint: disable=import-outside-toplevel
    except Exception as exc:  # pylint: disable=broad-exception-caught
        note(f"Could not load the managed-binary helper: {exc}")
        return
    try:
        path = ensure_tmux()
        if path:
            info(f"psmux installed at {path}")
        else:
            note("psmux was not downloaded; terminal_* tools will be unavailable until it is installed.")
    except Exception as exc:  # pylint: disable=broad-exception-caught
        note(f"Could not download psmux: {exc}")
    bash = resolve_bash()
    if bash:
        info(f"Using Git Bash at {bash}")
    else:
        note("Git Bash was not found. Install Git for Windows to enable terminal_* tools.")


def install(args: argparse.Namespace) -> None:
    target = Path(args.dir).expanduser().resolve() if args.dir else (Path.cwd() / "AgentOne").resolve()

    if sys.version_info < MIN_PYTHON:
        raise InstallError(f"AgentOne needs Python {MIN_PYTHON[0]}.{MIN_PYTHON[1]} or newer.")
    if not shutil.which("git"):
        raise InstallError("git is required but was not found on PATH.")

    clone_repo(target, args.branch)
    python = ensure_venv(target)

    info("Installing Python dependencies")
    _run([python, "-m", "pip", "install", "--upgrade", "pip"], cwd=target)
    requirements = target / "requirements.txt"
    if not requirements.exists():
        raise InstallError(f"requirements.txt is missing from {target}.")
    _run([python, "-m", "pip", "install", "-r", str(requirements)], cwd=target)

    if not args.skip_terminal_binaries:
        prepare_terminal_bins(target)

    if not args.skip_setup and not (target / "config" / "settings_local.py").exists():
        info("Interactive setup (database, Redis, listen address, TLS)")
        _run([python, "manage.py", "server", "setup"], cwd=target)

    info("Migrating database")
    _run([python, "manage.py", "migrate", "--noinput"], cwd=target)

    info("Collecting static files")
    _run([python, "manage.py", "collectstatic", "--noinput"], cwd=target)

    info("Reloading manifests")
    _run([python, "manage.py", "reload_all"], cwd=target)

    if args.with_browser:
        note("--with-browser is deprecated; the Camoufox browser is now installed by default.")
    if not args.skip_browser:
        info("Fetching Camoufox browser build (large download)")
        _run([python, "manage.py", "server", "browser", "fetch"], cwd=target)

    check_redis()

    python_cmd = str(python)
    activate = "venv\\Scripts\\activate" if sys.platform == "win32" else "source venv/bin/activate"
    print(f"""
AgentOne installed in {target}

Next steps:
  cd {_quote(target)}
  {_quote(python_cmd)} manage.py server run

  Activating the venv (`{activate}`) is optional: manage.py automatically
  re-runs itself with {_quote(python_cmd)} if you invoke plain `python3`.

Optional (needs admin/root):
  {_quote(python_cmd)} manage.py server service install

Future updates:
  {_quote(python_cmd)} manage.py server update
  ...or use Settings -> System -> Update AgentOne in the UI.
""")


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="install.py", description="Install AgentOne from GitHub.")
    parser.add_argument("--dir", default=DEFAULT_DIR, help="target directory (default: ./AgentOne)")
    parser.add_argument("--branch", default=DEFAULT_BRANCH, help="branch to check out (default: main)")
    parser.add_argument("--skip-setup", action="store_true", help="do not run the interactive setup wizard")
    parser.add_argument("--skip-browser", action="store_true", help="do not download the Camoufox browser build")
    parser.add_argument(
        "--with-browser",
        action="store_true",
        help="deprecated: the browser is installed by default (use --skip-browser to opt out)",
    )
    parser.add_argument(
        "--skip-terminal-binaries",
        action="store_true",
        help="do not download psmux (Windows) for terminal_* tools",
    )
    return parser.parse_args(argv)


def main(argv=None) -> int:
    install(parse_args(argv))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except InstallError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
