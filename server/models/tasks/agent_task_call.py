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
from server.models.base_model import BaseModel, Observables
from server.models.content import GenericContent, pack_large_string
from server.models.enums.task_enums import TaskCallStatus, TaskCallStatusDetail
from server.models.message import Message
from server.models.queries.query import Query
from server.models.queries.response import Response
from server.tasks.task_dispatcher import celery_delay

if TYPE_CHECKING:
    from server.models.tasks.task_instance import TaskInstance
    from server.models.tasks.agent_task_run import AgentTaskRun


def pending_rate_limit_call_ids(
    provider_id: int | None = None, model_id: int | None = None
) -> list[int]:
    """PKs of WAITING_RATELIMIT calls whose resolved model matches.

    ``provider_id`` and ``model_id`` are ANDed; pass ``None`` to skip a filter.
    Resolution goes through the session version's pinned settings (recursion-safe),
    since ``AgentTaskCall`` has no direct aimodel/provider join.
    """
    from server.models.enums.task_enums import TaskCallStatusDetail

    matching = []
    for call in AgentTaskCall.objects.filter(
        status_detail=TaskCallStatusDetail.WAITING_RATELIMIT,
    ).iterator():
        aimodel = call.session_version.unresolved_aimodel()
        if aimodel is None:
            continue
        if provider_id is not None and aimodel.api_provider_id != provider_id:
            continue
        if model_id is not None and aimodel.pk != model_id:
            continue
        matching.append(call.pk)
    return matching


class AgentTaskCall(BaseModel):
    """Specific invocation of a task — equivalent to a Celery task message.

    Captures the call arguments, scheduling options, retry policy,
    hook references, and lifecycle status.
    """

    class AgentTaskCallObservables(Observables):
        """Explicit observable keys for an AgentTaskCall (IDE autocomplete)."""
        @property
        def runs(self):
            return f"AgentTaskRun.agent_task_call:{self.model.pk}"
        @property
        def collection_items(self):
            return f"CollectionItem.source_call:{self.model.pk}"
        @property
        def message_parts(self):
            return f"MessagePart.tool_call:{self.model.pk}"
        


    task_definition = models.ForeignKey( "server.TaskDefinition", on_delete=models.CASCADE, related_name="related_agent_task_calls", default=None, null=True, blank=True)
    task_definition_version = models.ForeignKey( "TaskDefinitionVersion", on_delete=models.CASCADE, related_name="related_agent_task_calls", default=None, null=True, blank=True)
    task_instance = models.ForeignKey( "TaskInstance", on_delete=models.CASCADE, related_name="related_agent_task_calls", default=None, null=True)
    session = models.ForeignKey( "SessionModel", on_delete=models.CASCADE, related_name="related_agent_task_calls")
    session_version = models.ForeignKey( "SessionVersionModel", on_delete=models.CASCADE, related_name="related_agent_task_calls")

    carguments_json = models.JSONField(default=dict, null=False)

    dont_start_before = models.DateTimeField(default=None, null=True, blank=True)
    dont_start_after = models.DateTimeField(default=None, null=True, blank=True)
    requires_approval = models.BooleanField(default=None, null=False)
    guardrail_reason = models.TextField(default=None, blank=True, null= True)

    auto_review_status = models.CharField(max_length=20, default=None, null=True, blank=True)
    auto_review_reason = models.TextField(default=None, blank=True, null=True)

    time_limit = models.IntegerField(default=None, null=True, blank=True)
    max_subtask_errors = models.IntegerField(default=None, null=False)
    max_subtask_error_rate = models.IntegerField(default=None, null=False)
    limit_subtask_parallel_runs = models.IntegerField(default=None, null=False)
    limit_per_instance_parallel_runs = models.IntegerField(default=None, null=False)
    priority = models.IntegerField(default=99)  # 0 = most urgent, 99 = lowest

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

    status = models.CharField( choices=TaskCallStatus.choices, default=TaskCallStatus.NEW, max_length=61,db_index=True)
    status_detail = models.CharField( choices=TaskCallStatusDetail.choices, default=TaskCallStatusDetail.NEW, max_length=61,db_index=True)

    taskcall_result_run = models.ForeignKey( "server.AgentTaskRun", null=True, blank=True, default=None, on_delete=models.SET_DEFAULT, related_name="rev_taskcall_result_run")

    session_root_task = models.ForeignKey(
        "self", on_delete=models.CASCADE,
        related_name="session_child_task_calls",
        default=None, null=True, blank=True
    )

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

        # Dynamic intercept hooks (``hooks: - before:`` entries on the
        # session agent). Inline entries join the input-transform chain
        # above (blocking: the call waits on them via arg references);
        # detached entries get a snapshot of the *original* arguments and
        # are dispatched fire-and-forget in ``apply_async``.
        detached_before_calls: list[AgentTaskCall] = []
        try:
            from runtime import hooks as _hookmod

            entries = _hookmod.get_session_agent_hooks(task_instance.session_version)
            ctx = _hookmod.call_match_context(task_instance)
            for intercept in _hookmod.matching_intercepts(entries, "before", ctx):
                hook_ti = _hookmod.build_hook_task_instance(task_instance.session_version, intercept["before"])
                if hook_ti is None:
                    continue
                if intercept.get("mode") == "detached":
                    snapshot = dict(arguments) if isinstance(arguments, dict) else arguments
                    detached_before_calls.append(hook_ti.create_call(kwargs=snapshot))
                else:
                    next_input = hook_ti.create_call(kwargs=next_input)
                    before_hook_calls.append(next_input)
        except Exception as e:  # pylint: disable=broad-exception-caught
            print(f"[hooks] error resolving intercept before hooks: {e}")

        arguments_json, ref_pks = AgentTaskCall.create_call_arguments_json(
            arguments=next_input
        )

        # Determine session_root_task
        root = None
        if parent_run and parent_run.session_version.session_id == task_instance.session_id and parent_run.agent_task_call:
            root = parent_run.agent_task_call.session_root_task or parent_run.agent_task_call

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
            limit_subtask_parallel_runs=limit_subtask_parallel_runs
            if limit_subtask_parallel_runs is not None
            else task_instance.limit_subtask_parallel_runs,
            limit_per_instance_parallel_runs=limit_per_instance_parallel_runs
            if limit_per_instance_parallel_runs is not None
            else task_instance.limit_per_instance_parallel_runs,
            priority=priority if priority else task_instance.priority,
            max_retries=max_retries if max_retries else task_instance.max_retries,
            retry_delay=retry_delay if retry_delay else task_instance.retry_delay,
            retry_requires_approval=retry_requires_approval if retry_requires_approval else task_instance.retry_requires_approval,
            is_approved=None,
            parent_taskrun=parent_run,
            cronjob=cronjob,
            session_root_task=root,
        )
        taskcall.taskcall_before_run_hooks.set(before_hook_calls)
        # Transient (non-DB) carry-over for detached intercept calls —
        # dispatched fire-and-forget in ``apply_async`` below.
        taskcall._detached_intercept_calls = detached_before_calls

        if not root:
            AgentTaskCall.objects.filter(pk=taskcall.pk).update(session_root_task=taskcall)
            taskcall.session_root_task = taskcall

        if ref_pks:
            taskcall.taskcall_arg_references.set(ref_pks)

        return taskcall


    def apply_async(self) -> AgentTaskCall:
        """Dispatch this call to the scheduler for execution."""
        if not self.pk:
            raise Exception("Must save first")
        for before_hook_call in self.taskcall_before_run_hooks.all():
            before_hook_call.apply_async()
        for detached_call in getattr(self, "_detached_intercept_calls", []) or []:
            try:
                detached_call.apply_async()
            except Exception as e:  # pylint: disable=broad-exception-caught
                print(f"[hooks] error dispatching detached before hook: {e}")
        from runtime.tasks.call_scheduler import CallScheduler

        CallScheduler._apply_async(self.pk)
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
            if isinstance(obj, (int, float, bool)) or obj is None:
                return obj
            if isinstance(obj, str):
                return pack_large_string(obj)
            if isinstance(obj, (list, set, tuple)):
                return [_create_recursive(item, ref_pks) for item in obj]
            if isinstance(obj, dict):
                if "_type" in obj and "pk" in obj and len(obj) == 2:
                    if obj["_type"] in allowed_objects:
                        # Only AgentTaskCall refs create arg dependencies;
                        # other model refs (incl. GenericContent, whose pk is
                        # a sha string) are passed through without tracking.
                        if obj["_type"] == "AgentTaskCall":
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
        """Resolve the stored call arguments, recursively fetching referenced objects.

        GenericContent refs are unwrapped to plain strings so callers see
        the same types as if no dedup had happened.
        """
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
                    if isinstance(model_instance, GenericContent):
                        try:
                            return model_instance.get()
                        except Exception:
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

    def get_direct_subcalls(self) -> models.QuerySet:
        """Return the task calls directly launched by this call's runs.

        A tool/task running inside :meth:`AgentTaskRun.apply` creates new
        calls via ``.delay()`` while ``ContextTracker`` points at its run,
        so those children carry ``parent_taskrun__agent_task_call_id`` equal
        to this call's pk — including cross-session children (e.g.
        ``delegate_task``), which share the parent run but live in another
        session.
        """
        return AgentTaskCall.objects.filter(
            parent_taskrun__agent_task_call_id=self.pk
        ).select_related("task_definition").order_by("pk")

    def get_subcall_tree(
        self, max_depth: int = 6, max_nodes: int = 200, active_only: bool = False
    ) -> list[dict[str, Any]]:
        """Return this call's descendant sub-calls as a flat depth-tagged list.

        Each entry is ``{"call": AgentTaskCall, "depth": int}`` in BFS
        order (direct children first), capped at *max_depth* levels below
        this call and *max_nodes* total entries. Never raises — returns ``[]``
        when the call is unsaved or the DB is unreachable (templates).

        With *active_only* finished (``ENDED``) branches are pruned at the
        DB level, so a long-finished tool costs a single cheap query instead
        of a full subtree walk — this is what the chat renders by default.
        """
        if not getattr(self, "pk", None):
            return []
        try:
            max_depth = max(0, int(max_depth))
            max_nodes = max(0, int(max_nodes))
        except (TypeError, ValueError):
            return []
        if max_nodes == 0:
            return []
        tree: list[dict[str, Any]] = []
        visited: set[int] = {self.pk}
        queue: list[tuple[int, int]] = [(self.pk, 0)]
        while queue and len(tree) < max_nodes:
            parent_pk, parent_depth = queue.pop(0)
            if parent_depth >= max_depth:
                continue
            try:
                qs = AgentTaskCall.objects.filter(
                    parent_taskrun__agent_task_call_id=parent_pk
                )
                if active_only:
                    qs = qs.exclude(status=TaskCallStatus.ENDED)
                children = list(
                    qs.select_related("task_definition").order_by("pk")[
                        : max_nodes - len(tree)
                    ]
                )
            except Exception:
                return tree
            for child in children:
                if child.pk in visited:
                    continue
                visited.add(child.pk)
                entry = {"call": child, "depth": parent_depth + 1}
                tree.append(entry)
                if len(tree) >= max_nodes:
                    break
                queue.append((child.pk, parent_depth + 1))
        return tree

    def count_subcalls(
        self, max_depth: int = 6, max_nodes: int = 200
    ) -> dict[str, Any]:
        """Return cheap descendant stats without loading full objects.

        Same BFS as :meth:`get_subcall_tree` but fetching only ``(pk,
        status)`` pairs, so no heavy payload columns (``carguments_json``,
        ``raw_data``) are loaded.         Returns ``{"active": int, "finished":
        int, "executing": [(pk, depth), ...], "truncated": bool}`` where
        ``active`` means not ``ENDED`` and ``executing`` lists the
        currently-executing (``ACTIVE`` status) descendants — capped at 10
        — so the UI can pin the actually-running calls to the top
        regardless of display caps. ``truncated`` is True when the walk hit
        its caps (counts understate the real tree). Never raises — returns
        zeros when unreachable.
        """
        counts: dict[str, Any] = {"active": 0, "finished": 0, "executing": []}
        if not getattr(self, "pk", None):
            return counts
        try:
            max_depth = max(0, int(max_depth))
            max_nodes = max(0, int(max_nodes))
        except (TypeError, ValueError):
            return counts
        if max_nodes == 0:
            return counts
        try:
            ended = TaskCallStatus.ENDED
        except Exception:
            ended = "ENDED"
        try:
            active_status = TaskCallStatus.ACTIVE
        except Exception:
            active_status = "ACTIVE"
        visited: set[int] = {self.pk}
        queue: list[tuple[int, int]] = [(self.pk, 0)]
        seen_total = 0
        while queue and seen_total < max_nodes:
            parent_pk, parent_depth = queue.pop(0)
            if parent_depth >= max_depth:
                continue
            try:
                rows = list(
                    AgentTaskCall.objects.filter(
                        parent_taskrun__agent_task_call_id=parent_pk
                    )
                    .order_by("pk")
                    .values_list("pk", "status")[: max_nodes - seen_total]
                )
            except Exception:
                return counts
            for child_pk, status in rows:
                if child_pk in visited:
                    continue
                visited.add(child_pk)
                seen_total += 1
                if status == ended:
                    counts["finished"] += 1
                else:
                    counts["active"] += 1
                    if status == active_status and len(counts["executing"]) < 10:
                        counts["executing"].append((child_pk, parent_depth + 1))
                if seen_total >= max_nodes:
                    break
                queue.append((child_pk, parent_depth + 1))
        if queue and seen_total >= max_nodes:
            counts["truncated"] = True
        return counts

    def get_executing_subcalls(
        self,
        max_active_scan: int = 100,
        max_depth: int = 20,
        max_pins: int = 10,
    ) -> list[dict[str, Any]]:
        """Find currently-executing (``ACTIVE``) descendants by reverse lookup.

        The forward BFS (:meth:`get_subcall_tree` / :meth:`count_subcalls`)
        is oldest-first and capped, so on huge trees (thousands of finished
        calls) a lone executing call beyond the cap is never reached. The
        globally ``ACTIVE`` set, however, is tiny (bounded by worker
        concurrency), so walk *up* from each ACTIVE call via
        ``parent_taskrun`` and keep the ones descending from this call —
        crossing sessions (delegated subtasks) transparently.

        Returns ``[{"call": AgentTaskCall, "depth": int}]``. Never raises.
        """
        result: list[dict[str, Any]] = []
        if not getattr(self, "pk", None):
            return result
        try:
            max_active_scan = max(0, int(max_active_scan))
            max_depth = max(0, int(max_depth))
            max_pins = max(0, int(max_pins))
        except (TypeError, ValueError):
            return result
        if max_active_scan == 0 or max_pins == 0:
            return result
        try:
            active_pks = list(
                AgentTaskCall.objects.filter(status=TaskCallStatus.ACTIVE)
                .order_by("pk")
                .values_list("pk", flat=True)[:max_active_scan]
            )
        except Exception:
            return result
        for apk in active_pks:
            if apk == self.pk or len(result) >= max_pins:
                continue
            try:
                call = AgentTaskCall.objects.select_related(
                    "task_definition", "parent_taskrun"
                ).get(pk=apk)
            except Exception:
                continue
            depth = 0
            seen: set[int] = set()
            current = call.parent_taskrun
            while current is not None and depth < max_depth:
                try:
                    parent_pk = current.agent_task_call_id
                except Exception:
                    break
                if not parent_pk or parent_pk in seen:
                    break
                seen.add(parent_pk)
                depth += 1
                if parent_pk == self.pk:
                    result.append({"call": call, "depth": depth})
                    break
                try:
                    parent_call = AgentTaskCall.objects.select_related(
                        "parent_taskrun"
                    ).get(pk=parent_pk)
                except Exception:
                    break
                current = parent_call.parent_taskrun
        return result

    def get_ancestor_call_pks(self, max_depth: int = 20) -> list[int]:
        """Return ancestor call pks via the ``parent_taskrun`` chain.

        Walks ``parent_taskrun -> agent_task_call`` upwards (crossing
        sessions for delegated subtasks). Never raises — returns whatever
        prefix was resolvable.
        """
        ancestors: list[int] = []
        try:
            from server.models.tasks.agent_task_run import AgentTaskRun as _Run

            current = self.parent_taskrun
            if current is not None and getattr(current, "agent_task_call_id", None) is None:
                try:
                    current = _Run.objects.select_related(
                        "agent_task_call"
                    ).get(pk=current.pk)
                except Exception:
                    return ancestors
        except Exception:
            return ancestors
        seen: set[int] = set()
        depth = 0
        while current is not None and depth < max_depth:
            try:
                parent_pk = getattr(current, "agent_task_call_id", None)
            except Exception:
                break
            if not parent_pk or parent_pk in seen:
                break
            seen.add(parent_pk)
            ancestors.append(parent_pk)
            depth += 1
            try:
                parent_call = AgentTaskCall.objects.select_related(
                    "parent_taskrun"
                ).get(pk=parent_pk)
            except Exception:
                break
            current = parent_call.parent_taskrun
        return ancestors

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
