"""Collect memory inputs and maintain the per-memory-root todo queue."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from django.utils import timezone as dj_timezone

from runtime.memory import git as memgit
from runtime.memory import paths as mempaths
from runtime.memory.tree import extract_report_text
from runtime.session.session import Session
from server.models.enums.message_enums import MessageType
from server.models.message import Message
from server.models.project import Project
from server.models.workspace import WorkspaceModel


def _roots() -> list[tuple[str, Path]]:
    out: list[tuple[str, Path]] = []
    out.append(("global", mempaths.memory_root()))
    try:
        for p in Project.objects.all():
            out.append((f"proj:{p.pk}", mempaths.memory_root(project=p)))
    except Exception:  # pylint: disable=broad-exception-caught
        pass
    try:
        for w in WorkspaceModel.objects.all():
            out.append((f"ws:{w.pk}", mempaths.memory_root(workspace=w)))
    except Exception:  # pylint: disable=broad-exception-caught
        pass
    return out


def _queue_path(root: Path) -> Path:
    return root / ".memory_queue.json"


def _load_queue(root: Path) -> dict[str, Any]:
    p = _queue_path(root)
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError):
        data = {}
    if not isinstance(data, dict) or not isinstance(data.get("items"), list):
        data = {"items": []}
    return data


def _save_queue(root: Path, data: dict[str, Any]) -> None:
    mempaths.ensure_dir(root)
    _queue_path(root).write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def _pending_keys(queue: dict[str, Any]) -> set[tuple[Any, Any]]:
    return {(i.get("bucket"), i.get("target_dir")) for i in queue.get("items", [])
            if i.get("status", "pending") in ("pending", "running")}


def _enqueue(queue: dict[str, Any], item: dict[str, Any]) -> None:
    if (item.get("bucket"), item.get("target_dir")) in _pending_keys(queue):
        return
    item.setdefault("id", uuid.uuid4().hex)
    item.setdefault("status", "pending")
    item.setdefault("created_at", datetime.now(timezone.utc).isoformat())
    item.setdefault("attempts", 0)
    queue["items"].append(item)


def _files(root: Path, *patterns: str) -> list[str]:
    if not root.is_dir():
        return []
    out: list[str] = []
    for pattern in patterns:
        for p in sorted(root.rglob(pattern)):
            if ".git" in p.parts:
                continue
            out.append(str(p))
    return out


def memory_collect_inputs(_session: Session, lookback_minutes: int = 5, **kwargs: Any):
    """Collect recent reflection/compaction messages and update the todo queue."""
    import datetime as _dt

    cutoff = dj_timezone.now() - _dt.timedelta(minutes=int(lookback_minutes or 5))
    qs = Message.objects.filter(
        message_type__in=[MessageType.REFLECTION, MessageType.COMPACTION],
        created_at__gte=cutoff,
    ).select_related("session", "session_version")

    groups: dict[tuple, dict[str, Any]] = {}
    scope_roots: dict[str, Path] = {}

    for msg in qs:
        sv = getattr(msg, "session_version", None)
        session_model = getattr(sv, "session", None) if sv is not None else getattr(msg, "session", None)
        if session_model is None:
            continue
        try:
            rt = Session(session_model=session_model, pinned_session_version=sv)
        except Exception:  # pylint: disable=broad-exception-caught
            continue
        try:
            agent_pk = rt.get_version_model().agent_id
        except Exception:  # pylint: disable=broad-exception-caught
            continue
        if agent_pk is None:
            continue
        group_key = (getattr(rt, "group_key", "") or "").strip() or "default"
        ws = getattr(rt, "workspace", None)
        proj = rt.get_project() if hasattr(rt, "get_project") else None
        if ws is None and proj is None:
            scope = "global"
        elif ws is not None:
            scope = f"ws:{getattr(ws, 'pk', '')}"
        else:
            scope = f"proj:{getattr(proj, 'pk', '')}"
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
            text = extract_report_text(msg)
            if not text:
                continue
            mempaths.write_text(sess_dir / mempaths.report_filename(msg), text)

    _scope_set = set(scope_roots.keys())
    for scope, root in _roots():
        try:
            memgit.ensure_repo(root)
            if scope in _scope_set:
                session_head = memgit.commit_all(root, message="memory: session reports")
            else:
                session_head = memgit.commit_all(root, message="memory: sync")
        except OSError:
            continue
        queue = _load_queue(root)

        task_root = root / "agents"
        agent_dirs = sorted(task_root.glob("*")) if task_root.is_dir() else []

        # Task-level items
        for agent_dir in agent_dirs:
            if not agent_dir.is_dir():
                continue
            agent_pk = agent_dir.name
            tasks_dir = agent_dir / "tasks"
            if not tasks_dir.is_dir():
                continue
            for task_dir in sorted(tasks_dir.glob("*")):
                if not task_dir.is_dir():
                    continue
                old = memgit.load_processed(task_dir)
                rel = f"agents/{agent_pk}/tasks/{task_dir.name}/sessions"
                if old is None:
                    if not (task_dir / "memory.md").exists():
                        sources = _files(task_dir / "sessions", "*.md")
                        _enqueue(queue, {
                            "bucket": "task",
                            "scope": scope,
                            "memory_root": str(root),
                            "target_dir": str(task_dir),
                            "sources": sources,
                            "changed_files": sources,
                            "change_score": len(sources),
                        })
                else:
                    changed = memgit.changed_paths(root, old, session_head, rel_prefix=rel)
                    if changed:
                        sources = _files(task_dir / "sessions", "*.md")
                        _enqueue(queue, {
                            "bucket": "task",
                            "scope": scope,
                            "memory_root": str(root),
                            "target_dir": str(task_dir),
                            "sources": sources,
                            "changed_files": changed,
                            "change_score": len(changed),
                        })
                memgit.save_processed(task_dir, session_head)

        # Agent-level items
        for agent_dir in agent_dirs:
            if not agent_dir.is_dir():
                continue
            agent_pk = agent_dir.name
            old = memgit.load_processed(agent_dir)
            rel = f"agents/{agent_pk}/tasks"
            if old is None:
                if not (agent_dir / "memory.md").exists():
                    sources = _files(agent_dir / "tasks", "memory.md") + _files(agent_dir / "tasks", "reflection.md")
                    _enqueue(queue, {
                        "bucket": "agent",
                        "scope": scope,
                        "memory_root": str(root),
                        "target_dir": str(agent_dir),
                        "sources": sources,
                        "changed_files": sources,
                        "change_score": len(sources),
                    })
            else:
                changed = [p for p in memgit.changed_paths(root, old, session_head, rel_prefix=rel)
                           if p.endswith("memory.md") or p.endswith("reflection.md")]
                if changed:
                    sources = _files(agent_dir / "tasks", "memory.md") + _files(agent_dir / "tasks", "reflection.md")
                    _enqueue(queue, {
                        "bucket": "agent",
                        "scope": scope,
                        "memory_root": str(root),
                        "target_dir": str(agent_dir),
                        "sources": sources,
                        "changed_files": changed,
                        "change_score": len(changed),
                    })
            memgit.save_processed(agent_dir, session_head)

        # Scope-level item
        old = memgit.load_processed(root)
        if old is None:
            if not (root / "memory.md").exists():
                sources = _files(root / "agents", "memory.md") + _files(root / "agents", "reflection.md")
                _enqueue(queue, {
                    "bucket": "scope",
                    "scope": scope,
                    "memory_root": str(root),
                    "target_dir": str(root),
                    "sources": sources,
                    "changed_files": sources,
                    "change_score": len(sources),
                })
        else:
            changed = [p for p in memgit.changed_paths(root, old, session_head, rel_prefix="agents")
                       if p.endswith("memory.md") or p.endswith("reflection.md")]
            if changed:
                sources = _files(root / "agents", "memory.md") + _files(root / "agents", "reflection.md")
                _enqueue(queue, {
                    "bucket": "scope",
                    "scope": scope,
                    "memory_root": str(root),
                    "target_dir": str(root),
                    "sources": sources,
                    "changed_files": changed,
                    "change_score": len(changed),
                })
        memgit.save_processed(root, session_head)

        _save_queue(root, queue)

    return True, {"scopes": len(scope_roots), "sessions": len(groups)}
