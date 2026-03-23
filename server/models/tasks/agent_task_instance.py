from functools import wraps
from types import GeneratorType
from django.db import models
from runtime.context_manager import ContextTracker
from server.models.tasks.agent_task_call import AgentTaskCall
from server.models.base_model import BaseModel
from django.core.exceptions import ValidationError
from celery.utils.functional import is_list, maybe_list, regen, seq_concat_item, seq_concat_seq

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from server.models.agents.agent_version import AgentVersion
    from runtime.tasks.bound_agent_function import BoundAgentFunction

class AgentTaskInstanceSubtask(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    parent = models.ForeignKey("server.AgentTaskInstance", related_name="child_relations", on_delete=models.CASCADE)
    child  = models.ForeignKey("server.AgentTaskInstance", related_name="parent_relations", on_delete=models.CASCADE)
    index  = models.IntegerField(default=0)


class AgentTaskInstance(BaseModel):
    """Binds a task definition to a specific agent instance"""
    agent_task_definition   = models.ForeignKey("AgentTaskDefinition" , on_delete=models.CASCADE, related_name="related_agent_task_instances")
    agent_instance          = models.ForeignKey("AgentInstance"       , on_delete=models.CASCADE, related_name="related_agent_task_instances")
    agent_instance_version  = models.ForeignKey("AgentInstanceVersion", on_delete=models.CASCADE, related_name="related_agent_task_instances")

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

    taskinstance_arg_references    = models.ManyToManyField("self", help_text="AgentTaskInstances used in instance args/kwargs", symmetrical=False, blank=True, related_name="rev_taskinstance_arg_references")
    taskinstance_result_references = models.ManyToManyField("self", help_text="", symmetrical=False, blank=True, related_name="rev_taskinstance_result_references")
    taskinstance_sub_taskinstances = models.ManyToManyField("self", help_text="", symmetrical=False, blank=True, related_name="rev_taskinstance_sub_taskinstances", through=AgentTaskInstanceSubtask, through_fields=("parent", "child") )

    taskinstances_on_success_callbacks = models.ManyToManyField("self", help_text="", symmetrical=False, blank=True, related_name="rev_taskinstances_on_success_callbacks")
    taskinstances_on_error_callbacks   = models.ManyToManyField("self", help_text="", symmetrical=False, blank=True, related_name="rev_taskinstances_callback_on_erro")
    taskinstances_before_run_hooks     = models.ManyToManyField("self", help_text="", symmetrical=False, blank=True, related_name="rev_taskinstances_hook_before_run")
    taskinstances_after_run_hooks      = models.ManyToManyField("self", help_text="", symmetrical=False, blank=True, related_name="rev_taskinstances_hook_after_run")

    @property
    def task_type(self):
        return self.agent_task_definition.task_type

    @property
    def agent_task_calls(self):
        return self.related_agent_task_calls # pyright: ignore[reportAttributeAccessIssue]

    @classmethod
    def get_or_create(cls, boundAgentTaskDefinition: "BoundAgentFunction", args = None, kwargs=None, **options ) -> "AgentTaskInstance":
        """Create AgentTaskInstance.
        Returns:
            :class:`AgentTaskInstance`:  object for this task, wrapping arguments and options for multiple task invocation.
        """
        from runtime.tasks.bound_agent_function import BoundAgentFunction
        agent_instance = boundAgentTaskDefinition.agent_instance
        agent_task_definition = boundAgentTaskDefinition.agent_task_definition
        agent_instance_version = boundAgentTaskDefinition.agent_instance_version

        args = args if args else []
        kwargs = kwargs if kwargs else {}
        if not isinstance(args,(list, set, tuple)):
            args = [args, ]
        if args:
            kwargs["*"] = args
        arguments_json, ref_pks = AgentTaskInstance.instanceargs_to_json(kwargs)

        agent_task_instance, created = AgentTaskInstance.objects.get_or_create(
            agent_task_definition = agent_task_definition,
            agent_instance = agent_instance,
            agent_instance_version = agent_instance_version,
            # Arguments
            iarguments_json = arguments_json,
            # Options - Startup
            requires_approval = agent_task_definition.requires_approval,
            # Options - Run
            time_limit      = agent_task_definition.time_limit ,  
            max_subtask_errors     = agent_task_definition.max_subtask_errors,   # for groups,absolute number, also used when timeout
            max_subtask_error_rate = agent_task_definition.max_subtask_error_rate, # for groups, in percent, also used when timeout
            limit_subtask_parallel_runs  = agent_task_definition.limit_subtask_parallel_runs, # how many subtasks cn run in parallel, for groups 0=no limit
            limit_per_instance_parallel_runs  = agent_task_definition.limit_per_instance_parallel_runs, #how many times this task can run in parallel per agentInstance it belongs to, 0=no limit
            priority = agent_task_definition.priority,
            # Options - Retry
            max_retries  = agent_task_definition.max_retries,   # how many retries to we make in case of error
            retry_delay  = agent_task_definition.retry_delay,  # time between retries in seconds
            retry_requires_approval =agent_task_definition.retry_requires_approval,  # required user approval before run
            # Runtime values
            is_approved = False if agent_task_definition.requires_approval else None, # user did appove this call            
        )
        
        if not created:
            return agent_task_instance
        
        # Store references that are used for args/kwargs
        agent_task_instance.taskinstance_arg_references.set(ref_pks)

        if agent_task_definition.task_type in ["CHAIN",  "GROUP"]:
            if len(args) == 1 and isinstance(args[0], (list, set, tuple, GeneratorType) ):
                args = args[0]
            else:
                args = kwargs.pop("*",[])

            # RUN THE CHAIN/GROUP Function
            sub_instances = boundAgentTaskDefinition.func(boundAgentTaskDefinition.agent_runtime, *args, **kwargs)
            for index, sub_task_instance in enumerate(sub_instances):
                print("si", sub_task_instance, "end")
                t = AgentTaskInstanceSubtask.objects.get_or_create(
                    parent_id = agent_task_instance.pk,
                    child_id  = sub_task_instance.pk,
                    index = index,
                )
                print("t:", t)

        return agent_task_instance

    def delay(self, *partial_args, **partial_kwargs):
        """Shortcut to :meth:`apply_async` using star arguments. """
        print("AgentTaskInstance.delay", self.agent_task_definition.name, partial_args, partial_kwargs)
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
        print("AgentTaskInstance.apply_async", self.agent_task_definition.name, args, kwargs, options, link, link_error)
        taskcall = self.call(args=args, kwargs=kwargs, **options)
        taskcall.apply_async()
        return taskcall

    def call(self, args:list|None=None, kwargs:dict|None=None, dont_start_before=None, dont_start_after=None, requires_approval=None, time_limit=None, max_subtask_errors=None, max_subtask_error_rate=None, limit_subtask_parallel_runs=None, limit_per_instance_parallel_runs=None, max_retries = None, retry_delay = None, retry_requires_approval = None, priority=None ):
        """Create AgentTaskCall.

        Returns:
            :class:`AgentTaskCall`: 
        """
        return AgentTaskCall.create(
            agent_task_instance=self,
            args=args,
            kwargs=kwargs,
            dont_start_before=dont_start_before,
            dont_start_after=dont_start_after,
            requires_approval=requires_approval,
            time_limit=time_limit,
            max_subtask_errors=max_subtask_errors,
            max_subtask_error_rate=max_subtask_error_rate,
            limit_subtask_parallel_runs=limit_subtask_parallel_runs,
            limit_per_instance_parallel_runs=limit_per_instance_parallel_runs,
            priority = priority,
            max_retries = max_retries,
            retry_delay = retry_delay,
            retry_requires_approval=retry_requires_approval
        )

    @staticmethod
    def instanceargs_to_json(obj, ref_pks=None):
        if ref_pks is None:
            ref_pks = list()
        if isinstance(obj,  (str, int,float, bool) ) or obj is None:
            return obj, ref_pks
        if isinstance(obj, dict):
            if "_type" in obj and "pk" in obj and len(obj) == 2:
                if obj["_type"] == "AgentTaskInstance":
                    ref_pks.append(obj["pk"])
                    return obj, ref_pks
                raise Exception(f"Type {obj["_type"]} not allowed")
            return {k: AgentTaskInstance.instanceargs_to_json(v, ref_pks)[0] for k, v in obj.items()}, ref_pks
        if isinstance(obj, list):
            return [AgentTaskInstance.instanceargs_to_json(item, ref_pks)[0] for item in obj], ref_pks
        if isinstance(obj, set):
            return set([AgentTaskInstance.instanceargs_to_json(item, ref_pks)[0] for item in obj]), ref_pks
        if isinstance(obj, tuple):
            return tuple([AgentTaskInstance.instanceargs_to_json(item, ref_pks)[0] for item in obj]), ref_pks
        if isinstance(obj, AgentTaskInstance):
            return {"_type": "AgentTaskInstance", "pk": obj.pk}, ref_pks
        raise Exception(f"Type {obj} unknown")

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError(f"You may not edit an existing {self._meta.model_name}")
        super().save(*args, **kwargs) 

    def __str__(self):
        return f"AgentTaskInstance#{self.pk}[{self.agent_task_definition.name}]"
