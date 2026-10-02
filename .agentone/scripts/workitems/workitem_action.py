"""Agent-facing CRUD for durable work items.

A work item is a *thing someone wants done* — it outlives the turn that
created it, can have children, and is dispatched by the scheduler rather than
by the calling agent.  This is the structured replacement for writing a task
into a todo list.

The scheduler owns dispatch and verification; this tool only shapes intent.
Creating an item does **not** start it — set ``status="ready"`` when you want it
dispatched, or leave it ``backlog`` while the plan is still forming.
"""

from __future__ import annotations

from typing import Any, Literal, Optional

from runtime.session.session import Session

# Statuses this tool accepts as a target for ``workitem_update``.  Mirrors
# ``server.models.workitems.enums.WorkItemStatus``; the FSM is authoritative and
# rejects anything illegal, so this list exists only to give the LLM a useful
# error before that happens.
UPDATABLE_STATUSES = (
    "backlog",
    "ready",
    "blocked",
    "done",
    "cancelled",
)

#: Every status an item can be in, including the two an agent cannot set
#: directly. workitem_list filters on these, so an unknown value is rejected
#: rather than matching nothing.
ALL_STATUSES = UPDATABLE_STATUSES + ("in_progress", "in_review")

#: Cap on items returned by one workitem_list call, so a large backlog cannot
#: blow up the conversation. Page with ``offset``; ``has_more`` says if there
#: is anything left.
PAGE_SIZE = 100


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------

def _resolve_project(_session: Session, project_name: str) -> tuple[Any, Optional[str]]:
    """Find a Project by name. Returns ``(project, error)``."""
    from server.models.project import Project

    if not project_name:
        return None, None
    project = Project.objects.filter(name=project_name).first()
    if project is None:
        return None, f"No project named {project_name!r}."
    return project, None


def _resolve_agent(_session: Session, agent_name: str) -> tuple[Any, Optional[str]]:
    """Find an AgentModel by name. Returns ``(agent, error)``."""
    from server.models.agents.agent import AgentModel

    if not agent_name:
        return None, None
    agent = AgentModel.objects.filter(name=agent_name).first()
    if agent is None:
        return None, f"No agent named {agent_name!r}. Use get_available_agents to list them."
    return agent, None


def _session_project(_session: Session) -> Any:
    """Return the project this session belongs to, or ``None``.

    ``Session`` exposes the model as ``.model``; the project FK on
    ``SessionModel`` is ``parent_project``.
    """
    model = getattr(_session, "model", None)
    return getattr(model, "parent_project", None) if model else None


def _visible_items(_session: Session, item_id: Optional[int] = None) -> Any:
    """Work items this session's project may see, highest priority first.

    Scoped to the session's project so a planner working on one project cannot
    read or hijack another project's queue.

    A session with *no* project is the unfiled inbox: it sees only items that
    themselves have no project, and creates them unfiled. Returning the whole
    table for that case would be a cross-project leak dressed up as a
    convenience — a session that lost its project association would silently
    gain read and write access to every project on the instance.
    """
    from server.models.workitems.work_item import WorkItem

    queryset = WorkItem.objects.all()
    project = _session_project(_session)
    queryset = queryset.filter(project=project) if project is not None else queryset.filter(project__isnull=True)
    if item_id is not None:
        queryset = queryset.filter(pk=item_id)
    return queryset.order_by("-priority", "created_at")


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

def workitem_create(
    _session: Session,
    title: str,
    body: str = "",
    assigned_agent: str = "",
    project: str = "",
    parent_id: int = 0,
    priority: int = 0,
    requires_verification: bool = False,
    status: Literal["backlog", "ready"] = "backlog",
) -> tuple[bool, dict]:
    """
    Create a durable work item — a task that outlives this turn.

    Use this for work you are being asked to *track*, not work you are doing
    right now. A work item sits in the backlog until something queues it, is
    then dispatched to an agent on its own, and is checked by a separate
    reviewer before it can count as done.

    How an item actually progresses (all of this happens without you):
        backlog -> ready -> in_progress -> (in_review) -> done
    A queued "ready" item is picked up within about 10 seconds by the
    scheduler. A "ready" item with no ``assigned_agent`` cannot run and is
    moved to ``blocked``, so always name an agent if you want it to run.

    Args:
        title: Short imperative summary, e.g. "Migrate billing to the new schema".
        body: The full requirement. This text is what the executing agent
            receives as its prompt, and what a reviewer judges against — so
            state the deliverable and any acceptance criteria explicitly.
            It is stored on the item and can be read back later.
        assigned_agent: Name of the agent to run this. Required for the item
            to ever dispatch; an item without one is blocked rather than
            guessed at.
        project: Project name. Defaults to the current session's project.
            Pass another name to file the item elsewhere; the item is then
            visible only in that project's sessions.
        parent_id: Optional id of a parent work item, for subtasks. The child
            is dispatched on its own like any other item — it is not run as
            part of its parent, and the parent does not wait for it.
        priority: Higher runs first among ready items. Defaults to 0.
        requires_verification: Set true when the result needs a second opinion
            before it counts as done — research, analysis, anything where
            "it ran without errors" is not evidence of quality. A separate
            reviewer agent judges the result against ``body``. Rejection sends
            the item back to blocked for a human, not straight back to ready.
        status: "backlog" (default, will not dispatch yet) or "ready" (queue it
            for dispatch now).

    Returns:
        The created item's fields, including its ``id`` and the ``body`` you
        supplied, so you can confirm what was recorded.
    """
    from server.models.workitems.enums import WorkItemStatus
    from server.models.workitems.work_item import WorkItem
    from runtime.events import publish_model_event

    if status not in ("backlog", "ready"):
        return False, {"error": "status must be 'backlog' or 'ready' on create."}

    if not title.strip():
        return False, {"error": "title is required."}

    project_obj, error = _resolve_project(_session, project)
    if error:
        return False, {"error": error}
    if project_obj is None:
        project_obj = _session_project(_session)

    agent_obj, error = _resolve_agent(_session, assigned_agent)
    if error:
        return False, {"error": error}

    parent_obj = None
    if parent_id:
        # Scope the parent to what this session may see, so an agent working one
        # project cannot graft a subtask onto another project's item.
        parent_obj = _visible_items(_session, parent_id).first()
        if parent_obj is None:
            return False, {"error": f"No work item with id {parent_id}."}

    item = WorkItem.objects.create(
        project=project_obj,
        parent=parent_obj,
        title=title.strip(),
        body=body or "",
        assigned_agent=agent_obj,
        priority=priority,
        requires_verification=requires_verification,
        status=WorkItemStatus.BACKLOG,
    )
    publish_model_event(item, "create")

    if status == "ready":
        from runtime.workitems.workitem_fsm import WorkItemStateMachine

        if not WorkItemStateMachine.mark_ready(item.pk):
            return False, {
                "error": f"Created work item {item.pk} but could not queue it for "
                f"dispatch. It is in 'backlog'; use workitem_update to retry."
            }
        # mark_ready updates via the queryset; re-read before summarising.
        item.refresh_from_db()

    return True, item.summarise_with_body()


def workitem_update(
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
    """
    Update a work item, or move it to a new status.

    Fields and status can be changed in one call. Leave a field out (or pass
    its default) to keep it unchanged.

    Legal status changes — anything else is refused with an error rather than
    silently ignored:
        backlog    -> ready, blocked, cancelled
        ready      -> backlog, blocked, cancelled
        in_progress-> done*, blocked, cancelled
        in_review  -> done (approves the review), backlog, blocked, cancelled
        blocked    -> ready, backlog, cancelled
        cancelled  -> ready, backlog
        done       -> (terminal, nothing here)
    *in_progress -> done* is refused while the item ``requires_verification``.
    The dispatch moves a verified item into ``in_review`` on its own, so an
    in_progress item that still needs review means the work is not finished;
    marking it done here would make the review flag decorative.
    "in_progress" and "in_review" are *not* settable: an agent's own dispatch
    moves an item into them, and a review verdict moves it out. Setting a
    status to the value the item already has is accepted as a no-op.

    Args:
        work_item_id: Id of the item to change.
        title: New title, if changing it.
        body: New requirement text, if changing it.
        assigned_agent: New agent name, or "" to leave unchanged. Note there is
            no way to unassign an item: pass a different agent, or cancel it.
        status: New status — one of backlog, ready, blocked, done, cancelled,
            as allowed by the table above. "ready" queues the item for
            dispatch; "blocked" requires a ``reason``.
        priority: New priority, if changing it.
        requires_verification: true/false, if changing it.
        reason: Short note recorded with the change — required when blocking
            an item, so whoever picks it up next knows why. Recorded on
            blocking, completion, cancellation and rejection; ignored by the
            other moves.

    Returns:
        The item's fields after the change, including its ``body``.

    On refusal the first element is ``False`` and the second is
    ``{"error": "..."}`` — read it, because a stale item id or an illegal
    status leaves the item exactly as it was.
    """
    item = _visible_items(_session, work_item_id).first()
    if item is None:
        return False, {"error": f"No work item with id {work_item_id} in this project."}

    if status and status not in UPDATABLE_STATUSES:
        return False, {
            "error": f"Cannot set status {status!r}. Use one of: {', '.join(UPDATABLE_STATUSES)}."
        }
    if status == "blocked" and not reason:
        return False, {"error": "Blocking an item requires a reason."}

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
        agent_obj, error = _resolve_agent(_session, assigned_agent)
        if error:
            return False, {"error": error}
        changes["assigned_agent"] = agent_obj

    # The status move runs *before* the field writes. A refused transition then
    # leaves the item completely untouched, instead of half-updated: title saved,
    # status silently unchanged, and a success return claiming both landed.
    if status:
        error = _apply_status(item, status, reason)
        if error:
            return False, {"error": error}
        # The FSM transitions with queryset .update(), so the in-memory copy
        # still holds the pre-transition status. Re-read before writing fields.
        item.refresh_from_db()

    if changes:
        from django.utils import timezone

        for field, value in changes.items():
            setattr(item, field, value)
        item.updated_at = timezone.now()
        item.save()
        if status:
            # Re-applying fields after the transition may have re-warmed a
            # stale in_review row, so settle on one row before summarising.
            item.refresh_from_db()

    return True, item.summarise_with_body()


def _apply_status(item: Any, status: str, reason: str) -> str:
    """Route a status change through the FSM.

    Every path goes through :class:`WorkItemStateMachine` so the work item keeps
    its one-writer guarantee; the tool never assigns ``status`` directly.

    Returns an error string, or "" on success.

    The FSM methods signal a lost race by returning ``False`` rather than
    raising, so every branch below checks that return value. Ignoring it would
    report success for a no-op — telling the agent it had re-queued an item
    that was still ``in_progress``, or cancelled a finished one.
    """
    from django.utils import timezone

    from runtime.workitems.workitem_fsm import InvalidTransition, WorkItemStateMachine

    if status == item.status:
        return ""

    try:
        if status == "ready":
            ok = WorkItemStateMachine.mark_ready(item.pk)
        elif status == "blocked":
            ok = WorkItemStateMachine.mark_blocked(item.pk, reason or "blocked by agent")
        elif status == "done":
            # Confirmation routes through whichever transition the current state
            # allows, so a human or agent confirming a review does not bypass it.
            if item.status == "in_review":
                ok = WorkItemStateMachine.approve(item.pk, reason or "confirmed by agent")
            else:
                if item.requires_verification:
                    # Marking this done here would make the review flag
                    # decorative. The dispatch already moved the item to
                    # in_review on its own if verification was due, so an
                    # in_progress item with verification pending means the
                    # work is not actually finished.
                    return (
                        f"Item {item.pk} is in_progress and requires verification, so "
                        f"it cannot be marked done directly. Finish the work and let "
                        f"the dispatch complete, or set requires_verification=false "
                        f"in a separate call if verification is genuinely not needed."
                    )
                # in_progress -> done is a legal transition. Note we must NOT use
                # report_success() here: that is in_progress -> blocked by design
                # (a dispatch costs one human action), so it would silently block a
                # finished item instead of completing it.
                ok = WorkItemStateMachine.transition(
                    item.pk,
                    item.status,
                    "done",
                    extra={"completed_at": timezone.now()},
                )
        elif status == "cancelled":
            ok = WorkItemStateMachine.cancel(item.pk, reason or "cancelled by agent")
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
            "or decided since you read it). Re-read it with workitem_list and retry."
        )
    return ""


def workitem_list(
    _session: Session,
    status: Literal[
        "backlog", "ready", "in_progress", "in_review", "blocked", "done", "cancelled"
    ] = "",
    project: str = "",
    parent_id: int = 0,
    offset: int = 0,
    include_body: bool = True,
) -> tuple[bool, dict]:
    """
    List work items, so you can see what is queued, running or blocked.

    This is the only way to read an item's requirement text back, so results
    include ``body`` by default.

    Args:
        status: Filter to one status; omit for all. Accepts backlog, ready,
            in_progress, in_review, blocked, done, cancelled. An unrecognised
            value is an error, not an empty list — a typo that silently
            returned nothing would look like "no work is outstanding".
        project: Project name; defaults to the current session's project.
        parent_id: If set, list only the direct children of this item.
        offset: How many matches to skip, for paging. ``count`` always reports
            the full number of matches, so page until offset >= count.
        include_body: Set false to drop the requirement text and fit more items
            in the response.

    Returns:
        ``{"items": [...], "count": <total matches>, "offset": <offset>,
        "returned": <len(items)>, "has_more": <bool>}``, highest priority
        first. At most 100 items are returned per call.
    """
    if status and status not in ALL_STATUSES:
        return False, {
            "error": f"Unknown status {status!r}. Use one of: {', '.join(ALL_STATUSES)}."
        }
    if offset < 0:
        return False, {"error": "offset cannot be negative."}

    items = _visible_items(_session)

    if status:
        items = items.filter(status=status)
    if parent_id:
        items = items.filter(parent_id=parent_id)
    if project:
        items = items.filter(project__name=project)

    count = items.count()
    page = list(items[offset : offset + PAGE_SIZE])
    return True, {
        "items": [
            (i.summarise_with_body() if include_body else i.summarise()) for i in page
        ],
        "count": count,
        "offset": offset,
        "returned": len(page),
        "has_more": offset + len(page) < count,
    }


def workitem_add_child(
    _session: Session,
    parent_id: int,
    title: str,
    body: str = "",
    assigned_agent: str = "",
    requires_verification: bool = False,
    priority: int = 0,
    status: Literal["backlog", "ready"] = "ready",
) -> tuple[bool, dict]:
    """
    Break a work item into a subtask.

    Use this when a requirement is really several pieces of work. Children are
    ordinary work items with ``parent`` set, so they dispatch independently and
    in parallel, and the subtree can be reported on collectively.

    Args:
        parent_id: Id of the parent work item.
        title: Short imperative summary of this piece of work.
        body: The full requirement for this piece. It is dispatched verbatim as
            the child's prompt, so it must stand alone — the child cannot see
            its parent's context. Without it the child gets only the title.
        assigned_agent: Agent to run this piece. Required for it to dispatch.
        requires_verification: true if this piece needs a second opinion.
        priority: Higher runs first.
        status: "ready" (default) to queue it, or "backlog" to hold it.

    Returns:
        The created child's fields, including its ``id`` and ``body``.
    """
    parent = _visible_items(_session, parent_id).first()
    if parent is None:
        return False, {"error": f"No work item with id {parent_id} in this project."}

    return workitem_create(
        _session,
        title=title,
        body=body,
        assigned_agent=assigned_agent,
        parent_id=parent_id,
        priority=priority,
        requires_verification=requires_verification,
        status=status,
    )
