from __future__ import annotations
import copy
import json
from functools import wraps
from pathlib import Path
import time
import traceback
from types import GeneratorType
from django.db import models
from runtime.rate_limiter import RateLimitError
from server.models.tasks.task_definition import TaskDefinition
from server.models.content import GenericContent
from runtime.context_manager import ContextTracker
from server.models.enums.task_enums import TaskRunStatus
from server.models.sessions.session_version import SessionVersionModel
from server.models.message import Message
from server.models.queries.query import Query
from server.models.queries.response import Response
from server.tasks.task_dispatcher import celery_delay
from server.models.base_model import BaseModel
from django.core.exceptions import ValidationError
from typing import TYPE_CHECKING
from server.models.tasks.agent_task_call import AgentTaskCall
from django.apps import apps

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
    task_definition_version = models.ForeignKey("TaskDefinitionVersion",   on_delete=models.CASCADE, related_name="related_agent_task_runs", default=None, null=True, blank=True)
    session_version = models.ForeignKey(SessionVersionModel, on_delete=models.CASCADE, related_name="related_agent_task_runs")

    # ARGUMENTS - Created by call by mergeing partial args/kwargs of instance with call specific arguments
    arguments_json = models.JSONField(default=dict, null=False)

    # Options - Startup
    dont_start_before = models.DateTimeField(default=None, null=True ) # Absolute time and date of when the task should be executed. 
    dont_start_after  = models.DateTimeField(default=None, null=True) #  Datetime or seconds in the future for the task should expire. The task won't be executed after the expiration time.
    requires_approval = models.BooleanField(default=None, null=False)  # required user approval before run
    priority = models.IntegerField(default=0)   # 0 = highest, 1..999 less important

    # Options - Run
    time_limit      = models.IntegerField(default=None, null=True)     #   
    max_subtask_errors     = models.IntegerField(default=None, null=False)   # for groups,absolute number, also used when timeout
    max_subtask_error_rate = models.IntegerField(default=None, null=False)# for groups, in percent, also used when timeout
    limit_subtask_parallel_runs  = models.IntegerField(default=None, null=False) # how many subtasks cn run in parallel, for groups 0=no limit
    limit_per_instance_parallel_runs  = models.IntegerField(default=None, null=False) #how many times this task can run in parallel per agentInstance it belongs to, 0=no limit

    # Runtime values
    is_approved = models.BooleanField(default=False)  # user did appove this call
    ended_at = models.DateTimeField(editable=False, null=True, default=None)


    # References in Arguments for a TaskRun must be TaskRun, referencing the actual finished execution of a TaskCall
    # References in results must be TaskCall, hiding the actual (retried and so on) TaskRun that will be launched. 
    taskrun_arg_references     = models.ManyToManyField("server.AgentTaskRun", help_text="AgentTaskRuns used in args/kwargs", symmetrical=False, blank=True, related_name="rev_taskrun_arg_references")
    taskrun_result_references  = models.ManyToManyField("server.AgentTaskCall", help_text="AgentTaskCalls returned in results", symmetrical=False, blank=True, related_name="rev_taskrun_result_references")
    taskrun_subtask_references = models.ManyToManyField("server.AgentTaskCall", help_text="AgentTaskCalls spawned", symmetrical=False, blank=True, related_name="rev_taskrun_subtask_references", through=AgentTaskRunSubtask, through_fields=("parent", "child") )

    status = models.CharField(choices=TaskRunStatus.choices, default=TaskRunStatus.NEW, max_length=61)
    result_json  = models.JSONField(default=None, null=True)

    @classmethod
    def create(cls, agent_task_call: AgentTaskCall, args=None, kwargs=None, dont_start_before=None, dont_start_after=None, requires_approval=None, time_limit=None, max_subtask_errors=None, max_subtask_error_rate=None, limit_subtask_parallel_runs=None, limit_per_instance_parallel_runs=None) -> "AgentTaskRun":
        print("create taskru ", agent_task_call.task_definition_version, agent_task_call.task_definition_version, args, kwargs)
        agent_task_instance = agent_task_call.agent_task_instance
        agent_task_instance: AgentTaskInstance
        
        args = args if args else []
        kwargs = kwargs if kwargs else {}

        arguments_json, ref_pks = AgentTaskRun._create_run_arguments_json(args=args, kwargs=kwargs)
        print("IN CREATE")
        taskrun = AgentTaskRun.objects.create(
            agent_task_call = agent_task_call,
            agent_task_instance = agent_task_instance,
            task_definition_version = agent_task_call.task_definition_version,
            session_version  = agent_task_call.session_version,
            #agent_variant  =  agent_task_call.session_version.pinned_agent_variant  if agent_task_call.session_version.pinned_agent_variant else agent_task_call.session_version.get_or_create_variant(),
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
            taskrun.taskrun_arg_references.set(ref_pks)
        print("TASKRUN", taskrun)
        
        return taskrun

    def apply_async(self):
        print("TASKRUN apply_async")
        query = AgentTaskRun.objects.filter(pk = self.pk, status = TaskRunStatus.NEW)
        if 0 == query.update(status = TaskRunStatus.QUEUED):
            return # was not queued, maybe some race condition
        from runtime.tasks.run_scheduler import RunScheduler
        celery_delay(RunScheduler._apply_async, self.pk)
    
    def apply(self):
        print("AgentTaskCall.run", self.task_definition_version)
        task_definition=  self.task_definition_version.task_definition
        new_sub_task_calls = []
        result = None
        with ContextTracker(self):
            try:
                runtime = self.session_version.get_runtime()

                if task_definition.task_type == "CHAIN":
                    # Start subcalls for chain
                    next_step_arguments = self.arguments_json
                    for sub_task_instance in self.agent_task_instance.taskinstance_sub_taskinstances.order_by('parent_relations__index').all():
                        next_step_arguments = sub_task_instance.apply_async(kwargs=next_step_arguments)
                        new_sub_task_calls.append(next_step_arguments)
                    result = new_sub_task_calls[-1]

                elif task_definition.task_type == "GROUP":
                    # Start subcalls for groups
                    for sub_task_instance in self.agent_task_instance.taskinstance_sub_taskinstances.order_by('parent_relations__index').all():
                        call = sub_task_instance.apply_async(kwargs=self.arguments_json)
                        new_sub_task_calls.append(call)
                    result = new_sub_task_calls

                else: 
                    # normal executions            
                    bound_agent_function = getattr(runtime, task_definition.name)
                    args, kwargs = self._resolve_run_arguments(timeout=0)
                    print("args, kwargs", args, kwargs)
                    result = bound_agent_function.call(*args, **kwargs)

                self.result_json, ref_pks = self._create_result_json(result=result)
                self.taskrun_result_references.set(ref_pks)
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
                self.result_json = json.dumps({"exception": f"{e}", "traceback": traceback.format_exc()})
                self.status = TaskRunStatus.FAILURE

        # Save result and status atomically
        query = AgentTaskRun.objects.filter(pk=self.pk, status=TaskRunStatus.ACTIVE)
        if not query.update(status=self.status, result_json=self.result_json):
            return None, None

    @staticmethod
    def _create_run_arguments_json(args, kwargs):

        def _create_recursive(obj, ref_pks:list[int]):
            if isinstance(obj,  (str, int,float, bool) ) or obj is None:
                return obj
            if isinstance(obj, (list, set, tuple)):
                return obj.__class__(_create_recursive(item, ref_pks) for item in obj)
            if isinstance(obj, (AgentTaskRun, Message, GenericContent, Query, Response)):
                return {"_type": obj.__class__.__qualname__, "pk": obj.pk}
            if isinstance(obj, dict):
                if "_type" in obj and "pk" in obj and len(obj) == 2:
                    if obj["_type"] == "AgentTaskRun":
                        ref_pks.append(obj["pk"])
                        return obj
                    if obj["_type"] in [ "Message",  "Query", "Response", ]:
                        return obj
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
                        return {"_type": "AgentTaskRun", "pk": a.taskcall_result_run.pk if a.taskcall_result_run  else f"call:{obj["pk"]}"}
                    raise Exception(f"Type {obj["_type"]} not allowed in AgentTaskRun.resolve_calls_to_runs")
                return {k: _create_recursive(v, ref_pks) for k, v in obj.items()}
            if isinstance(obj, Path):
                return obj.as_posix()
            raise Exception(f"Type {type(obj)} unknown")
        
        arguments = copy.copy(kwargs)
        if isinstance(args, GeneratorType):
            args = list(args)
        if not isinstance(args, (list, set, tuple)):
            args = [args, ]
        if args:
            arguments["*"] = args

        ref_pks=list()
        return _create_recursive(obj=arguments, ref_pks=ref_pks), ref_pks

    def _resolve_run_arguments(self, timeout=0, recursive=True, allow_partial_results=False):
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
        
        arguments = _get_recursive(data = self.arguments_json, timeout=timeout, recursive=recursive, allow_partial_results=allow_partial_results)

        kwargs = {}
        if isinstance(arguments, dict):
            args = arguments.pop("*", [])
            kwargs = arguments
        elif not isinstance(arguments, (list, set, tuple)):
            print("ISINSTANCE", arguments)
            args = [arguments, ]

        return args, kwargs
      
    @staticmethod
    def _create_result_json(result):
        def _create_recursive(obj, ref_pks:list[int]):
            if isinstance(obj,  (str, int,float, bool) ) or obj is None:
                return  obj
            if isinstance(obj, dict):
                return {k: _create_recursive(v, ref_pks) for k, v in obj.items()}
            if isinstance(obj, (list, set, tuple)):
                return obj.__class__(_create_recursive(item, ref_pks) for item in obj)
            if isinstance(obj, ( AgentTaskCall, Message, Query, Response)):
                if isinstance(obj, AgentTaskCall):
                    ref_pks.append( obj.pk)
                return {"_type": obj.__class__.__qualname__, "pk": obj.pk}
            if isinstance(obj, Path):
                return obj.as_posix()
            raise Exception(f"Type {type(obj)} unknown")
        ref_pks=list()
        return _create_recursive(obj=result, ref_pks=ref_pks), ref_pks

    def get_result(self, timeout=0, recursive=False, allow_partial_results=False):
        '''
        recursive: for AgentTaskCall items in result return their .get_result()
        timeout: seconds to block while waiting for result pending subresult, 0 for no timeout, None for never. 
        allow_partial_results: return partial results that dont fully resolve all recursive results from sub calls, otherwise fail
        '''
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
            return data

        s = time.time()
        subtimeout = timeout
        while True:
            if self.status in [TaskRunStatus.SUCCESS, TaskRunStatus.FAILURE]:
                if self.result_json:
                    return _get_recursive(data = self.result_json, timeout=subtimeout, recursive=recursive, allow_partial_results=allow_partial_results)
                return None
            if timeout is not None:
                if time.time() - s >= timeout:
                    if allow_partial_results:
                        return None
                    raise TimeoutError("TaskRunResult not ready")
                if subtimeout > 0:
                    subtimeout -= 1
            time.sleep(1)
      
            
    def save(self, *args,  allow=False, **kwargs):
        if not allow and self.pk:
            raise ValidationError(f"You may not edit an existing {self._meta.model_name}")
        super().save(*args, **kwargs)

    def __str__(self):
        try:
            return f"AgentTaskRun[{self.task_definition_version.name if hasattr(self, 'agent_task_definition') else None}]#{self.pk}: {self.status}"
        except:
            return f"AgentTaskRun[{self}]#{self.pk}: {self.status}"
