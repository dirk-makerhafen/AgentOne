from functools import wraps
from pathlib import Path
from types import GeneratorType
from django.db import models
from runtime.context_manager import ContextTracker
from server.models.tasks.agent_task_call import AgentTaskCall
from server.models.base_model import BaseModel
from django.core.exceptions import ValidationError
from celery.utils.functional import is_list, maybe_list, regen, seq_concat_item, seq_concat_seq
from sortedm2m.fields import SortedManyToManyField

from typing import TYPE_CHECKING

from server.models.tasks.task_definition_version import TaskDefinitionVersion


class AgentTaskInstance(BaseModel):
    """Binds a task definition to a specific agent instance"""
    task_definition_version   = models.ForeignKey("TaskDefinitionVersion" ,default=None, null=True, on_delete=models.CASCADE, related_name="related_agent_task_instances")
    session          = models.ForeignKey("SessionModel"       , on_delete=models.CASCADE, related_name="related_agent_task_instances")
    session_version  = models.ForeignKey("SessionVersionModel", on_delete=models.CASCADE, related_name="related_agent_task_instances")

    # instance wide args/kwargs, will be prepended/merged with call args/kwargs
    iarguments_json = models.JSONField(default=dict, null=True)

    # Options - Startup
    requires_approval = models.BooleanField(default=None, null=False)  # required user approval before run

    # Options - Run
    time_limit      = models.IntegerField(default=None, null=True)     #   
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
    retry_count = models.IntegerField(default=0) 

    child_instances = SortedManyToManyField("self", symmetrical=False, blank=True, related_name="parent_instances" )

    taskinstance_arg_references    = models.ManyToManyField("self", help_text="AgentTaskInstances used in instance args/kwargs", symmetrical=False, blank=True, related_name="rev_taskinstance_arg_references")
    taskinstance_result_references = models.ManyToManyField("self", help_text="", symmetrical=False, blank=True, related_name="rev_taskinstance_result_references")

    taskinstances_on_success_callbacks = models.ManyToManyField("self", help_text="", symmetrical=False, blank=True, related_name="rev_taskinstances_on_success_callbacks")
    taskinstances_on_error_callbacks   = models.ManyToManyField("self", help_text="", symmetrical=False, blank=True, related_name="rev_taskinstances_callback_on_erro")
    taskinstances_before_run_hooks     = models.ManyToManyField("self", help_text="", symmetrical=False, blank=True, related_name="rev_taskinstances_hook_before_run")
    taskinstances_after_run_hooks      = models.ManyToManyField("self", help_text="", symmetrical=False, blank=True, related_name="rev_taskinstances_hook_after_run")

    @property
    def task_type(self):
        return self.task_definition_version.task_type

    @property
    def agent_task_calls(self):
        return self.related_agent_task_calls # pyright: ignore[reportAttributeAccessIssue]

    @property
    def task_execution_mode(self):
        return self.task_definition_version.task_execution_mode

    @classmethod
    def get_or_create(cls, task_definition:TaskDefinitionVersion, session_version, args = None, kwargs=None, **options ) -> "AgentTaskInstance":
        """Create AgentTaskInstance.
        Returns:
            :class:`AgentTaskInstance`:  object for this task, wrapping arguments and options for multiple task invocation.
        """
        print("get_or_create44", cls, task_definition, session_version, args, kwargs)
        session = session_version.session

        args = args if args else []
        arguments = kwargs if kwargs else {}
        if not isinstance(args,(list, set, tuple)):
            args = [args, ]
        if args:
            arguments["*"] = args
            
        arguments_json, ref_pks = AgentTaskInstance._create_instance_arguments_json(arguments=arguments)

        agent_task_instance, created = AgentTaskInstance.objects.get_or_create(
            task_definition_version = task_definition,
            session = session,
            session_version = session_version,
            # Arguments
            iarguments_json = arguments_json,
            # Options - Startup
            requires_approval = task_definition.requires_approval,
            # Options - Run
            time_limit      = task_definition.time_limit ,  
            max_subtask_errors     = task_definition.max_subtask_errors,   # for groups,absolute number, also used when timeout
            max_subtask_error_rate = task_definition.max_subtask_error_rate, # for groups, in percent, also used when timeout
            limit_subtask_parallel_runs = task_definition.limit_subtask_parallel_runs, # how many subtasks cn run in parallel, for groups 0=no limit
            limit_per_instance_parallel_runs = task_definition.limit_per_instance_parallel_runs, #how many times this task can run in parallel per agentInstance it belongs to, 0=no limit
            priority = task_definition.priority,
            # Options - Retry
            max_retries  = task_definition.max_retries,   # how many retries to we make in case of error
            retry_delay  = task_definition.retry_delay,  # time between retries in seconds
            retry_requires_approval = task_definition.retry_requires_approval,  # required user approval before run
            # Runtime values
            is_approved = False if task_definition.requires_approval else None, # user did appove this call            
        )
        print("FOOOBAR55", agent_task_instance)
        if not created:
            print("NOT CREATED")
            return agent_task_instance
        
        # Store references that are used for args/kwargs
        agent_task_instance.taskinstance_arg_references.set(ref_pks)

        if task_definition.task_execution_mode in ("CHAIN", "GROUP"):
            if len(args) == 1 and isinstance(args[0], (list, set, tuple, GeneratorType)):
                args = args[0]
            else:
                args = kwargs.pop("*", [])

            child_versions = task_definition.child_tasks.all()
            for index, child_tdv in enumerate(child_versions):
                child_instance = AgentTaskInstance.get_or_create(
                    task_definition=child_tdv,
                    session_version=session_version,
                    args=list(args) if index == 0 else None,
                )
                agent_task_instance.child_instances.add(child_instance)

        return agent_task_instance

    def delay(self, *partial_args, **partial_kwargs):
        """Shortcut to :meth:`apply_async` using star arguments. """
        print("AgentTaskInstance.delay", self.task_definition_version, partial_args, partial_kwargs)
        return self.apply_async(args=partial_args, kwargs=partial_kwargs)

    def apply_async(self, args=None, kwargs=None, link = None, link_error=None,**options):
        """Apply this task asynchronously.
        Arguments:
            args (Tuple): Partial args to be prepended to the call args.
            kwargs (Dict): Partial kwargs to be merged with call kwargs.
            options (Dict): Partial options to be merged with call options.

        Returns:
            ~@AgentTaskCall: promise of future evaluation.
        """
        print("AgentTaskInstance.apply_async", self.task_definition_version, args, kwargs, options, link, link_error)
        taskcall = self.call(args=args, kwargs=kwargs, **options)
        taskcall.apply_async()
        return taskcall

    def call(self, args:list|None=None, kwargs:dict|None=None, dont_start_before=None, dont_start_after=None, requires_approval=None, time_limit=None, max_subtask_errors=None, max_subtask_error_rate=None, limit_subtask_parallel_runs=None, limit_per_instance_parallel_runs=None, max_retries = None, retry_delay = None, retry_requires_approval = None, priority=None ):
        """Create AgentTaskCall.

        Returns:
            :class:`AgentTaskCall`: 
        """
        return AgentTaskCall.create(
            agent_task_instance = self,
            args = args,
            kwargs = kwargs,
            dont_start_before = dont_start_before,
            dont_start_after = dont_start_after,
            requires_approval = requires_approval,
            time_limit = time_limit,
            max_subtask_errors = max_subtask_errors,
            max_subtask_error_rate = max_subtask_error_rate,
            limit_subtask_parallel_runs = limit_subtask_parallel_runs,
            limit_per_instance_parallel_runs = limit_per_instance_parallel_runs,
            priority = priority,
            max_retries = max_retries,
            retry_delay = retry_delay,
            retry_requires_approval=retry_requires_approval
        )

    @staticmethod
    def _create_instance_arguments_json(arguments:dict):
        def _create_recursive(obj, ref_pks:list[int]):
            if isinstance(obj,  (str, int,float, bool) ) or obj is None:
                return obj
            if isinstance(obj, dict):
                if "_type" in obj and "pk" in obj and len(obj) == 2:
                    if obj["_type"] == "AgentTaskInstance":
                        ref_pks.append(obj["pk"])
                        return obj
                    raise Exception(f"Type {obj["_type"]} not allowed")
                return {k: _create_recursive(v, ref_pks) for k, v in obj.items()}
            if isinstance(obj, list):
                return [_create_recursive(item, ref_pks) for item in obj]
            if isinstance(obj, set):
                return set(_create_recursive(item, ref_pks) for item in obj)
            if isinstance(obj, tuple):
                return tuple(_create_recursive(item, ref_pks) for item in obj)
            if isinstance(obj, AgentTaskInstance):
                return {"_type": "AgentTaskInstance", "pk": obj.pk}
            if isinstance(obj, Path):
                return obj.as_posix()
            raise Exception(f"Type {type(obj)} unknown")
        ref_pks=list()
        return _create_recursive(obj=arguments, ref_pks=ref_pks), ref_pks

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError(f"You may not edit an existing {self._meta.model_name}")
        super().save(*args, **kwargs) 

    def __str__(self):
        return f"AgentTaskInstance#{self.pk}[{self.task_definition_version}]"
