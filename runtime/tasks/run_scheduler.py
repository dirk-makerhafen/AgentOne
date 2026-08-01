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
    def taskrun_result_reference_ended(
        taskrun_id: int,
        result_taskcall_id: int,
        result_taskcall_status: TaskCallStatusDetail | str,
    ) -> None:
        """
        Called when a result-referenced task call ends.

        If the referenced call failed, the parent run transitions to
        ``FAILURE``.  Otherwise, once **all** result references have ended,
        :meth:`all_taskrun_result_references_ended` is invoked.
        """
        if result_taskcall_status != TaskCallStatusDetail.ENDED_SUCCESS:
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

        If any ended unsuccessfully the run fails; otherwise it succeeds.
        """
        unsuccessful = AgentTaskCall.objects.filter(
            ~Q(status_detail=TaskCallStatusDetail.ENDED_SUCCESS),
            rev_taskrun_result_references__id=taskrun_id,
        )
        if unsuccessful.exists():
            if TaskRunStateMachine.fail(taskrun_id):
                CallScheduler.on_taskrun_ended(taskrun_id, TaskRunStatus.FAILURE)
            return
        if TaskRunStateMachine.succeed(taskrun_id):
            CallScheduler.on_taskrun_ended(taskrun_id, TaskRunStatus.SUCCESS)
