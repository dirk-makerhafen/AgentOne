"""Memory storage layout helpers."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from runtime.paths import agentone_home, ensure_private_dir
from runtime.session_folder import (
    _agentone_dir,
    _project_of,
    _safe_segment,
    _workspace_of,
)


def _resolve_scope(session_or_pk: Any, *, workspace: Any = None, project: Any = None) -> tuple[Any, Any]:
    if isinstance(session_or_pk, (int, str)) and workspace is None and project is None:
        try:
            from server.models.sessions.session import SessionModel

            obj = SessionModel.objects.get(pk=int(session_or_pk))
            return _resolve_scope(obj)
        except Exception:  # pylint: disable=broad-exception-caught
            pass
    if session_or_pk is not None and not isinstance(session_or_pk, (int, str, Path)):
        if workspace is None:
            workspace = _workspace_of(session_or_pk)
        if project is None:
            project = _project_of(session_or_pk, workspace)
    return workspace, project


def memory_root(session_or_pk: Any = None, *, workspace: Any = None, project: Any = None) -> Path:
    ws, proj = _resolve_scope(session_or_pk, workspace=workspace, project=project)
    if ws is None and proj is None:
        base = agentone_home()
    else:
        base = _agentone_dir(ws, proj)
    return base / "memory"


def agent_memory_dir(root: Any, agent_pk: Any) -> Path:
    return Path(root) / "agents" / f"{agent_pk}"


def task_memory_dir(agent_dir: Any, group_key: Any) -> Path:
    group = str(group_key or "").strip() or "default"
    return Path(agent_dir) / "tasks" / f"task_{_safe_segment(group)}"


def session_memory_dir(task_dir: Any, session_pk: Any) -> Path:
    return Path(task_dir) / "sessions" / f"{session_pk}"


def ensure_dir(path: Any, mode: int = 0o700) -> Path:
    return ensure_private_dir(Path(path), mode)


def timestamp() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def write_text(path: Any, content: str) -> Path:
    path = Path(path)
    ensure_dir(path.parent)
    path.write_text(content, encoding="utf-8")
    return path


def read_text(path: Any) -> str:
    path = Path(path)
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return ""


def newest_mtime(directory: Any) -> float:
    directory = Path(directory)
    if not directory.is_dir():
        return 0.0
    mtimes = [p.stat().st_mtime for p in directory.rglob("*") if p.is_file() and ".git" not in p.parts]
    return max(mtimes) if mtimes else 0.0
