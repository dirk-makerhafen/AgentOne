"""The AgentOne self-update pipeline.

This is the single implementation behind both ``manage.py server update`` and
the UI-triggered Celery task.  Every step is logged through a callback so the
CLI can print it and the UI can show the same lines while the job runs.

Update order matters:

1. refuse a dirty worktree (a pull would otherwise clobber local edits),
2. fetch + fast-forward pull,
3. install dependencies,
4. migrate,
5. collectstatic,
6. reload manifests,
7. schedule a service restart (detached, so it survives this process).
"""

from __future__ import annotations

import contextlib
import io
import queue
import subprocess
import threading
import time
from pathlib import Path
from typing import Callable

from django.conf import settings

from launcher import runtime_env
from launcher.update_lock import UpdateLockError, update_lock

LogFn = Callable[[str, str], None]

_NOOP_LOG: LogFn = lambda message, level="info": None  # noqa: E731


class UpdateError(RuntimeError):
    """A fatal update failure; later steps must not run."""


def _log(log: LogFn, message: str, level: str = "info"):
    log(message, level)


def _git_capture(args, root: Path, description: str) -> str:
    proc = subprocess.run(
        ["git", *args],
        cwd=str(root),
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout).strip()
        raise UpdateError(f"{description} failed: {detail or f'exit {proc.returncode}'}")
    return proc.stdout.strip()


def _run_streaming(command, root: Path, description: str, log: LogFn, timeout: int = 1800):
    """Run *command*, streaming combined output into the update log."""
    _log(log, f"$ {' '.join(command)}")
    try:
        proc = subprocess.Popen(
            command,
            cwd=str(root),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
    except OSError as exc:
        raise UpdateError(f"{description} could not start: {exc}") from exc

    assert proc.stdout is not None  # always set by PIPE above
    lines = queue.Queue()

    def drain():
        for line in proc.stdout:
            lines.put(line.rstrip())
        lines.put(None)

    reader = threading.Thread(target=drain, daemon=True)
    reader.start()
    deadline = time.monotonic() + timeout
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            proc.kill()
            proc.wait()
            raise UpdateError(f"{description} timed out after {timeout}s")
        try:
            line = lines.get(timeout=min(remaining, 1.0))
        except queue.Empty:
            continue
        if line is None:
            break
        if line:
            _log(log, line)

    try:
        code = proc.wait(timeout=max(1, deadline - time.monotonic()))
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()
        raise UpdateError(f"{description} timed out after {timeout}s")

    if code != 0:
        raise UpdateError(f"{description} failed (exit {code})")
    _log(log, f"{description} complete.", "success")


def _django_command(name: str, log: LogFn, **kwargs):
    """Run a management command, forwarding its stdout line by line."""
    from django.core.management import call_command

    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        call_command(name, **kwargs)
    for line in buffer.getvalue().splitlines():
        if line.strip():
            _log(log, line)


def _pip_executable(root: Path) -> str:
    """Use the checkout's venv Python even if the caller forgot to activate it."""
    return runtime_env.current_python(root)


def run_update(
    path=None,
    *,
    allow_dirty: bool = False,
    force: bool = False,
    restart: bool = True,
    branch: str | None = None,
    log: LogFn | None = None,
) -> dict:
    """Update the installation at *path*, under a cross-process lock."""
    try:
        with update_lock():
            return _run_update_unlocked(
                path,
                allow_dirty=allow_dirty,
                force=force,
                restart=restart,
                branch=branch,
                log=log,
            )
    except UpdateLockError as exc:
        raise UpdateError(str(exc)) from exc


def _run_update_unlocked(
    path=None,
    *,
    allow_dirty: bool = False,
    force: bool = False,
    restart: bool = True,
    branch: str | None = None,
    log: LogFn | None = None,
) -> dict:
    """The pipeline itself. Callers must hold :func:`update_lock`."""
    log = log or _NOOP_LOG
    from runtime.version import clear_version_cache, get_version_info

    root = Path(path or getattr(settings, "BASE_DIR", Path.cwd())).resolve()
    if not (root / ".git").exists():
        raise UpdateError("Not a git repository. AgentOne must be installed via git for updates.")

    python = runtime_env.current_python(root)
    _log(log, f"Using Python: {python}")
    if runtime_env.venv_python(root) is None:
        _log(
            log,
            f"No virtual environment found in {root}; dependencies will be installed "
            "into the current interpreter. Re-run install.py to repair the setup.",
            "warning",
        )

    before = get_version_info(root, refresh=True)

    dirty = _git_capture(["status", "--porcelain"], root, "Checking worktree")
    if dirty and not allow_dirty:
        raise UpdateError(
            "You have uncommitted changes. Stash or commit them first, then retry "
            "(or use --allow-dirty on the CLI)."
        )

    current_branch = branch or before["branch"] or "main"
    _log(log, f"Fetching origin/{current_branch}...")
    _git_capture(["fetch", "--tags", "--quiet", "origin", current_branch], root, "Fetching remote")

    # Fetch and compare the same ref, so --branch cannot silently compare
    # against a stale remote-tracking ref for a different branch.
    ref = f"origin/{current_branch}"
    behind_raw = _git_capture(["rev-list", "--count", f"HEAD..{ref}"], root, "Comparing commits")
    try:
        behind = int(behind_raw or "0")
    except ValueError as exc:
        raise UpdateError(f"Unexpected commit count from git: {behind_raw!r}") from exc

    if behind == 0 and not force:
        _log(log, "Already up to date with remote.", "success")
        result = {
            "status": "up_to_date",
            "before": before["version"],
            "after": before["version"],
            "commit_before": before["commit"],
            "commit_after": before["commit"],
            "behind": 0,
            "restart": "skipped",
        }
        return result

    _log(log, f"Behind remote by {behind} commit(s). Pulling...")
    _git_capture(
        ["pull", "--quiet", "--ff-only", "origin", current_branch],
        root, "Fast-forward pull",
    )

    requirements = root / "requirements.txt"
    if requirements.exists():
        _log(log, "Updating Python dependencies...")
        _run_streaming(
            [_pip_executable(root), "-m", "pip", "install", "-r", str(requirements)],
            root, "pip install", log,
        )
    else:
        _log(log, "No requirements.txt found; skipping dependency install.", "warning")

    _log(log, "Applying database migrations...")
    try:
        _django_command("migrate", log, interactive=False, verbosity=1)
        _log(log, "Migrations applied.", "success")
    except Exception as exc:  # pylint: disable=broad-exception-caught
        raise UpdateError(f"Migration failed: {exc}") from exc

    if not getattr(settings, "DEBUG", False):
        _log(log, "Collecting static files...")
        try:
            _django_command("collectstatic", log, interactive=False, verbosity=1, clear=True)
            _log(log, "Static files collected.", "success")
        except Exception as exc:  # pylint: disable=broad-exception-caught
            raise UpdateError(f"collectstatic failed: {exc}") from exc
    else:
        _log(log, "DEBUG is on; skipping collectstatic (served from source).")

    _log(log, "Reloading manifests...")
    try:
        from registry.management.commands.reload_all import run_reload_all

        reload_result = run_reload_all(str(root))
        _log(log, reload_result.get("summary", "Manifests reloaded."))
        for error in reload_result.get("errors", []) or []:
            _log(log, f"  {error}", "warning")
    except Exception as exc:  # pylint: disable=broad-exception-caught
        # A bad manifest must not undo an otherwise successful code update.
        _log(log, f"Manifest reload failed: {exc}", "warning")

    clear_version_cache()
    after = get_version_info(root, refresh=True)

    result = {
        "status": "updated",
        "before": before["version"],
        "after": after["version"],
        "commit_before": before["commit"],
        "commit_after": after["commit"],
        "behind": behind,
        "restart": "not_configured",
    }

    if restart:
        from launcher.restart import detect_restart_command, request_restart

        command = detect_restart_command(root)
        if command:
            request_restart(command, root=root)
            _log(log, f"Scheduled service restart: {' '.join(command)}", "success")
            result["restart"] = "scheduled"
        else:
            _log(
                log,
                "No service manager detected. Restart AgentOne manually "
                "(or set AGENTONE_RESTART_COMMAND) to load the new code.",
                "warning",
            )
    else:
        result["restart"] = "skipped"

    _log(log, f"Update complete: {result['before']} → {result['after']}", "success")
    return result
