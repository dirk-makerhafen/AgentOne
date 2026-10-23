from __future__ import annotations

import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from django.utils import timezone

from runtime.memory import paths as mempaths
from runtime.session.session import Session
from server.models.enums.message_enums import MessageType
from server.models.enums.session_enums import SessionType
from server.models.message import Message


def _lock_path() -> Path:
    from runtime.paths import agentone_home
    return agentone_home() / ".memory_update.lock"


def _acquire_lock() -> bool:
    p = _lock_path()
    try:
        if p.exists() and time.time() - p.stat().st_mtime < 300:
            return False
        p.unlink(missing_ok=True)
        p.write_text(str(time.time()), encoding="utf-8")
        return True
    except OSError:
        return False


def _release_lock() -> None:
    try:
        _lock_path().unlink(missing_ok=True)
    except OSError:
        pass


def _scope_key(session: Any) -> str:
    ws = getattr(session, "workspace", None)
    proj = session.get_project() if hasattr(session, "get_project") else None
    if ws is not None:
        return f"ws:{getattr(ws, 'pk', '')}"
    if proj is not None:
        return f"proj:{getattr(proj, 'pk', '')}"
    return "global"



def _files(root: Path, *patterns: str) -> list[str]:
    if not root.is_dir():
        return []
    out: list[str] = []
    for pattern in patterns:
        out.extend(str(p) for p in sorted(root.rglob(pattern)))
    return out


def _spawn(av: Any, session: Any, name: str, prompt: str) -> None:
    sv = av.get_or_create_session(
        name=name,
        workspace=session.workspace,
        session_type=SessionType.SUBSESSION,
        group_key="memory:aggregate",
        #settings_overrides={"tool_call_allowlist": ["final_result", "filesystem-read", "filesystem-write"]},
    )
    Session(session_model=sv.session, pinned_session_version=sv).add_user_message(prompt)
   

def update_memory(_session: Session, lookback_minutes: int = 5, **kwargs: Any):
    """Collect recent reflection/compaction messages and roll them up."""
    if not _acquire_lock():
        return False, {"skipped": "previous run still active"}

    try:
        cutoff = timezone.now() - timedelta(minutes=int(lookback_minutes or 5))
        qs = Message.objects.filter(
            message_type__in=[MessageType.REFLECTION, MessageType.COMPACTION],
            created_at__gte=cutoff,
        ).select_related("session", "session_version")

        groups: dict[tuple, dict[str, Any]] = {}
        scope_roots: dict[str, Path] = {}
        updated_tasks: set[tuple] = set()
        updated_agents: set[tuple] = set()

        for msg in qs:
            sv = getattr(msg, "session_version", None)
            session_model = getattr(sv, "session", None) if sv is not None else getattr(msg, "session", None)
            if session_model is None:
                continue
            try:
                rt = Session(session_model=session_model, pinned_session_version=sv)
            except Exception:  # pylint: disable=broad-exception-caught
                continue
            agent_pk = rt.get_version_model().agent_id
            if agent_pk is None:
                continue
            group_key =  ( rt.group_key or "").strip() or "default"
            scope = _scope_key(rt)
            root = mempaths.memory_root(rt)
            sess_dir = mempaths.session_memory_dir(
                mempaths.task_memory_dir(mempaths.agent_memory_dir(root, agent_pk), group_key),
                session_model.pk,
            )
            key = (scope, agent_pk, group_key, session_model.pk, root)
            groups.setdefault(key, {"dir": sess_dir, "items": []})["items"].append((msg, rt))
            scope_roots[scope] = root

        for key, data in groups.items():
            scope, agent_pk, group_key, session_pk, root = key
            sess_dir = data["dir"]
            mempaths.ensure_dir(sess_dir)
            for msg, _rt in data["items"]:
                text = ""
                try:
                    for part in msg.parts.order_by("pk"):
                        content = part.content.get() if part.content else None
                        if content:
                            text += str(content)
                except Exception:  # pylint: disable=broad-exception-caught
                    text = str(getattr(msg, "content", "") or "")
                mempaths.write_text(sess_dir / mempaths.report_filename(msg), text)
            updated_tasks.add((scope, agent_pk, group_key, root))
            updated_agents.add((scope, agent_pk, root))

        av = getattr(getattr(_session, "agent", None), "get_version_model", lambda: None)()
        if av is not None:
            for scope, agent_pk, group_key, root in updated_tasks:
                task_dir = mempaths.task_memory_dir(mempaths.agent_memory_dir(root, agent_pk), group_key)
                sources = _files(task_dir / "sessions", "*.md")
                _spawn(
                    av,
                    _session,
                    f"memory:task:{agent_pk}:{group_key}:{datetime.now().strftime('%Y.%m.%d-%H:%M:%S')}",
                    "Synthesize the following session report files into consolidated memory.\n"
                    f"Target directory: {task_dir}\n"
                    f"Source files:\n" + "\n".join(sources) + "\n\n"
                    "Write two files in the target directory using the filesystem tool:\n"
                    "  - memory.md : durable facts/knowledge to remember\n"
                    "  - reflection.md : consolidated self-improvement observations\n"
                    "Keep each under ~4000 characters. Then call final_result.",
                )

            for scope, agent_pk, root in updated_agents:
                agent_dir = mempaths.agent_memory_dir(root, agent_pk)
                task_root = agent_dir / "tasks"
                sources = _files(task_root, "memory.md") + _files(task_root, "reflection.md")
                _spawn(
                    av,
                    _session,
                    f"memory:agent:{agent_pk}:{datetime.now().strftime('%Y.%m.%d-%H:%M:%S')}",
                    "Synthesize the following task-level report files into agent-level memory.\n"
                    f"Target directory: {agent_dir}\n"
                    f"Source files:\n" + "\n".join(sources) + "\n\n"
                    "Write two files in the target directory using the filesystem tool:\n"
                    "  - memory.md\n  - reflection.md\n"
                    "Keep each under ~4000 characters. Then call final_result.",
                )

            for scope, root in scope_roots.items():
                agent_root = root / "agents"
                sources = _files(agent_root, "memory.md") + _files(agent_root, "reflection.md")
                _spawn(
                    av,
                    _session,
                    f"memory:scope:{scope}:{datetime.now().strftime('%Y.%m.%d-%H:%M:%S')}",
                    "Synthesize the following agent-level report files into scope-level memory.\n"
                    f"Target directory: {root}\n"
                    f"Source files:\n" + "\n".join(sources) + "\n\n"
                    "Write two files in the target directory using the filesystem tool:\n"
                    "  - memory.md\n  - reflection.md\n"
                    "Keep each under ~4000 characters. Then call final_result.",
                )

        _release_lock()
        return True, {
            "sessions": len(groups),
            "tasks": len(updated_tasks),
            "agents": len(updated_agents),
            "scopes": len(scope_roots),
        }
    except Exception as exc:  # pylint: disable=broad-exception-caught
        _release_lock()
        return False, {"error": str(exc)}
