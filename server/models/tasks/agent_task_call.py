from __future__ import annotations
from datetime import timedelta
from functools import wraps
import random
import threading
import traceback
from django.db import models
from server.models.content import GenericContent
from server.models.conversation_message import ConversationMessage
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

class AgentTaskCallResult():
    def __init__(self, agent_task_call) -> None:
        self.agent_task_call = agent_task_call

    def get(self, timeout=None):
        s = time.time()
        while True:
            self.agent_task_call.refresh_from_db()
            if self.agent_task_call.status in [TaskCallStatus.ENDED]:
                return self.agent_task_call.taskcall_result_run.result_json
            if timeout and time.time() - s >= timeout:
                break
            time.sleep(1)
            print("PENDING for result of", self.agent_task_call, self.agent_task_call.status )
        print("data",self.agent_task_call.taskcall_result_run.result_json)
        print(self.agent_task_call)
        
        return None


'''
class AgentTaskCallSubtask(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    parent = models.ForeignKey("server.AgentTaskCall", related_name="child_relations", on_delete=models.CASCADE)
    child  = models.ForeignKey("server.AgentTaskCall", related_name="parent_relations", on_delete=models.CASCADE)
    index  = models.IntegerField(default=0)
'''

class AgentTaskCall(BaseModel):
    """Specific invocation - equivalent to celery task"""
    agent_task_instance = models.ForeignKey("AgentTaskInstance", on_delete=models.CASCADE, related_name="related_agent_task_calls")
    agent_task_definition = models.ForeignKey("AgentTaskDefinition", on_delete=models.CASCADE, related_name="related_agent_task_calls")
    agent_instance = models.ForeignKey("AgentInstance", on_delete=models.CASCADE, related_name="related_agent_task_calls")
    agent_instance_version = models.ForeignKey("AgentInstanceVersion", on_delete=models.CASCADE, related_name="related_agent_task_calls")
    
    # ARGUMENTS - Call Arguments, will be merged with Instance arguments
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

    # Options - Retry
    max_retries  = models.IntegerField(default=None, null=False)   # how many retries to we make in case of error
    retry_delay  = models.IntegerField(default=None, null=False)  # time between retries in seconds
    retry_requires_approval = models.BooleanField(default=None, null=False)  # required user approval before run

    # Runtime values
    is_approved = models.BooleanField(default=None, null=True)  # user did appove this call
    retry_count = models.IntegerField(default=0)   #count will not be avauilable 

    taskcall_arg_references     = models.ManyToManyField("self", help_text="AgentTaskCalls used in call args/kwargs", symmetrical=False, blank=True, related_name="rev_taskcall_arg_references")
    
    taskcall_on_success_callbacks = models.ManyToManyField("self", help_text="", symmetrical=False, blank=True, related_name="rev_taskcall_on_success_callbacks")
    taskcall_on_error_callbacks   = models.ManyToManyField("self", help_text="", symmetrical=False, blank=True, related_name="rev_taskcall_on_error_callbacks")
    taskcall_before_run_hooks = models.ManyToManyField("self", help_text="", symmetrical=False, blank=True, related_name="rev_taskcall_before_run_hooks")
    taskcall_after_run_hooks  = models.ManyToManyField("self", help_text="", symmetrical=False, blank=True, related_name="rev_taskcall_after_run_hooks")

    # Status
    status = models.CharField(choices=TaskCallStatus.choices, default=TaskCallStatus.NEW, max_length=61)
    status_detail = models.CharField(choices=TaskCallStatusDetail.choices, default=TaskCallStatusDetail.NEW, max_length=61)

    taskcall_result_run = models.ForeignKey("server.AgentTaskRun", null=True, blank=True, default=None, on_delete=models.SET_DEFAULT)

    @property
    def results(self):
        return AgentTaskCallResult(self)

    @classmethod
    def create(cls, agent_task_instance: "AgentTaskInstance", args=None, kwargs=None, dont_start_before=None, dont_start_after=None, requires_approval=None, time_limit=None, max_subtask_errors=None, max_subtask_error_rate=None, limit_subtask_parallel_runs=None, limit_per_instance_parallel_runs=None, max_retries = None, retry_delay = None, retry_requires_approval = None ):
        """Create AgentTaskCall.

        Returns:
            :class:`AgentTaskCall`: 
        """
        parent_run = ContextTracker.current
        from server.models.tasks.agent_task_run import AgentTaskRunSubtask

        args = args if args else []
        kwargs = kwargs if kwargs else {}
        if not isinstance(args,(list, set, tuple)):
            args = [args, ]
        if args:
            kwargs["*"] = args
        next_input = kwargs
        print("testing", kwargs, args)
        # --- BEFORE_RUN Hooks Create ---
        before_hooks = list(agent_task_instance.taskinstances_before_run_hooks.all().order_by('pk'))
        before_hook_calls = []
        if before_hooks:
            print(f"DEBUG: Dispatching BEFORE_RUN hooks for {agent_task_instance.agent_task_definition.name}. {len(before_hooks)} hooks found.")
            for i, hook_instance in enumerate(before_hooks):
                hook_instance: AgentTaskInstance
                print(f"  -> Launching before_run hook {hook_instance.agent_task_definition.name} (step {i+1}/{len(before_hooks)})")
                next_input = hook_instance.call(kwargs=next_input)
                before_hook_calls.append(next_input)
                
        # --- END BEFORE_RUN Hooks Create ---
        arguments_json  , ref_pks = AgentTaskCall.callargs_to_json(next_input)
        taskcall = AgentTaskCall.objects.create(
            agent_task_instance = agent_task_instance,
            agent_task_definition = agent_task_instance.agent_task_definition,
            agent_instance = agent_task_instance.agent_instance,
            agent_instance_version = agent_task_instance.agent_instance_version,
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
            limit_subtask_parallel_runs  = limit_subtask_parallel_runs if limit_subtask_parallel_runs else agent_task_instance.limit_per_instance_parallel_runs, # how many subtasks cn run in parallel, for groups 0=no limit
            limit_per_instance_parallel_runs  = limit_per_instance_parallel_runs if limit_per_instance_parallel_runs else agent_task_instance.limit_subtask_parallel_runs, #how many times this task can run in parallel per agentInstance it belongs to, 0=no limit

            # Options - Retry
            max_retries  = max_retries if max_retries else agent_task_instance.max_retries,   # how many retries to we make in case of error
            retry_delay  = retry_delay if retry_delay else agent_task_instance.retry_delay,  # time between retries in seconds
            retry_requires_approval = retry_requires_approval if retry_requires_approval else agent_task_instance.retry_requires_approval,  # required user approval before run
            # Runtime values
            is_approved = None
        )
        taskcall.taskcall_before_run_hooks.set(before_hook_calls)

        if ref_pks:
            print("ref_pks", ref_pks)
            taskcall.taskcall_arg_references.set(ref_pks)

        # AUTOMATIC TRACKING
        if parent_run:
            AgentTaskRunSubtask.objects.get_or_create(
                parent=parent_run,
                child=taskcall,
                defaults={'index': parent_run.child_relations.count()}
            )

        return taskcall

    def apply_async(self):
        if not self.pk:
            raise Exception("Must save first")
        print("current ctx2" , ContextTracker.current)
        for before_hook_call in self.taskcall_before_run_hooks.all(): # start calls after their reference is set
            before_hook_call.apply_async()
        from runtime.tasks.call_runtime import AgentTaskCallRuntime
        celery_delay(AgentTaskCallRuntime._apply_async, self.pk)

    @staticmethod
    def callargs_to_json(obj, ref_pks=None):
        from server.models.tasks.agent_task_run import AgentTaskRun

        if ref_pks is None:
            ref_pks = list()
        if isinstance(obj,  (str, int,float, bool) ) or obj is None:
            return obj, ref_pks
        if isinstance(obj, dict):
            if "_type" in obj and "pk" in obj and len(obj) == 2:
                if obj["_type"] == "AgentTaskCall":
                    ref_pks.append(obj["pk"])
                    return obj, ref_pks
                if obj["_type"] == "AgentTaskRun":
                    return obj, ref_pks
                if obj["_type"] == "ConversationMessage":
                    return obj, ref_pks
                if obj["_type"] == "GenericContent":
                    return obj, ref_pks
                raise Exception(f"This should not be here in AgentTaskCall.arguments_to_json {obj}")
            return {k: AgentTaskCall.callargs_to_json(v, ref_pks)[0] for k, v in obj.items()}, ref_pks
        if isinstance(obj, list):
            return [AgentTaskCall.callargs_to_json(item, ref_pks)[0] for item in obj], ref_pks
        if isinstance(obj, set):
            return set([AgentTaskCall.callargs_to_json(item, ref_pks)[0] for item in obj]), ref_pks
        if isinstance(obj, tuple):
            return tuple([AgentTaskCall.callargs_to_json(item, ref_pks)[0] for item in obj]), ref_pks
        if isinstance(obj, AgentTaskCall):
            ref_pks.append(obj.pk)
            return {"_type": "AgentTaskCall", "pk": obj.pk}, ref_pks
        if isinstance(obj, AgentTaskRun):
            return {"_type": "AgentTaskRun", "pk": obj.pk}, ref_pks
        if isinstance(obj, ConversationMessage):
            return {"_type": "ConversationMessage", "pk": obj.pk}, ref_pks
        if isinstance(obj, GenericContent):
            return {"_type": "GenericContent", "pk": obj.pk}, ref_pks
        raise Exception(f"Type {obj} unknown")

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError(f"You may not edit an existing {self._meta.model_name}")
        super().save(*args, **kwargs)

    def __str__(self):
        return f"<AgentTaskCall[{self.pk}]# {self.agent_task_definition.name if self.agent_task_definition else None}>"
