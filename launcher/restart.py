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
    "windows": "agentone_server",
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


def _windows_service_exists(name: str) -> bool:
    """``sc query`` exits 0 even for missing services, so check its output."""
    try:
        proc = subprocess.run(
            ["sc", "query", name], capture_output=True, text=True, timeout=5, check=False
        )
    except (OSError, subprocess.SubprocessError):
        return False
    if proc.returncode != 0:
        return False
    output = (proc.stdout or "").lower()
    return "service_name" in output and "state" in output


def _windows_restart_command(name: str) -> list[str] | None:
    """Build a PowerShell stop/wait/start command (``sc`` has no restart verb)."""
    powershell = shutil.which("powershell") or shutil.which("pwsh")
    if not powershell:
        return None
    script = (
        "$ErrorActionPreference='Stop';"
        f"$n='{name}';"
        "for($i=0;$i -lt 40;$i++){"
        "try{Stop-Service -Name $n -Force -ErrorAction Stop}catch{};"
        "if((Get-Service -Name $n).Status -eq 'Stopped'){break};"
        "Start-Sleep -Milliseconds 500};"
        "Start-Service -Name $n"
    )
    return [
        powershell, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
        "-Command", script,
    ]


def detect_restart_command(root=None) -> list[str] | None:
    """Return the restart command for the detected service manager, if any."""
    configured = _configured()
    if configured:
        return configured

    manager = str(getattr(settings, "AGENTONE_SERVICE_MANAGER", "auto") or "auto").lower()
    name = str(getattr(settings, "AGENTONE_SERVICE_NAME", "") or "")

    # On Windows, check this first: supervisorctl/systemctl can be present via
    # WSL or Git Bash but are almost never the manager running AgentOne.
    if sys.platform == "win32" and manager in ("auto", "windows"):
        service = name or _SERVICE_NAMES["windows"]
        if _windows_service_exists(service):
            return _windows_restart_command(service)

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
    kwargs = {
        "cwd": cwd,
        "stdin": subprocess.DEVNULL,
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
    }
    if sys.platform == "win32":
        # start_new_session is POSIX-only and silently ignored on Windows.
        # Without these flags the helper dies with the service it restarts.
        kwargs["creationflags"] = (
            getattr(subprocess, "DETACHED_PROCESS", 0)
            | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
            | getattr(subprocess, "CREATE_NO_WINDOW", 0)
        )
    else:
        kwargs["start_new_session"] = True
    try:
        subprocess.Popen(args, **kwargs)
    except (OSError, ValueError):
        return False
    return True
