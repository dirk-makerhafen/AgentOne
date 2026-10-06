"""libtmux-backed persistent terminal manager.

One tmux session per ``TerminalSession`` row, named
``agentone-s<session_pk>-<slug>``. All functions are agent-only —
there is no browser input path (planning decision).

libtmux is imported lazily so a missing dependency (or missing ``tmux``
binary) produces a clean ``(False, {...})`` tool result instead of an
import-time crash. Unit tests stub ``_server`` / pane objects.
"""
from __future__ import annotations

import logging
import re
import shutil
import time
import uuid
from pathlib import Path
from typing import Any

from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)

_NAME_RE = re.compile(r"[^a-z0-9-]+")

#: Prefix for every tmux session we own (used by orphan cleanup).
TMUX_PREFIX = "agentone-s"

# Raw pty bytes that leak into captures / pipe-pane logs from interactive
# shells (zsh bracketed-paste toggles, prompt redraws, SGR colors).
_ANSI_OSC_RE = re.compile(r"\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)")
_ANSI_CSI_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
_ANSI_OTHER_RE = re.compile(r"\x1b(?:[PX^_][^\x1b]*?\x1b\\|[@-Z\\-_])")
_C0_EXCEPT_WS_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def clean_terminal_output(text: str) -> str:
    """Strip terminal control bytes from captured pty text.

    ``capture_pane`` (no ``-e``) already drops most attributes, but the
    ``pipe-pane`` log inspected by the UI viewer records the raw stream:
    ANSI CSI/OSC sequences, bracketed-paste toggles (``?2004h/l``), zsh
    prompt redraws (``[K``, ``[J``, reverse-video ``%``), backspace
    overstrikes from input echo, and ``\\r`` progress-bar redraws. This
    reduces all of that to plain readable text, preserving tabs,
    newlines, and line-internal spacing.
    """
    if not text:
        return ""
    text = _ANSI_OSC_RE.sub("", text)
    text = _ANSI_CSI_RE.sub("", text)
    text = _ANSI_OTHER_RE.sub("", text)
    # Backspace overstrikes from input echo ("l\\x08ls" → "ls").
    while "\x08" in text:
        reduced = re.sub(r"[^\n]\x08", "", text)
        if reduced == text:
            text = text.replace("\x08", "")
            break
        text = reduced
    # Lone carriage returns redraw the line (progress bars): keep the
    # final segment of each line; CRLF is just a newline.
    lines = []
    for line in text.replace("\r\n", "\n").split("\n"):
        lines.append(line.split("\r")[-1].rstrip())
    return "\n".join(lines).strip("\n")


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
    server = Server()
    _check_libtmux_api(server)
    return server


def _check_libtmux_api(server: Any) -> None:
    """Fail fast with a clear error when the libtmux API surface moved.

    libtmux removed ``find_where`` / ``list_sessions`` / ``.get()`` /
    ``kill_session`` / ``pipe_pane`` across the 0.x series; those used to
    surface here as a misleading "terminal died". Verify the surface we
    rely on instead.
    """
    missing = []
    sessions = getattr(server, "sessions", None)
    if sessions is None or not callable(getattr(sessions, "get", None)):
        missing.append("Server.sessions.get()")
    if not callable(getattr(server, "new_session", None)):
        missing.append("Server.new_session()")
    if missing:
        try:
            import libtmux

            version = getattr(libtmux, "__version__", "unknown")
        except Exception:  # pylint: disable=broad-exception-caught
            version = "unknown"
        raise RuntimeError(
            f"Incompatible libtmux version ({version}): missing "
            f"{', '.join(missing)}. Persistent terminals need a libtmux "
            "with the post-0.17 attribute API (e.g. `pip install -U libtmux`)."
        )


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
    """Find a tmux session by name (``None`` when absent).

    Unexpected libtmux errors are logged — never silently swallowed: a
    lookup failure used to masquerade as "terminal died".
    """
    try:
        return server.sessions.get(session_name=tmux_name, default=None)
    except Exception as exc:  # pylint: disable=broad-exception-caught
        logger.warning("tmux lookup for %s failed: %s", tmux_name, exc)
        return None


def _session_names(server: Any) -> set[str]:
    """Return the names of all live tmux sessions (empty set on error)."""
    try:
        return {s.session_name for s in server.sessions}
    except Exception as exc:  # pylint: disable=broad-exception-caught
        logger.warning("tmux session listing failed: %s", exc)
        return set()


def _live_tmux_session(server: Any, session_model: Any, row: Any) -> tuple[Any, Any]:
    """Return ``(row, tmux_session)`` for a live terminal, recreating once.

    When the tmux side is gone (externally killed, reboot, stale row) the
    terminal is recreated transparently instead of failing with "re-run
    to recreate it". Recreates at most once per call; a second miss means
    tmux itself is broken and raises.
    """
    from server.models.terminal import TerminalStatus

    tmux_session = _find_tmux_session(server, row.tmux_session_name)
    if tmux_session is not None:
        return row, tmux_session
    logger.info(
        "terminal '%s' (%s) missing in tmux — recreating",
        row.name, row.tmux_session_name,
    )
    type(row).objects.filter(pk=row.pk).update(status=TerminalStatus.DEAD)
    row = ensure_terminal(session_model, name=row.name)
    tmux_session = _find_tmux_session(server, row.tmux_session_name)
    if tmux_session is None:
        raise RuntimeError(
            f"Terminal '{row.name}' could not be (re)created in tmux — "
            "is the tmux server running (`tmux ls`)?"
        )
    return row, tmux_session


def _active_pane(tmux_session: Any) -> Any:
    window = tmux_session.active_window
    return window.active_pane


def _capture(pane: Any) -> str:
    lines = pane.capture_pane()
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
                # pipe-pane targets the pane via Pane.cmd's -t binding.
                pane.cmd("pipe-pane", "-o", f"cat >> {log_path}")
            except Exception as exc:  # pylint: disable=broad-exception-caught
                logger.warning("pipe-pane for %s failed: %s", tmux_name, exc)
            type(row).objects.filter(pk=row.pk).update(log_path=log_path)
            row.refresh_from_db()
        except Exception as exc:  # pylint: disable=broad-exception-caught
            logger.warning("terminal log setup for %s failed: %s", tmux_name, exc)
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

    A missing tmux session is recreated transparently (see
    :func:`_live_tmux_session`).
    """
    command = (command or "").strip()
    if not command:
        return {"status": "error", "stdout": "", "stderr": "Empty command.", "return_code": -1}
    timeout = max(1, min(int(timeout or 60), 600))

    row = ensure_terminal(session_model, name=name)
    server = _server()
    row, tmux_session = _live_tmux_session(server, session_model, row)
    pane = _active_pane(tmux_session)
    before = _capture(pane)
    token = uuid.uuid4().hex[:12]
    marker = f"__AGENTONE_DONE_{token}"
    pane.send_keys(f"{command}\necho {marker}=$?")
    deadline = time.time() + timeout
    output = before
    shell_exited = False
    while time.time() < deadline:
        time.sleep(0.3)
        output = _capture(pane)
        if marker in output:
            break
        # `exit` / `exec` / `kill $$` kill the shell itself, so the
        # sentinel never prints and the session vanishes. Fail fast with
        # a clear message instead of polling until timeout.
        if _find_tmux_session(server, row.tmux_session_name) is None:
            shell_exited = True
            break
    _touch(row)
    if shell_exited:
        from server.models.terminal import TerminalStatus

        type(row).objects.filter(pk=row.pk).update(status=TerminalStatus.DEAD)
        return {
            "status": "error",
            "stdout": _tail(clean_terminal_output(output), 20000),
            "stderr": (
                "The terminal's shell exited before the command finished "
                "(the command likely ended the shell itself, e.g. `exit`, "
                "`exec`, or killing its own PID). The terminal was closed; "
                "re-run to get a fresh one."
            ),
            "return_code": -1,
            "terminal": row.name,
            "shell_exited": True,
        }
    if marker not in output:
        return {
            "status": "timeout",
            "stdout": _tail(clean_terminal_output(output[len(before):]), 20000),
            "stderr": f"Timed out after {timeout}s waiting for command to finish.",
            "return_code": -1,
            "terminal": row.name,
        }
    new_text = output[len(before):] if len(output) >= len(before) else output
    result_re = re.compile(rf"{re.escape(marker)}=(-?\d+)")
    return_code = -1
    stdout_lines: list[str] = []
    for line in new_text.splitlines():
        match = result_re.search(line)
        if match:
            return_code = int(match.group(1))
            break
        if marker in line:
            # Echoed input line (the shell echoing our own
            # ``echo <marker>=$?``) — not command output, keep scanning.
            continue
        stdout_lines.append(line)
    # Drop the echoed command line itself when present.
    if stdout_lines and stdout_lines[0].strip() == command.strip().splitlines()[0][:200]:
        stdout_lines = stdout_lines[1:]
    stdout = _tail(clean_terminal_output("\n".join(stdout_lines).strip()), _max_output_chars())
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
    row, tmux_session = _live_tmux_session(server, session_model, row)
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
    row, tmux_session = _live_tmux_session(server, session_model, row)
    pane = _active_pane(tmux_session)
    text = _capture(pane)
    _touch(row)
    tail = "\n".join(text.splitlines()[-max(1, min(int(lines or 200), 2000)):])
    return {"status": "success", "terminal": row.name, "output": clean_terminal_output(tail)}


def list_terminals(session_model: Any) -> list[dict[str, Any]]:
    """List this session's terminal rows with liveness info."""
    from server.models.terminal import TerminalSession

    try:
        live = _session_names(_server())
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
            tmux_session.kill()
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
                tmux_session.kill()
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
        owned = [
            s for s in server.sessions
            if str(s.session_name).startswith(TMUX_PREFIX)
        ]
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
            name = tmux_session.session_name
        except Exception:  # pylint: disable=broad-exception-caught
            continue
        if name not in live_names:
            try:
                tmux_session.kill()
                count += 1
            except Exception:  # pylint: disable=broad-exception-caught
                pass
    # Mark rows whose tmux session vanished as dead.
    present = _session_names(server)
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
