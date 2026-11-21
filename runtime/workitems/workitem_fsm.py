"""State machine for :class:`~server.models.workitems.work_item.WorkItem`.

Mirrors :mod:`runtime.tasks.call_fsm`: a ``_VALID_TRANSITIONS`` frozenset plus
named methods delegating to one atomic ``transition()`` guarded by
``WHERE status = <from>``.  A losing racer gets ``False`` back, never an
exception — the tick runs every 10s and must not log spurious errors.

The work layer deliberately does **not** reuse ``call_fsm`` or
``TaskCallStatusDetail``; the two lifecycles have different time scales
(``docs/work-items.md`` §2.2).
"""
from __future__ import annotations

from django.core.exceptions import FieldDoesNotExist
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from server.models.workitems.enums import WorkItemStatus, WorkItemVerifyStatus
from server.models.workitems.work_item import MAX_VERIFY_ATTEMPTS, WorkItem


# ---------------------------------------------------------------------------
# Valid transitions — (from, to)
# ---------------------------------------------------------------------------
_VALID_TRANSITIONS: frozenset[tuple[WorkItemStatus, WorkItemStatus]] = frozenset({
    # Intake: a captured item is not yet eligible for the ready queue.
    (WorkItemStatus.BACKLOG, WorkItemStatus.READY),
    (WorkItemStatus.BACKLOG, WorkItemStatus.CANCELLED),

    # Ready queue -> execution.
    (WorkItemStatus.READY, WorkItemStatus.IN_PROGRESS),

    # Deferral.  Note there is no ready -> ready: success goes to blocked, never
    # back to the queue, so an agent cannot re-dispatch itself forever
    # (docs/work-items.md §7.4).
    (WorkItemStatus.READY, WorkItemStatus.BLOCKED),
    (WorkItemStatus.READY, WorkItemStatus.BACKLOG),
    (WorkItemStatus.READY, WorkItemStatus.CANCELLED),

    # Terminal outcome of a dispatch.
    #
    # in_progress -> in_review is the verification route; in_progress -> blocked
    # covers both failure and "succeeded, awaiting human review".
    (WorkItemStatus.IN_PROGRESS, WorkItemStatus.IN_REVIEW),
    (WorkItemStatus.IN_PROGRESS, WorkItemStatus.BLOCKED),
    # Direct completion, used when a human confirms an unverified item.
    (WorkItemStatus.IN_PROGRESS, WorkItemStatus.DONE),
    (WorkItemStatus.IN_PROGRESS, WorkItemStatus.READY),
    (WorkItemStatus.IN_PROGRESS, WorkItemStatus.CANCELLED),

    # Reviewer verdicts.
    (WorkItemStatus.IN_REVIEW, WorkItemStatus.DONE),      # approve
    (WorkItemStatus.IN_REVIEW, WorkItemStatus.BLOCKED),   # reject
    (WorkItemStatus.IN_REVIEW, WorkItemStatus.IN_REVIEW),  # escalate: stay put
    # Human sends it back for another attempt: a fresh dispatch, not a state
    # the scheduler will never observe (see ``mark_ready``).
    (WorkItemStatus.IN_REVIEW, WorkItemStatus.READY),
    (WorkItemStatus.IN_REVIEW, WorkItemStatus.CANCELLED),

    # Human re-queue.
    (WorkItemStatus.BLOCKED, WorkItemStatus.READY),
    (WorkItemStatus.BLOCKED, WorkItemStatus.IN_PROGRESS),
    (WorkItemStatus.BLOCKED, WorkItemStatus.CANCELLED),

    # Reopen / restore.
    (WorkItemStatus.DONE, WorkItemStatus.READY),
    (WorkItemStatus.CANCELLED, WorkItemStatus.READY),
})


class InvalidTransition(Exception):
    """Raised when a transition pair is not in ``_VALID_TRANSITIONS``."""


def _snapshot_fields(item_id: int, fields: dict) -> dict:
    """Read the values a transitioning update is about to overwrite.

    The FSM uses raw ``QuerySet.update()`` calls for their atomic
    ``WHERE status = ...`` guards, so unlike ``atomic_update()`` it must capture
    the old side itself.  Without it a terminal transition publishes only the
    new filter value and terminal-list subscribers can never drop the row.
    """
    attnames = []
    known_attnames = {field.attname for field in WorkItem._meta.concrete_fields}
    for name in fields:
        try:
            attnames.append(WorkItem._meta.get_field(name).attname)
        except FieldDoesNotExist:
            # Some callers pass an attname (``root_task_id``) directly.
            if name in known_attnames:
                attnames.append(name)
    if not attnames:
        return {}
    return WorkItem.objects.filter(pk=item_id).values(*attnames).first() or {}


def _publish_item_event(
    item_id: int,
    action: str = "update",
    data: dict | None = None,
    previous: dict | None = None,
) -> None:
    """Publish a model event for a WorkItem after a transition.

    ``data`` carries the fields written by the transition (for updates) or
    the full row (for creates) so subscribers can react without re-reading.
    ``previous`` carries the pre-update values so old-side filter keys fire.
    """
    try:
        WorkItem.publish_by_pk(item_id, action, data=data, previous=previous)
    except Exception as e:  # pylint: disable=broad-exception-caught
        # A failed UI push must never fail the state transition itself.
        print(f"[workitems] model event publish failed for item {item_id}: {e}")


def _undecided_filter() -> Q:
    """Match rows whose verdict has not been decided yet.

    ``verify_status__in=[None, ...]`` would compile to ``IN (NULL, ...)``, which
    never matches a NULL column in SQL — the decision would silently never
    apply.  ``isnull=True`` is the only correct way to match a NULL.
    """
    return (
        Q(verify_status__isnull=True)
        | Q(verify_status="")
        | Q(verify_status=WorkItemVerifyStatus.PENDING)
    )


class WorkItemStateMachine:
    """Single entry point for all WorkItem status transitions.

    Every method returns ``True`` if the update was applied and ``False`` on a
    race condition (the row was already in a different state).
    """

    @staticmethod
    def transition(
        item_id: int,
        from_status: WorkItemStatus,
        to_status: WorkItemStatus,
        extra_filter: Q | None = None,
        extra: dict | None = None,
    ) -> bool:
        """Core atomic status transition.

        Parameters
        ----------
        item_id : int
            PK of the WorkItem.
        from_status, to_status : WorkItemStatus
            Expected current state and target state.
        extra_filter : Q | None
            Additional WHERE conditions (e.g. "only if not already decided").
        extra : dict | None
            Additional field updates (e.g. ``last_outcome``).

        Returns
        -------
        bool
            ``True`` if exactly one row was updated.

        Raises
        ------
        InvalidTransition
            If ``(from_status, to_status)`` is not in ``_VALID_TRANSITIONS``.
        """
        if (from_status, to_status) not in _VALID_TRANSITIONS:
            raise InvalidTransition(
                f"Invalid WorkItem transition: {from_status} → {to_status}"
            )

        query = WorkItem.objects.filter(pk=item_id, status=from_status)
        if extra_filter is not None:
            query = query.filter(extra_filter)

        fields: dict = {"status": to_status, "updated_at": timezone.now()}
        if extra:
            fields.update(extra)

        previous = _snapshot_fields(item_id, fields)
        updated = query.update(**fields) > 0
        if updated:
            _publish_item_event(item_id, "update", data=fields, previous=previous)
        return updated

    # ------------------------------------------------------------------
    # Intake
    # ------------------------------------------------------------------

    @staticmethod
    def mark_ready(item_id: int) -> bool:
        """``backlog``/``blocked``/``cancelled``/``in_review``/``done`` → ``ready``.

        A requeue — including reopening finished work or sending reviewed work
        back — means "do this work again", so the *previous* attempt's dispatch
        and verdict bookkeeping is cleared:

        * ``root_task`` — dispatch only selects items whose ``root_task`` is
          NULL, so leaving the old call in place would strand the item in
          ``ready`` forever with no way to re-run it.
        * ``verify_status``/``verify_reason`` — the tick only claims a NULL
          ``verify_status``, so a stale ``rejected``/``escalated`` would block
          the new attempt from ever being reviewed.

        ``verify_attempts`` and ``dispatch_count`` are deliberately *kept* so the
        reject/verify budget stays cumulative and the loop stays bounded.
        ``executor_session`` is kept so the new turn continues the same
        conversation rather than starting over.
        """
        # Multi-from handled in one atomic update, like enter_dependency_wait().
        fields = {
            "status": WorkItemStatus.READY,
            "root_task": None,
            "verify_status": None,
            "verify_reason": "",
            "completed_at": None,
            "updated_at": timezone.now(),
        }
        previous = _snapshot_fields(item_id, fields)
        updated = WorkItem.objects.filter(
            pk=item_id,
            status__in=[
                WorkItemStatus.BACKLOG,
                WorkItemStatus.BLOCKED,
                WorkItemStatus.CANCELLED,
                WorkItemStatus.IN_REVIEW,
                WorkItemStatus.DONE,
            ],
        ).update(**fields) > 0
        if updated:
            _publish_item_event(item_id, "update", data=fields, previous=previous)
        return updated

    @staticmethod
    def mark_blocked(item_id: int, reason: str = "") -> bool:
        """Defer an item, recording *reason* in ``last_outcome``.

        Accepts ``ready`` and ``in_progress`` — an unassigned item never
        dispatches, and a failed dispatch lands here.
        """
        return WorkItemStateMachine._block_from_ready_or_active(item_id, reason)

    @staticmethod
    def _block_from_ready_or_active(item_id: int, reason: str) -> bool:
        """``ready``/``in_progress`` → ``blocked`` (atomic multi-from)."""
        fields = {
            "status": WorkItemStatus.BLOCKED,
            "last_outcome": reason or "",
            "updated_at": timezone.now(),
        }
        previous = _snapshot_fields(item_id, fields)
        updated = WorkItem.objects.filter(
            pk=item_id,
            status__in=[WorkItemStatus.READY, WorkItemStatus.IN_PROGRESS],
        ).update(**fields) > 0
        if updated:
            _publish_item_event(item_id, "update", data=fields, previous=previous)
        return updated

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    @staticmethod
    def start_dispatch(item_id: int, **fields) -> bool:
        """``ready`` → ``in_progress``, recording the dispatch's provenance.

        ``fields`` carries ``executor_session``, ``started_at``,
        ``dispatch_count`` and (possibly) ``root_task``.
        """
        extra = dict(fields)
        extra.setdefault("started_at", timezone.now())
        return WorkItemStateMachine.transition(
            item_id, WorkItemStatus.READY, WorkItemStatus.IN_PROGRESS, extra=extra
        )

    @staticmethod
    def attach_root_task(item_id: int, root_task_id: int) -> bool:
        """Record the turn's root ATC once the dispatch has created it.

        Split from :meth:`start_dispatch` because ``ingest_user_message`` is
        dispatched asynchronously: the ``process_turn`` call does not exist yet
        when the tick first moves the item to ``in_progress``.  Writes without
        a status change, so it is safe to retry on the next tick.
        """
        fields = {"root_task_id": root_task_id, "updated_at": timezone.now()}
        previous = _snapshot_fields(item_id, fields)
        updated = (
            WorkItem.objects.filter(pk=item_id, root_task__isnull=True)
            .update(**fields)
            > 0
        )
        if updated:
            _publish_item_event(item_id, "update", data=fields, previous=previous)
        return updated

    @staticmethod
    def report_success(item_id: int, outcome: str = "") -> bool:
        """``in_progress`` → ``blocked`` — finished, awaiting human review.

        Deliberately *not* a re-queue: one dispatch costs one human action
        (``docs/work-items.md`` §7.4).
        """
        return WorkItemStateMachine.transition(
            item_id,
            WorkItemStatus.IN_PROGRESS,
            WorkItemStatus.BLOCKED,
            extra={"last_outcome": outcome or ""},
        )

    @staticmethod
    def report_failure(item_id: int, reason: str = "") -> bool:
        """``in_progress`` → ``blocked``, recording the failure reason."""
        return WorkItemStateMachine.transition(
            item_id,
            WorkItemStatus.IN_PROGRESS,
            WorkItemStatus.BLOCKED,
            extra={"last_outcome": reason or ""},
        )

    @staticmethod
    def begin_review(item_id: int, outcome: str = "") -> bool:
        """``in_progress`` → ``in_review`` — hand off to the agent reviewer."""
        return WorkItemStateMachine.transition(
            item_id,
            WorkItemStatus.IN_PROGRESS,
            WorkItemStatus.IN_REVIEW,
            extra={"last_outcome": outcome or ""},
        )

    # ------------------------------------------------------------------
    # Verdicts
    # ------------------------------------------------------------------

    @staticmethod
    def approve(item_id: int, reason: str = "") -> bool:
        """``in_review`` → ``done``, recording the approval.

        Guarded on ``verify_status`` being unset or ``pending`` so a duplicate
        verdict (retry of the reviewer's tool call) cannot overwrite a human's
        decision.
        """
        return WorkItemStateMachine.transition(
            item_id,
            WorkItemStatus.IN_REVIEW,
            WorkItemStatus.DONE,
            extra_filter=_undecided_filter(),
            extra={
                "verify_status": WorkItemVerifyStatus.APPROVED,
                "verify_reason": reason or "",
                "completed_at": timezone.now(),
                "last_outcome": reason or "",
            },
        )

    @staticmethod
    def reject(item_id: int, reason: str = "") -> bool:
        """``in_review`` → ``blocked`` and consume one verify attempt.

        The caller is responsible for honouring ``MAX_VERIFY_ATTEMPTS`` — see
        :meth:`reject_or_escalate`, which does both in one step.
        """
        return WorkItemStateMachine.transition(
            item_id,
            WorkItemStatus.IN_REVIEW,
            WorkItemStatus.BLOCKED,
            extra_filter=_undecided_filter(),
            extra={
                "verify_status": WorkItemVerifyStatus.REJECTED,
                "verify_reason": reason or "",
                "last_outcome": reason or "",
            },
        )

    @staticmethod
    def escalate(item_id: int, reason: str = "") -> bool:
        """``in_review`` → ``in_review`` (stay) for a human to decide.

        Also used when the reject budget is exhausted, so the item parks with
        a human instead of collecting rejection after rejection.
        """
        return WorkItemStateMachine.transition(
            item_id,
            WorkItemStatus.IN_REVIEW,
            WorkItemStatus.IN_REVIEW,
            extra_filter=_undecided_filter(),
            extra={
                "verify_status": WorkItemVerifyStatus.ESCALATED,
                "verify_reason": reason or "",
            },
        )

    @staticmethod
    def reject_or_escalate(item_id: int, reason: str = "") -> str | None:
        """Apply a rejection while honouring the verify-attempt bound.

        Returns the verify_status actually written: ``"rejected"`` while
        budget remains, ``"escalated"`` once ``MAX_VERIFY_ATTEMPTS`` is spent,
        or ``None`` when the item was no longer awaiting an undecided review.
        Without this bound a reviewer that keeps rejecting would let a human
        re-queue indefinitely and the item would ping-pong forever
        (``docs/work-items.md`` §8.5).

        The attempt counter and the status change are written by one atomic,
        conditional update under a row lock.  Incrementing first and then
        calling :meth:`reject` let a stale/racing verdict consume budget
        without changing the item, eventually escalating over a history that
        never happened.
        """
        with transaction.atomic():
            item = (
                WorkItem.objects.select_for_update().filter(pk=item_id).first()
            )
            if item is None or item.status != WorkItemStatus.IN_REVIEW:
                return None
            if item.verify_attempts >= MAX_VERIFY_ATTEMPTS:
                applied = WorkItemStateMachine.escalate(
                    item_id,
                    f"Rejected {item.verify_attempts}× without meeting the requirement; "
                    f"escalating to a human. Last reason: {reason}",
                )
                return WorkItemVerifyStatus.ESCALATED if applied else None
            applied = WorkItemStateMachine.transition(
                item_id,
                WorkItemStatus.IN_REVIEW,
                WorkItemStatus.BLOCKED,
                extra_filter=_undecided_filter(),
                extra={
                    "verify_status": WorkItemVerifyStatus.REJECTED,
                    "verify_reason": reason or "",
                    "last_outcome": reason or "",
                    "verify_attempts": item.verify_attempts + 1,
                },
            )
            return WorkItemVerifyStatus.REJECTED if applied else None

    # ------------------------------------------------------------------
    # Terminal
    # ------------------------------------------------------------------

    @staticmethod
    def cancel(item_id: int, reason: str = "") -> bool:
        """Cancel an item from any non-terminal state."""
        fields = {
            "status": WorkItemStatus.CANCELLED,
            "last_outcome": reason or "",
            "completed_at": timezone.now(),
            "updated_at": timezone.now(),
        }
        previous = _snapshot_fields(item_id, fields)
        updated = (
            WorkItem.objects.filter(
                pk=item_id,
                status__in=[
                    WorkItemStatus.BACKLOG,
                    WorkItemStatus.READY,
                    WorkItemStatus.IN_PROGRESS,
                    WorkItemStatus.IN_REVIEW,
                    WorkItemStatus.BLOCKED,
                ],
            )
            .update(**fields)
            > 0
        )
        if updated:
            _publish_item_event(item_id, "update", data=fields, previous=previous)
        return updated

    @staticmethod
    def reopen(item_id: int) -> bool:
        """``done`` → ``ready`` — send completed work back to an agent.

        Reopening is a *new attempt*, so it re-enters the ready queue rather
        than jumping to ``in_progress``.  ``in_progress`` with the old
        (already terminal) ``root_task`` still attached would be reported as
        finished by the next tick (``_report_work_item_outcomes``), silently
        converting ``done`` into ``blocked`` with the previous outcome.
        """
        return WorkItemStateMachine.mark_ready(item_id)

    @staticmethod
    def resume(item_id: int) -> bool:
        """``in_review`` → ``ready`` — send reviewed work back for another attempt.

        Same trap as :meth:`reopen`: leaving the old ``root_task`` attached
        makes the outcome reporter bounce the item straight to ``blocked``.
        """
        return WorkItemStateMachine.mark_ready(item_id)
