"""libtmux-backed persistent terminal manager.

One tmux session per ``TerminalSession`` row, named
``agentone-s<session_pk>-<slug>``. All functions are agent-only —
there is no browser input path (planning decision).

libtmux is imported lazily so a missing dependency (or missing ``tmux``
binary) produces a clean ``(False, {...})`` tool result instead of an
import-time crash. Unit tests stub ``_server`` / pane objects.
"""
from __future__ import annotations

import re
import shutil
import time
import uuid
from pathlib import Path
from typing import Any

from django.conf import settings
from django.utils import timezone

_NAME_RE = re.compile(r"[^a-z0-9-]+")

#: Prefix for every tmux session we own (used by orphan cleanup).
TMUX_PREFIX = "agentone-s"


def tmux_available() -> bool:
    """True when both the ``tmux`` binary and ``libtmux`` are importable."""
    if shutil.which("tmux") is None:
        return False
    try:
        import libtmux  # noqa: F401

        return True
    except ImportError:
        return False


def _server() -> Any:
    """Return a live ``libtmux.Server`` or raise a helpful ``RuntimeError``."""
    if shutil.which("tmux") is None:
        raise RuntimeError(
            "tmux binary not found. Install tmux (e.g. `brew install tmux`) "
            "to use persistent terminals."
        )
    try:
        from libtmux import Server
    except ImportError as exc:
        raise RuntimeError(
            "libtmux is not installed. Add it (`pip install libtmux`) "
            "to use persistent terminals."
        ) from exc
    return Server()


def slugify(name: str) -> str:
    """Normalise a terminal *name* to a tmux-safe slug."""
    slug = _NAME_RE.sub("-", (name or "default").lower()).strip("-")
    return slug[:48] or "default"


def tmux_name_for(session_pk: int, name: str) -> str:
    """Derive the tmux session name for a (session, terminal) pair."""
    return f"{TMUX_PREFIX}{session_pk}-{slugify(name)}"


def _default_cwd(session_model: Any) -> str:
    """Resolve the working directory for a new terminal."""
    try:
        version = session_model.latest_session_version
        workspace = getattr(version, "workspace", None)
        if workspace is not None and getattr(workspace, "path", None):
            resolved = str(Path(workspace.path).expanduser().resolve())
            if Path(resolved).is_dir():
                return resolved
    except Exception:  # pylint: disable=broad-exception-caught
        pass
    try:
        from runtime.session_folder import ensure_session_dir

        return str(ensure_session_dir(session_model.pk))
    except Exception:  # pylint: disable=broad-exception-caught
        return str(Path.home())


def _find_tmux_session(server: Any, tmux_name: str) -> Any | None:
    try:
        return server.find_where({"session_name": tmux_name})
    except Exception:  # pylint: disable=broad-exception-caught
        return None


def _active_pane(tmux_session: Any) -> Any:
    window = tmux_session.active_window
    return window.active_pane


def _capture(pane: Any) -> str:
    try:
        lines = pane.capture_pane()
    except TypeError:
        # Older libtmux versions take no kwargs / different call shape.
        lines = pane.capture_pane()  # type: ignore[no-untyped-call]
    if isinstance(lines, str):
        return lines
    return "\n".join(str(line) for line in (lines or []))


def _touch(row: Any) -> None:
    try:
        type(row).objects.filter(pk=row.pk).update(last_active_at=timezone.now())
    except Exception:  # pylint: disable=broad-exception-caught
        pass


def ensure_terminal(
    session_model: Any,
    name: str = "default",
    shell: str = "",
    cwd: str = "",
) -> Any:
    """Get-or-create the ``TerminalSession`` row *and* its tmux session."""
    from server.models.terminal import TerminalSession, TerminalStatus

    slug = slugify(name)
    tmux_name = tmux_name_for(session_model.pk, slug)
    target_cwd = cwd or _default_cwd(session_model)
    workspace = None
    try:
        workspace = getattr(session_model.latest_session_version, "workspace", None)
    except Exception:  # pylint: disable=broad-exception-caught
        workspace = None

    row, _ = TerminalSession.objects.get_or_create(
        session=session_model,
        name=slug,
        defaults={
            "tmux_session_name": tmux_name,
            "status": TerminalStatus.CREATED,
            "shell": shell,
            "cwd": target_cwd,
            "workspace": workspace,
        },
    )
    # Repair legacy/diverged rows (name was unique alone before).
    updates: dict[str, Any] = {}
    if row.tmux_session_name != tmux_name:
        updates["tmux_session_name"] = tmux_name
    if cwd:
        updates["cwd"] = target_cwd
    if shell:
        updates["shell"] = shell
    if updates:
        type(row).objects.filter(pk=row.pk).update(**updates)
        row.refresh_from_db()

    server = _server()
    tmux_session = _find_tmux_session(server, tmux_name)
    if tmux_session is None:
        kwargs: dict[str, Any] = {
            "session_name": tmux_name,
            "start_directory": target_cwd,
            "attach": False,
        }
        if shell:
            kwargs["default_command"] = shell
        tmux_session = server.new_session(**kwargs)
        try:
            pane = _active_pane(tmux_session)
            log_path = str(
                Path.home() / ".agentone" / "terminals" / f"{tmux_name}.log"
            )
            Path(log_path).parent.mkdir(parents=True, exist_ok=True)
            try:
                pane.pipe_pane(f"cat >> {log_path}")
            except Exception:  # pylint: disable=broad-exception-caught
                pass
            type(row).objects.filter(pk=row.pk).update(log_path=log_path)
            row.refresh_from_db()
        except Exception:  # pylint: disable=broad-exception-caught
            pass
    type(row).objects.filter(pk=row.pk).update(
        status=TerminalStatus.RUNNING, last_active_at=timezone.now()
    )
    row.refresh_from_db()
    return row


def exec_command(
    session_model: Any,
    command: str,
    name: str = "default",
    timeout: int = 60,
) -> dict[str, Any]:
    """Run *command* in the named persistent terminal and wait for exit.

    Sends the command plus a sentinel ``echo`` marker, then polls
    ``capture_pane`` until the marker appears or *timeout* elapses.
    """
    from server.models.terminal import TerminalStatus

    command = (command or "").strip()
    if not command:
        return {"status": "error", "stdout": "", "stderr": "Empty command.", "return_code": -1}
    timeout = max(1, min(int(timeout or 60), 600))

    row = ensure_terminal(session_model, name=name)
    server = _server()
    tmux_session = _find_tmux_session(server, row.tmux_session_name)
    if tmux_session is None:
        type(row).objects.filter(pk=row.pk).update(status=TerminalStatus.DEAD)
        raise RuntimeError(f"Terminal '{row.name}' died — re-run to recreate it.")
    pane = _active_pane(tmux_session)
    before = _capture(pane)
    token = uuid.uuid4().hex[:12]
    marker = f"__AGENTONE_DONE_{token}"
    pane.send_keys(f"{command}\necho {marker}=$?")
    deadline = time.time() + timeout
    output = before
    while time.time() < deadline:
        time.sleep(0.3)
        output = _capture(pane)
        if marker in output:
            break
    _touch(row)
    if marker not in output:
        return {
            "status": "timeout",
            "stdout": _tail(output[len(before):], 20000),
            "stderr": f"Timed out after {timeout}s waiting for command to finish.",
            "return_code": -1,
            "terminal": row.name,
        }
    new_text = output[len(before):] if len(output) >= len(before) else output
    return_code = -1
    stdout_lines: list[str] = []
    for line in new_text.splitlines():
        if marker in line:
            match = re.search(rf"{marker}=(-?\d+)", line)
            if match:
                return_code = int(match.group(1))
            break
        stdout_lines.append(line)
    # Drop the echoed command line itself when present.
    if stdout_lines and stdout_lines[0].strip() == command.strip().splitlines()[0][:200]:
        stdout_lines = stdout_lines[1:]
    stdout = _tail("\n".join(stdout_lines).strip(), _max_output_chars())
    return {
        "status": "success" if return_code == 0 else "error",
        "stdout": stdout,
        "stderr": "",
        "return_code": return_code,
        "terminal": row.name,
    }


def send_input(
    session_model: Any, text: str, name: str = "default", submit: bool = True
) -> dict[str, Any]:
    """Send keystrokes to a terminal (interactive CLIs, prompts)."""
    row = ensure_terminal(session_model, name=name)
    server = _server()
    tmux_session = _find_tmux_session(server, row.tmux_session_name)
    if tmux_session is None:
        from server.models.terminal import TerminalStatus

        type(row).objects.filter(pk=row.pk).update(status=TerminalStatus.DEAD)
        raise RuntimeError(f"Terminal '{row.name}' died — re-run to recreate it.")
    pane = _active_pane(tmux_session)
    pane.send_keys(text or "", enter=submit)
    _touch(row)
    time.sleep(0.3)
    return {"status": "success", "terminal": row.name, "submitted": submit}


def poll_output(
    session_model: Any, name: str = "default", lines: int = 200
) -> dict[str, Any]:
    """Read the visible buffer of a terminal without executing anything."""
    row = ensure_terminal(session_model, name=name)
    server = _server()
    tmux_session = _find_tmux_session(server, row.tmux_session_name)
    if tmux_session is None:
        from server.models.terminal import TerminalStatus

        type(row).objects.filter(pk=row.pk).update(status=TerminalStatus.DEAD)
        raise RuntimeError(f"Terminal '{row.name}' died — re-run to recreate it.")
    pane = _active_pane(tmux_session)
    text = _capture(pane)
    _touch(row)
    tail = "\n".join(text.splitlines()[-max(1, min(int(lines or 200), 2000)):])
    return {"status": "success", "terminal": row.name, "output": tail}


def list_terminals(session_model: Any) -> list[dict[str, Any]]:
    """List this session's terminal rows with liveness info."""
    from server.models.terminal import TerminalSession

    try:
        server = _server()
        live = {s.get("session_name") for s in server.list_sessions()}
    except Exception:  # pylint: disable=broad-exception-caught
        live = set()
    rows = []
    for row in TerminalSession.objects.filter(session=session_model).order_by("name"):
        rows.append(
            {
                "name": row.name,
                "status": row.status,
                "tmux": row.tmux_session_name,
                "alive": row.tmux_session_name in live,
                "cwd": row.cwd,
                "last_active_at": str(row.last_active_at) if row.last_active_at else None,
            }
        )
    return rows


def kill_terminal(session_model: Any, name: str = "default") -> dict[str, Any]:
    """Kill one named terminal (tmux session + row status)."""
    from server.models.terminal import TerminalSession, TerminalStatus

    slug = slugify(name)
    row = TerminalSession.objects.filter(session=session_model, name=slug).first()
    if row is None:
        return {"status": "error", "message": f"No terminal named '{slug}'."}
    try:
        server = _server()
        tmux_session = _find_tmux_session(server, row.tmux_session_name)
        if tmux_session is not None:
            tmux_session.kill_session()
    except Exception as exc:  # pylint: disable=broad-exception-caught
        return {"status": "error", "message": f"Kill failed: {exc}"}
    TerminalSession.objects.filter(pk=row.pk).update(status=TerminalStatus.DEAD)
    return {"status": "success", "terminal": slug}


def reap_idle_terminals(max_idle_seconds: int = 3600, limit: int = 10) -> int:
    """Kill terminals idle longer than *max_idle_seconds* (tick routine)."""
    from datetime import timedelta

    from server.models.terminal import TerminalSession, TerminalStatus

    if max_idle_seconds <= 0:
        return 0
    cutoff = timezone.now() - timedelta(seconds=max_idle_seconds)
    stale = list(
        TerminalSession.objects.filter(
            status=TerminalStatus.RUNNING, last_active_at__lt=cutoff
        ).order_by("last_active_at")[: max(1, limit)]
    )
    count = 0
    for row in stale:
        try:
            server = _server()
            tmux_session = _find_tmux_session(server, row.tmux_session_name)
            if tmux_session is not None:
                tmux_session.kill_session()
        except Exception:  # pylint: disable=broad-exception-caught
            pass
        TerminalSession.objects.filter(pk=row.pk).update(status=TerminalStatus.DEAD)
        count += 1
    return count


def cleanup_orphans() -> int:
    """Kill tmux sessions we own that have no live DB row (startup routine)."""
    from server.models.terminal import TerminalSession, TerminalStatus

    try:
        server = _server()
    except Exception:  # pylint: disable=broad-exception-caught
        return 0
    try:
        owned = [s for s in server.list_sessions() if str(s.get("session_name", "")).startswith(TMUX_PREFIX)]
    except Exception:  # pylint: disable=broad-exception-caught
        return 0
    live_names = set(
        TerminalSession.objects.filter(status=TerminalStatus.RUNNING).values_list(
            "tmux_session_name", flat=True
        )
    )
    count = 0
    for tmux_session in owned:
        try:
            name = tmux_session.get("session_name")
        except Exception:  # pylint: disable=broad-exception-caught
            continue
        if name not in live_names:
            try:
                tmux_session.kill_session()
                count += 1
            except Exception:  # pylint: disable=broad-exception-caught
                pass
    # Mark rows whose tmux session vanished as dead.
    try:
        present = {s.get("session_name") for s in server.list_sessions()}
    except Exception:  # pylint: disable=broad-exception-caught
        present = set()
    TerminalSession.objects.filter(status=TerminalStatus.RUNNING).exclude(
        tmux_session_name__in=present
    ).update(status=TerminalStatus.DEAD)
    return count


def _tail(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return "...[truncated]...\n" + text[-limit:]


def _max_output_chars() -> int:
    try:
        return int(getattr(settings, "TERMINAL_MAX_OUTPUT_CHARS", 20000))
    except (TypeError, ValueError):
        return 20000
