"""Work collection tools for the workitems_assistant agent.

All tools are bound: the managed scope is the calling session's project
(global inbox when unbound). Listing the queue, filing new work, and
queue health belong here; working on ONE item (describe, move, split)
belongs to ``workitem_assistant``. Every tool returns a ``(bool, dict)``
tuple.
"""
from __future__ import annotations

from typing import Literal

from runtime.session.session import Session

ALL_STATUSES = ("backlog", "ready", "blocked", "done", "cancelled",
                "in_progress", "in_review")
PAGE_SIZE = 100


def _visible_items(_session: Session):
    """Work items in the session's project scope, highest priority first."""
    from runtime.workitems.workitems import Workitems

    return Workitems(parent_project=_session.get_project()).all()


def _resolve_agent(agent_name: str):
    """Find an AgentModel by name. Returns ``(agent, error)``."""
    from server.models.agents.agent import AgentModel

    if not (agent_name or "").strip():
        return None, None
    agent = AgentModel.objects.filter(name=agent_name.strip()).first()
    if agent is None:
        return None, f"No agent named '{agent_name}'. Use get_available_agents to list them."
    return agent, None


def list_workitems(
    _session: Session,
    status: Literal["backlog", "ready", "in_progress", "in_review", "blocked", "done", "cancelled"] = "",
    parent_id: int = 0,
    offset: int = 0,
    include_body: bool = True,
) -> tuple[bool, dict]:
    """List the work items in your managed project scope, highest priority first.

    The queue overview: what is queued, running, blocked, or done.
    Results include the requirement text (``body``) by default.

    Args:
        status: Filter to one status; omit for all.
        parent_id: If set, list only the direct children of this item.
        offset: How many matches to skip, for paging (100 per call).
        include_body: Set false to drop requirement text and fit more items.

    Returns:
        ``(True, {"status": "success", "items": [...], "count": int,
        "offset": int, "returned": int, "has_more": bool})`` or
        ``(False, {"status": "error", ...})``.
    """
    if status and status not in ALL_STATUSES:
        return False, {"status": "error", "message": f"Unknown status {status!r}. Use one of: {', '.join(ALL_STATUSES)}."}
    if offset < 0:
        return False, {"status": "error", "message": "offset cannot be negative."}

    items = _visible_items(_session)
    if status:
        items = items.filter(status=status)
    if parent_id:
        items = items.filter(parent_id=parent_id)

    count = items.count()
    page = list(items[offset : offset + PAGE_SIZE])
    return True, {
        "status": "success",
        "items": [(i.summarise_with_body() if include_body else i.summarise()) for i in page],
        "count": count,
        "offset": offset,
        "returned": len(page),
        "has_more": offset + len(page) < count,
    }


def workitems_stats(_session: Session) -> tuple[bool, dict]:
    """Count work items by status in your managed project scope.

    The queue health overview: how much is queued, running, blocked, or
    waiting on review — plus the items needing attention (blocked items
    and items whose verification attempts are exhausted).

    Returns:
        ``(True, {"status": "success", "by_status": {...}, "total": int,
        "needs_attention": [...]})`` or ``(False, {"status": "error", ...})``.
    """
    from server.models.workitems.work_item import MAX_VERIFY_ATTEMPTS

    try:
        items = list(_visible_items(_session))
    except Exception as e:
        return False, {"status": "error", "message": f"Could not list work items: {e}"}
    by_status: dict[str, int] = {}
    needs_attention = []
    for item in items:
        by_status[item.status] = by_status.get(item.status, 0) + 1
        if item.status == "blocked" or item.verify_attempts >= MAX_VERIFY_ATTEMPTS:
            needs_attention.append(item.summarise())
    return True, {
        "status": "success",
        "by_status": by_status,
        "total": len(items),
        "needs_attention": needs_attention,
    }


def create_workitem(
    _session: Session,
    title: str,
    body: str = "",
    assigned_agent: str = "",
    priority: int = 99,
    requires_verification: bool = False,
    status: Literal["backlog", "ready"] = "backlog",
) -> tuple[bool, dict]:
    """File a new work item in your managed project scope.

    A work item is a durable queue entry, not a to-do note: it outlives
    this turn, is dispatched by the scheduler (not by you), and can be
    checked by a reviewer. Creating it does NOT start it — use
    ``status="ready"`` to queue it for dispatch, or leave it ``backlog``
    while the plan forms. A "ready" item with no ``assigned_agent``
    cannot run and is moved to ``blocked``, so always name an agent if
    you want it to run. Driving ONE item afterwards belongs to
    ``workitem_assistant``.

    Args:
        title: Short imperative summary (required).
        body: The full requirement — what the executor receives as its
            prompt and what a reviewer judges against. State the
            deliverable and acceptance criteria explicitly.
        assigned_agent: Agent to run this. Required for dispatch.
        priority: Lower number = higher priority (0 = most urgent, 99 = lowest).
        requires_verification: True when the result needs a second opinion
            before it counts as done. A reviewer judges against ``body``;
            rejection blocks the item for a human.
        status: "backlog" (default) or "ready" (queue now).

    Returns:
        ``(True, {"status": "success", item...})`` with the created item's
        fields including ``id`` and ``body`` (``item_status`` is the
        item's lifecycle status), or
        ``(False, {"status": "error", ...})``.
    """
    from server.models.workitems.enums import WorkItemStatus
    from server.models.workitems.work_item import WorkItem
    from runtime.workitems.workitem_fsm import WorkItemStateMachine

    if status not in ("backlog", "ready"):
        return False, {"status": "error", "message": "status must be 'backlog' or 'ready' on create."}
    if not (title or "").strip():
        return False, {"status": "error", "message": "title is required."}
    agent_obj, error = _resolve_agent(assigned_agent)
    if error:
        return False, {"status": "error", "message": error}

    item = WorkItem.objects.create(
        project=_session.get_project(),
        title=title.strip(),
        body=body or "",
        assigned_agent=agent_obj,
        priority=priority,
        requires_verification=requires_verification,
        status=WorkItemStatus.BACKLOG,
    )

    if status == "ready":
        if not WorkItemStateMachine.mark_ready(item.pk):
            return False, {
                "status": "error",
                "message": f"Created work item {item.pk} but could not queue it. It is in 'backlog'; use workitem_assistant to retry.",
            }
        item.refresh_from_db()

    info = item.summarise_with_body()
    info["item_status"] = info.pop("status", "")
    info["status"] = "success"
    return True, info
