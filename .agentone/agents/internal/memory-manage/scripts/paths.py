"""Memory storage layout helpers."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from runtime.paths import agentone_home, ensure_private_dir
from runtime.session_folder import (
    _agentone_dir,
    _project_of,
    _safe_segment,
    _workspace_of,
)


#: Sidecar written while a memory node is being synthesized.  It is never
#: committed (see ``memory_lib.git.ensure_repo``) and only exists to stop
#: two dispatch passes from synthesizing the same node in parallel.
INFLIGHT_FILENAME = ".memory_inflight"


def inflight_path(node_dir: Any) -> Path:
    """Return the in-flight marker path for a memory node directory."""
    return Path(node_dir) / INFLIGHT_FILENAME


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


#: Canonical report filenames.  A session keeps at most one of each: the
#: newest message wins, so the synthesis prompt always sees a single, small
#: artifact per session instead of an ever-growing pile of timestamped files.
COMPACTION_REPORT = "compaction.md"
REFLECTION_REPORT = "reflections.md"

#: Legacy per-message report names (``compaction_20261031-103959_152472.md``).
_LEGACY_REPORT_RE = re.compile(r"^(?:compaction|reflections)_\d{8}-\d{6}(?:_\d+)?\.md$")


def report_filename(message: Any) -> str:
    """Return the canonical report filename for a reflection/compaction message."""
    try:
        from server.models.enums.message_enums import MessageType

        if getattr(message, "message_type", None) == MessageType.REFLECTION:
            return REFLECTION_REPORT
    except Exception:  # pylint: disable=broad-exception-caught
        pass
    return COMPACTION_REPORT


def legacy_report_files(session_dir: Any) -> list[Path]:
    """Return timestamped report files left over in *session_dir*.

    Only files with the old ``<kind>_<stamp>_<pk>.md`` shape are returned; the
    canonical ``compaction.md`` / ``reflections.md`` names never match.
    """
    directory = Path(session_dir)
    try:
        return [
            path
            for path in directory.glob("*.md")
            if _LEGACY_REPORT_RE.fullmatch(path.name)
        ]
    except OSError:
        return []


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
