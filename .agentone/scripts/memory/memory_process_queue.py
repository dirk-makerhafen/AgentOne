"""Process a few items from the per-memory-root todo queue."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from runtime.memory import paths as mempaths
from runtime.session.session import Session
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


def _load_queue(root: Path) -> dict[str, Any]:
    p = root / ".memory_queue.json"
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError):
        data = {}
    if not isinstance(data, dict) or not isinstance(data.get("items"), list):
        data = {"items": []}
    return data


def _save_queue(root: Path, data: dict[str, Any]) -> None:
    mempaths.ensure_dir(root)
    (root / ".memory_queue.json").write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


SYNTH_TASK = {
    "task": "memory_synthesize_task",
    "agent": "memory_synthesize_agent",
    "scope": "memory_synthesize_scope",
}


def _select_pending(items: list[dict[str, Any]], max_items: int) -> list[dict[str, Any]]:
    buckets: dict[str, list[dict[str, Any]]] = {"task": [], "agent": [], "scope": []}
    for it in items:
        if it.get("status", "pending") != "pending":
            continue
        buckets.setdefault(it.get("bucket", "task"), []).append(it)

    selected: list[dict[str, Any]] = []
    seen: set[str] = set()

    # Priority order: task -> agent -> scope
    for bucket_name in ("task", "agent", "scope"):
        bucket_items = buckets.get(bucket_name, [])
        if not bucket_items:
            continue
        # largest first
        by_size = sorted(bucket_items, key=lambda x: int(x.get("change_score", 0)), reverse=True)
        # oldest first
        by_age = sorted(bucket_items, key=lambda x: str(x.get("created_at", "")))
        half = max(1, (max_items + 1) // 2)
        for it in by_size[:half] + by_age[:half]:
            iid = it.get("id")
            if iid in seen:
                continue
            seen.add(iid)
            selected.append(it)
            if len(selected) >= max_items:
                break
        if len(selected) >= max_items:
            break

    # If nothing selected but pending exists, take first pending
    if not selected:
        for it in items:
            if it.get("status", "pending") == "pending":
                selected.append(it)
                break
    return selected[:max_items]


def memory_process_queue(_session: Session, max_items: int = 2, **kwargs: Any):
    """Pop up to *max_items* pending items and dispatch synthesis tasks."""
    dispatched: list[str] = []
    for _scope, root in _roots():
        queue = _load_queue(root)
        items = queue.get("items", [])
        selected = _select_pending(items, max_items)
        if not selected:
            continue
        id_set = {it.get("id") for it in selected}
        for it in items:
            if it.get("id") in id_set:
                it["status"] = "running"
        _save_queue(root, queue)

        for it in selected:
            task_name = SYNTH_TASK.get(it.get("bucket", "task"), "memory_synthesize_task")
            bt = _session.get_task(task_name)
            if bt is None:
                # mark failed
                for qit in queue.get("items", []):
                    if qit.get("id") == it.get("id"):
                        qit["status"] = "pending"
                        qit["attempts"] = int(qit.get("attempts", 0)) + 1
                _save_queue(root, queue)
                continue
            kwargs_call = {
                "item_id": it.get("id"),
                "memory_root": it.get("memory_root"),
                "target_dir": it.get("target_dir"),
                "sources": it.get("sources", []),
                "changed_files": it.get("changed_files", []),
            }
            try:
                call = bt.apply_async(kwargs=kwargs_call)
                dispatched.append(str(it.get("id")))
            except Exception:  # pylint: disable=broad-exception-caught
                for qit in queue.get("items", []):
                    if qit.get("id") == it.get("id"):
                        qit["status"] = "pending"
                        qit["attempts"] = int(qit.get("attempts", 0)) + 1
                _save_queue(root, queue)

    return True, {"dispatched": dispatched}
