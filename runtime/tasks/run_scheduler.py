from __future__ import annotations

from django.db.models import Q
from server.models.tasks.agent_task_run import AgentTaskRun
from server.models.enums.task_enums import TaskRunStatus, TaskCallStatus, TaskCallStatusDetail
from server.models.tasks.agent_task_call import AgentTaskCall
from runtime.tasks.call_scheduler import CallScheduler
from runtime.tasks.call_fsm import TaskCallStateMachine
from runtime.tasks.run_fsm import TaskRunStateMachine


class RunScheduler:
    """
    Orchestrates the execution lifecycle of AgentTaskRun instances.

    Delegates status transitions to :class:`TaskRunStateMachine` and
    coordinates with :class:`CallScheduler` / :class:`TaskCallStateMachine`
    for the paired task-call transitions.  Also tracks result-reference
    resolution for runs that produce sub-calls.
    """

    @staticmethod
    def _apply_async(taskrun_id: int) -> None:
        """
        Execute a task run.

        Transitions the run to ``ACTIVE`` and the parent call to
        ``ACTIVE_RUNNING`` (with rollback on race).  After ``apply()``
        inspects the result status and dispatches accordingly:

        - ``RATE_LIMITED`` → park the call via :meth:`TaskCallStateMachine.rate_limit`.
        - ``WAITING_RESULTTASKS`` → wait for result references.
        - ``FAILURE`` / ``SUCCESS`` → delegate to :class:`CallScheduler`.
        """
        print("task_run_id", taskrun_id)
        if not TaskRunStateMachine.start(taskrun_id):
            return
        taskrun = AgentTaskRun.objects.get(pk=taskrun_id)
        if not TaskCallStateMachine.start_running(taskrun.agent_task_call_id):
            TaskRunStateMachine.rollback_to_queued(taskrun_id)
            return

        taskrun.apply()

        # --- Handle RATE_LIMITED separately — not a failure, not a retry ---
        if taskrun.status == TaskRunStatus.RATE_LIMITED:
            # The run is terminal (won't be retried directly). Transition the
            # call to WAITING_RATELIMIT so the scheduler can re-dispatch it
            # when LLM capacity returns. Retry budget is NOT consumed.
            TaskCallStateMachine.rate_limit(taskrun.agent_task_call_id)
            print(f"[rate_limit] call {taskrun.agent_task_call_id} parked — run {taskrun_id}")
            return

        if taskrun.status == TaskRunStatus.WAITING_RESULTTASKS:
            pending = AgentTaskCall.objects.filter(
                ~Q(status=TaskCallStatus.ENDED),
                rev_taskrun_result_references=taskrun_id,
            )
            if pending.exists():
                # Result references still pending — park the call in WAITING_SUBTASKS_OR_HOOKS.
                # Despite the method name, wait_for_hooks uses the same state.
                TaskCallStateMachine.wait_for_hooks(taskrun.agent_task_call_id, taskrun_id)
                return
            # All referenced calls already ended — resolve immediately.
            RunScheduler.all_taskrun_result_references_ended(taskrun.pk)
            return

        if taskrun.status == TaskRunStatus.FAILURE:
            CallScheduler.on_taskrun_ended(taskrun.pk, TaskRunStatus.FAILURE)

        if taskrun.status == TaskRunStatus.SUCCESS:
            CallScheduler.on_taskrun_ended(taskrun.pk, TaskRunStatus.SUCCESS)

    # ------------------------------------------------------------------
    # Result reference tracking
    # ------------------------------------------------------------------

    @staticmethod
    def _error_tolerance(run: AgentTaskRun | None) -> tuple[int, int]:
        """Return ``(max_subtask_errors, max_subtask_error_rate)`` for *run*."""
        if run is None:
            return 0, 0
        return (
            int(getattr(run, "max_subtask_errors", 0) or 0),
            int(getattr(run, "max_subtask_error_rate", 0) or 0),
        )

    @staticmethod
    def _tolerance_configured(run: AgentTaskRun | None) -> bool:
        """True when *run* allows at least one failed subtask."""
        max_errors, max_rate = RunScheduler._error_tolerance(run)
        return max_errors > 0 or max_rate > 0

    @staticmethod
    def _errors_tolerated(run: AgentTaskRun | None, total: int, failed: int) -> bool:
        """True when *failed* of *total* subtask failures are within tolerance.

        ``max_subtask_errors`` is an absolute count; ``max_subtask_error_rate``
        is a percentage (0-100).  Either threshold grants tolerance (the more
        permissive wins).  When both are 0 the legacy behaviour applies: any
        failed reference fails the run.
        """
        if failed <= 0:
            return True
        max_errors, max_rate = RunScheduler._error_tolerance(run)
        if max_errors > 0 and failed <= max_errors:
            return True
        if max_rate > 0 and total > 0 and failed * 100 <= max_rate * total:
            return True
        return False

    @staticmethod
    def taskrun_result_reference_ended(
        taskrun_id: int,
        result_taskcall_id: int,
        result_taskcall_status: TaskCallStatusDetail | str,
    ) -> None:
        """
        Called when a result-referenced task call ends.

        If the referenced call failed, the parent run transitions to
        ``FAILURE`` — unless the run carries a subtask-error tolerance
        (``max_subtask_errors`` / ``max_subtask_error_rate``), in which case
        the remaining references are allowed to settle first and the failure
        budget is evaluated in :meth:`all_taskrun_result_references_ended`.
        Otherwise, once **all** result references have ended,
        :meth:`all_taskrun_result_references_ended` is invoked.
        """
        run = AgentTaskRun.objects.filter(pk=taskrun_id).first()
        if result_taskcall_status != TaskCallStatusDetail.ENDED_SUCCESS:
            if not RunScheduler._tolerance_configured(run):
                if TaskRunStateMachine.fail(taskrun_id):
                    CallScheduler.on_taskrun_ended(taskrun_id, TaskRunStatus.FAILURE)
                return
        query = AgentTaskCall.objects.filter(
            ~Q(status=TaskCallStatus.ENDED),
            rev_taskrun_result_references=taskrun_id,
        )
        if query.exists():
            return
        RunScheduler.all_taskrun_result_references_ended(taskrun_id)

    @staticmethod
    def all_taskrun_result_references_ended(taskrun_id: int) -> None:
        """
        All result references have resolved.

        Fails the run only when the failed-reference count exceeds the run's
        ``max_subtask_errors`` / ``max_subtask_error_rate`` tolerance; a run
        that tolerates them succeeds with partial results.
        """
        refs = AgentTaskCall.objects.filter(
            rev_taskrun_result_references__id=taskrun_id,
        )
        total = refs.count()
        failed = refs.exclude(
            status_detail=TaskCallStatusDetail.ENDED_SUCCESS,
        ).count()
        run = AgentTaskRun.objects.filter(pk=taskrun_id).first()
        if failed and not RunScheduler._errors_tolerated(run, total, failed):
            if TaskRunStateMachine.fail(taskrun_id):
                CallScheduler.on_taskrun_ended(taskrun_id, TaskRunStatus.FAILURE)
            return
        if TaskRunStateMachine.succeed(taskrun_id):
            CallScheduler.on_taskrun_ended(taskrun_id, TaskRunStatus.SUCCESS)
