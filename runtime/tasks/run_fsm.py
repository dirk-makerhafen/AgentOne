from __future__ import annotations
from django.utils import timezone
from server.models.enums.task_enums import TaskRunStatus


# ---------------------------------------------------------------------------
# Valid transitions
# ---------------------------------------------------------------------------
_VALID_TRANSITIONS: frozenset[tuple[TaskRunStatus, TaskRunStatus]] = frozenset({
    (TaskRunStatus.NEW,                 TaskRunStatus.QUEUED),
    (TaskRunStatus.QUEUED,              TaskRunStatus.ACTIVE),
    (TaskRunStatus.ACTIVE,              TaskRunStatus.WAITING_RESULTTASKS),
    (TaskRunStatus.ACTIVE,              TaskRunStatus.SUCCESS),
    (TaskRunStatus.ACTIVE,              TaskRunStatus.FAILURE),
    (TaskRunStatus.WAITING_RESULTTASKS, TaskRunStatus.SUCCESS),
    (TaskRunStatus.WAITING_RESULTTASKS, TaskRunStatus.FAILURE),
    (TaskRunStatus.ACTIVE,              TaskRunStatus.RATE_LIMITED),
})


class InvalidTransition(Exception):
    """Raised when a transition pair is not in ``_VALID_TRANSITIONS``."""

    pass


def _publish_run_event(run_id: int) -> None:
    """Publish a model event for an AgentTaskRun after a transition."""
    try:
        from runtime.events import publish_model_event
        from server.models.tasks.agent_task_run import AgentTaskRun
        run = AgentTaskRun.objects.get(pk=run_id)
        publish_model_event(run, "update")
    except Exception:
        pass


class TaskRunStateMachine:
    """
    Single entry point for all AgentTaskRun status transitions.

    Replaces ``RunScheduler._set_status()`` and the two raw ``.update()`` calls
    in ``_apply_async``.  TaskRun state is simpler than TaskCall — no approval
    gates, retries, or hooks.  Those live at the TaskCall level.

    ::

        NEW → QUEUED → ACTIVE → SUCCESS
                              → FAILURE
                              → WAITING_RESULTTASKS → SUCCESS
                                                    → FAILURE
                              → RATE_LIMITED
    """

    @staticmethod
    def transition(
        run_id: int,
        from_status: TaskRunStatus,
        to_status: TaskRunStatus,
        extra: dict | None = None,
    ) -> bool:
        """
        Core atomic transition.

        Parameters
        ----------
        run_id : int
            PK of the AgentTaskRun.
        from_status : TaskRunStatus
            Expected current status.
        to_status : TaskRunStatus
            Target status.
        extra : dict | None
            Additional field updates (e.g. ``ended_at``).

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
                f"Invalid AgentTaskRun transition: {from_status} → {to_status}"
            )
        from server.models.tasks.agent_task_run import AgentTaskRun

        fields: dict = {"status": to_status}
        if extra:
            fields.update(extra)

        updated = AgentTaskRun.objects.filter(pk=run_id, status=from_status).update(**fields) > 0
        if updated:
            _publish_run_event(run_id)
        return updated

    # ------------------------------------------------------------------
    # Named transition methods
    # ------------------------------------------------------------------

    @staticmethod
    def enqueue(run_id: int) -> bool:
        """``NEW`` → ``QUEUED`` (run created and submitted to the worker queue)."""
        return TaskRunStateMachine.transition(run_id, TaskRunStatus.NEW, TaskRunStatus.QUEUED)

    @staticmethod
    def start(run_id: int) -> bool:
        """
        ``QUEUED`` → ``ACTIVE``.

        Called from ``run_runtime._apply_async`` paired with the taskcall
        ``ACTIVE_QUEUED → ACTIVE_RUNNING`` update.  If this succeeds but the
        taskcall update fails, the caller must :meth:`rollback_to_queued`.
        """
        return TaskRunStateMachine.transition(run_id, TaskRunStatus.QUEUED, TaskRunStatus.ACTIVE)

    @staticmethod
    def rollback_to_queued(run_id: int) -> bool:
        """
        ``ACTIVE`` → ``QUEUED`` (exceptional rollback).

        Used in ``run_runtime._apply_async`` when the paired taskcall
        ``ACTIVE_QUEUED → ACTIVE_RUNNING`` update fails (race condition).
        This is the only reverse transition in the system — deliberately not
        in ``_VALID_TRANSITIONS``.
        """
        from server.models.tasks.agent_task_run import AgentTaskRun

        updated = AgentTaskRun.objects.filter(
            pk=run_id, status=TaskRunStatus.ACTIVE
        ).update(status=TaskRunStatus.QUEUED) > 0
        if updated:
            _publish_run_event(run_id)
        return updated

    @staticmethod
    def wait_for_results(run_id: int, extra: dict | None = None) -> bool:
        """
        ``ACTIVE`` → ``WAITING_RESULTTASKS``.

        The run's result contains AgentTaskCall references that haven't
        finished yet.  Stays open until all referenced calls reach ``ENDED``.

        Parameters
        ----------
        extra : dict | None
            Additional field updates to apply atomically with the transition
            (e.g. ``result_json``).
        """
        return TaskRunStateMachine.transition(
            run_id, TaskRunStatus.ACTIVE, TaskRunStatus.WAITING_RESULTTASKS, extra=extra
        )

    @staticmethod
    def succeed(run_id: int, extra: dict | None = None) -> bool:
        """
        ``WAITING_RESULTTASKS`` **or** ``ACTIVE`` → ``SUCCESS``.

        Tries ``WAITING_RESULTTASKS`` first (all referenced calls just
        finished), then falls back to ``ACTIVE`` (no result references).
        """
        succeeded = TaskRunStateMachine.transition(
            run_id, TaskRunStatus.WAITING_RESULTTASKS, TaskRunStatus.SUCCESS
        )
        extras = {"ended_at": timezone.now()}
        if extra:
            extras.update(extra)
        if not succeeded:
            succeeded = TaskRunStateMachine.transition(
                run_id=run_id,
                from_status=TaskRunStatus.ACTIVE,
                to_status=TaskRunStatus.SUCCESS,
                extra = extras,
            )
        return succeeded

    @staticmethod
    def fail(run_id: int, extra: dict | None = None) -> bool:
        """
        ``WAITING_RESULTTASKS`` **or** ``ACTIVE`` → ``FAILURE``.

        Tries ``WAITING_RESULTTASKS`` first (a referenced call failed), then
        falls back to ``ACTIVE`` (the run itself raised an exception).

        Parameters
        ----------
        extra : dict | None
            Additional field updates to apply atomically with the fallback
            transition (e.g. ``result_json``).
        """
        failed = TaskRunStateMachine.transition(
            run_id, TaskRunStatus.WAITING_RESULTTASKS, TaskRunStatus.FAILURE
        )
        extras = {"ended_at": timezone.now()}
        if extra:
            extras.update(extra)
        if not failed:
            failed = TaskRunStateMachine.transition(
                run_id=run_id,
                from_status=TaskRunStatus.ACTIVE,
                to_status=TaskRunStatus.FAILURE,
                extra=extras,
            )
        return failed

    @staticmethod
    def rate_limit(run_id: int) -> bool:
        """
        ``ACTIVE`` → ``RATE_LIMITED``.

        Called from ``AgentTaskRun.apply()`` when a ``RateLimitError`` is
        caught.  Does **not** consume the retry budget — the ATC is parked
        in ``WAITING_RATELIMIT`` for the scheduler to re-dispatch.
        """
        return TaskRunStateMachine.transition(
            run_id,
            TaskRunStatus.ACTIVE,
            TaskRunStatus.RATE_LIMITED,
            extra={"ended_at": timezone.now()},
        )
