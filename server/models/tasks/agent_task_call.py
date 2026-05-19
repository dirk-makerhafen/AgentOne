from __future__ import annotations
from datetime import timedelta
from functools import wraps
from pathlib import Path
import random
import threading
import traceback
from types import GeneratorType
from django.db import models
from server.models.queries.query import Query
from server.models.queries.response import Response
from server.models.content import GenericContent
from server.models.message import Message
from runtime.context_manager import ContextTracker
from server.models.enums.task_enums import TaskCallStatus, TaskCallStatusDetail
from server.tasks.task_dispatcher import celery_delay
from server.models.base_model import BaseModel
from django.apps import apps
from celery.utils.functional import is_list, maybe_list, regen, seq_concat_item, seq_concat_seq
from django.db.models import Q
from celery import shared_task
import time
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.db.models import F

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from server.models.tasks.agent_task_instance import AgentTaskInstance

class AgentTaskCall(BaseModel):
    """Specific invocation - equivalent to celery task"""
    agent_task_instance = models.ForeignKey("AgentTaskInstance", on_delete=models.CASCADE, related_name="related_agent_task_calls")
    task_definition_version = models.ForeignKey("TaskDefinitionVersion", on_delete=models.CASCADE, related_name="related_agent_task_calls", default=None, null=True, blank=True)
    session = models.ForeignKey("SessionModel", on_delete=models.CASCADE, related_name="related_agent_task_calls")
    session_version = models.ForeignKey("SessionVersionModel", on_delete=models.CASCADE, related_name="related_agent_task_calls")
    
    # ARGUMENTS - Call Arguments, will be merged with Session arguments
    carguments_json = models.JSONField(default=dict, null=False)

    # Options - Startup
    dont_start_before = models.DateTimeField(default=None, null=True) # Absolute time and date of when the task should be executed. 
    dont_start_after  = models.DateTimeField(default=None, null=True) #  Datetime or seconds in the future for the task should expire. The task won't be executed after the expiration time.
    requires_approval = models.BooleanField(default=None, null=False)  # required user approval before run
    
    # Options - Run
    time_limit      = models.IntegerField(default=None, null=True)
    max_subtask_errors     = models.IntegerField(default=None, null=False)   # for groups,absolute number, also used when timeout
    max_subtask_error_rate = models.IntegerField(default=None, null=False)# for groups, in percent, also used when timeout
    limit_subtask_parallel_runs  = models.IntegerField(default=None, null=False) # how many subtasks cn run in parallel, for groups 0=no limit
    limit_per_instance_parallel_runs  = models.IntegerField(default=None, null=False) #how many times this task can run in parallel per agentInstance it belongs to, 0=no limit
    priority = models.IntegerField(default=0)   # 0 = highest, 1..999 less important

    # Options - Retry
    max_retries  = models.IntegerField(default=None, null=False)   # how many retries to we make in case of error
    retry_delay  = models.IntegerField(default=None, null=False)  # time between retries in seconds
    retry_requires_approval = models.BooleanField(default=None, null=False)  # required user approval before run

    # Runtime values
    is_approved = models.BooleanField(default=None, null=True)  # user did appove this call
    retry_count = models.IntegerField(default=0)   #count will not be avauilable 
    ended_at = models.DateTimeField(editable=False, null=True, default=None)

    parent_taskruns = models.ForeignKey("server.AgentTaskCall", blank=True, on_delete=models.CASCADE, related_name="child_taskcalls" )

    taskcall_arg_references     = models.ManyToManyField("self", help_text="AgentTaskCalls used in call args/kwargs", symmetrical=False, blank=True, related_name="rev_taskcall_arg_references")
    
    taskcall_on_success_callbacks = models.ManyToManyField("self", help_text="", symmetrical=False, blank=True, related_name="rev_taskcall_on_success_callbacks")
    taskcall_on_error_callbacks   = models.ManyToManyField("self", help_text="", symmetrical=False, blank=True, related_name="rev_taskcall_on_error_callbacks")
    taskcall_before_run_hooks = models.ManyToManyField("self", help_text="", symmetrical=False, blank=True, related_name="rev_taskcall_before_run_hooks")
    taskcall_after_run_hooks  = models.ManyToManyField("self", help_text="", symmetrical=False, blank=True, related_name="rev_taskcall_after_run_hooks")

    # Status
    status = models.CharField(choices=TaskCallStatus.choices, default=TaskCallStatus.NEW, max_length=61)
    status_detail = models.CharField(choices=TaskCallStatusDetail.choices, default=TaskCallStatusDetail.NEW, max_length=61)

    taskcall_result_run = models.ForeignKey("server.AgentTaskRun", null=True, blank=True, default=None, on_delete=models.SET_DEFAULT, related_name="rev_taskcall_result_run")

    @classmethod
    def create(cls, agent_task_instance: "AgentTaskInstance", args=None, kwargs=None, dont_start_before=None, dont_start_after=None, requires_approval=None, time_limit=None, max_subtask_errors=None, max_subtask_error_rate=None, limit_subtask_parallel_runs=None, limit_per_instance_parallel_runs=None, max_retries = None, retry_delay = None, retry_requires_approval = None, priority:int|None = None ):
        """Create AgentTaskCall.

        Returns:
            :class:`AgentTaskCall`: 
        """
        parent_run = ContextTracker.current
        from server.models.tasks.agent_task_run import AgentTaskRunSubtask

        args = args if args else []
        arguments = kwargs if kwargs else {}
        if not isinstance(args,(list, set, tuple)):
            args = [args, ]
        if args:
            arguments["*"] = args

        next_input = arguments

        # --- BEFORE_RUN Hooks Create ---
        before_hooks = list(agent_task_instance.taskinstances_before_run_hooks.all().order_by('pk'))
        before_hook_calls = []
        if before_hooks:
            for i, hook_instance in enumerate(before_hooks):
                hook_instance: AgentTaskInstance
                next_input = hook_instance.call(kwargs=next_input)
                before_hook_calls.append(next_input)
        
        arguments_json, ref_pks = AgentTaskCall.create_call_arguments_json(arguments=next_input)
       
        taskcall = AgentTaskCall.objects.create(
            agent_task_instance = agent_task_instance,
            task_definition_version = agent_task_instance.task_definition_version,
            session = agent_task_instance.session,
            session_version = agent_task_instance.session_version,
            # Arguments
            carguments_json = arguments_json,

            # Options - Startup
            dont_start_before = dont_start_before if dont_start_before else None,
            dont_start_after = dont_start_after if dont_start_after else None,
            requires_approval = requires_approval if requires_approval else agent_task_instance.requires_approval,

            # Options - Run
            time_limit      = time_limit if time_limit else agent_task_instance.time_limit,     #
            max_subtask_errors     = max_subtask_errors if max_subtask_errors else agent_task_instance.max_subtask_errors,   # for groups,absolute number, also used when timeout
            max_subtask_error_rate = max_subtask_error_rate if max_subtask_error_rate else agent_task_instance.max_subtask_error_rate,# for groups, in percent, also used when timeout
            limit_subtask_parallel_runs  = limit_subtask_parallel_runs if limit_subtask_parallel_runs else agent_task_instance.limit_subtask_parallel_runs, # how many subtasks cn run in parallel, for groups 0=no limit
            limit_per_instance_parallel_runs  = limit_per_instance_parallel_runs if limit_per_instance_parallel_runs else agent_task_instance.limit_per_instance_parallel_runs, #how many times this task can run in parallel per agentInstance it belongs to, 0=no limit
            priority  = priority if priority else agent_task_instance.priority,   # how many retries to we make in case of error

            # Options - Retry
            max_retries  = max_retries if max_retries else agent_task_instance.max_retries,   # how many retries to we make in case of error
            retry_delay  = retry_delay if retry_delay else agent_task_instance.retry_delay,  # time between retries in seconds
            retry_requires_approval = retry_requires_approval if retry_requires_approval else agent_task_instance.retry_requires_approval,  # required user approval before run
            # Runtime values
            is_approved = None
        )
        taskcall.taskcall_before_run_hooks.set(before_hook_calls)

        if ref_pks:
            taskcall.taskcall_arg_references.set(ref_pks)

        # AUTOMATIC TRACKING
        if parent_run:
            AgentTaskRunSubtask.objects.get_or_create(
                parent=parent_run,
                child=taskcall,
                defaults={'index': parent_run.child_relations.count()}
            )

        return taskcall

    def apply_async(self) :
        if not self.pk:
            raise Exception("Must save first")
        print("current ctx2" , ContextTracker.current)
        for before_hook_call in self.taskcall_before_run_hooks.all(): # start calls after their reference is set
            before_hook_call.apply_async()
        from runtime.tasks.call_scheduler import CallScheduler
        celery_delay(CallScheduler._apply_async, self.pk)
        return self
    
    @staticmethod
    def create_call_arguments_json(arguments):
        from server.models.tasks.agent_task_run import AgentTaskRun
        allowed_objects = {
            "AgentTaskCall" : AgentTaskCall,  "AgentTaskRun" : AgentTaskRun,   "Message" : Message, 
            "GenericContent" : GenericContent,  "Query": Query, "Response": Response
        }

        def _create_recursive(obj, ref_pks:list[int]):
            if isinstance(obj,  (str, int,float, bool) ) or obj is None:
                return obj
            if isinstance(obj, (list, set, tuple)):
                return [_create_recursive(item, ref_pks) for item in obj]
            if isinstance(obj, dict):
                if "_type" in obj and "pk" in obj and len(obj) == 2:
                    if obj["_type"] in allowed_objects:
                        ref_pks.append(obj["pk"])
                        return obj
                    raise Exception(f"This should not be here in AgentTaskCall.arguments_to_json {obj}")
                return {k: _create_recursive(v, ref_pks) for k, v in obj.items()}
            if isinstance(obj, AgentTaskCall):
                ref_pks.append(obj.pk)
                return {"_type": "AgentTaskCall", "pk": obj.pk}
            try:
                if obj.__class__.__qualname__ in allowed_objects:
                    return {"_type": obj.__class__.__qualname__, "pk": obj.pk}
            except:
                pass
            if isinstance(obj, Path):
                return obj.as_posix()
            raise Exception(f"Type {type(obj)} unknown")
        ref_pks=list()
        return _create_recursive(obj=arguments,ref_pks=ref_pks), ref_pks
    
    def _resolve_call_arguments(self, timeout=0, recursive=True, allow_partial_results=False):
        from server.models.tasks.agent_task_call import AgentTaskCall
        from server.models.tasks.agent_task_run import AgentTaskRun
       
        def _get_recursive(data, timeout, recursive, allow_partial_results):
            if isinstance(data, dict):
                if "_type" in data and "pk" in data:
                    model_instance = apps.get_model('server', data["_type"]).objects.get(pk=data["pk"])
                    if recursive and (isinstance(model_instance, AgentTaskRun) or isinstance(model_instance, AgentTaskCall)):
                        return model_instance.get_result(recursive=recursive, timeout=timeout, allow_partial_results=allow_partial_results)
                    return model_instance
                return {k: _get_recursive(data=v, timeout=timeout, recursive=recursive, allow_partial_results=allow_partial_results) for k, v in data.items()}
            
            elif isinstance(data, list):
                return [_get_recursive(data=item, timeout=timeout, recursive=recursive, allow_partial_results=allow_partial_results) for item in data]
            
            elif isinstance(data, AgentTaskCall) or isinstance(data, AgentTaskRun):
                if recursive:
                    return data.get_result(timeout=timeout, recursive=recursive, allow_partial_results=allow_partial_results)
               
            return data
        return _get_recursive(data = self.carguments_json, timeout=timeout, recursive=recursive, allow_partial_results=allow_partial_results)
      

    def get_result(self, timeout=0, recursive=True, allow_partial_results=False):
        '''
        recursive: for AgentTaskCall items in result return their .get_result()
        timeout: seconds to block while waiting for result pending subresult, 0 for no timeout, None for never. 
        allow_partial_results: return partial results that dont fully resolve all recursive results from sub calls, otherwise fail
        '''
        s = time.time()
        subtimeout = timeout
        while True:
            if self.status in [TaskCallStatus.ENDED, ]:
                if self.taskcall_result_run:
                    return self.taskcall_result_run.get_result(timeout=subtimeout, recursive=recursive, allow_partial_results=allow_partial_results)
                return None
            if timeout is not None:
                if time.time() - s >= timeout:
                    if allow_partial_results:
                        return None
                    raise TimeoutError("TaskRunResult not ready")
                if subtimeout > 0:
                    subtimeout -= 1
            time.sleep(1)

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError(f"You may not edit an existing {self._meta.model_name}")
        super().save(*args, **kwargs)

    def __str__(self):
        try:
            return f"<AgentTaskCall[{self.pk}]# {self.task_definition_version.name if self.task_definition_version else None}>"
        except:
            return f"AgentTaskRun[{self.pk}]#{self.pk}: {self.status}"
