from __future__ import annotations
import json
from functools import wraps
import traceback
from django.db import models
from runtime.rate_limiter import RateLimitError
from server.models.tasks.agent_task_definition import AgentTaskDefinition
from server.models.content import GenericContent
from runtime.context_manager import ContextTracker
from server.models.enums.task_enums import TaskRunStatus
from server.models.agents.agent_instance_version import AgentInstanceVersion
from server.models.conversation_message import ConversationMessage
from server.models.queries.query import Query
from server.models.queries.response import Response
from server.tasks.task_dispatcher import celery_delay
from server.models.base_model import BaseModel, load_model_references, load_results_data
from django.core.exceptions import ValidationError
from typing import TYPE_CHECKING
from server.models.tasks.agent_task_call import AgentTaskCall

if TYPE_CHECKING:
    from server.models.tasks.agent_task_instance import AgentTaskInstance


class AgentTaskRunSubtask(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    parent = models.ForeignKey("server.AgentTaskRun", related_name="child_relations", on_delete=models.CASCADE)
    child  = models.ForeignKey("server.AgentTaskCall", related_name="parent_relations", on_delete=models.CASCADE)
    index  = models.IntegerField(default=0)

class AgentTaskRun(BaseModel):
    """Single execution attempt"""
    agent_task_call       = models.ForeignKey("AgentTaskCall",         on_delete=models.CASCADE, related_name="related_agent_task_runs")
    agent_task_instance   = models.ForeignKey("AgentTaskInstance",     on_delete=models.CASCADE, related_name="related_agent_task_runs")
    agent_task_definition = models.ForeignKey("AgentTaskDefinition",   on_delete=models.CASCADE, related_name="related_agent_task_runs")
    agent_instance_version = models.ForeignKey(AgentInstanceVersion, on_delete=models.CASCADE, related_name="related_agent_task_runs")
    agent_profile          = models.ForeignKey("server.AgentProfile",  on_delete=models.SET_NULL, related_name="related_agent_task_runs", null=True, blank=True) # will be random select if not given

    # ARGUMENTS - Created by call by mergeing partial args/kwargs of instance with call specific arguments
    arguments_json = models.JSONField(default=dict, null=False)

    # Options - Startup
    dont_start_before = models.DateTimeField(default=None, null=True ) # Absolute time and date of when the task should be executed. 
    dont_start_after  = models.DateTimeField(default=None, null=True) #  Datetime or seconds in the future for the task should expire. The task won't be executed after the expiration time.
    requires_approval = models.BooleanField(default=None, null=False)  # required user approval before run

    # Options - Run
    time_limit      = models.IntegerField(default=None, null=True)     #   
    max_subtask_errors     = models.IntegerField(default=None, null=False)   # for groups,absolute number, also used when timeout
    max_subtask_error_rate = models.IntegerField(default=None, null=False)# for groups, in percent, also used when timeout
    limit_subtask_parallel_runs  = models.IntegerField(default=None, null=False) # how many subtasks cn run in parallel, for groups 0=no limit
    limit_per_instance_parallel_runs  = models.IntegerField(default=None, null=False) #how many times this task can run in parallel per agentInstance it belongs to, 0=no limit

    # Runtime values
    is_approved = models.BooleanField(default=False)  # user did appove this call

    # References in Arguments for a TaskRun must be TaskRun, referencing the actual finished execution of a TaskCall
    # References in results must be TaskCall, hiding the actual (retried and so on) TaskRun that will be launched. 
    taskrun_arg_references     = models.ManyToManyField("server.AgentTaskRun", help_text="AgentTaskRuns used in args/kwargs", symmetrical=False, blank=True, related_name="rev_taskrun_arg_references")
    taskrun_result_references  = models.ManyToManyField("server.AgentTaskCall", help_text="AgentTaskCalls returned in results", symmetrical=False, blank=True, related_name="rev_taskrun_result_references")
    taskrun_subtask_references = models.ManyToManyField("server.AgentTaskCall", help_text="AgentTaskCalls spawned", symmetrical=False, blank=True, related_name="rev_taskrun_sub_taskcalls", through=AgentTaskRunSubtask, through_fields=("parent", "child") )

    status = models.CharField(choices=TaskRunStatus.choices, default=TaskRunStatus.NEW, max_length=61)
    result_json  = models.JSONField(default=None, null=True)

    @classmethod
    def create(cls, agent_task_call: AgentTaskCall, args=None, kwargs=None, dont_start_before=None, dont_start_after=None, requires_approval=None, time_limit=None, max_subtask_errors=None, max_subtask_error_rate=None, limit_subtask_parallel_runs=None, limit_per_instance_parallel_runs=None) -> "AgentTaskRun":
        print("create taskru ", agent_task_call.agent_task_definition.task_type, agent_task_call.agent_task_definition.name, args, kwargs)
        agent_task_instance = agent_task_call.agent_task_instance
        agent_task_instance: AgentTaskInstance
        
        args = args if args else []
        kwargs = kwargs if kwargs else {}        
        if not isinstance(args,(list, set, tuple)):
            args = [args, ]
        if args:
            kwargs["*"] = args
        arguments_json, ref_pks = AgentTaskRun.resolve_calls_to_runs(kwargs)

        taskrun = AgentTaskRun.objects.create(
            agent_task_call = agent_task_call,
            agent_task_instance = agent_task_instance,
            agent_task_definition = agent_task_call.agent_task_definition,
            agent_instance_version  = agent_task_call.agent_instance_version,
            #agent_variant  =  agent_task_call.agent_instance_version.pinned_agent_variant  if agent_task_call.agent_instance_version.pinned_agent_variant else agent_task_call.agent_instance_version.get_or_create_variant(),
            # Arguments
            arguments_json = arguments_json,

            # Options - Startup
            dont_start_before = dont_start_before if dont_start_before else None, # Absolute time and date of when the task should be executed. 
            dont_start_after  = dont_start_after if dont_start_after else None, #  Datetime or seconds in the future for the task should expire. The task won't be executed after the expiration time.
            requires_approval = requires_approval if requires_approval else agent_task_instance.requires_approval,   # required user approval before run

            # Options - Run
            time_limit      = time_limit if time_limit else agent_task_instance.time_limit,   #   
            max_subtask_errors     = max_subtask_errors if max_subtask_errors else agent_task_instance.max_subtask_errors,   # for groups,absolute number, also used when timeout
            max_subtask_error_rate = max_subtask_error_rate if max_subtask_error_rate else agent_task_instance.max_subtask_error_rate,# for groups, in percent, also used when timeout
            limit_subtask_parallel_runs  = limit_subtask_parallel_runs if limit_subtask_parallel_runs else agent_task_instance.limit_subtask_parallel_runs, # how many subtasks cn run in parallel, for groups 0=no limit
            limit_per_instance_parallel_runs = limit_per_instance_parallel_runs if limit_per_instance_parallel_runs else agent_task_instance.limit_per_instance_parallel_runs  #how many times this task can run in parallel per agentInstance it belongs to, 0=no limit
        )
        if ref_pks:
            print("ref_pks", ref_pks)
            taskrun.taskrun_arg_references.set(ref_pks)

        # AUTOMATIC TRACKING
        parent_call = ContextTracker.current
        '''
        # todo not sure if we need this tracking here, i think not
        if parent_call:
            # Fix: use the correct related name 'child_relations' 
            # and ensure we don't duplicate if already linked
            print("agent_task_call", agent_task_call)
            print("parent_call", parent_call)
            print("child_taskrun", taskrun)
            AgentTaskRunSubtask.objects.get_or_create(
                parent = parent_call,
                child = taskrun,
                defaults = {'index': parent_call.parent_relations.count()}
            )
            '''
        return taskrun

    @staticmethod
    def resolve_calls_to_runs(obj, ref_pks=None):
        if ref_pks is None:
            ref_pks = list()
        if isinstance(obj,  (str, int,float, bool) ) or obj is None:
            return obj, ref_pks
        if isinstance(obj, (list, set, tuple)):
            return obj.__class__(AgentTaskRun.resolve_calls_to_runs(item, ref_pks)[0] for item in obj), ref_pks
        if isinstance(obj, (AgentTaskRun, ConversationMessage, GenericContent)):
            return {"_type": obj.__class__.__qualname__, "pk": obj.pk}, ref_pks
        if isinstance(obj, dict):
            if "_type" in obj and "pk" in obj and len(obj) == 2:
                if obj["_type"] == "AgentTaskRun":
                    ref_pks.append(obj["pk"])
                    return obj, ref_pks
                if obj["_type"] == "ConversationMessage":
                    return obj, ref_pks
                if obj["_type"] == "GenericContent":
                    return obj, ref_pks
                if obj["_type"] == "AgentTaskCall":
                    a =  AgentTaskCall.objects.get(pk=obj["pk"])
                    # CRITICAL CHECK: The AgentTaskCall *must* have a result_run at this point.
                    if not a.taskcall_result_run:
                        raise ValueError(
                            f"Dispatcher Error: AgentTaskRun attempted to be created with AgentTaskCall "
                            f"{a.pk} as an argument, but its result_run is not set (status: {a.status_detail}). "
                            "This indicates a bug where AgentTaskRun.create was called prematurely."
                        )
                    ref_pks.append(a.taskcall_result_run.pk)
                    return {"_type": "AgentTaskRun", "pk": a.taskcall_result_run.pk if a.taskcall_result_run  else f"call:{obj["pk"]}"}, ref_pks
                raise Exception(f"Type {obj["_type"]} not allowed in AgentTaskRun.resolve_calls_to_runs")
            return {k: AgentTaskRun.resolve_calls_to_runs(v, ref_pks)[0] for k, v in obj.items()}, ref_pks
        raise Exception(f"Type {obj} unknown")
    
    @staticmethod
    def result_to_json(obj, ref_pks=None):
        print("result_to_json", obj, ref_pks)
        if ref_pks is None:
            ref_pks = []
        if isinstance(obj,  (str, int,float, bool) ) or obj is None:
            return  obj, ref_pks
        if isinstance(obj, dict):
            return {k: AgentTaskRun.result_to_json(v, ref_pks)[0] for k, v in obj.items()}, ref_pks
        if isinstance(obj, (list, set, tuple)):
            return obj.__class__(AgentTaskRun.result_to_json(item, ref_pks)[0] for item in obj), ref_pks
        if isinstance(obj, (Query, ConversationMessage, Response, AgentTaskCall, GenericContent)):
            if isinstance(obj, AgentTaskCall):
                ref_pks.append( obj.pk)
            return {"_type": obj.__class__.__qualname__, "pk": obj.pk}, ref_pks
        raise Exception(f"Type {obj} unknown")

    def apply_async(self):
        query = AgentTaskRun.objects.filter(pk = self.pk, status = TaskRunStatus.NEW)
        if 0 == query.update(status = TaskRunStatus.QUEUED):
            return # was not queued, maybe some race condition
        print("current ctx1" , ContextTracker.current, self)
        from runtime.task_run_runtime import AgentTaskRunRuntime
        celery_delay(AgentTaskRunRuntime._apply_async, self.pk)
    
    def apply(self):
        print("AgentTaskCall.run", self.agent_task_definition.name)
        new_sub_task_calls = []
        result = None
        with ContextTracker(self):
            try:
                runtime = self.agent_instance_version.get_runtime_instance()
                td = self.agent_task_definition
                x = getattr(runtime, td.name)
                kwargs = self.arguments_json
 
                if self.agent_task_definition.task_type == "CHAIN":
                    next_step_kwargs = kwargs
                    for sub_task_instance in self.agent_task_instance.taskinstance_sub_taskinstances.order_by('parent_relations__index').all():
                        next_step_kwargs = sub_task_instance.apply_async(kwargs=next_step_kwargs)
                        new_sub_task_calls.append(next_step_kwargs)
                    result = new_sub_task_calls[-1]
 
                elif self.agent_task_definition.task_type == "GROUP":
                    next_step_kwargs = kwargs
                    for sub_task_instance in self.agent_task_instance.taskinstance_sub_taskinstances.order_by('parent_relations__index').all():
                        call = sub_task_instance.apply_async(kwargs=next_step_kwargs)
                        new_sub_task_calls.append(call)
                    result = new_sub_task_calls
 
                else:
                    args, _ = load_model_references(self.arguments_json)
                    args = load_results_data(args, timeout=0)
                    kwargs = {}
                    if isinstance(args, dict):
                        kwargs = args
                        args = kwargs.pop("*", [])
                    elif not isinstance(args, (list, set, tuple)):
                        args = [args, ]
                    result = x.func(runtime, *args, **kwargs)
 
                self.result_json, ref_pks = AgentTaskRun.result_to_json(obj=result)
                self.taskrun_result_references.add(ref_pks)
                if ref_pks:
                    self.status = TaskRunStatus.WAITING_RESULTTASKS
                else:
                    self.status = TaskRunStatus.SUCCESS
 
            except RateLimitError:
                # LLM capacity was unavailable — not a failure, not a retry.
                # run_runtime._apply_async checks for RATE_LIMITED and transitions
                # the call to WAITING_RATELIMIT without consuming retry budget.
                # result_json is left None — the run will be re-dispatched from scratch.
                self.status = TaskRunStatus.RATE_LIMITED
 
            except Exception as e:
                self.result_json = json.dumps({
                    "exception": f"{e}",
                    "traceback": traceback.format_exc(),
                })
                self.status = TaskRunStatus.FAILURE
 
        # Save result and status atomically
        if not AgentTaskRun.objects.filter(
            pk=self.pk, status=TaskRunStatus.ACTIVE
        ).update(status=self.status, result_json=self.result_json):
            return None, None
        
    def save(self, *args,  allow=False, **kwargs):
        if not allow and self.pk:
            raise ValidationError(f"You may not edit an existing {self._meta.model_name}")
        super().save(*args, **kwargs)

    def __str__(self):
        return f"AgentTaskRun[{self.agent_task_definition.name if self.agent_task_definition else None}]#{self.pk}: {self.status}"
