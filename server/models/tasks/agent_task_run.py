"""AgentTaskRun model — a single execution attempt of a task call."""
from __future__ import annotations

import copy
import json
import time
import traceback
from pathlib import Path
from types import GeneratorType
from typing import TYPE_CHECKING, Any, Optional

from django.apps import apps
from django.core.exceptions import ValidationError
from django.db import models

from runtime.context_manager import ContextTracker
from runtime.rate_limiter import RateLimitError
from server.models.base_model import BaseModel
from server.models.content import GenericContent
from server.models.enums.task_enums import TaskRunStatus, TaskType
from server.models.message import Message
from server.models.queries.query import Query
from server.models.queries.response import Response
from server.models.tasks.agent_task_call import AgentTaskCall
from server.tasks.task_dispatcher import celery_delay

if TYPE_CHECKING:
    from runtime.session.session import Session



class AgentTaskRun(BaseModel):
    """Single execution attempt of an AgentTaskCall.

    Captures resolved arguments, the runtime result, status transitions,
    and references to other runs/calls used in arguments or results.
    """

    agent_task_call = models.ForeignKey("AgentTaskCall",on_delete=models.CASCADE,related_name="related_agent_task_runs",)
    task_instance = models.ForeignKey("TaskInstance",on_delete=models.CASCADE,related_name="related_agent_task_runs",default=None,null=True,)

    task_definition_version = models.ForeignKey("TaskDefinitionVersion",on_delete=models.CASCADE,related_name="related_agent_task_runs",default=None,null=True,blank=True,)
    session_version = models.ForeignKey("SessionVersionModel",on_delete=models.CASCADE,related_name="related_agent_task_runs",)

    arguments_json = models.JSONField(default=dict, null=False)

    dont_start_before = models.DateTimeField(default=None, null=True, blank=True)
    dont_start_after = models.DateTimeField(default=None, null=True, blank=True)
    requires_approval = models.BooleanField(default=None, null=False)
    priority = models.IntegerField(default=0)

    time_limit = models.IntegerField(default=None, null=True, blank=True)
    max_subtask_errors = models.IntegerField(default=None, null=False)
    max_subtask_error_rate = models.IntegerField(default=None, null=False)
    limit_subtask_parallel_runs = models.IntegerField(default=None, null=False)
    limit_per_instance_parallel_runs = models.IntegerField(default=None, null=False)

    is_approved = models.BooleanField(default=False)
    ended_at = models.DateTimeField(editable=False, null=True, default=None)

    taskrun_arg_references = models.ManyToManyField("server.AgentTaskRun",help_text="AgentTaskRuns used in args/kwargs",symmetrical=False,blank=True,related_name="rev_taskrun_arg_references",)
    taskrun_result_references = models.ManyToManyField("server.AgentTaskCall",help_text="AgentTaskCalls returned in results",symmetrical=False,blank=True,related_name="rev_taskrun_result_references",)

    status = models.CharField(choices=TaskRunStatus.choices, default=TaskRunStatus.NEW, max_length=61)
    result_json = models.JSONField(default=None, null=True)

    @classmethod
    def create(
        cls,
        agent_task_call: AgentTaskCall,
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
    ) -> AgentTaskRun:
        """Create an AgentTaskRun from the given call, resolving the task version.

        Dynamically resolves the task definition version from the session's
        current agent version scope, so retries pick up updated versions.
        """
        session: Session = agent_task_call.session.latest_session_version.get_runtime()

        task_type = agent_task_call.task_definition_version.task_type
        task_name = agent_task_call.task_definition.name

        if task_type == TaskType.TASK:
            task_definition_version = session.get_task(task_name).task_definition_version
        elif task_type == TaskType.TOOL:
            task_definition_version = session.get_tool(task_name).task_definition_version
        elif task_type == TaskType.COMMAND:
            task_definition_version = session.get_command(task_name).task_definition_version
        else:
            task_definition_version = agent_task_call.task_definition_version

        args = args if args else []
        kwargs = kwargs if kwargs else {}

        arguments_json, ref_pks = AgentTaskRun._create_run_arguments_json(
            args=args, kwargs=kwargs
        )

        taskrun = AgentTaskRun.objects.create(
            agent_task_call=agent_task_call,
            task_instance=agent_task_call.task_instance,
            task_definition_version=task_definition_version,
            session_version=agent_task_call.session_version,
            arguments_json=arguments_json,
            dont_start_before=dont_start_before if dont_start_before else None,
            dont_start_after=dont_start_after if dont_start_after else None,
            requires_approval=requires_approval
            if requires_approval is not None
            else task_definition_version.requires_approval,
            time_limit=time_limit if time_limit else task_definition_version.time_limit,
            max_subtask_errors=max_subtask_errors
            if max_subtask_errors
            else task_definition_version.max_subtask_errors,
            max_subtask_error_rate=max_subtask_error_rate
            if max_subtask_error_rate
            else task_definition_version.max_subtask_error_rate,
            limit_subtask_parallel_runs=limit_subtask_parallel_runs
            if limit_subtask_parallel_runs
            else task_definition_version.limit_subtask_parallel_runs,
            limit_per_instance_parallel_runs=limit_per_instance_parallel_runs
            if limit_per_instance_parallel_runs
            else task_definition_version.limit_per_instance_parallel_runs,
        )
        if ref_pks:
            taskrun.taskrun_arg_references.set(ref_pks)

        return taskrun

    def apply_async(self) -> None:
        """Dispatch this run asynchronously via Celery."""
        query = AgentTaskRun.objects.filter(pk=self.pk, status=TaskRunStatus.NEW)
        if 0 == query.update(status=TaskRunStatus.QUEUED):
            return
        from runtime.tasks.run_scheduler import RunScheduler

        celery_delay(RunScheduler._apply_async, self.pk)

    def apply(self) -> tuple[Any, Any] | None:
        """Execute this run synchronously.

        Handles CHAIN, GROUP, and normal (FUNCTION/SCRIPT) execution modes.
        Updates status to SUCCESS, FAILURE, or RATE_LIMITED and saves atomically.
        """
        if not self.task_definition_version:
            return None
        task_definition = self.task_definition_version.task_definition
        new_sub_task_calls: list[Any] = []
        result = None
        with ContextTracker(self):
            try:
                session = self.session_version.get_runtime()
                session._current_taskrun = self

                if self.task_definition_version.task_execution_mode == "CHAIN":
                    next_step_arguments = self.arguments_json
                    for sub_task_instance in self.task_instance.child_instances.all():
                        next_step_arguments = sub_task_instance.apply_async(
                            kwargs=next_step_arguments
                        )
                        new_sub_task_calls.append(next_step_arguments)
                    result = new_sub_task_calls[-1]

                elif self.task_definition_version.task_execution_mode == "GROUP":
                    for sub_task_instance in self.task_instance.child_instances.all():
                        call = sub_task_instance.apply_async(kwargs=self.arguments_json)
                        new_sub_task_calls.append(call)
                    result = new_sub_task_calls

                elif self.task_definition_version.task_execution_mode == "MAP":
                    producer = self.task_instance.child_instances.first()
                    consumer = self.task_instance.child_instances.last()
                    items = producer.apply_async(kwargs=self.arguments_json)
                    result = session.get_task("map").delay(items=items, target_pk=consumer.pk)
                else:
                    bound_task = None
                    if self.task_definition_version.task_type == TaskType.TASK:
                        bound_task = session.get_task(task_definition.name)
                    elif self.task_definition_version.task_type == TaskType.TOOL:
                        bound_task = session.get_tool(task_definition.name)
                    elif self.task_definition_version.task_type == TaskType.COMMAND:
                        bound_task = session.get_command(task_definition.name)
                    if not bound_task:
                        raise Exception(
                            f"Unsupported task type '{self.task_definition_version.task_type}'"
                        )

                    args, kwargs = self._resolve_run_arguments(timeout=0)
                    result = bound_task.call(*args, **kwargs)

                self.result_json, ref_pks = self._create_result_json(result=result)
                self.taskrun_result_references.set(ref_pks)

                from runtime.tasks.run_fsm import TaskRunStateMachine
                if ref_pks:
                    self.status = TaskRunStatus.WAITING_RESULTTASKS
                    TaskRunStateMachine.wait_for_results(
                        self.pk, extra={"result_json": self.result_json}
                    )
                else:
                    self.status = TaskRunStatus.SUCCESS
                    TaskRunStateMachine.succeed(
                        self.pk, extra={"result_json": self.result_json}
                    )

            except RateLimitError:
                self.status = TaskRunStatus.RATE_LIMITED
                AgentTaskRun.objects.filter(pk=self.pk, status=TaskRunStatus.ACTIVE).update(
                    status=self.status
                )

            except Exception as e:
                self.status = TaskRunStatus.FAILURE
                exception_json = json.dumps(
                    {"exception": f"{e}", "traceback": traceback.format_exc()}
                )
                from runtime.tasks.run_fsm import TaskRunStateMachine
                TaskRunStateMachine.fail(
                    self.pk, extra={"result_json": exception_json}
                )

    @staticmethod
    def _create_run_arguments_json(
        args: Any, kwargs: Any
    ) -> tuple[dict[str, Any], list[int]]:
        """Serialise run arguments, resolving AgentTaskCall references to their result runs."""

        def _create_recursive(obj: Any, ref_pks: list[int]) -> Any:
            if isinstance(obj, (str, int, float, bool)) or obj is None:
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
                    if obj["_type"] in ("Message", "Query", "Response"):
                        return obj
                    if obj["_type"] == "AgentTaskCall":
                        a = AgentTaskCall.objects.get(pk=obj["pk"])
                        if not a.taskcall_result_run:
                            raise ValueError(
                                f"Dispatcher Error: AgentTaskRun attempted to be created with "
                                f"AgentTaskCall {a.pk} as an argument, but its result_run is "
                                f"not set (status: {a.status_detail})."
                            )
                        ref_pks.append(a.taskcall_result_run.pk)
                        return {
                            "_type": "AgentTaskRun",
                            "pk": a.taskcall_result_run.pk,
                        }
                    raise Exception(
                        f"Type {obj['_type']} not allowed in AgentTaskRun.resolve_calls_to_runs"
                    )
                return {
                    k: _create_recursive(v, ref_pks) for k, v in obj.items()
                }
            if isinstance(obj, Path):
                return obj.as_posix()
            raise Exception(f"Type {type(obj)} unknown")

        arguments = copy.copy(kwargs)
        if isinstance(args, GeneratorType):
            args = list(args)
        if not isinstance(args, (list, set, tuple)):
            args = [args]
        if args:
            arguments["*"] = args

        ref_pks: list[int] = []
        return _create_recursive(obj=arguments, ref_pks=ref_pks), ref_pks

    def _resolve_run_arguments(
        self,
        timeout: int = 0,
        recursive: bool = True,
        allow_partial_results: bool = False,
    ) -> tuple[list[Any], dict[str, Any]]:
        """Resolve stored run arguments, splitting into positional args and kwargs."""

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

        arguments = _get_recursive(
            data=self.arguments_json,
            timeout=timeout,
            recursive=recursive,
            allow_partial_results=allow_partial_results,
        )

        kwargs: dict[str, Any] = {}
        if isinstance(arguments, dict):
            args = arguments.pop("*", [])
            kwargs = arguments
        elif not isinstance(arguments, (list, set, tuple)):
            args = [arguments]
        else:
            args = list(arguments)

        return args, kwargs

    @staticmethod
    def _create_result_json(result: Any) -> tuple[Any, list[int]]:
        """Serialise a result into JSON-safe form, extracting model references."""

        def _create_recursive(obj: Any, ref_pks: list[int]) -> Any:
            if isinstance(obj, (str, int, float, bool)) or obj is None:
                return obj
            if isinstance(obj, dict):
                return {k: _create_recursive(v, ref_pks) for k, v in obj.items()}
            if isinstance(obj, (list, set, tuple)):
                return obj.__class__(_create_recursive(item, ref_pks) for item in obj)
            if isinstance(obj, (AgentTaskCall, Message, Query, Response)):
                if isinstance(obj, AgentTaskCall):
                    ref_pks.append(obj.pk)
                return {"_type": obj.__class__.__qualname__, "pk": obj.pk}
            if isinstance(obj, Path):
                return obj.as_posix()
            raise Exception(f"Type {type(obj)} unknown")

        ref_pks: list[int] = []
        return _create_recursive(obj=result, ref_pks=ref_pks), ref_pks

    def get_result(
        self,
        timeout: int = 0,
        recursive: bool = False,
        allow_partial_results: bool = False,
    ) -> Any:
        """Block until the run's result is available, then return it.

        Args:
            timeout: Seconds to wait (0 = no wait, None = forever).
            recursive: If True, recursively resolve AgentTaskCall items in results.
            allow_partial_results: Return partial results if not fully resolved.

        Raises:
            TimeoutError: If the result is not ready within the timeout.
        """

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
            return data

        s = time.time()
        subtimeout = timeout
        while True:
            if self.status in [TaskRunStatus.SUCCESS, TaskRunStatus.FAILURE]:
                if self.result_json:
                    return _get_recursive(
                        data=self.result_json,
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

    def save(self, *args: Any, allow: bool = False, **kwargs: Any) -> None:
        """Save the run. By default, prevents updates to existing instances.

        Pass ``allow=True`` to override the immutability check.
        """
        if not allow and self.pk:
            raise ValidationError(f"You may not edit an existing {self._meta.model_name}")
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        try:
            tdv = self.task_definition_version
            name = tdv.task_definition.name if tdv and tdv.task_definition else None
            return f"AgentTaskRun[{name}]#{self.pk}: {self.status}"
        except Exception:
            return f"AgentTaskRun[{self}]#{self.pk}: {self.status}"
