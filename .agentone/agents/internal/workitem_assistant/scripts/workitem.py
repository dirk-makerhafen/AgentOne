"""Single-work-item tools for the workitem_assistant agent.

All tools are bound and take the item's ``work_item_id``: they describe
one item in full, edit its requirement or move it through its lifecycle,
and split it into subtasks — all inside the calling session's project
scope (global inbox when unbound). Collection operations (list, file new
work, queue health) belong to ``workitems_assistant``. Every tool returns
a ``(bool, dict)`` tuple.

Status moves route through :class:`WorkItemStateMachine` so the one-writer
guarantee holds — this module never assigns ``status`` directly. The legal
move table:

    backlog     -> ready, blocked, cancelled
    ready       -> backlog, blocked, cancelled
    in_progress -> done*, blocked, cancelled  (*refused when verification pending)
    in_review   -> done, backlog, blocked, cancelled
    blocked     -> ready, backlog, cancelled
    cancelled   -> ready, backlog
    done        -> (terminal)
"""
from __future__ import annotations

from typing import Any, Literal, Optional

from runtime.session.session import Session

UPDATABLE_STATUSES = ("backlog", "ready", "blocked", "done", "cancelled")


def _session_project(_session: Session) -> Any:
    """Return the project this session belongs to, or ``None`` for the inbox."""
    from runtime.session.sessions import Sessions

    return Sessions.project_of(_session)


def _visible_items(_session: Session, item_id: Optional[int] = None):
    """Work items in the session's project scope, highest priority first."""
    from runtime.session.sessions import Sessions
    from runtime.workitems.workitems import Workitems

    queryset = Workitems(parent_project=Sessions.project_of(_session)).all()
    if item_id is not None:
        queryset = queryset.filter(pk=item_id)
    return queryset


def _resolve_agent(agent_name: str):
    """Find an AgentModel by name. Returns ``(agent, error)``."""
    from server.models.agents.agent import AgentModel

    if not (agent_name or "").strip():
        return None, None
    agent = AgentModel.objects.filter(name=agent_name.strip()).first()
    if agent is None:
        return None, f"No agent named '{agent_name}'. Use get_available_agents to list them."
    return agent, None


def workitem_details(_session: Session, work_item_id: int) -> tuple[bool, dict]:
    """Show one work item in full: requirement, status, assignment, verification, and children.

    Args:
        work_item_id: Id of the item (required).

    Returns:
        ``(True, {item summary..., "verify_reason": str, "children": [...],
        "status": "success"})`` (``item_status`` is the item's lifecycle
        status) or ``(False, {"status": "error", "message": ...})``.
    """
    item = _visible_items(_session, work_item_id).first()
    if item is None:
        return False, {"status": "error", "message": f"No work item with id {work_item_id} in this project scope."}
    children = list(
        _visible_items(_session).filter(parent_id=item.pk).order_by("-priority", "created_at")
    )
    info = item.summarise_with_body()
    info["item_status"] = info.pop("status", "")
    info.update({
        "verify_reason": item.verify_reason or "",
        "children": [c.summarise() for c in children],
        "status": "success",
    })
    return True, info


def edit_workitem(
    _session: Session,
    work_item_id: int,
    title: str = "",
    body: str = "",
    assigned_agent: str = "",
    status: Literal["backlog", "ready", "blocked", "done", "cancelled"] = "",
    priority: Optional[int] = None,
    requires_verification: Optional[bool] = None,
    reason: str = "",
) -> tuple[bool, dict]:
    """Update one work item, or move it to a new status.

    Fields and status can be changed in one call; omit a field to keep it.
    Legal status moves (anything else is refused, leaving the item untouched):

        backlog     -> ready, blocked, cancelled
        ready       -> backlog, blocked, cancelled
        in_progress -> done*, blocked, cancelled (*refused while verification pending)
        in_review   -> done, backlog, blocked, cancelled
        blocked     -> ready, backlog, cancelled
        cancelled   -> ready, backlog
        done        -> (terminal)

    "in_progress" and "in_review" are not settable — dispatch moves items
    into them on its own. An item with ``requires_verification`` cannot be
    marked ``done`` directly; the reviewer has the final say.

    Args:
        work_item_id: Id of the item (required).
        title: New title, if changing it.
        body: New requirement text, if changing it.
        assigned_agent: New agent name (no way to unassign: pass a
            different agent, or cancel the item).
        status: New status, as allowed by the table above. "blocked"
            requires ``reason``.
        priority: New priority, if changing it.
        requires_verification: true/false, if changing it.
        reason: Note recorded with the change — required when blocking.

    Returns:
        ``(True, {"status": "success", item...})`` with the fields after
        the change (``item_status`` is the item's lifecycle status),
        or ``(False, {"status": "error", "message": ...})``.
    """
    item = _visible_items(_session, work_item_id).first()
    if item is None:
        return False, {"status": "error", "message": f"No work item with id {work_item_id} in this project scope."}
    if status and status not in UPDATABLE_STATUSES:
        return False, {
            "status": "error",
            "message": f"Cannot set status {status!r}. Use one of: {', '.join(UPDATABLE_STATUSES)}.",
        }
    if status == "blocked" and not reason:
        return False, {"status": "error", "message": "Blocking an item requires a reason."}

    changes: dict[str, Any] = {}
    if title:
        changes["title"] = title.strip()
    if body:
        changes["body"] = body
    if priority is not None:
        changes["priority"] = priority
    if requires_verification is not None:
        changes["requires_verification"] = requires_verification
    if assigned_agent:
        agent_obj, error = _resolve_agent(assigned_agent)
        if error:
            return False, {"status": "error", "message": error}
        changes["assigned_agent"] = agent_obj

    if status:
        error = _apply_status(item, status, reason)
        if error:
            return False, {"status": "error", "message": error}
        item.refresh_from_db()

    if changes:
        from django.utils import timezone

        for field, value in changes.items():
            setattr(item, field, value)
        item.updated_at = timezone.now()
        item.save()
        if status:
            item.refresh_from_db()

    info = item.summarise_with_body()
    info["item_status"] = info.pop("status", "")
    info["status"] = "success"
    return True, info


def _apply_status(item: Any, status: str, reason: str) -> str:
    """Route a status change through the FSM. Returns an error string, or "" on success."""
    from django.utils import timezone

    from runtime.workitems.workitem_fsm import InvalidTransition, WorkItemStateMachine

    if status == item.status:
        return ""
    try:
        if status == "ready":
            ok = WorkItemStateMachine.mark_ready(item.pk)
        elif status == "blocked":
            ok = WorkItemStateMachine.mark_blocked(item.pk, reason or "blocked by workitem_assistant")
        elif status == "done":
            if item.status == "in_review":
                ok = WorkItemStateMachine.approve(item.pk, reason or "confirmed by workitem_assistant")
            else:
                if item.requires_verification:
                    return (
                        f"Item {item.pk} is in_progress and requires verification, so "
                        f"it cannot be marked done directly. Finish the work and let "
                        f"the dispatch complete, or set requires_verification=false "
                        f"in a separate call if verification is genuinely not needed."
                    )
                ok = WorkItemStateMachine.transition(
                    item.pk, item.status, "done", extra={"completed_at": timezone.now()}
                )
        elif status == "cancelled":
            ok = WorkItemStateMachine.cancel(item.pk, reason or "cancelled by workitem_assistant")
        elif status == "backlog":
            ok = WorkItemStateMachine.transition(item.pk, item.status, "backlog")
        else:  # pragma: no cover — UPDATABLE_STATUSES is checked by the caller
            return f"Cannot set status {status!r}."
    except InvalidTransition as exc:
        return f"Cannot move a {item.status} item to {status}: {exc}"
    if not ok:
        return (
            f"Could not move item {item.pk} from {item.status!r} to {status!r}: "
            f"the item is no longer in {item.status!r} (it may have been dispatched "
            "or decided since you read it). Re-read it and retry."
        )
    return ""


def create_child_workitem(
    _session: Session,
    parent_id: int,
    title: str,
    body: str = "",
    assigned_agent: str = "",
    requires_verification: bool = False,
    priority: int = 99,
    status: Literal["backlog", "ready"] = "ready",
) -> tuple[bool, dict]:
    """Break one work item into a subtask in your managed project scope.

    Children are ordinary work items with ``parent`` set: they dispatch
    independently and in parallel, and the subtree can be reported on
    collectively.

    Args:
        parent_id: Id of the parent work item (required).
        title: Short imperative summary of this piece (required).
        body: The full requirement for this piece — dispatched verbatim as
            the child's prompt, so it must stand alone.
        assigned_agent: Agent to run this piece. Required for dispatch.
        requires_verification: true if this piece needs a second opinion.
        priority: Lower number = higher priority (0 = most urgent, 99 = lowest).
        status: "ready" (default, queue it) or "backlog" (hold it).

    Returns:
        ``(True, {"status": "success", child...})`` or
        ``(False, {"status": "error", "message": ...})``.
    """
    parent = _visible_items(_session, parent_id).first()
    if parent is None:
        return False, {"status": "error", "message": f"No work item with id {parent_id} in this project scope."}
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

    child = WorkItem.objects.create(
        project=_session_project(_session),
        parent=parent,
        title=title.strip(),
        body=body or "",
        assigned_agent=agent_obj,
        priority=priority,
        requires_verification=requires_verification,
        status=WorkItemStatus.BACKLOG,
    )
    if status == "ready":
        if not WorkItemStateMachine.mark_ready(child.pk):
            return False, {
                "status": "error",
                "message": f"Created child work item {child.pk} but could not queue it. It is in 'backlog'; use edit_workitem to retry.",
            }
        child.refresh_from_db()
    info = child.summarise_with_body()
    info["item_status"] = info.pop("status", "")
    info["status"] = "success"
    return True, info
