
from __future__ import annotations
from datetime import timedelta
from functools import wraps
import random
import threading
import traceback
from django.db import models
from server.models.tasks.agent_task_call import AgentTaskCall
from runtime.context_manager import ContextTracker
from server.models.enums.task_enums import TaskCallStatus, TaskCallStatusDetail, TaskRunStatus
from server.tasks.task_dispatcher import celery_delay
from server.models.base_model import BaseModel
from django.apps import apps
from django.db.models import Q
import time
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.db.models import F

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from server.models.tasks.agent_task_instance import AgentTaskInstance


class AgentTaskCallRuntime():

    @staticmethod
    def _apply_async(task_call_id):
        print("start_task1", task_call_id)
        tc = AgentTaskCall.objects.get(pk=task_call_id)
        print(tc)
        print(tc.agent_task_definition.name)
        print(tc.taskcall_arg_references.all(), [r.status for r in tc.taskcall_arg_references.all()])
        print("test")
        query = AgentTaskCall.objects.filter(pk = task_call_id, status_detail__in = [TaskCallStatusDetail.NEW, TaskCallStatusDetail.WAITING_RETRY])
        if 0 == query.update(status = TaskCallStatus.WAITING, status_detail = TaskCallStatusDetail.WAITING_DEPENDENCY):
            print("not updated, skip")
            return
        print("her1",AgentTaskCall.objects.filter(~Q(status=TaskCallStatus.ENDED), taskcall_arg_references__pk=task_call_id))
        print("her1",AgentTaskCall.objects.filter(~Q(status=TaskCallStatus.ENDED), rev_taskcall_arg_references__pk=task_call_id))

        tc = AgentTaskCall.objects.get(pk=task_call_id)
        if tc.taskcall_arg_references.exclude(status=TaskCallStatus.ENDED).exists():
            print("required_calls unfinished")
            return
        AgentTaskCallRuntime.on_all_arg_reference_tasks_ended(task_call_id)


    # TASKCALLS FOR ARGUMENTS
    @staticmethod
    def on_arg_reference_task_ended(task_call_id, last_taskrun_id, related_call_status: TaskCallStatusDetail|str):
        '''
        called by the tasks in self.related_calls_sub_task after they finish
        '''
        print("required_task_call_ended", task_call_id)

        if related_call_status == TaskCallStatusDetail.ENDED_STOPPED:

            if AgentTaskCallRuntime._set_status( task_call_id,  TaskCallStatusDetail.WAITING_DEPENDENCY, TaskCallStatusDetail.ENDED_STOPPED):
                AgentTaskCallRuntime._on_taskcall_ended(task_call_id, last_taskrun_id, TaskCallStatusDetail.ENDED_CANCELLED)
                print("required_task_call.ENDED_STOPPED, TaskCallStatusDetail.ENDED_STOPPED")
            return

        if related_call_status != TaskCallStatusDetail.ENDED_SUCCESS:
            print("required_task_call NOT ENDED_SUCCESS, TaskCallStatusDetail.ENDED_CANCELLED", related_call_status)
            if AgentTaskCallRuntime._set_status( task_call_id, TaskCallStatusDetail.WAITING_DEPENDENCY, TaskCallStatusDetail.ENDED_CANCELLED):
                AgentTaskCallRuntime._on_taskcall_ended(task_call_id, last_taskrun_id, TaskCallStatusDetail.ENDED_CANCELLED)
            return

        tc = AgentTaskCall.objects.get(pk=task_call_id)
        # Check if ANY of the tasks it lists as arguments are still unfinished
        if tc.taskcall_arg_references.exclude(status=TaskCallStatus.ENDED).exists():
            return # Still waiting for other arguments
        AgentTaskCallRuntime.on_all_arg_reference_tasks_ended(task_call_id)


    @staticmethod
    def on_all_arg_reference_tasks_ended(task_call_id):
        print("all_required_task_calls_ended", task_call_id)
        if AgentTaskCallRuntime._set_status( task_call_id, TaskCallStatusDetail.WAITING_DEPENDENCY, TaskCallStatusDetail.HALTED_APPROVAL, filter=~Q(is_approved = True) & Q(requires_approval=True)):
            print(" # WAIT FOR APPROVAL")
            return # WAIT FOR APPROVAL

        if not AgentTaskCallRuntime._set_status( task_call_id, TaskCallStatusDetail.WAITING_DEPENDENCY, TaskCallStatusDetail.WAITING_QUEUE, filter=Q(is_approved = True) | Q(requires_approval = False)):
            print("# was not queued, maybe some race condition")
            return # was not queued, maybe some race condition

        AgentTaskCallRuntime.start_new_taskrun(task_call_id)


    # HUMAN APPROVAL
    @staticmethod
    def approve_taskcall(task_call_id): 
        if not AgentTaskCallRuntime._set_status(task_call_id, TaskCallStatusDetail.HALTED_APPROVAL, TaskCallStatusDetail.WAITING_QUEUE, set={"is_approved": True}):
            print(" # was not queued, maybe some race condition")
            return # was not queued, maybe some race condition
        AgentTaskCallRuntime.start_new_taskrun(task_call_id)


    # START / END TASKRUN
    @staticmethod
    def start_new_taskrun(task_call_id):
        if not AgentTaskCallRuntime._set_status(task_call_id, TaskCallStatusDetail.WAITING_QUEUE, TaskCallStatusDetail.ACTIVE_QUEUED):
            print(" # was not queued, maybe some race condition")
            return # was not queued, maybe some race condition
        print("start_task", ContextTracker.current)
        taskcall = AgentTaskCall.objects.get(pk=task_call_id)
        #print("start_task", taskcall, taskcall._parent, threading.get_ident())
        args = []
        args.extend(taskcall.agent_task_instance.iarguments_json.get("*",[]))
        args.extend(taskcall.carguments_json.get("*",[]))
        kwargs = {}
        kwargs.update(taskcall.agent_task_instance.iarguments_json)
        kwargs.update(taskcall.carguments_json)
        if args:
            kwargs["*"] = args
        from server.models.tasks.agent_task_run import AgentTaskRun
        taskrun = AgentTaskRun.create(agent_task_call=taskcall, args=args, kwargs=kwargs)
        taskrun.apply_async()

    @staticmethod
    def on_taskrun_ended(taskrun_id, taskrun_status:TaskRunStatus):
        from server.models.tasks.agent_task_run import AgentTaskRun
        run = AgentTaskRun.objects.get(pk=taskrun_id)
        call = run.agent_task_call
        print("on_taskrun_ended" , taskrun_status, run, call)

        if taskrun_status == TaskRunStatus.FAILURE:  # Handle retries
            values = {"retry_count":F("retry_count") + 1, "dont_start_before": timezone.now() + timedelta(seconds=call.retry_delay)}
            if AgentTaskCallRuntime._set_status(call.pk,  TaskCallStatusDetail.ACTIVE_RUNNING, TaskCallStatusDetail.WAITING_RETRY, filter=Q(retry_count__lt=call.max_retries), set=values):
                return
            if AgentTaskCallRuntime._set_status(call.pk,  TaskCallStatusDetail.ACTIVE_RUNNING, TaskCallStatusDetail.ENDED_FAILURE_EXCEPTION):
                AgentTaskCallRuntime._on_taskcall_ended(call.pk, taskrun_id, TaskCallStatusDetail.ENDED_FAILURE_EXCEPTION)
            return

        if taskrun_status == TaskRunStatus.SUCCESS:
            after_hooks = list(run.agent_task_instance.taskinstances_after_run_hooks.all().order_by('pk'))
            if not after_hooks:
                AgentTaskCallRuntime.on_all_on_posthook_ended(call.pk, taskrun_id)
                return

            # --- AFTER_RUN Hooks Dispatch ---
            after_hook_calls = []
            #result, _ = AgentTaskRun.result_to_json(obj=result)
            print(f"DEBUG: Dispatching AFTER_RUN hooks for {run.agent_task_definition.name}. {len(after_hooks)} hooks found.")
            updated = AgentTaskCall.objects.filter(
                pk=call.pk, status_detail__in=[TaskCallStatusDetail.ACTIVE_RUNNING, TaskCallStatusDetail.WAITING_SUBTASK]
            ).update(
                status=TaskCallStatus.WAITING, status_detail=TaskCallStatusDetail.WAITING_SUBTASK, taskcall_result_run_id=taskrun_id
            )
            hook_arguments = run
            for i, hook_instance in enumerate(after_hooks):
                hook_instance: AgentTaskInstance
                print(f"  -> Launching after_run hook {hook_instance.agent_task_definition.name} (step {i+1}/{len(after_hooks)})")
                result = hook_instance.call(args=hook_arguments)
                after_hook_calls.append(result)
                hook_arguments = result
            call.taskcall_after_run_hooks.set(after_hook_calls)
            for after_hook_call in after_hook_calls: # start calls after their reference is set
                after_hook_call.apply_async()
            # --- END AFTER_RUN Hooks Dispatch ---


    @staticmethod
    def on_posthook_ended(task_call_id, last_taskrun_id, related_call_status: TaskCallStatusDetail|str):
        '''
        called by the tasks in self.taskcall_after_run_hooks after they finish
        '''
        print("on_posthook_ended", task_call_id, last_taskrun_id, related_call_status)

        if related_call_status == TaskCallStatusDetail.ENDED_STOPPED:
            if AgentTaskCallRuntime._set_status( task_call_id,  TaskCallStatusDetail.WAITING_SUBTASK, TaskCallStatusDetail.ENDED_STOPPED):
                AgentTaskCallRuntime._on_taskcall_ended(task_call_id, last_taskrun_id, TaskCallStatusDetail.ENDED_CANCELLED)
                print("required_task_call.ENDED_STOPPED, TaskCallStatusDetail.ENDED_STOPPED")
            return

        if related_call_status != TaskCallStatusDetail.ENDED_SUCCESS:
            print("required_task_call NOT ENDED_SUCCESS, TaskCallStatusDetail.ENDED_CANCELLED", related_call_status)
            if AgentTaskCallRuntime._set_status( task_call_id, TaskCallStatusDetail.WAITING_SUBTASK, TaskCallStatusDetail.ENDED_CANCELLED):
                AgentTaskCallRuntime._on_taskcall_ended(task_call_id, last_taskrun_id, TaskCallStatusDetail.ENDED_CANCELLED)
            return

        tc = AgentTaskCall.objects.get(pk=task_call_id)
        if tc.taskcall_after_run_hooks.exclude(status=TaskCallStatus.ENDED).exists():
            print("Not all ended")
            return # Still waiting for other arguments    
        AgentTaskCallRuntime.on_all_on_posthook_ended(task_call_id, last_taskrun_id)


    @staticmethod
    def on_all_on_posthook_ended(task_call_id, last_taskrun_id):
        print("on_all_on_posthook_ended", task_call_id, last_taskrun_id)
        updated = AgentTaskCall.objects.filter(
            pk=task_call_id, status_detail__in=[TaskCallStatusDetail.ACTIVE_RUNNING, TaskCallStatusDetail.WAITING_SUBTASK]
        ).update(
            status=TaskCallStatus.ENDED, status_detail=TaskCallStatusDetail.ENDED_SUCCESS, taskcall_result_run_id=last_taskrun_id
        )
        if updated:
            AgentTaskCallRuntime._on_taskcall_ended(task_call_id, last_taskrun_id, TaskCallStatusDetail.ENDED_SUCCESS)


    # ENDED
    @staticmethod
    def _on_taskcall_ended(task_call_id, last_taskrun_id, taskcall_status_detail):
        print("_on_taskcall_ended", task_call_id)
        #task_call = AgentTaskCall.objects.get(pk=task_call_id)
        from server.models.tasks.agent_task_run import AgentTaskRun
        from runtime.task_run_runtime import AgentTaskRunRuntime

        # In case We are a subtask of another task that waits for us to finish for its results
        parent_run_ids = AgentTaskRun.objects.filter(taskrun_result_references__pk=task_call_id, status=TaskRunStatus.WAITING_RESULTTASKS).values_list('pk', flat=True)
        print("parent_run_ids", parent_run_ids)
        for parent_run_id in parent_run_ids:
            AgentTaskRunRuntime.taskrun_result_reference_ended(parent_run_id, task_call_id, taskcall_status_detail)

        # Call tasks that wait for us because their arguments need us
        dependent_ids = AgentTaskCall.objects.filter(taskcall_arg_references__pk=task_call_id, status_detail=TaskCallStatusDetail.WAITING_DEPENDENCY).values_list('pk', flat=True)
        print("dependent_ids", dependent_ids)
        for dependent_id in dependent_ids:
            AgentTaskCallRuntime.on_arg_reference_task_ended(dependent_id, last_taskrun_id, taskcall_status_detail)

        # In case we are a run after hook, call our parent task
        after_run_hook_ids = AgentTaskCall.objects.filter(taskcall_after_run_hooks__pk=task_call_id, status_detail=TaskCallStatusDetail.WAITING_SUBTASK).values_list('pk', flat=True)
        print("after_run_hook_ids", after_run_hook_ids)
        for after_run_hook_id in after_run_hook_ids:
            AgentTaskCallRuntime.on_posthook_ended(after_run_hook_id, last_taskrun_id, taskcall_status_detail)

        # --- taskcall_on_success_callbacks Dispatch ---
        run = AgentTaskRun.objects.get(pk=last_taskrun_id)
        call =  AgentTaskCall.objects.get(pk=task_call_id)
        if taskcall_status_detail == TaskCallStatusDetail.ENDED_SUCCESS:
            print("taskcall_on_success_callbacks", )
            callback_instances = list(run.agent_task_instance.taskinstances_on_success_callbacks.all().order_by('pk'))
            print("callback_instances", callback_instances)
            if callback_instances:
                callbacks = []
                print(f"DEBUG: Dispatching taskcall_on_success_callbacks for taskrun:#{last_taskrun_id}. {len(callback_instances)} found.")
                for i, callback_instance in enumerate(callback_instances):
                    callback_instance: AgentTaskInstance
                    print(f"  -> Launching taskcall_on_success_callback {callback_instance.agent_task_definition.name} (step {i+1}/{len(callback_instances)})")
                    callback = callback_instance.apply_async(kwargs=run)
                    callbacks.append(callback)
                call.taskcall_on_success_callbacks.set(callbacks)

        # --- taskcall_on_error_callbacks Dispatch ---
        elif taskcall_status_detail in [TaskCallStatusDetail.ENDED_FAILURE_EXCEPTION,  TaskCallStatusDetail.ENDED_FAILURE_LOGIC]:
            callback_instances = list(run.agent_task_instance.taskinstances_on_error_callbacks.all().order_by('pk'))
            if callback_instances:
                callbacks = []
                print(f"DEBUG: Dispatching taskcall_on_error_callbacks for taskrun:#{last_taskrun_id}. {len(callback_instances)} found.")
                for i, callback_instance in enumerate(callback_instances):
                    callback_instance: AgentTaskInstance
                    print(f"  -> Launching taskcall_on_error_callback {callback_instance.agent_task_definition.name} (step {i+1}/{len(callback_instances)})")
                    callback = callback_instance.apply_async(kwargs=run)
                    callbacks.append(callback)
                call.taskcall_on_error_callbacks.set(callbacks)


    @staticmethod
    def _set_status(task_call_id, from_status_detail:TaskCallStatusDetail, to_status_detail:TaskCallStatusDetail, filter=None, set=None):
        from_status = TaskCallStatus[from_status_detail.value.split("_",1)[0]]
        to_status = TaskCallStatus[to_status_detail.value.split("_",1)[0]]
        query = AgentTaskCall.objects.filter(pk = task_call_id, status = from_status, status_detail = from_status_detail)
        if filter:
            query = query.filter(filter)
        set = set if set else {}
        updated = query.update(status = to_status, status_detail = to_status_detail, **set)
        return updated > 0
