
from __future__ import annotations
from functools import wraps
from server.models.tasks.agent_task_run import AgentTaskRun
from server.models.enums.task_enums import TaskRunStatus, TaskCallStatus, TaskCallStatusDetail

from django.db.models import Q
from typing import TYPE_CHECKING
from server.models.tasks.agent_task_call import AgentTaskCall
from runtime.task_call_runtime import AgentTaskCallRuntime

class AgentTaskRunRuntime():

    @staticmethod
    def _apply_async(taskrun_id):
        print("task_run_id", taskrun_id)
        if not AgentTaskRun.objects.filter(pk = taskrun_id, status = TaskRunStatus.QUEUED).update( status = TaskRunStatus.ACTIVE):
            return
        taskrun = AgentTaskRun.objects.get(pk=taskrun_id)
        if not AgentTaskCall.objects.filter(pk=taskrun.agent_task_call_id, status_detail=TaskCallStatusDetail.ACTIVE_QUEUED).update(status=TaskCallStatus.ACTIVE, status_detail=TaskCallStatusDetail.ACTIVE_RUNNING):
            AgentTaskRun.objects.filter(pk = taskrun_id, status = TaskRunStatus.ACTIVE).update( status = TaskRunStatus.QUEUED)
            return
        
        print("APPLY HERE taskrun.apply()", taskrun)
        
        taskrun.apply()

        if taskrun.status == TaskRunStatus.WAITING_RESULTTASKS:
            # Check if we can move to success immediately (if result calls are already done)
            query = AgentTaskCall.objects.filter(~Q(status=TaskCallStatus.ENDED), rev_taskrun_result_references=taskrun_id)
            if query.exists():
                # We also need to update the CALL status to reflect it's waiting
                AgentTaskCallRuntime._set_status(taskrun.agent_task_call_id, TaskCallStatusDetail.ACTIVE_RUNNING, TaskCallStatusDetail.WAITING_SUBTASK)
                return
        
        if taskrun.status == TaskRunStatus.FAILURE:  # Handle retries
            print("todo should we cancle started result/subtasks now? ")
            AgentTaskCallRuntime.on_taskrun_ended(taskrun.pk, TaskRunStatus.FAILURE)

        if taskrun.status == TaskRunStatus.SUCCESS:
            AgentTaskCallRuntime.on_taskrun_ended(taskrun.pk, TaskRunStatus.SUCCESS)


    # MANAGE SUB TASKS NEEDED FOR RESULTS
    @staticmethod
    def taskrun_result_reference_ended(taskrun_id, result_taskcall_id,  result_taskcall_status:TaskCallStatusDetail|str):
        # todo check if group has failed too many tasks, if yes cancel group tasks, end call
        if result_taskcall_status != TaskCallStatusDetail.ENDED_SUCCESS:
            AgentTaskRunRuntime._set_status( taskrun_id, TaskRunStatus.WAITING_RESULTTASKS, TaskRunStatus.FAILURE)
            return
        print("taskrun_result_reference_ended", taskrun_id, result_taskcall_id,  result_taskcall_status )
        query = AgentTaskCall.objects.filter(~Q(status=TaskCallStatus.ENDED), rev_taskrun_result_references=taskrun_id)
        if query.exists(): # some result calls have not finished yet
            return
        AgentTaskRunRuntime.all_taskrun_result_references_ended(taskrun_id)


    @staticmethod
    def all_taskrun_result_references_ended(taskrun_id):
        print("all_taskrun_result_references_ended",taskrun_id )
        unsuccessful_result_calls = AgentTaskCall.objects.filter(~Q(status_detail=TaskCallStatusDetail.ENDED_SUCCESS), rev_taskrun_result_references__id=taskrun_id)
        print("all_taskrun_result_references_ended", unsuccessful_result_calls.all())
        if unsuccessful_result_calls.exists():  # some sub calls failed
            if AgentTaskRunRuntime._set_status(taskrun_id, TaskRunStatus.WAITING_RESULTTASKS, TaskRunStatus.FAILURE):
                AgentTaskCallRuntime.on_taskrun_ended(taskrun_id, TaskRunStatus.FAILURE)
            return
        if AgentTaskRunRuntime._set_status(taskrun_id, TaskRunStatus.WAITING_RESULTTASKS, TaskRunStatus.SUCCESS):
            AgentTaskCallRuntime.on_taskrun_ended(taskrun_id, TaskRunStatus.SUCCESS)

    @staticmethod
    def _set_status(task_run_id, from_status:TaskRunStatus, to_status:TaskRunStatus,filter=None,  set=None):
        query = AgentTaskRun.objects.filter(pk = task_run_id, status = from_status)
        if filter:
            query = query.filter(filter)
        set = set if set else {}
        updated = query.update(status = to_status, **set)
        return updated > 0
