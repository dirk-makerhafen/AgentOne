from __future__ import annotations
from server.models.tasks.agent_task_run import AgentTaskRun
from server.models.enums.task_enums import TaskRunStatus, TaskCallStatus, TaskCallStatusDetail

from django.db.models import Q
from server.models.tasks.agent_task_call import AgentTaskCall
from AgentOne.runtime.tasks.call_scheduler import CallScheduler
from runtime.tasks.call_fsm import TaskCallStateMachine
from runtime.tasks.run_fsm import TaskRunStateMachine


class RunScheduler():

    @staticmethod
    def _apply_async(taskrun_id):
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
                # Result references still pending — park the call in WAITING_SUBTASK.
                # Despite the method name, wait_for_hooks uses the same state.
                TaskCallStateMachine.wait_for_hooks(taskrun.agent_task_call_id, taskrun_id)
                return

        if taskrun.status == TaskRunStatus.FAILURE:
            CallScheduler.on_taskrun_ended(taskrun.pk, TaskRunStatus.FAILURE)

        if taskrun.status == TaskRunStatus.SUCCESS:
            CallScheduler.on_taskrun_ended(taskrun.pk, TaskRunStatus.SUCCESS)

    # ------------------------------------------------------------------
    # Result reference tracking
    # ------------------------------------------------------------------

    @staticmethod
    def taskrun_result_reference_ended(taskrun_id, result_taskcall_id, result_taskcall_status: TaskCallStatusDetail | str):
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
    def all_taskrun_result_references_ended(taskrun_id):
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