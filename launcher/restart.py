"""Detect the service manager and schedule a detached restart after an update.

A restart must not be executed inline: the CLI command or Celery worker issuing
the update is itself part of the service being restarted.  We hand the command
to a short-lived helper that waits a few seconds, by which time the update job
has finished and written its final state.
"""

from __future__ import annotations

import json
import platform
import shutil
import subprocess
import sys
from pathlib import Path

from django.conf import settings

_SERVICE_NAMES = {
    "supervisor": "agentone-server",
    "systemd": "agentone_server.service",
    "launchd": "com.agentone.agentone_server",
}


def _configured() -> list[str] | None:
    command = getattr(settings, "AGENTONE_RESTART_COMMAND", None)
    if command:
        return [str(part) for part in command]
    return None


def _command_ok(command: list[str]) -> bool:
    try:
        proc = subprocess.run(command, capture_output=True, text=True, timeout=5, check=False)
    except (OSError, subprocess.SubprocessError):
        return False
    return proc.returncode == 0


def detect_restart_command(root=None) -> list[str] | None:
    """Return the restart command for the detected service manager, if any."""
    configured = _configured()
    if configured:
        return configured

    manager = str(getattr(settings, "AGENTONE_SERVICE_MANAGER", "auto") or "auto").lower()
    name = str(getattr(settings, "AGENTONE_SERVICE_NAME", "") or "")

    if manager in ("auto", "supervisor") and shutil.which("supervisorctl"):
        program = name or _SERVICE_NAMES["supervisor"]
        if _command_ok(["supervisorctl", "status", program]):
            return ["supervisorctl", "restart", program]

    if manager in ("auto", "systemd") and shutil.which("systemctl"):
        unit = name or _SERVICE_NAMES["systemd"]
        if _command_ok(["systemctl", "is-enabled", unit]):
            return ["systemctl", "restart", unit]

    if manager in ("auto", "launchd") and platform.system() == "Darwin" and shutil.which("launchctl"):
        label = name or _SERVICE_NAMES["launchd"]
        plist = Path("/Library/LaunchDaemons") / f"{label}.plist"
        if plist.exists():
            # ``kickstart -k`` keeps the job alive if it is already running.
            return ["launchctl", "kickstart", "-k", label]

    return None


def _restart_log() -> Path:
    from runtime.paths import log_base

    base = Path(getattr(settings, "LOG_DIR", None) or log_base())
    base.mkdir(parents=True, exist_ok=True)
    return base / "agentone-restart.log"


def request_restart(command: list[str], root=None, delay: int = 3) -> bool:
    """Spawn a detached helper that runs *command* after *delay* seconds."""
    args = [
        sys.executable,
        "-m",
        "launcher.restart_helper",
        "--delay", str(delay),
        "--command", json.dumps(list(command)),
        "--log-file", str(_restart_log()),
    ]
    # -m resolves packages relative to cwd; without this the helper fails
    # silently when the CLI is invoked by absolute path from another folder.
    cwd = str(Path(root).resolve()) if root else str(Path(settings.BASE_DIR).resolve())
    try:
        subprocess.Popen(
            args,
            cwd=cwd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    except OSError:
        return False
    return True
