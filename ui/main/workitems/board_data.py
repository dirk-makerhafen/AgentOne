"""Pure data helpers for the Work Items board.

Kept free of pyHtmlGui imports so both the sidebar list and the main board —
and the unit tests — can share one implementation of the three things that
must never drift apart:

* which status columns exist, in which order;
* how a queryset is scoped to the sidebar's selected project;
* which human actions are legal from a given status, and the single FSM entry
  point that applies them.

Nothing here writes ``WorkItem.status`` directly.  Every mutation in
:func:`apply_action` goes through
:class:`runtime.workitems.workitem_fsm.WorkItemStateMachine`, which is the
sole writer of the work-item FSM (``docs/work-items.md`` §2.2).
"""
from __future__ import annotations

from typing import Any, Iterable

from django.db.models import QuerySet

from server.models.workitems.enums import WorkItemStatus
from server.models.workitems.work_item import WorkItem

#: Board column order.  This is pipeline order, not ``WorkItemStatus`` order:
#: work flows backlog → ready → in_progress → in_review → done, and the two
#: off-path states (blocked, cancelled) sit at the end where they are noticed
#: rather than scrolled past.
STATUS_COLUMNS: tuple[tuple[str, str], ...] = (
    (WorkItemStatus.BACKLOG, "Backlog"),
    (WorkItemStatus.READY, "Ready"),
    (WorkItemStatus.IN_PROGRESS, "In Progress"),
    (WorkItemStatus.IN_REVIEW, "In Review"),
    (WorkItemStatus.BLOCKED, "Blocked"),
    (WorkItemStatus.DONE, "Done"),
    (WorkItemStatus.CANCELLED, "Cancelled"),
)

#: Statuses hidden by default so the board opens on live work.  Terminal
#: states are the ones nobody acts on.
TERMINAL_STATUSES: frozenset[str] = frozenset({
    WorkItemStatus.DONE,
    WorkItemStatus.CANCELLED,
})


# ---------------------------------------------------------------------------
# Queries
# ---------------------------------------------------------------------------
def scoped_queryset(
    project_id: int | None,
    include_terminal: bool = True,
) -> QuerySet:
    """Work items visible for *project_id*.

    ``project_id is None`` means "All projects" (the sidebar's null selection),
    which is the union of every project's items and the unfiled inbox.  It is
    deliberately *not* "items with no project" — an unfiled inbox needs its own
    filter, and the selector has no such affordance.
    """
    query = WorkItem.objects.all()
    if project_id is not None:
        query = query.filter(project_id=project_id)
    if not include_terminal:
        query = query.exclude(status__in=TERMINAL_STATUSES)
    return query.select_related("assigned_agent").order_by("-priority", "created_at")


def agent_filter_options(project_id: int | None) -> list[dict[str, Any]]:
    """Distinct assignees present in scope, for the filter select."""
    names = (
        scoped_queryset(project_id)
        .exclude(assigned_agent__isnull=True)
        .values_list("assigned_agent__name", flat=True)
        .distinct()
    )
    return [{"id": name, "label": name} for name in sorted(n for n in names if n)]


# ---------------------------------------------------------------------------
# Row shaping
# ---------------------------------------------------------------------------
def item_row(item) -> dict[str, Any]:
    """Flatten a WorkItem into the dict the templates read.

    Attribute access on the model is avoided so a test can pass a stub.
    """
    assigned = getattr(item, "assigned_agent", None)
    return {
        "id": getattr(item, "pk", None),
        "title": getattr(item, "title", "") or "",
        "body": (getattr(item, "body", "") or "").strip(),
        "status": getattr(item, "status", WorkItemStatus.BACKLOG),
        "status_label": status_label(getattr(item, "status", "")),
        "priority": getattr(item, "priority", 0) or 0,
        "project_id": getattr(item, "project_id", None),
        "parent_id": getattr(item, "parent_id", None),
        "assignee": getattr(assigned, "name", None) if assigned is not None else None,
        "requires_verification": bool(getattr(item, "requires_verification", False)),
        "verify_status": getattr(item, "verify_status", None) or "",
        "verify_reason": (getattr(item, "verify_reason", "") or "").strip(),
        "verify_attempts": getattr(item, "verify_attempts", 0) or 0,
        "dispatch_count": getattr(item, "dispatch_count", 0) or 0,
        "last_outcome": (getattr(item, "last_outcome", "") or "").strip(),
        "started_at": getattr(item, "started_at", None),
        "completed_at": getattr(item, "completed_at", None),
        "created_at": getattr(item, "created_at", None),
    }


def status_label(status: str) -> str:
    """Human label for a status value, falling back to the raw value."""
    for value, label in STATUS_COLUMNS:
        if value == status:
            return label
    return str(status).replace("_", " ").title()


def group_by_status(items: Iterable[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """Bucket item rows by status, pre-seeding every column with an empty list."""
    grouped: dict[str, list[dict[str, Any]]] = {value: [] for value, _ in STATUS_COLUMNS}
    for row in items:
        grouped.setdefault(row["status"], []).append(row)
    return grouped


def count_by_status(items: Iterable[dict[str, Any]]) -> dict[str, int]:
    counts = {value: 0 for value, _ in STATUS_COLUMNS}
    for row in items:
        counts[row["status"]] = counts.get(row["status"], 0) + 1
    return counts


# ---------------------------------------------------------------------------
# Human actions
# ---------------------------------------------------------------------------
#: ``status -> ((action_key, label, danger), ...)``.
#:
#: Deliberately excludes the transitions the scheduler owns: ``ready ->
#: in_progress`` (:meth:`WorkItemStateMachine.start_dispatch`) and
#: ``in_progress -> in_review`` (:meth:`begin_review`).  A human clicking
#: "Ready" wants the item *queued*, not executing; the tick dispatches it.
#: Manual ``done`` from ``in_progress`` is kept because that is the
#: "unverified work, human confirms" route documented in §7.3.
HUMAN_ACTIONS: dict[str, tuple[tuple[str, str, bool], ...]] = {
    WorkItemStatus.BACKLOG: (
        ("mark_ready", "Queue for dispatch", False),
        ("cancel", "Cancel", True),
    ),
    WorkItemStatus.READY: (
        ("defer", "Defer to backlog", False),
        ("block", "Block", True),
        ("cancel", "Cancel", True),
    ),
    WorkItemStatus.IN_PROGRESS: (
        ("finish", "Mark done", False),
        ("block", "Block", True),
    ),
    WorkItemStatus.IN_REVIEW: (
        ("approve", "Approve", False),
        ("reject", "Reject", False),
        ("resume", "Send back to agent", False),
        ("cancel", "Cancel", True),
    ),
    WorkItemStatus.BLOCKED: (
        ("mark_ready", "Requeue", False),
        ("cancel", "Cancel", True),
    ),
    WorkItemStatus.DONE: (
        ("reopen", "Reopen", False),
    ),
    WorkItemStatus.CANCELLED: (
        ("mark_ready", "Requeue", False),
    ),
}


def actions_for(item) -> list[dict[str, Any]]:
    """Legal human actions for *item* (model or row dict), as template dicts.

    The label for the direct-completion route changes on an item that still
    owes a review: the human is overriding the verification, not confirming
    it, and "Mark done" would claim the review happened. ``apply_action``
    records that as ``verify_status=SKIPPED`` either way, so the column
    renders the review badge as skipped rather than silently green.
    """
    status = item.get("status") if isinstance(item, dict) else getattr(item, "status", "")
    needs_review = (
        item.get("requires_verification")
        if isinstance(item, dict)
        else getattr(item, "requires_verification", False)
    )
    out = []
    for key, label, danger in HUMAN_ACTIONS.get(status, ()):
        if key == "finish" and needs_review:
            label = "Skip review and mark done"
        out.append({"key": key, "label": label, "danger": danger})
    return out


def apply_action(item_id: int, action_key: str, reason: str = "") -> tuple[bool, str]:
    """Apply a human *action_key* to item *item_id* through the FSM.

    Returns ``(ok, message)``.  The message is user-facing: either the error
    that blocked the change, or a short confirmation.

    Unknown keys and keys illegal from the item's current status are refused
    here rather than in the template, so a stale browser tab cannot drive a
    transition the FSM would not allow anyway.
    """
    from runtime.workitems.workitem_fsm import (
        InvalidTransition,
        WorkItemStateMachine,
    )
    from server.models.workitems.enums import WorkItemVerifyStatus

    item = WorkItem.objects.filter(pk=item_id).first()
    if item is None:
        return False, "Work item not found."

    status = item.status
    legal = {key for key, _, _ in HUMAN_ACTIONS.get(status, ())}
    if action_key not in legal:
        return False, f"'{action_key}' is not available from status '{status_label(status)}'."

    reason = (reason or "").strip()

    try:
        if action_key == "mark_ready":
            ok = WorkItemStateMachine.mark_ready(item_id)
        elif action_key == "cancel":
            ok = WorkItemStateMachine.cancel(item_id, reason)
        elif action_key == "block":
            ok = WorkItemStateMachine.mark_blocked(item_id, reason)
        elif action_key == "defer":
            ok = WorkItemStateMachine.transition(
                item_id, WorkItemStatus.READY, WorkItemStatus.BACKLOG,
                extra={"last_outcome": reason or ""},
            )
        elif action_key == "finish":
            # The direct-completion route for work nobody asked to verify.
            ok = WorkItemStateMachine.transition(
                item_id, WorkItemStatus.IN_PROGRESS, WorkItemStatus.DONE,
                extra={
                    "completed_at": _now(),
                    "last_outcome": reason or "",
                    "verify_status": WorkItemVerifyStatus.SKIPPED,
                },
            )
        elif action_key == "approve":
            ok = WorkItemStateMachine.approve(item_id, reason)
        elif action_key == "reject":
            # reject_or_escalate returns the applied verify_status, not a bool,
            # and its inner reject() is guarded on the verdict still being
            # undecided. A stale board can therefore no-op, so compare the
            # verdict before and after rather than assuming the write landed.
            before = (item.status, item.verify_status)
            WorkItemStateMachine.reject_or_escalate(item_id, reason)
            item.refresh_from_db()
            ok = (item.status, item.verify_status) != before
        elif action_key == "resume":
            ok = WorkItemStateMachine.transition(
                item_id, WorkItemStatus.IN_REVIEW, WorkItemStatus.IN_PROGRESS,
                extra={"verify_status": None, "verify_reason": ""},
            )
        elif action_key == "reopen":
            ok = WorkItemStateMachine.reopen(item_id)
        else:  # pragma: no cover — guarded by the ``legal`` check above
            return False, f"Unknown action '{action_key}'."
    except InvalidTransition as exc:
        return False, str(exc)

    if not ok:
        return False, "The item changed state since this board was rendered. Reload and try again."
    return True, f"Item #{item_id} updated."


def _now():
    from django.utils import timezone

    return timezone.now()
