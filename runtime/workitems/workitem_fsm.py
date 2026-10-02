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
    # Human sends it back for another attempt.
    (WorkItemStatus.IN_REVIEW, WorkItemStatus.IN_PROGRESS),
    (WorkItemStatus.IN_REVIEW, WorkItemStatus.CANCELLED),

    # Human re-queue.
    (WorkItemStatus.BLOCKED, WorkItemStatus.READY),
    (WorkItemStatus.BLOCKED, WorkItemStatus.IN_PROGRESS),
    (WorkItemStatus.BLOCKED, WorkItemStatus.CANCELLED),

    # Reopen / restore.
    (WorkItemStatus.DONE, WorkItemStatus.IN_PROGRESS),
    (WorkItemStatus.CANCELLED, WorkItemStatus.READY),
})


class InvalidTransition(Exception):
    """Raised when a transition pair is not in ``_VALID_TRANSITIONS``."""


def _publish_item_event(item_id: int) -> None:
    """Publish a model event for a WorkItem after a transition."""
    try:
        from runtime.events import publish_model_event

        item = WorkItem.objects.get(pk=item_id)
        publish_model_event(item, "update")
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

        updated = query.update(**fields) > 0
        if updated:
            _publish_item_event(item_id)
        return updated

    # ------------------------------------------------------------------
    # Intake
    # ------------------------------------------------------------------

    @staticmethod
    def mark_ready(item_id: int) -> bool:
        """``backlog``/``blocked``/``cancelled`` → ``ready``.

        A requeue means "do this work again", so the *previous* attempt's
        dispatch and verdict bookkeeping is cleared:

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
        updated = WorkItem.objects.filter(
            pk=item_id,
            status__in=[
                WorkItemStatus.BACKLOG,
                WorkItemStatus.BLOCKED,
                WorkItemStatus.CANCELLED,
            ],
        ).update(
            status=WorkItemStatus.READY,
            root_task=None,
            verify_status=None,
            verify_reason="",
            completed_at=None,
            updated_at=timezone.now(),
        ) > 0
        if updated:
            _publish_item_event(item_id)
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
        updated = WorkItem.objects.filter(
            pk=item_id,
            status__in=[WorkItemStatus.READY, WorkItemStatus.IN_PROGRESS],
        ).update(
            status=WorkItemStatus.BLOCKED,
            last_outcome=reason or "",
            updated_at=timezone.now(),
        ) > 0
        if updated:
            _publish_item_event(item_id)
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
        updated = (
            WorkItem.objects.filter(pk=item_id, root_task__isnull=True)
            .update(root_task_id=root_task_id, updated_at=timezone.now())
            > 0
        )
        if updated:
            _publish_item_event(item_id)
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
    def reject_or_escalate(item_id: int, reason: str = "") -> str:
        """Apply a rejection while honouring the verify-attempt bound.

        Returns the verify_status actually applied: ``"rejected"`` while
        budget remains, ``"escalated"`` once ``MAX_VERIFY_ATTEMPTS`` is spent.
        Without this bound a reviewer that keeps rejecting would let a human
        re-queue indefinitely and the item would ping-pong forever
        (``docs/work-items.md`` §8.5).
        """
        item = WorkItem.objects.filter(pk=item_id).first()
        if item is None:
            return WorkItemVerifyStatus.ESCALATED
        if item.verify_attempts >= MAX_VERIFY_ATTEMPTS:
            WorkItemStateMachine.escalate(
                item_id,
                f"Rejected {item.verify_attempts}× without meeting the requirement; "
                f"escalating to a human. Last reason: {reason}",
            )
            return WorkItemVerifyStatus.ESCALATED
        WorkItem.objects.filter(pk=item_id).update(
            verify_attempts=item.verify_attempts + 1, updated_at=timezone.now()
        )
        WorkItemStateMachine.reject(item_id, reason)
        return WorkItemVerifyStatus.REJECTED

    # ------------------------------------------------------------------
    # Terminal
    # ------------------------------------------------------------------

    @staticmethod
    def cancel(item_id: int, reason: str = "") -> bool:
        """Cancel an item from any non-terminal state."""
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
            .update(
                status=WorkItemStatus.CANCELLED,
                last_outcome=reason or "",
                completed_at=timezone.now(),
                updated_at=timezone.now(),
            )
            > 0
        )
        if updated:
            _publish_item_event(item_id)
        return updated

    @staticmethod
    def reopen(item_id: int) -> bool:
        """``done`` → ``in_progress`` — send completed work back to an agent."""
        return WorkItemStateMachine.transition(
            item_id,
            WorkItemStatus.DONE,
            WorkItemStatus.IN_PROGRESS,
            extra={"completed_at": None, "verify_status": WorkItemVerifyStatus.SKIPPED},
        )
