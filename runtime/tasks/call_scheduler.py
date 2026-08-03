from __future__ import annotations
from typing import TYPE_CHECKING

from server.models.tasks.agent_task_call import AgentTaskCall
from server.models.enums.task_enums import TaskCallStatus, TaskCallStatusDetail, TaskRunStatus
from runtime.tasks.call_fsm import TaskCallStateMachine
if TYPE_CHECKING:
    from server.models.tasks.agent_task_run import AgentTaskRun
    from server.models.tasks.task_instance import TaskInstance


class CallScheduler:
    """
    Orchestrates the lifecycle of AgentTaskCall instances.

    Coordinates dependency resolution, approval gating, task-run dispatch,
    after-run hooks, and success/error callbacks.  All status changes are
    delegated to :class:`TaskCallStateMachine`.
    """

    @staticmethod
    def _apply_async(task_call_id: int) -> None:
        """
        Entry point for scheduling a task call.

        Transitions the call to ``WAITING_DEPENDENCY`` and, if no argument
        references are still running, immediately proceeds to
        :meth:`on_all_arg_reference_tasks_ended`.
        """
        tc = AgentTaskCall.objects.get(pk=task_call_id)
        if not TaskCallStateMachine.enter_dependency_wait(task_call_id):
            print("not updated, skip")
            return

        tc = AgentTaskCall.objects.get(pk=task_call_id)
        if tc.taskcall_arg_references.exclude(status=TaskCallStatus.ENDED).exists():
            print("required_calls unfinished")
            return
        CallScheduler.on_all_arg_reference_tasks_ended(task_call_id)

    # ------------------------------------------------------------------
    # Argument (dependency) task handling
    # ------------------------------------------------------------------

    @staticmethod
    def on_arg_reference_task_ended(
        task_call_id: int,
        last_taskrun_id: int,
        related_call_status: TaskCallStatusDetail | str,
    ) -> None:
        """
        Called when one of the argument-reference tasks has finished.

        If the referenced task was stopped or failed, this call is also
        stopped/cancelled.  Otherwise, once **all** argument references have
        ended, :meth:`on_all_arg_reference_tasks_ended` is invoked.
        """
        print("required_task_call_ended", task_call_id)

        if related_call_status == TaskCallStatusDetail.ENDED_STOPPED:
            if TaskCallStateMachine.stop(task_call_id, TaskCallStatusDetail.WAITING_DEPENDENCY):
                CallScheduler._on_taskcall_ended(
                    task_call_id, last_taskrun_id, TaskCallStatusDetail.ENDED_CANCELLED
                )
                print("required_task_call.ENDED_STOPPED, TaskCallStatusDetail.ENDED_STOPPED")
            return

        if related_call_status != TaskCallStatusDetail.ENDED_SUCCESS:
            print(
                "required_task_call NOT ENDED_SUCCESS, TaskCallStatusDetail.ENDED_CANCELLED",
                related_call_status,
            )
            if TaskCallStateMachine.cancel(task_call_id, TaskCallStatusDetail.WAITING_DEPENDENCY):
                CallScheduler._on_taskcall_ended(
                    task_call_id, last_taskrun_id, TaskCallStatusDetail.ENDED_CANCELLED
                )
            else:
                # Dependent may have progressed past WAITING_DEPENDENCY
                # (e.g. WAITING_RETRY, WAITING_QUEUE, ACTIVE_QUEUED).
                CallScheduler._cancel_safe(task_call_id, last_taskrun_id, TaskCallStatusDetail.ENDED_CANCELLED)
            return

        tc = AgentTaskCall.objects.get(pk=task_call_id)
        # Check if ANY of the tasks it lists as arguments are still unfinished
        if tc.taskcall_arg_references.exclude(status=TaskCallStatus.ENDED).exists():
            return  # Still waiting for other arguments
        CallScheduler.on_all_arg_reference_tasks_ended(task_call_id)

    @staticmethod
    def on_all_arg_reference_tasks_ended(task_call_id: int) -> None:
        """
        All argument dependencies have resolved.

        If the call requires approval it is paused at ``HALTED_APPROVAL``;
        otherwise it is enqueued and a new task run is started.

        Guardrail check: for ``shell`` tool calls, run sh-guard on the
        command source.  If the verdict is ``ask`` (risky or blocked) the
        call is dynamically marked as requiring approval so the user can
        decide.
        """
        print("all_required_task_calls_ended", task_call_id)

        # --- Guardrail checks ---
        CallScheduler._guardrail_shell_check(task_call_id)
        CallScheduler._guardrail_python_check(task_call_id)

        if TaskCallStateMachine.request_approval(task_call_id):
            print(" # WAIT FOR APPROVAL")
            return  # WAIT FOR APPROVAL

        if not TaskCallStateMachine.enqueue_after_dependencies(task_call_id):
            print("# was not queued, maybe some race condition")
            return  # was not queued, maybe some race condition

        CallScheduler.start_new_taskrun(task_call_id)

    @staticmethod
    def _guardrail_python_check(task_call_id: int) -> None:
        """Run guardrail on Python code and dynamically require approval if needed."""
        from server.models.tasks.agent_task_call import AgentTaskCall
        from runtime.guardrails import check_python_command

        try:
            tc = AgentTaskCall.objects.get(pk=task_call_id)
        except AgentTaskCall.DoesNotExist:
            return

        task_name = getattr(tc.task_definition, "name", "") if tc.task_definition else ""

        if task_name != "python":
            return

        source = tc.carguments_json.get("source", "")
        if not source:
            args = tc.carguments_json.get("*", [])
            source = args[0] if args else ""

        if not source:
            instance_args = getattr(tc.task_instance, "iarguments_json", {}).get("*", [])
            source = instance_args[0] if instance_args else ""

        source = str(source) if source else ""
        if not source:
            return

        verdict = check_python_command(source)

        if verdict.action == "ask" and not tc.requires_approval:
            from server.models.tasks.agent_task_call import AgentTaskCall as _ATC
            _ATC.objects.filter(pk=tc.pk).update(
                requires_approval=True, guardrail_reason = verdict.reason
            )
            print(f"  # PYTHON GUARDRAIL: {verdict.level} ({verdict.score}) — {verdict.reason[:80]}")

    @staticmethod
    def _guardrail_shell_check(task_call_id: int) -> None:
        """Run guardrail on shell commands and dynamically require approval if needed."""
        from server.models.tasks.agent_task_call import AgentTaskCall
        from runtime.guardrails import check_shell_command

        try:
            tc = AgentTaskCall.objects.get(pk=task_call_id)
        except AgentTaskCall.DoesNotExist:
            return

        task_name = getattr(tc.task_definition, "name", "") if tc.task_definition else ""

        if task_name != "shell":
            return

        # Extract the 'source' argument from call or instance defaults
        source = tc.carguments_json.get("source", "")
        if not source:
            args = tc.carguments_json.get("*", [])
            source = args[0] if args else ""

        if not source:
            instance_args = getattr(tc.task_instance, "iarguments_json", {}).get("*", [])
            source = instance_args[0] if instance_args else ""

        source = str(source) if source else ""
        if not source:
            return

        verdict = check_shell_command(source)

        if verdict.action == "ask" and not tc.requires_approval:
            from server.models.tasks.agent_task_call import AgentTaskCall as _ATC
            _ATC.objects.filter(pk=tc.pk).update(
                requires_approval=True, guardrail_reason = verdict.reason,
            )
            print(f"  # GUARDRAIL: {verdict.level} ({verdict.score}) — {verdict.reason[:80]}")

    # ------------------------------------------------------------------
    # Human approval
    # ------------------------------------------------------------------

    @staticmethod
    def approve_taskcall(task_call_id: int) -> None:
        """Approve a halted call and start a new task run."""
        if not TaskCallStateMachine.approve(task_call_id):
            print(" # was not queued, maybe some race condition")
            return  # was not queued, maybe some race condition
        CallScheduler.start_new_taskrun(task_call_id)

    # ------------------------------------------------------------------
    # Task-run dispatch
    # ------------------------------------------------------------------

    @staticmethod
    def _ancestor_call_ids(task_call_id: int) -> list[int]:
        """Collect the ``agent_task_call`` ids of all ancestor runs of a call.

        Walks the ``parent_taskrun`` chain (the run that spawned this call, that
        run's own call, and so on up to the session root).  A call's ancestors
        on the same task_instance form a *same-turn continuation* chain (e.g.
        ``decide_next_step`` at the tail of a ``process_turn`` chain dispatching
        the next ``process_turn``); their runs must not count against the
        per-TaskInstance parallel limit or the continuation would deadlock
        against the very run that spawned it (E5).
        """
        from server.models.tasks.agent_task_call import AgentTaskCall as _ATC

        ancestor_ids: list[int] = []
        seen: set[int] = set()
        current = _ATC.objects.filter(pk=task_call_id).only(
            "pk", "parent_taskrun_id"
        ).first()
        while current and current.parent_taskrun_id and current.pk not in seen:
            seen.add(current.pk)
            parent = current.parent_taskrun
            if parent and parent.agent_task_call_id:
                ancestor_ids.append(parent.agent_task_call_id)
                current = _ATC.objects.filter(pk=parent.agent_task_call_id).only(
                    "pk", "parent_taskrun_id"
                ).first()
            else:
                break
        return ancestor_ids

    @staticmethod
    def start_new_taskrun(task_call_id: int) -> None:
        """
        Transition the call to ``ACTIVE_QUEUED`` and create a new
        :class:`AgentTaskRun` for it.
        """
        from server.models.tasks.agent_task_run import AgentTaskRun as _ATR
        from server.models.enums.task_enums import TaskRunStatus as _TRS
        from django.db import transaction

        taskcall = AgentTaskCall.objects.get(pk=task_call_id)

        # Enforce per-TaskInstance parallel run limit.
        limit = taskcall.limit_per_instance_parallel_runs
        if limit > 0:
            # I1 race: the count-then-create sequence is racy.  Two concurrent
            # dispatches for *different* calls on the same task_instance can
            # both read ``running < limit`` and both create runs, exceeding the
            # parallel limit.  Lock the task_instance row so admission control
            # (count + pick_up + run creation) is atomic.
            from server.models.tasks.task_instance import TaskInstance

            with transaction.atomic():
                TaskInstance.objects.select_for_update().get(pk=taskcall.task_instance_id)
                running = _ATR.objects.filter(
                    task_instance=taskcall.task_instance,
                ).exclude(
                    status__in=[_TRS.SUCCESS, _TRS.FAILURE]
                ).exclude(
                    # A call that is a *descendant* of a running call on the
                    # same task_instance is a same-turn continuation (e.g.
                    # ``decide_next_step`` at the tail of a ``process_turn``
                    # chain dispatching the next ``process_turn``), not a
                    # concurrent turn.  Counting the ancestor's run here would
                    # block the continuation against the very run that spawned
                    # it — the E5 circular deadlock.  Exclude ancestors so the
                    # loop can proceed; genuinely independent calls (sibling
                    # turns, separate messages) are still serialized.
                    agent_task_call_id__in=CallScheduler._ancestor_call_ids(task_call_id),
                ).count()
                if running >= limit:
                    return  # Stay in WAITING_QUEUE — drain will pick up later

                taskrun = CallScheduler._pick_up_and_create_run(task_call_id)
        else:
            taskrun = CallScheduler._pick_up_and_create_run(task_call_id)

        if taskrun:
            taskrun.apply_async()

    @staticmethod
    def _pick_up_and_create_run(task_call_id: int) -> AgentTaskRun | None:
        """``pick_up()`` the call, merge its args, and create the run.

        Returns ``None`` if ``pick_up()`` lost the race (call no longer in
        ``WAITING_QUEUE``).  The run is dispatched by the caller after the
        admission-control transaction commits.
        """
        if not TaskCallStateMachine.pick_up(task_call_id):
            print(f" # TaksCallId {task_call_id} was not queued, maybe some race condition")
            return None

        taskcall = AgentTaskCall.objects.get(pk=task_call_id)

        # Merge positional args, deduplicating while preserving order.
        # iargs (instance defaults) come first; call-level overrides appended
        # only if not already present (handles dict/list args via equality).
        iargs = taskcall.task_instance.iarguments_json.get("*", [])
        cargs = taskcall.carguments_json.get("*", [])
        args = list(iargs)
        for x in cargs:
            if x not in iargs:
                args.append(x)

        kwargs: dict = {}
        kwargs.update(taskcall.task_instance.iarguments_json)
        kwargs.update(taskcall.carguments_json)
        if args:
            kwargs["*"] = args

        from server.models.tasks.agent_task_run import AgentTaskRun

        return AgentTaskRun.create(agent_task_call=taskcall, args=args, kwargs=kwargs)

    @staticmethod
    def on_taskrun_ended(taskrun_id: int, taskrun_status: TaskRunStatus) -> None:
        """
        Handle the completion of a task run.

        - On ``FAILURE``: attempt retry via :meth:`TaskCallStateMachine.schedule_retry`;
          if the retry budget is exhausted, transition to failure.
        - On ``SUCCESS``: dispatch after-run hooks if any are registered,
          otherwise finalise immediately.
        """
        from server.models.tasks.agent_task_run import AgentTaskRun

        run = AgentTaskRun.objects.get(pk=taskrun_id)
        call = run.agent_task_call
        print("on_taskrun_ended", taskrun_status, run, call)

        if taskrun_status == TaskRunStatus.FAILURE:  # Handle retries
            if TaskCallStateMachine.schedule_retry(call.pk, call.retry_delay, call.max_retries):
                return
            if TaskCallStateMachine.fail(call.pk):
                CallScheduler._on_taskcall_ended(
                    call.pk, taskrun_id, TaskCallStatusDetail.ENDED_FAILURE_EXCEPTION
                )
            return

        if taskrun_status == TaskRunStatus.SUCCESS:
            after_hooks = list(
                run.task_instance.taskinstances_after_run_hooks.all().order_by('pk')
            )
            if not after_hooks:
                CallScheduler.on_all_on_posthook_ended(call.pk, taskrun_id)
                return

            # --- AFTER_RUN Hooks Dispatch ---
            after_hook_calls = []
            print(
                f"DEBUG: Dispatching AFTER_RUN hooks for "
                f"{run.task_definition_version.name}. {len(after_hooks)} hooks found."
            )
            updated = TaskCallStateMachine.wait_for_hooks(call.pk, taskrun_id)
            if updated:
                hook_arguments = run
                for i, hook_instance in enumerate(after_hooks):
                    hook_instance: TaskInstance
                    print(
                        f"  -> Launching after_run hook "
                        f"{hook_instance.task_definition_version.name} "
                        f"(step {i + 1}/{len(after_hooks)})"
                    )
                    result = hook_instance.create_call(kwargs=hook_arguments)
                    after_hook_calls.append(result)
                    hook_arguments = result
                call.taskcall_after_run_hooks.set(after_hook_calls)
                for after_hook_call in after_hook_calls:
                    after_hook_call.apply_async()

    @staticmethod
    def on_posthook_ended(
        task_call_id: int,
        last_taskrun_id: int,
        related_call_status: TaskCallStatusDetail | str,
    ) -> None:
        """
        Called when one of the after-run hook calls finishes.

        If the hook stopped/failed the parent call is stopped/cancelled.
        Once all hooks have ended :meth:`on_all_on_posthook_ended` fires.
        """
        print("on_posthook_ended", task_call_id, last_taskrun_id, related_call_status)

        if related_call_status == TaskCallStatusDetail.ENDED_STOPPED:
            if TaskCallStateMachine.stop(task_call_id, TaskCallStatusDetail.WAITING_SUBTASKS_OR_HOOKS):
                CallScheduler._on_taskcall_ended(
                    task_call_id, last_taskrun_id, TaskCallStatusDetail.ENDED_CANCELLED
                )
                print("required_task_call.ENDED_STOPPED, TaskCallStatusDetail.ENDED_STOPPED")
            return

        if related_call_status != TaskCallStatusDetail.ENDED_SUCCESS:
            print(
                "required_task_call NOT ENDED_SUCCESS, TaskCallStatusDetail.ENDED_CANCELLED",
                related_call_status,
            )
            if TaskCallStateMachine.cancel(task_call_id, TaskCallStatusDetail.WAITING_SUBTASKS_OR_HOOKS):
                CallScheduler._on_taskcall_ended(
                    task_call_id, last_taskrun_id, TaskCallStatusDetail.ENDED_CANCELLED
                )
            else:
                # Hook parent may have progressed past WAITING_SUBTASKS_OR_HOOKS
                # (e.g. WAITING_RETRY, WAITING_QUEUE, ACTIVE_QUEUED).
                CallScheduler._cancel_safe(task_call_id, last_taskrun_id, TaskCallStatusDetail.ENDED_CANCELLED)
            return

        tc = AgentTaskCall.objects.get(pk=task_call_id)
        if tc.taskcall_after_run_hooks.exclude(status=TaskCallStatus.ENDED).exists():
            print("Not all ended")
            return  # Still waiting for other arguments
        CallScheduler.on_all_on_posthook_ended(task_call_id, last_taskrun_id)

    @staticmethod
    def on_all_on_posthook_ended(task_call_id: int, last_taskrun_id: int) -> None:
        """
        All after-run hooks have finished.  Transition the call to
        ``ENDED_SUCCESS``.
        """
        print("on_all_on_posthook_ended", task_call_id, last_taskrun_id)
        if TaskCallStateMachine.succeed(task_call_id, last_taskrun_id):
            CallScheduler._on_taskcall_ended(
                task_call_id, last_taskrun_id, TaskCallStatusDetail.ENDED_SUCCESS
            )

    # ------------------------------------------------------------------
    # Finalisation
    # ------------------------------------------------------------------

    @staticmethod
    def _on_taskcall_ended(
        task_call_id: int,
        last_taskrun_id: int,
        taskcall_status_detail: TaskCallStatusDetail,
    ) -> None:
        """
        Finalise a task call and propagate the result:

        1. Notify parent runs waiting for this call as a result reference.
        2. Notify dependent calls that listed this call as an argument.
        3. Notify parent calls that listed this as an after-run hook.
        4. Dispatch success/error callbacks.
        """
        from server.models.tasks.agent_task_run import AgentTaskRun
        from runtime.tasks.run_scheduler import RunScheduler

        # I4 invariant: the call is ending — any run still non-terminal is
        # stranded.  A force-cancel (UI cancel, duplicate-query dedup, bulk
        # root cancel) can end an ACTIVE_RUNNING call while its worker is
        # mid-apply().  Fail the run so no ACTIVE run outlives its call; the
        # worker's later succeed()/fail() is a no-op because the run is
        # already FAILURE.  Mirrors the run sweep in _recover_stuck_calls
        # step 3.
        from django.utils import timezone
        AgentTaskRun.objects.filter(
            agent_task_call_id=task_call_id,
        ).exclude(
            status__in=[TaskRunStatus.SUCCESS, TaskRunStatus.FAILURE],
        ).update(
            status=TaskRunStatus.FAILURE,
            ended_at=timezone.now(),
            updated_at=timezone.now(),
        )

        # In case We are a subtask of another task that waits for us to
        # finish for its results
        parent_run_ids = AgentTaskRun.objects.filter(
            taskrun_result_references__pk=task_call_id,
            status=TaskRunStatus.WAITING_RESULTTASKS,
        ).values_list('pk', flat=True)
        print("parent_run_ids", parent_run_ids)
        for parent_run_id in parent_run_ids:
            RunScheduler.taskrun_result_reference_ended(
                parent_run_id, task_call_id, taskcall_status_detail
            )
        from server.models.enums.task_enums import TaskCallStatus, TaskCallStatusDetail

        # Call tasks that wait for us because their arguments need us
        dependent_ids = AgentTaskCall.objects.filter(
            taskcall_arg_references__pk=task_call_id,
            status_detail=TaskCallStatusDetail.WAITING_DEPENDENCY,
        ).values_list('pk', flat=True)
        for dependent_id in dependent_ids:
            from server.tasks.task_dispatcher import celery_delay
            celery_delay(
                CallScheduler.on_arg_reference_task_ended,
                dependent_id, last_taskrun_id, taskcall_status_detail,
            )

        # In case we are a run after hook, call our parent task
        after_run_hook_ids = AgentTaskCall.objects.filter(
            taskcall_after_run_hooks__pk=task_call_id,
            status_detail=TaskCallStatusDetail.WAITING_SUBTASKS_OR_HOOKS,
        ).values_list('pk', flat=True)
        #print("after_run_hook_ids", after_run_hook_ids)
        for after_run_hook_id in after_run_hook_ids:
            from server.tasks.task_dispatcher import celery_delay
            celery_delay(
                CallScheduler.on_posthook_ended,
                after_run_hook_id, last_taskrun_id, taskcall_status_detail,
            )

        # --- taskcall_on_success_callbacks Dispatch ---
        try:
            run = AgentTaskRun.objects.get(pk=last_taskrun_id)
        except AgentTaskRun.DoesNotExist:
            run = None
        call = AgentTaskCall.objects.get(pk=task_call_id)
        if not run:
            pass  # no run to dispatch callbacks from
        elif taskcall_status_detail == TaskCallStatusDetail.ENDED_SUCCESS:
            print("taskcall_on_success_callbacks")
            callback_instances = list(
                run.task_instance.taskinstances_on_success_callbacks.all().order_by('pk')
            )
            print("callback_instances", callback_instances)
            if callback_instances:
                callbacks = []
                print(
                    f"DEBUG: Dispatching taskcall_on_success_callbacks for "
                    f"taskrun:#{last_taskrun_id}. {len(callback_instances)} found."
                )
                for i, callback_instance in enumerate(callback_instances):
                    callback_instance: TaskInstance
                    print(
                        f"  -> Launching taskcall_on_success_callback "
                        f"{callback_instance.task_definition_version.name} "
                        f"(step {i + 1}/{len(callback_instances)})"
                    )
                    callback = callback_instance.apply_async(kwargs=run)
                    callbacks.append(callback)
                call.taskcall_on_success_callbacks.set(callbacks)

        # --- taskcall_on_error_callbacks Dispatch ---
        elif taskcall_status_detail in (
            TaskCallStatusDetail.ENDED_FAILURE_EXCEPTION,
            TaskCallStatusDetail.ENDED_FAILURE_LOGIC,
        ):
            callback_instances = list(
                run.task_instance.taskinstances_on_error_callbacks.all().order_by('pk')
            )
            if callback_instances:
                callbacks = []
                print(
                    f"DEBUG: Dispatching taskcall_on_error_callbacks for "
                    f"taskrun:#{last_taskrun_id}. {len(callback_instances)} found."
                )
                for i, callback_instance in enumerate(callback_instances):
                    callback_instance: TaskInstance
                    print(
                        f"  -> Launching taskcall_on_error_callback "
                        f"{callback_instance.task_definition_version.name} "
                        f"(step {i + 1}/{len(callback_instances)})"
                    )
                    callback = callback_instance.apply_async(kwargs=run)
                    callbacks.append(callback)
                call.taskcall_on_error_callbacks.set(callbacks)

        # --- Drain per-TaskInstance queue (release calls blocked by parallel limit) ---
        if call.limit_per_instance_parallel_runs > 0:
            from server.models.tasks.agent_task_call import AgentTaskCall as _ATC
            from server.models.enums.task_enums import TaskCallStatusDetail
            next_waiting = _ATC.objects.filter(
                task_instance=call.task_instance,
                status_detail=TaskCallStatusDetail.WAITING_QUEUE,
            ).order_by("created_at").first()
            if next_waiting:
                CallScheduler.start_new_taskrun(next_waiting.pk)

        # --- Drain session queue for ingest calls (per-session FIFO) ---
        if call.task_definition and call.task_definition.name in (
            "ingest_user_message", "ingest_slash_command",
        ):
            CallScheduler._release_next_queued_call(call.session)

    @staticmethod
    def _cancel_safe(call_id: int, last_taskrun_id: int, status_detail: TaskCallStatusDetail) -> None:
        """Cancel a call in whatever state it is currently in, then propagate.

        Used as a fallback when :meth:`on_arg_reference_task_ended` or
        :meth:`on_posthook_ended` find the target call has progressed past
        the expected ``WAITING_DEPENDENCY`` / ``WAITING_SUBTASKS_OR_HOOKS`` state
        (e.g. into ``WAITING_RETRY``, ``WAITING_QUEUE``, or ``ACTIVE_QUEUED``).
        """
        from server.models.tasks.agent_task_call import AgentTaskCall
        from runtime.tasks.call_fsm import _publish_call_event

        try:
            tc = AgentTaskCall.objects.get(pk=call_id)
        except AgentTaskCall.DoesNotExist:
            return

        if tc.status == TaskCallStatus.ENDED:
            return

        sd = TaskCallStatusDetail(tc.status_detail)

        # ACTIVE_RUNNING calls must go through fail() (no FSM path to ENDED_CANCELLED)
        if sd == TaskCallStatusDetail.ACTIVE_RUNNING:
            if TaskCallStateMachine.fail(call_id):
                CallScheduler._on_taskcall_ended(call_id, last_taskrun_id, status_detail)
            return

        # Try FSM transition from the call's current state
        if TaskCallStateMachine.transition(
            call_id, sd, TaskCallStatusDetail.ENDED_CANCELLED,
            extra={"ended_at": timezone.now()},
        ):
            CallScheduler._on_taskcall_ended(call_id, last_taskrun_id, status_detail)
            return

        # Fallback for any state the FSM doesn't cover.
        # This should never fire — all non-terminal states now have FSM paths.
        # If it does, it indicates a programming bug (a state was added without
        # updating the FSM). We still do the cascade to leave the system
        # consistent, then raise.
        updated = AgentTaskCall.objects.filter(pk=call_id).update(
            status=TaskCallStatus.ENDED,
            status_detail=TaskCallStatusDetail.ENDED_CANCELLED,
            ended_at=timezone.now(),
        ) > 0
        if updated:
            _publish_call_event(call_id)
            CallScheduler._on_taskcall_ended(call_id, last_taskrun_id, status_detail)
        raise RuntimeError(
            f"_cancel_safe fallback fired for call {call_id} "
            f"(state={tc.status_detail}) — programming bug: no FSM path to ENDED_CANCELLED"
        )

    @staticmethod
    def cancel_root_tasktree(root_call_id: int) -> None:
        """Cancel an entire root task tree (root + all children).

        Traverses ``session_child_task_calls`` to find all non-ended
        children of *root_call_id* and cancels them deepest-first,
        then cancels the root itself.  Each cancellation cascades
        through the dependency graph via ``_on_taskcall_ended``.
        """
        from server.models.tasks.agent_task_call import AgentTaskCall
        from server.models.enums.task_enums import TaskCallStatus

        root = AgentTaskCall.objects.filter(pk=root_call_id).first()
        if not root:
            return

        actual_root_id = root.session_root_task_id or root.pk

        # Cancel all non-ended children (deepest first via -pk ordering,
        # since children created later tend to be deeper in the tree).
        for child in AgentTaskCall.objects.filter(
            session_root_task_id=actual_root_id,
        ).exclude(status=TaskCallStatus.ENDED).order_by("-pk"):
            if child.pk == actual_root_id:
                continue  # skip root, we do it last
            CallScheduler._cancel_safe(child.pk, 0, TaskCallStatusDetail.ENDED_CANCELLED)

        # Finally cancel the root itself.
        if root.status != TaskCallStatus.ENDED:
            CallScheduler._cancel_safe(root.pk, 0, TaskCallStatusDetail.ENDED_CANCELLED)

    @staticmethod
    def _release_next_queued_call(session) -> None:
        """Dispatch the oldest WAITING_QUEUE call for *session*, if any."""
        from server.models.tasks.agent_task_call import AgentTaskCall as _ATC
        from server.models.enums.task_enums import TaskCallStatusDetail

        next_call = _ATC.objects.filter(
            session=session,
            status_detail=TaskCallStatusDetail.WAITING_QUEUE,
        ).order_by("created_at").first()
        if next_call:
            CallScheduler.start_new_taskrun(next_call.pk)
