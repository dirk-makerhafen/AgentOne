"""Collect a finished synthesis result and continue the queue loop."""

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


def memory_collect_results(_session: Session, item_id: str = "", memory_root: str = "", result: Any = None, **kwargs: Any):
    """Mark *item_id* as done and continue processing if queue non-empty."""
    root = Path(memory_root) if memory_root else None
    if root is None:
        # search roots
        for _scope, r in _roots():
            q = _load_queue(r)
            if any(i.get("id") == item_id for i in q.get("items", [])):
                root = r
                break
    if root is None:
        return False, {"error": "item not found"}

    queue = _load_queue(root)
    items = queue.get("items", [])
    found = False
    for it in items:
        if it.get("id") == item_id:
            it["status"] = "done"
            it["result"] = str(result)[:500] if result is not None else ""
            found = True
    # drop done items older than retry? keep simple: remove done
    queue["items"] = [i for i in items if i.get("status") != "done"]
    _save_queue(root, queue)

    # retry handling: if a running item had attempts >=3, drop it
    # (handled in process step; here just log)
    pending = [i for i in queue.get("items", []) if i.get("status") == "pending"]
    if pending:
        try:
            proc = _session.get_tool("memory_process_queue")
            if proc is not None:
                proc.delay()
        except Exception:  # pylint: disable=broad-exception-caught
            pass
    return True, {"found": found, "remaining": len(pending)}
