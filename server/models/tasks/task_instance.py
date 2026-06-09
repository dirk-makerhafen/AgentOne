"""TaskInstance model — binds a task definition version to a specific session."""
from __future__ import annotations

from pathlib import Path
from types import GeneratorType
from typing import TYPE_CHECKING, Any, Optional

from django.core.exceptions import ValidationError
from django.db import models
from sortedm2m.fields import SortedManyToManyField

from runtime.context_manager import ContextTracker
from server.models.base_model import BaseModel
from server.models.tasks.agent_task_call import AgentTaskCall
from server.models.tasks.task_definition_version import TaskDefinitionVersion

if TYPE_CHECKING:
    pass


class TaskInstance(BaseModel):
    """Binds a task definition version to a specific agent session instance.

    Carries instance-wide arguments, execution options, retry policy,
    and references to child instances (for CHAIN/GROUP) and hooks.
    """

    task_definition_version = models.ForeignKey(
        "TaskDefinitionVersion",
        default=None,
        null=True,
        on_delete=models.CASCADE,
        related_name="related_task_instances",
    )
    session = models.ForeignKey(
        "SessionModel",
        on_delete=models.CASCADE,
        related_name="related_task_instances",
    )
    session_version = models.ForeignKey(
        "SessionVersionModel",
        on_delete=models.CASCADE,
        related_name="related_task_instances",
    )

    iarguments_json = models.JSONField(default=dict, null=True)

    requires_approval = models.BooleanField(default=None, null=False)

    time_limit = models.IntegerField(default=None, null=True)
    max_subtask_errors = models.IntegerField(default=None, null=False)
    max_subtask_error_rate = models.IntegerField(default=None, null=False)
    limit_subtask_parallel_runs = models.IntegerField(default=None, null=False)
    limit_per_instance_parallel_runs = models.IntegerField(default=None, null=False)
    priority = models.IntegerField(default=0)

    max_retries = models.IntegerField(default=None, null=False)
    retry_delay = models.IntegerField(default=None, null=False)
    retry_requires_approval = models.BooleanField(default=None, null=False)

    is_approved = models.BooleanField(default=None, null=True)
    retry_count = models.IntegerField(default=0)

    child_instances = SortedManyToManyField(
        "self", symmetrical=False, blank=True, related_name="parent_instances"
    )

    taskinstance_arg_references = models.ManyToManyField(
        "self",
        help_text="AgentTaskInstances used in instance args/kwargs",
        symmetrical=False,
        blank=True,
        related_name="rev_taskinstance_arg_references",
    )
    taskinstance_result_references = models.ManyToManyField(
        "self",
        help_text="",
        symmetrical=False,
        blank=True,
        related_name="rev_taskinstance_result_references",
    )

    taskinstances_on_success_callbacks = models.ManyToManyField(
        "self",
        help_text="",
        symmetrical=False,
        blank=True,
        related_name="rev_taskinstances_on_success_callbacks",
    )
    taskinstances_on_error_callbacks = models.ManyToManyField(
        "self",
        help_text="",
        symmetrical=False,
        blank=True,
        related_name="rev_taskinstances_callback_on_erro",
    )
    taskinstances_before_run_hooks = models.ManyToManyField(
        "self",
        help_text="",
        symmetrical=False,
        blank=True,
        related_name="rev_taskinstances_hook_before_run",
    )
    taskinstances_after_run_hooks = models.ManyToManyField(
        "self",
        help_text="",
        symmetrical=False,
        blank=True,
        related_name="rev_taskinstances_hook_after_run",
    )

    @property
    def task_type(self) -> str:
        """Return the task type from the linked definition version."""
        if not self.task_definition_version:
            raise Exception("task_type not set")
        return self.task_definition_version.task_type

    @property
    def agent_task_calls(self):
        """Return related AgentTaskCall queryset."""
        return self.related_agent_task_calls  # pyright: ignore[reportAttributeAccessIssue]

    @property
    def task_execution_mode(self) -> str:
        """Return the execution mode from the linked definition version."""
        if not self.task_definition_version:
            raise Exception("task_execution_mode not set")
        return self.task_definition_version.task_execution_mode

    @classmethod
    def get_or_create(
        cls,
        task_definition: TaskDefinitionVersion,
        session_version: Any,
        args: Any = None,
        kwargs: Any = None,
        **options: Any,
    ) -> TaskInstance:
        """Get or create a TaskInstance for the given task definition version.

        Merges call-level arguments, serialises references, and auto-creates
        child instances for CHAIN/GROUP execution modes.

        Returns:
            The existing or newly created TaskInstance.
        """
        session = session_version.session

        args = args if args else []
        arguments = kwargs if kwargs else {}
        if not isinstance(args, (list, set, tuple)):
            args = [args]
        if args:
            arguments["*"] = args

        arguments_json, ref_pks = TaskInstance._create_instance_arguments_json(arguments=arguments)

        task_instance, created = TaskInstance.objects.get_or_create(
            task_definition_version=task_definition,
            session=session,
            session_version=session_version,
            iarguments_json=arguments_json,
            requires_approval=task_definition.requires_approval,
            time_limit=task_definition.time_limit,
            max_subtask_errors=task_definition.max_subtask_errors,
            max_subtask_error_rate=task_definition.max_subtask_error_rate,
            limit_subtask_parallel_runs=task_definition.limit_subtask_parallel_runs,
            limit_per_instance_parallel_runs=task_definition.limit_per_instance_parallel_runs,
            priority=task_definition.priority,
            max_retries=task_definition.max_retries,
            retry_delay=task_definition.retry_delay,
            retry_requires_approval=task_definition.retry_requires_approval,
            is_approved=False if task_definition.requires_approval else None,
        )
        if not created:
            return task_instance

        task_instance.taskinstance_arg_references.set(ref_pks)

        if task_definition.task_execution_mode in ("CHAIN", "GROUP", "MAP"):
            if len(args) == 1 and isinstance(args[0], (list, set, tuple, GeneratorType)):
                args = args[0]
            else:
                args = kwargs.pop("*", [])

            child_versions = task_definition.child_tasks.all()
            for index, child_tdv in enumerate(child_versions):
                child_instance = TaskInstance.get_or_create(
                    task_definition=child_tdv,
                    session_version=session_version,
                    args=list(args) if index == 0 else None,
                )
                task_instance.child_instances.add(child_instance)

        return task_instance

    def delay(self, *partial_args: Any, **partial_kwargs: Any) -> AgentTaskCall:
        """Shortcut to :meth:`apply_async` using star arguments."""
        return self.apply_async(args=partial_args, kwargs=partial_kwargs)

    def apply_async(
        self,
        args: Any = None,
        kwargs: Any = None,
        link: Any = None,
        link_error: Any = None,
        **options: Any,
    ) -> AgentTaskCall:
        """Apply this task asynchronously.

        Args:
            args: Partial args to be prepended to the call args.
            kwargs: Partial kwargs to be merged with call kwargs.
            options: Partial options to be merged with call options.

        Returns:
            The created AgentTaskCall (promise of future evaluation).
        """
        taskcall = self.create_call(args=args, kwargs=kwargs, **options)
        taskcall.apply_async()
        return taskcall

    def create_call(
        self,
        args: list[Any] | None = None,
        kwargs: dict[str, Any] | None = None,
        dont_start_before: Any = None,
        dont_start_after: Any = None,
        requires_approval: Any = None,
        time_limit: Any = None,
        max_subtask_errors: Any = None,
        max_subtask_error_rate: Any = None,
        limit_subtask_parallel_runs: Any = None,
        limit_per_instance_parallel_runs: Any = None,
        max_retries: Any = None,
        retry_delay: Any = None,
        retry_requires_approval: Any = None,
        priority: Any = None,
        cronjob: Any = None,
    ) -> AgentTaskCall:
        """Create an AgentTaskCall for this task instance.

        Returns:
            The newly created AgentTaskCall.
        """
        return AgentTaskCall.create(
            task_instance=self,
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
            priority=priority,
            max_retries=max_retries,
            retry_delay=retry_delay,
            retry_requires_approval=retry_requires_approval,
            cronjob=cronjob,
        )

    @staticmethod
    def _create_instance_arguments_json(arguments: dict[str, Any]) -> tuple[Any, list[int]]:
        """Serialise instance arguments into JSON-safe form, extracting references."""

        def _create_recursive(obj: Any, ref_pks: list[int]) -> Any:
            if isinstance(obj, (str, int, float, bool)) or obj is None:
                return obj
            if isinstance(obj, dict):
                if "_type" in obj and "pk" in obj and len(obj) == 2:
                    if obj["_type"] == "AgentTaskInstance":
                        ref_pks.append(obj["pk"])
                        return obj
                    raise Exception(f"Type {obj['_type']} not allowed")
                return {k: _create_recursive(v, ref_pks) for k, v in obj.items()}
            if isinstance(obj, list):
                return [_create_recursive(item, ref_pks) for item in obj]
            if isinstance(obj, set):
                return {_create_recursive(item, ref_pks) for item in obj}
            if isinstance(obj, tuple):
                return tuple(_create_recursive(item, ref_pks) for item in obj)
            if isinstance(obj, TaskInstance):
                return {"_type": "AgentTaskInstance", "pk": obj.pk}
            if isinstance(obj, Path):
                return obj.as_posix()
            raise Exception(f"Type {type(obj)} unknown")

        ref_pks: list[int] = []
        return _create_recursive(obj=arguments, ref_pks=ref_pks), ref_pks

    def save(self, *args: Any, **kwargs: Any) -> None:
        """Prevent updates to existing TaskInstance instances."""
        if self.pk:
            raise ValidationError(f"You may not edit an existing {self._meta.model_name}")
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"AgentTaskInstance#{self.pk}[{self.task_definition_version}]"
