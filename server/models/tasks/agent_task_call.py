"""AgentTaskCall model — represents a single invocation of a task definition."""
from __future__ import annotations

import time
import traceback
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

from django.apps import apps
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q
from django.utils import timezone

from runtime.context_manager import ContextTracker
from server.models.base_model import BaseModel
from server.models.content import GenericContent
from server.models.enums.task_enums import TaskCallStatus, TaskCallStatusDetail
from server.models.message import Message
from server.models.queries.query import Query
from server.models.queries.response import Response
from server.tasks.task_dispatcher import celery_delay

if TYPE_CHECKING:
    from server.models.tasks.task_instance import TaskInstance
    from server.models.tasks.agent_task_run import AgentTaskRun


class AgentTaskCall(BaseModel):
    """Specific invocation of a task — equivalent to a Celery task message.

    Captures the call arguments, scheduling options, retry policy,
    hook references, and lifecycle status.
    """

    task_definition = models.ForeignKey( "server.TaskDefinition", on_delete=models.CASCADE, related_name="related_agent_task_calls", default=None, null=True, blank=True)
    task_definition_version = models.ForeignKey( "TaskDefinitionVersion", on_delete=models.CASCADE, related_name="related_agent_task_calls", default=None, null=True, blank=True)
    task_instance = models.ForeignKey( "TaskInstance", on_delete=models.CASCADE, related_name="related_agent_task_calls", default=None, null=True)
    session = models.ForeignKey( "SessionModel", on_delete=models.CASCADE, related_name="related_agent_task_calls")
    session_version = models.ForeignKey( "SessionVersionModel", on_delete=models.CASCADE, related_name="related_agent_task_calls")

    carguments_json = models.JSONField(default=dict, null=False)

    dont_start_before = models.DateTimeField(default=None, null=True)
    dont_start_after = models.DateTimeField(default=None, null=True)
    requires_approval = models.BooleanField(default=None, null=False)
    guardrail_reason = models.TextField(default=None, blank=True, null= True)

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
    ended_at = models.DateTimeField(editable=False, null=True, default=None)

    cronjob = models.ForeignKey("server.Cronjob", blank=True, on_delete=models.SET_NULL, related_name="related_task_calls", default=None, null=True)
    parent_taskrun = models.ForeignKey( "server.AgentTaskRun", blank=True, on_delete=models.SET_NULL, related_name="child_taskcalls", default=None, null=True)

    taskcall_arg_references = models.ManyToManyField( "self", help_text="AgentTaskCalls used in call args/kwargs", symmetrical=False, blank=True, related_name="rev_taskcall_arg_references")

    taskcall_on_success_callbacks = models.ManyToManyField( "self", help_text="", symmetrical=False, blank=True, related_name="rev_taskcall_on_success_callbacks")
    taskcall_on_error_callbacks = models.ManyToManyField( "self", help_text="", symmetrical=False, blank=True, related_name="rev_taskcall_on_error_callbacks")
    taskcall_before_run_hooks = models.ManyToManyField( "self", help_text="", symmetrical=False, blank=True, related_name="rev_taskcall_before_run_hooks")
    taskcall_after_run_hooks = models.ManyToManyField( "self", help_text="", symmetrical=False, blank=True, related_name="rev_taskcall_after_run_hooks")

    status = models.CharField( choices=TaskCallStatus.choices, default=TaskCallStatus.NEW, max_length=61)
    status_detail = models.CharField( choices=TaskCallStatusDetail.choices, default=TaskCallStatusDetail.NEW, max_length=61)

    taskcall_result_run = models.ForeignKey( "server.AgentTaskRun", null=True, blank=True, default=None, on_delete=models.SET_DEFAULT, related_name="rev_taskcall_result_run")

    @classmethod
    def create(
        cls,
        task_instance: TaskInstance,
        args: Any = None,
        kwargs: Any = None,
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
        priority: int | None = None,
        cronjob: Any = None,
    ) -> AgentTaskCall:
        """Create an AgentTaskCall for the given task instance.

        Merges call-level arguments with instance-level defaults,
        resolves before-run hooks, and serialises argument references.

        Returns:
            The newly created AgentTaskCall.
        """
        parent_run = ContextTracker.current

        args = args if args else []
        arguments = kwargs if kwargs else {}
        if not isinstance(args, (list, set, tuple)):
            args = [args]
        if args:
            arguments["*"] = args

        next_input = arguments

        before_hooks = list(
            task_instance.taskinstances_before_run_hooks.all().order_by("pk")
        )
        before_hook_calls: list[AgentTaskCall] = []
        if before_hooks:
            for i, hook_instance in enumerate(before_hooks):
                next_input = hook_instance.create_call(kwargs=next_input)
                before_hook_calls.append(next_input)

        arguments_json, ref_pks = AgentTaskCall.create_call_arguments_json(
            arguments=next_input
        )

        taskcall = AgentTaskCall.objects.create(
            task_instance=task_instance,
            task_definition=task_instance.task_definition_version.task_definition,
            task_definition_version=task_instance.task_definition_version,
            session=task_instance.session,
            session_version=task_instance.session_version,
            carguments_json=arguments_json,
            dont_start_before=dont_start_before if dont_start_before else None,
            dont_start_after=dont_start_after if dont_start_after else None,
            requires_approval=requires_approval if requires_approval is not None else task_instance.requires_approval,
            time_limit=time_limit if time_limit else task_instance.time_limit,
            max_subtask_errors=max_subtask_errors if max_subtask_errors else task_instance.max_subtask_errors,
            max_subtask_error_rate=max_subtask_error_rate if max_subtask_error_rate else task_instance.max_subtask_error_rate,
            limit_subtask_parallel_runs=limit_subtask_parallel_runs if limit_subtask_parallel_runs else task_instance.limit_subtask_parallel_runs,
            limit_per_instance_parallel_runs=limit_per_instance_parallel_runs if limit_per_instance_parallel_runs else task_instance.limit_per_instance_parallel_runs,
            priority=priority if priority else task_instance.priority,
            max_retries=max_retries if max_retries else task_instance.max_retries,
            retry_delay=retry_delay if retry_delay else task_instance.retry_delay,
            retry_requires_approval=retry_requires_approval if retry_requires_approval else task_instance.retry_requires_approval,
            is_approved=None,
            parent_taskrun=parent_run,
            cronjob=cronjob,
        )
        taskcall.taskcall_before_run_hooks.set(before_hook_calls)

        if ref_pks:
            taskcall.taskcall_arg_references.set(ref_pks)

        return taskcall

    def apply_async(self) -> AgentTaskCall:
        """Dispatch this call to the Celery-backed scheduler for execution."""
        if not self.pk:
            raise Exception("Must save first")
        for before_hook_call in self.taskcall_before_run_hooks.all():
            before_hook_call.apply_async()
        from runtime.tasks.call_scheduler import CallScheduler

        celery_delay(CallScheduler._apply_async, self.pk)
        return self

    @staticmethod
    def create_call_arguments_json(arguments: Any) -> tuple[dict[str, Any], list[int]]:
        """Serialise call arguments into JSON-safe dicts, extracting model references.

        Returns:
            A tuple ``(json_dict, ref_pks)`` where ``ref_pks`` are the primary
            keys of referenced ``AgentTaskCall`` instances.
        """
        from server.models.tasks.agent_task_run import AgentTaskRun

        allowed_objects: dict[str, type] = {
            "AgentTaskCall": AgentTaskCall,
            "AgentTaskRun": AgentTaskRun,
            "Message": Message,
            "GenericContent": GenericContent,
            "Query": Query,
            "Response": Response,
        }

        def _create_recursive(obj: Any, ref_pks: list[int]) -> Any:
            if isinstance(obj, (str, int, float, bool)) or obj is None:
                return obj
            if isinstance(obj, (list, set, tuple)):
                return [_create_recursive(item, ref_pks) for item in obj]
            if isinstance(obj, dict):
                if "_type" in obj and "pk" in obj and len(obj) == 2:
                    if obj["_type"] in allowed_objects:
                        ref_pks.append(obj["pk"])
                        return obj
                    raise Exception(
                        f"This should not be here in AgentTaskCall.arguments_to_json {obj}"
                    )
                return {
                    k: _create_recursive(v, ref_pks) for k, v in obj.items()
                }
            if isinstance(obj, AgentTaskCall):
                ref_pks.append(obj.pk)
                return {"_type": "AgentTaskCall", "pk": obj.pk}
            try:
                if obj.__class__.__qualname__ in allowed_objects:
                    return {"_type": obj.__class__.__qualname__, "pk": obj.pk}
            except Exception:
                pass
            if isinstance(obj, Path):
                return obj.as_posix()
            raise Exception(f"Type {type(obj)} unknown")

        ref_pks: list[int] = []
        return _create_recursive(obj=arguments, ref_pks=ref_pks), ref_pks

    def _resolve_call_arguments(
        self,
        timeout: int = 0,
        recursive: bool = True,
        allow_partial_results: bool = False,
    ) -> Any:
        """Resolve the stored call arguments, recursively fetching referenced objects."""
        from server.models.tasks.agent_task_run import AgentTaskRun

        def _get_recursive(
            data: Any,
            timeout: int,
            recursive: bool,
            allow_partial_results: bool,
        ) -> Any:
            if isinstance(data, dict):
                if "_type" in data and "pk" in data:
                    try:
                        model_instance = apps.get_model("server", data["_type"]).objects.get(
                            pk=data["pk"]
                        )
                    except:
                        return None
                    if recursive and (
                        isinstance(model_instance, AgentTaskRun)
                        or isinstance(model_instance, AgentTaskCall)
                    ):
                        return model_instance.get_result(
                            recursive=recursive,
                            timeout=timeout,
                            allow_partial_results=allow_partial_results,
                        )
                    return model_instance
                return {
                    k: _get_recursive(
                        v, timeout=timeout, recursive=recursive, allow_partial_results=allow_partial_results
                    )
                    for k, v in data.items()
                }
            elif isinstance(data, list):
                return [
                    _get_recursive(
                        item,
                        timeout=timeout,
                        recursive=recursive,
                        allow_partial_results=allow_partial_results,
                    )
                    for item in data
                ]
            elif isinstance(data, (AgentTaskCall, AgentTaskRun)):
                if recursive:
                    return data.get_result(
                        timeout=timeout,
                        recursive=recursive,
                        allow_partial_results=allow_partial_results,
                    )
            return data

        return _get_recursive(
            data=self.carguments_json,
            timeout=timeout,
            recursive=recursive,
            allow_partial_results=allow_partial_results,
        )

    def get_result(
        self,
        timeout: int = 0,
        recursive: bool = True,
        allow_partial_results: bool = False,
    ) -> Any:
        """Block until the call's result is available, then return it.

        Args:
            timeout: Seconds to wait (0 = no wait, None = forever).
            recursive: If True, recursively resolve AgentTaskCall items in results.
            allow_partial_results: Return partial results if not fully resolved.

        Raises:
            TimeoutError: If the result is not ready within the timeout.
        """
        s = time.time()
        subtimeout = timeout
        while True:
            if self.status in [TaskCallStatus.ENDED]:
                if self.taskcall_result_run:
                    return self.taskcall_result_run.get_result(
                        timeout=subtimeout,
                        recursive=recursive,
                        allow_partial_results=allow_partial_results,
                    )
                return None
            if timeout is not None:
                if time.time() - s >= timeout:
                    if allow_partial_results:
                        return None
                    raise TimeoutError("TaskRunResult not ready")
                if subtimeout > 0:
                    subtimeout -= 1
            time.sleep(1)

    def save(self, *args: Any, **kwargs: Any) -> None:
        """Prevent updates to existing AgentTaskCall instances."""
        if self.pk:
            raise ValidationError(f"You may not edit an existing {self._meta.model_name}")
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        try:
            name = self.task_definition.name if self.task_definition else None
            return f"<AgentTaskCall[{self.pk}]# {name}>"
        except Exception:
            return f"AgentTaskRun[{self.pk}]#{self.pk}: {self.status}"
