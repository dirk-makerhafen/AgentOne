from __future__ import annotations
from django.db.models import Q, F
from django.utils import timezone
from datetime import timedelta
from server.models.enums.task_enums import TaskCallStatus, TaskCallStatusDetail


# ---------------------------------------------------------------------------
# Valid transitions — (from_detail, to_detail)
# ---------------------------------------------------------------------------
_VALID_TRANSITIONS: frozenset[tuple[TaskCallStatusDetail, TaskCallStatusDetail]] = frozenset({
    # Entry: both NEW and WAITING_RETRY re-enter WAITING_DEPENDENCY the same way.
    # The multi-from-state case is handled atomically in enter_dependency_wait().
    (TaskCallStatusDetail.NEW,                TaskCallStatusDetail.WAITING_DEPENDENCY),
    (TaskCallStatusDetail.WAITING_RETRY,      TaskCallStatusDetail.WAITING_DEPENDENCY),

    # After all arg-tasks finish: conditional gate on approval
    (TaskCallStatusDetail.WAITING_DEPENDENCY, TaskCallStatusDetail.HALTED_APPROVAL),
    (TaskCallStatusDetail.WAITING_DEPENDENCY, TaskCallStatusDetail.WAITING_QUEUE),

    # Human approved / denied
    (TaskCallStatusDetail.HALTED_APPROVAL,    TaskCallStatusDetail.WAITING_QUEUE),
    (TaskCallStatusDetail.HALTED_APPROVAL,    TaskCallStatusDetail.ENDED_CANCELLED),

    # Scheduler picks it up
    (TaskCallStatusDetail.WAITING_QUEUE,      TaskCallStatusDetail.ACTIVE_QUEUED),

    # Recovery: re-queue a call whose Celery run message was lost
    (TaskCallStatusDetail.ACTIVE_QUEUED,      TaskCallStatusDetail.WAITING_QUEUE),

    # Worker begins execution (atomically paired with taskrun QUEUED→ACTIVE in run_runtime)
    (TaskCallStatusDetail.ACTIVE_QUEUED,      TaskCallStatusDetail.ACTIVE_RUNNING),

    # Run succeeded, after-hooks pending.
    # wait_for_hooks() accepts both states via __in (matches original on_taskrun_ended).
    (TaskCallStatusDetail.ACTIVE_RUNNING,     TaskCallStatusDetail.WAITING_SUBTASKS_OR_HOOKS),
    (TaskCallStatusDetail.WAITING_SUBTASKS_OR_HOOKS,    TaskCallStatusDetail.WAITING_SUBTASKS_OR_HOOKS),

    # Success terminal — from either state depending on hook path.
    # succeed() accepts both via __in (matches original on_all_on_posthook_ended).
    (TaskCallStatusDetail.ACTIVE_RUNNING,     TaskCallStatusDetail.ENDED_SUCCESS),
    (TaskCallStatusDetail.WAITING_SUBTASKS_OR_HOOKS,    TaskCallStatusDetail.ENDED_SUCCESS),

    # Retry — only if retry_count < max_retries (enforced inside schedule_retry())
    (TaskCallStatusDetail.ACTIVE_RUNNING,     TaskCallStatusDetail.WAITING_RETRY),

    # Hard failure — no retries left
    (TaskCallStatusDetail.ACTIVE_RUNNING,     TaskCallStatusDetail.ENDED_FAILURE_EXCEPTION),
    (TaskCallStatusDetail.WAITING_SUBTASKS_OR_HOOKS,    TaskCallStatusDetail.ENDED_FAILURE_EXCEPTION),

    # Dependency or hook failed
    (TaskCallStatusDetail.WAITING_DEPENDENCY, TaskCallStatusDetail.ENDED_CANCELLED),
    (TaskCallStatusDetail.WAITING_SUBTASKS_OR_HOOKS,    TaskCallStatusDetail.ENDED_CANCELLED),

    # Direct cancel from NEW/WAITING_RETRY (no need to chain through WAITING_DEPENDENCY)
    (TaskCallStatusDetail.NEW,                TaskCallStatusDetail.ENDED_CANCELLED),
    (TaskCallStatusDetail.WAITING_RETRY,      TaskCallStatusDetail.ENDED_CANCELLED),
    (TaskCallStatusDetail.NEW,                TaskCallStatusDetail.ENDED_STOPPED),
    (TaskCallStatusDetail.WAITING_RETRY,      TaskCallStatusDetail.ENDED_STOPPED),

    # External stop
    (TaskCallStatusDetail.WAITING_DEPENDENCY, TaskCallStatusDetail.ENDED_STOPPED),
    (TaskCallStatusDetail.WAITING_SUBTASKS_OR_HOOKS,    TaskCallStatusDetail.ENDED_STOPPED),

    # Cancel from queue or active-queued (no FSM path existed before — gap)
    (TaskCallStatusDetail.WAITING_QUEUE,      TaskCallStatusDetail.ENDED_CANCELLED),
    (TaskCallStatusDetail.ACTIVE_QUEUED,      TaskCallStatusDetail.ENDED_CANCELLED),
    (TaskCallStatusDetail.WAITING_QUEUE,      TaskCallStatusDetail.ENDED_STOPPED),
    (TaskCallStatusDetail.ACTIVE_QUEUED,      TaskCallStatusDetail.ENDED_STOPPED),

    # Rate limiting.
    # ACTIVE_RUNNING → WAITING_RATELIMIT: _execute_query discovered no LLM capacity.
    # WAITING_RATELIMIT → WAITING_QUEUE:  scheduler releases when capacity returns.
    # Does NOT consume retry budget — this is capacity queuing, not failure.
    (TaskCallStatusDetail.ACTIVE_RUNNING,     TaskCallStatusDetail.WAITING_RATELIMIT),
    (TaskCallStatusDetail.WAITING_RATELIMIT,  TaskCallStatusDetail.WAITING_QUEUE),

    # Allow cancellation/stop while rate-limited
    (TaskCallStatusDetail.WAITING_RATELIMIT,  TaskCallStatusDetail.ENDED_CANCELLED),
    (TaskCallStatusDetail.WAITING_RATELIMIT,  TaskCallStatusDetail.ENDED_STOPPED),
})


class InvalidTransition(Exception):
    """Raised when a transition pair is not in ``_VALID_TRANSITIONS``."""

    pass


def _detail_to_status(detail: TaskCallStatusDetail) -> TaskCallStatus:
    """Derive the coarse TaskCallStatus from the detail prefix.

    Example: ``WAITING_DEPENDENCY`` → ``WAITING``.
    """
    prefix = detail.value.split("_", 1)[0]
    return TaskCallStatus[prefix]


def _publish_call_event(call_id: int) -> None:
    """Publish a model event for an AgentTaskCall after a transition."""
    try:
        from runtime.events import publish_model_event
        from server.models.tasks.agent_task_call import AgentTaskCall
        call = AgentTaskCall.objects.get(pk=call_id)
        publish_model_event(call, "update")
    except Exception:
        pass


class TaskCallStateMachine:
    """
    Single entry point for all AgentTaskCall status transitions.

    Replaces ``CallScheduler._set_status()`` and the one raw ``.update()`` in
    ``on_all_on_posthook_ended()``.  All callers in ``call_runtime.py`` and
    ``run_runtime.py`` should go through here.

    Each method returns ``True`` if the update was applied, ``False`` on a race
    condition (the row was already in a different state).
    """

    @staticmethod
    def transition(
        call_id: int,
        from_detail: TaskCallStatusDetail,
        to_detail: TaskCallStatusDetail,
        extra_filter: Q | None = None,
        extra: dict | None = None,
    ) -> bool:
        """
        Core atomic status transition.

        Parameters
        ----------
        call_id : int
            PK of the AgentTaskCall.
        from_detail : TaskCallStatusDetail
            Expected current detail value.
        to_detail : TaskCallStatusDetail
            Target detail value.
        extra_filter : Q | None
            Additional WHERE conditions.
        extra : dict | None
            Additional field updates (e.g. ``ended_at``).

        Returns
        -------
        bool
            ``True`` if exactly one row was updated.

        Raises
        ------
        InvalidTransition
            If ``(from_detail, to_detail)`` is not in ``_VALID_TRANSITIONS``.
        """
        if (from_detail, to_detail) not in _VALID_TRANSITIONS:
            raise InvalidTransition(
                f"Invalid AgentTaskCall transition: {from_detail} → {to_detail}"
            )
        from server.models.tasks.agent_task_call import AgentTaskCall

        from_status = _detail_to_status(from_detail)
        to_status = _detail_to_status(to_detail)

        query = AgentTaskCall.objects.filter(
            pk=call_id,
            status=from_status,
            status_detail=from_detail,
        )
        if extra_filter is not None:
            query = query.filter(extra_filter)

        fields: dict = {"status": to_status, "status_detail": to_detail}
        if extra:
            fields.update(extra)

        updated = query.update(**fields) > 0
        if updated:
            _publish_call_event(call_id)
        return updated

    # ------------------------------------------------------------------
    # Named transition methods
    # ------------------------------------------------------------------

    @staticmethod
    def enter_dependency_wait(call_id: int) -> bool:
        """
        Atomic transition: ``NEW`` **or** ``WAITING_RETRY`` → ``WAITING_DEPENDENCY``.

        Accepts both from-states in one atomic update, matching the original
        ``_apply_async``: ``filter(status_detail__in=[NEW, WAITING_RETRY])``.
        """
        from server.models.tasks.agent_task_call import AgentTaskCall

        updated = AgentTaskCall.objects.filter(
            pk=call_id,
            status_detail__in=[
                TaskCallStatusDetail.NEW,
                TaskCallStatusDetail.WAITING_RETRY,
            ],
        ).update(
            status=TaskCallStatus.WAITING,
            status_detail=TaskCallStatusDetail.WAITING_DEPENDENCY,
        ) > 0
        if updated:
            _publish_call_event(call_id)
        return updated

    @staticmethod
    def request_approval(call_id: int) -> bool:
        """
        ``WAITING_DEPENDENCY`` → ``HALTED_APPROVAL``.

        Only fires when ``requires_approval=True`` and not yet approved.
        Mirrors the first branch of ``on_all_arg_reference_tasks_ended``.
        """
        return TaskCallStateMachine.transition(
            call_id,
            TaskCallStatusDetail.WAITING_DEPENDENCY,
            TaskCallStatusDetail.HALTED_APPROVAL,
            extra_filter=~Q(is_approved=True) & Q(requires_approval=True),
        )

    @staticmethod
    def enqueue_after_dependencies(call_id: int) -> bool:
        """
        ``WAITING_DEPENDENCY`` → ``WAITING_QUEUE``.

        Only fires when approval is not required or already granted.
        Mirrors the second branch of ``on_all_arg_reference_tasks_ended``.
        """
        return TaskCallStateMachine.transition(
            call_id,
            TaskCallStatusDetail.WAITING_DEPENDENCY,
            TaskCallStatusDetail.WAITING_QUEUE,
            extra_filter=Q(is_approved=True) | Q(requires_approval=False),
        )

    @staticmethod
    def approve(call_id: int) -> bool:
        """``HALTED_APPROVAL`` → ``WAITING_QUEUE`` (human approved)."""
        return TaskCallStateMachine.transition(
            call_id,
            TaskCallStatusDetail.HALTED_APPROVAL,
            TaskCallStatusDetail.WAITING_QUEUE,
            extra={"is_approved": True},
        )

    @staticmethod
    def pick_up(call_id: int) -> bool:
        """``WAITING_QUEUE`` → ``ACTIVE_QUEUED``."""
        return TaskCallStateMachine.transition(
            call_id,
            TaskCallStatusDetail.WAITING_QUEUE,
            TaskCallStatusDetail.ACTIVE_QUEUED,
        )

    @staticmethod
    def re_queue(call_id: int) -> bool:
        """``ACTIVE_QUEUED`` → ``WAITING_QUEUE`` — recovery path for lost Celery runs."""
        return TaskCallStateMachine.transition(
            call_id,
            TaskCallStatusDetail.ACTIVE_QUEUED,
            TaskCallStatusDetail.WAITING_QUEUE,
        )

    @staticmethod
    def start_running(call_id: int) -> bool:
        """
        ``ACTIVE_QUEUED`` → ``ACTIVE_RUNNING``.

        Called from ``run_runtime._apply_async`` paired with taskrun
        ``QUEUED → ACTIVE``.  If this returns ``False`` the caller must roll
        the taskrun back to ``QUEUED``.

        Includes a defensive guard: if this call has a root task
        (``session_root_task``) and that root is already ``ENDED``, the
        transition is rejected.  Prevents child calls from activating
        after their root turn was cancelled (race safety).
        """
        extra_filter = Q(session_root_task__status__in=[
            TaskCallStatus.NEW,
            TaskCallStatus.WAITING,
            TaskCallStatus.ACTIVE,
            TaskCallStatus.HALTED,
        ]) | Q(session_root_task__isnull=True)

        return TaskCallStateMachine.transition(
            call_id,
            TaskCallStatusDetail.ACTIVE_QUEUED,
            TaskCallStatusDetail.ACTIVE_RUNNING,
            extra_filter=extra_filter,
        )

    @staticmethod
    def wait_for_hooks(call_id: int, result_run_id: int) -> bool:
        """
        ``ACTIVE_RUNNING`` **or** ``WAITING_SUBTASKS_OR_HOOKS`` → ``WAITING_SUBTASKS_OR_HOOKS``.

        Accepts both from-states via ``__in``, matching the original
        ``on_taskrun_ended`` which uses
        ``status_detail__in=[ACTIVE_RUNNING, WAITING_SUBTASKS_OR_HOOKS]``.
        """
        from server.models.tasks.agent_task_call import AgentTaskCall

        updated = AgentTaskCall.objects.filter(
            pk=call_id,
            status_detail__in=[
                TaskCallStatusDetail.ACTIVE_RUNNING,
                TaskCallStatusDetail.WAITING_SUBTASKS_OR_HOOKS,
            ],
        ).update(
            status=TaskCallStatus.WAITING,
            status_detail=TaskCallStatusDetail.WAITING_SUBTASKS_OR_HOOKS,
            taskcall_result_run_id=result_run_id,
        ) > 0
        if updated:
            _publish_call_event(call_id)
        return updated

    @staticmethod
    def succeed(call_id: int, result_run_id: int) -> bool:
        """
        ``ACTIVE_RUNNING`` **or** ``WAITING_SUBTASKS_OR_HOOKS`` → ``ENDED_SUCCESS``.

        Accepts both from-states via ``__in``, matching the original
        ``on_all_on_posthook_ended``.
        """
        from server.models.tasks.agent_task_call import AgentTaskCall

        updated = AgentTaskCall.objects.filter(
            pk=call_id,
            status_detail__in=[
                TaskCallStatusDetail.ACTIVE_RUNNING,
                TaskCallStatusDetail.WAITING_SUBTASKS_OR_HOOKS,
            ],
        ).update(
            status=TaskCallStatus.ENDED,
            status_detail=TaskCallStatusDetail.ENDED_SUCCESS,
            taskcall_result_run_id=result_run_id,
            ended_at=timezone.now(),
        ) > 0
        if updated:
            _publish_call_event(call_id)
        return updated

    @staticmethod
    def schedule_retry(call_id: int, retry_delay_seconds: int, max_retries: int) -> bool:
        """
        ``ACTIVE_RUNNING`` → ``WAITING_RETRY``, only if
        ``retry_count < max_retries``.

        The retry-budget check is atomic in the WHERE clause — if it returns
        ``False`` the caller must immediately call :meth:`fail`.
        """
        return TaskCallStateMachine.transition(
            call_id,
            TaskCallStatusDetail.ACTIVE_RUNNING,
            TaskCallStatusDetail.WAITING_RETRY,
            extra_filter=Q(retry_count__lt=max_retries),
            extra={
                "retry_count": F("retry_count") + 1,
                "dont_start_before": timezone.now() + timedelta(seconds=retry_delay_seconds),
            },
        )

    @staticmethod
    def fail(call_id: int) -> bool:
        """``ACTIVE_RUNNING`` **or** ``WAITING_SUBTASKS_OR_HOOKS`` → ``ENDED_FAILURE_EXCEPTION`` (retries exhausted)."""
        from server.models.tasks.agent_task_call import AgentTaskCall

        updated = AgentTaskCall.objects.filter(
            pk=call_id,
            status_detail__in=[
                TaskCallStatusDetail.ACTIVE_RUNNING,
                TaskCallStatusDetail.WAITING_SUBTASKS_OR_HOOKS,
            ],
        ).update(
            status=TaskCallStatus.ENDED,
            status_detail=TaskCallStatusDetail.ENDED_FAILURE_EXCEPTION,
            ended_at=timezone.now(),
        ) > 0
        if updated:
            _publish_call_event(call_id)
        return updated

    @staticmethod
    def cancel(call_id: int, from_detail: TaskCallStatusDetail) -> bool:
        """
        ``WAITING_DEPENDENCY``, ``HALTED_APPROVAL``, **or** ``WAITING_SUBTASKS_OR_HOOKS``
        → ``ENDED_CANCELLED``.

        Parameters
        ----------
        from_detail : TaskCallStatusDetail
            Must be a valid source state for ``ENDED_CANCELLED``.
        """
        return TaskCallStateMachine.transition(
            call_id=call_id,
            from_detail=from_detail,
            to_detail=TaskCallStatusDetail.ENDED_CANCELLED,
            extra={"ended_at": timezone.now()},
        )

    @staticmethod
    def stop(call_id: int, from_detail: TaskCallStatusDetail) -> bool:
        """
        ``WAITING_DEPENDENCY``, ``WAITING_SUBTASKS_OR_HOOKS``, **or**
        ``WAITING_RATELIMIT`` → ``ENDED_STOPPED``.
        """
        return TaskCallStateMachine.transition(
            call_id=call_id,
            from_detail=from_detail,
            to_detail=TaskCallStatusDetail.ENDED_STOPPED,
            extra={"ended_at": timezone.now()},
        )

    @staticmethod
    def rate_limit(call_id: int) -> bool:
        """
        ``ACTIVE_RUNNING`` → ``WAITING_RATELIMIT``.

        Called from ``run_runtime._apply_async`` when
        ``AgentTaskRun.apply()`` returns ``status=RATE_LIMITED``.
        Does **not** consume the retry budget.
        """
        return TaskCallStateMachine.transition(
            call_id,
            TaskCallStatusDetail.ACTIVE_RUNNING,
            TaskCallStatusDetail.WAITING_RATELIMIT,
        )

    @staticmethod
    def release_rate_limit(call_id: int) -> bool:
        """
        ``WAITING_RATELIMIT`` → ``WAITING_QUEUE``.

        Called by the scheduler when LLM capacity returns.  After this
        succeeds the scheduler calls ``start_new_taskrun()`` to re-dispatch.
        """
        return TaskCallStateMachine.transition(
            call_id,
            TaskCallStatusDetail.WAITING_RATELIMIT,
            TaskCallStatusDetail.WAITING_QUEUE,
        )
