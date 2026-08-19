from __future__ import annotations
from typing import TYPE_CHECKING, Any

from server.models.tasks.agent_task_call import AgentTaskCall
from server.models.enums.task_enums import TaskCallStatus, TaskCallStatusDetail, TaskRunStatus
from runtime.tasks.call_fsm import TaskCallStateMachine
if TYPE_CHECKING:
    from server.models.tasks.agent_task_run import AgentTaskRun
    from server.models.tasks.task_instance import TaskInstance


def _merge_guardrail_verdicts(*verdicts: Any) -> Any:
    """Combine guardrail verdicts — ``deny`` wins, else ``ask``, else allow."""
    best = None
    for verdict in verdicts:
        if verdict is None:
            continue
        if verdict.action == "deny":
            return verdict
        if verdict.action == "ask" and (best is None or best.action == "allow"):
            best = verdict
    return best if best is not None else (verdicts[0] if verdicts else None)


AUTO_REVIEW_TOOL_NAMES = ("python", "shell")


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
        CallScheduler._guardrail_filesystem_check(task_call_id)

        if TaskCallStateMachine.request_approval(task_call_id):
            print(" # WAIT FOR APPROVAL")
            CallScheduler._dispatch_auto_review(task_call_id)
            return  # WAIT FOR APPROVAL

        if not TaskCallStateMachine.enqueue_after_dependencies(task_call_id):
            print("# was not queued, maybe some race condition")
            return  # was not queued, maybe some race condition

        CallScheduler.start_new_taskrun(task_call_id)

    @staticmethod
    def _guardrail_python_check(task_call_id: int) -> None:
        """Run guardrail on Python code and dynamically require approval if needed."""
        from server.models.tasks.agent_task_call import AgentTaskCall

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

        from runtime.guardrails import check_python_command, check_python_paths
        from runtime.workspace_access import resolve_policy

        policy = resolve_policy(tc.session_version.get_runtime())
        verdict = _merge_guardrail_verdicts(
            check_python_command(source),
            check_python_paths(source, policy),
        )

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

        from runtime.guardrails import check_shell_command, check_shell_paths
        from runtime.workspace_access import resolve_policy

        policy = resolve_policy(tc.session_version.get_runtime())
        verdict = _merge_guardrail_verdicts(
            check_shell_command(source),
            check_shell_paths(source, policy),
        )

        if verdict.action == "ask" and not tc.requires_approval:
            from server.models.tasks.agent_task_call import AgentTaskCall as _ATC
            _ATC.objects.filter(pk=tc.pk).update(
                requires_approval=True, guardrail_reason = verdict.reason,
            )
            print(f"  # GUARDRAIL: {verdict.level} ({verdict.score}) — {verdict.reason[:80]}")

    @staticmethod
    # pylint: disable=too-many-locals
    def _guardrail_filesystem_check(task_call_id: int) -> None:
        """Evaluate filesystem tool paths against the workspace access policy.

        Out-of-scope ``ask`` verdicts mark the call as requiring approval.
        ``deny`` verdicts are enforced at execution time in ``BoundTask.call``.
        """
        from server.models.tasks.agent_task_call import AgentTaskCall
        from runtime.workspace_access import (
            evaluate,
            extract_path_args,
            resolve_policy,
            task_access_posture,
        )

        try:
            tc = AgentTaskCall.objects.get(pk=task_call_id)
        except AgentTaskCall.DoesNotExist:
            return

        task_definition = tc.task_definition
        if not task_definition:
            return
        task_name = task_definition.name
        posture = task_access_posture(task_definition)
        if posture is None:
            return

        args = dict(tc.carguments_json or {})
        if "*" in args:
            args.pop("*")

        policy = resolve_policy(tc.session_version.get_runtime())
        ask_reasons: list[str] = []
        for path, action in extract_path_args(task_name, posture, args):
            verdict = evaluate(policy, path, action)
            if verdict.action == "ask":
                ask_reasons.append(f"{path} ({action})")
            elif verdict.action == "deny":
                # deny is enforced at execution; no approval can override it.
                return

        if ask_reasons and not tc.requires_approval:
            from server.models.tasks.agent_task_call import AgentTaskCall as _ATC
            _ATC.objects.filter(pk=tc.pk).update(
                requires_approval=True,
                guardrail_reason="Filesystem access policy: " + "; ".join(ask_reasons),
            )
            print(f"  # FILESYSTEM GUARDRAIL: {'; '.join(ask_reasons)}")

    # ------------------------------------------------------------------
    # Automated approval review (approval_decider agent)
    #
    # python/shell calls that trip a guardrail and halt for approval are
    # routed to a dedicated ``approval_decider`` subagent.  The decider
    # receives the command, the guardrail reason, the requesting agent's
    # allowed tools and its filesystem permissions, then renders an
    # ``approval_verdict``: ``allow`` (auto-approve), ``deny`` (auto-deny,
    # reason fed back via ``catch_approval_denied``) or ``ask_human``
    # (leaves the call halted for the human).  Opt out per agent with
    # ``extra_settings: {auto_review_approvals: false}``.
    # ------------------------------------------------------------------

    @staticmethod
    def _auto_review_enabled(parent_session: Any) -> bool:
        """Return whether auto-review is enabled for *parent_session*.

        Reads ``extra_settings.auto_review_approvals`` on the agent.  Omitting
        it (or ``true``) enables auto-review; ``false`` or an empty list
        disables it; a list restricts review to the named tools.
        """
        try:
            extra = parent_session.agent.get_agent_setting("extra_settings") or {}
        except Exception:  # pylint: disable=broad-exception-caught
            extra = {}
        setting = extra.get("auto_review_approvals", True)
        if setting is False:
            return False
        if setting is True or setting is None:
            return True
        if isinstance(setting, (list, tuple)):
            return bool(setting)
        return True

    @staticmethod
    def _dispatch_auto_review(task_call_id: int) -> None:
        """Mark a halted python/shell call for automated review and launch it.

        Only fires for python/shell calls that are not already under review.
        Marks the call ``auto_review_status="pending"`` and dispatches
        :meth:`auto_review_approval` to a worker.
        """
        from server.models.tasks.agent_task_call import AgentTaskCall as _ATC

        call = _ATC.objects.filter(pk=task_call_id).first()
        if call is None:
            return
        tool_name = call.task_definition.name if call.task_definition else ""
        if tool_name not in AUTO_REVIEW_TOOL_NAMES:
            return
        if call.auto_review_status:
            return  # already pending or decided

        try:
            from runtime.session.session import Session
            parent_session = Session(
                session_model=call.session, pinned_session_version=call.session_version
            )
        except Exception:  # pylint: disable=broad-exception-caught
            parent_session = None
        if parent_session is None or not CallScheduler._auto_review_enabled(parent_session):
            return

        _ATC.objects.filter(pk=call.pk).update(auto_review_status="pending")
        print(f"  # AUTO-REVIEW: reviewing {tool_name} call #{task_call_id}")
        from server.tasks.task_dispatcher import celery_delay
        celery_delay(CallScheduler.auto_review_approval, task_call_id)

    @staticmethod
    def auto_review_approval(task_call_id: int) -> None:
        """Launch an ``approval_decider`` subagent to review a halted call.

        Runs on a worker (dispatched via :meth:`_dispatch_auto_review`).
        Builds the review brief, spawns the decider session and sends the
        brief.  The decider's ``approval_verdict`` tool applies the result.
        Any failure escalates: the call stays ``HALTED_APPROVAL`` for a human.
        """
        from server.models.tasks.agent_task_call import AgentTaskCall as _ATC
        from server.models.enums.task_enums import TaskCallStatusDetail

        call = _ATC.objects.filter(pk=task_call_id).first()
        if call is None:
            return
        if call.status_detail != TaskCallStatusDetail.HALTED_APPROVAL:
            return  # a human (or another process) already decided
        tool_name = call.task_definition.name if call.task_definition else ""
        if tool_name not in AUTO_REVIEW_TOOL_NAMES:
            return

        try:
            from runtime.session.session import Session
            parent_session = Session(
                session_model=call.session, pinned_session_version=call.session_version
            )
            brief = CallScheduler._build_review_brief(parent_session, call, tool_name)
            CallScheduler._launch_review_session(parent_session, call, brief)
        except Exception as exc:  # pylint: disable=broad-exception-caught
            print(f"auto_review_approval: review of call #{task_call_id} failed -> escalate: {exc}")
            _ATC.objects.filter(pk=call.pk).update(
                auto_review_status="escalated",
                auto_review_reason=f"Auto-review failed: {exc}",
            )

    @staticmethod
    def _build_review_brief(
        parent_session: Any, call: Any, tool_name: str
    ) -> str:
        """Compose the review brief handed to the approval decider.

        Includes the exact command, the guardrail reason, the requesting
        agent's allowed tools and its resolved filesystem permissions — the
        context the decider needs to judge whether the command grants the
        agent more power than it already has.
        """
        from runtime.workspace_access import resolve_policy

        source = call.carguments_json.get("source", "")
        if not source:
            args = call.carguments_json.get("*", [])
            source = args[0] if args else ""

        lines = [
            "Review the command below and render your approval verdict.",
            "",
            f"Tool: {tool_name}",
            f"task_call_id: {call.pk}  (copy this exact number verbatim into your approval_verdict call)",
            "",
            "Script source:",
            "```",
            str(source) if source else "(empty)",
            "```",
            "",
            f"Guardrail reason: {call.guardrail_reason or 'unspecified'}",
            "",
            f"Requesting agent: {parent_session.agent.name}",
            "Allowed tools: "
            + (", ".join(sorted(parent_session.allowedToolNames)) or "(none)"),
            "",
            "Filesystem permissions:",
            CallScheduler._render_policy(resolve_policy(parent_session)),
        ]
        return "\n".join(lines)

    @staticmethod
    def _render_policy(policy: Any) -> str:
        """Human-readable rendering of a workspace access policy."""

        def _fmt(action_policy: Any) -> str:
            return (
                f"default={action_policy.default or 'inherit'}; "
                f"allow={action_policy.allow or []}; "
                f"ask={action_policy.ask or []}; "
                f"deny={action_policy.deny or []}"
            )

        lines = [f"workspace root: {policy.workspace_root or 'none'}"]
        lines.append(f"  inside read:     {_fmt(policy.inside_read)}")
        lines.append(f"  inside write:    {_fmt(policy.inside_write)}")
        lines.append(f"  external read:   {_fmt(policy.external_read)}")
        lines.append(f"  external write:  {_fmt(policy.external_write)}")
        return "\n".join(lines)

    @staticmethod
    def _launch_review_session(
        parent_session: Any, call: Any, brief: str
    ) -> Any:
        """Spawn an ``approval_decider`` session to review *call*.

        Returns the child :class:`Session`.  The child session's settings
        declare ``review_task_call_id`` so the decider's ``approval_verdict``
        tool can validate the id it echoes back (never trust a hallucinated id).
        """
        from datetime import datetime
        from time import time_ns

        from server.models.agents.agent import AgentModel
        from server.models.enums.message_enums import MessageContentType, MessagePartType
        from server.models.enums.session_enums import SessionType
        from server.models.settings import SettingsModel
        from server.models.sessions.session_version import SessionVersionModel
        from runtime.session.session import Session

        decider = AgentModel.objects.filter(name="approval_decider").first()
        if decider is None:
            raise RuntimeError("approval_decider agent not loaded")

        decider_av = decider.get_runtime().get_version_model()
        child_sv = decider_av.get_or_create_session(
            name=f"approval-review:{call.pk}:{time_ns()}",
            display_name=f"Approval review of {call.task_definition.name} call #{call.pk}",
            description=brief[:100],
            workspace=parent_session.workspace,
            parent_session_version=call.session_version,
            session_type=SessionType.SUBTASK_FORK,
        )

        # Declare the review target on the child session settings.
        settings = SettingsModel(extra_settings={"review_task_call_id": call.pk})
        settings.save()
        SessionVersionModel.objects.filter(pk=child_sv.pk).update(session_settings=settings)

        child_session = Session(
            session_model=child_sv.session, pinned_session_version=child_sv
        )
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        working_dir = (
            child_session.workspace.path if child_session.workspace else "unknown"
        )
        parts = [
            {
                "type": MessagePartType.MESSAGE,
                "content_type": MessageContentType.TEXT,
                "content": f"It is now {now}, your working dir is '{working_dir}'.\n",
            },
            {
                "type": MessagePartType.MESSAGE,
                "content_type": MessageContentType.TEXT,
                "content": (
                    "You are the Approval Decider reviewing a pending command. "
                    "Analyse the brief, then call approval_verdict once with your "
                    "decision. The verdict ends this review session — no final_result "
                    "needed.\n\n" + brief
                ),
            },
        ]
        child_session.add_user_message(parts=parts)
        return child_session

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

    @staticmethod
    def deny_taskcall(task_call_id: int, feedback: str = "") -> bool:
        """Deny a halted approval call, feeding the denial back to the LLM.

        Cancels the original call.  When the call is wired into a conversation
        (a ``MessagePart`` references it via ``tool_call`` — i.e. it was
        dispatched by ``ingest_assistant_message``), a ``catch_approval_denied``
        report call is dispatched in its place and the message part + waiting
        result references are re-pointed to it, so the tool-response slot the
        LLM sees on the next turn carries the denial reason and any user
        feedback instead of the chain dying silently.

        Returns:
            ``True`` if the call was cancelled (regardless of whether the
            report dispatch succeeded), ``False`` if it could not be denied.
        """
        from server.models.tasks.agent_task_call import AgentTaskCall
        from server.models.enums.task_enums import TaskCallStatusDetail

        call = AgentTaskCall.objects.filter(pk=task_call_id).first()
        if call is None:
            return False

        cancelled = TaskCallStateMachine.cancel(
            call.pk, TaskCallStatusDetail.HALTED_APPROVAL
        )
        if not cancelled:
            return False

        try:
            CallScheduler._report_approval_denial(call, feedback)
        except Exception as exc:  # pragma: no cover - defensive
            print(f"deny_taskcall: failed to report denial back to LLM: {exc}")
        return True

    @staticmethod
    def _report_approval_denial(call: AgentTaskCall, feedback: str) -> None:
        """Dispatch a ``catch_approval_denied`` report for a denied call.

        Re-points the conversation so the report call's result becomes the tool
        response for the denied call.  No-op when the call is not linked to a
        message part or the report tool is not registered for the session.
        """
        from server.models.message import MessagePart
        from server.models.tasks.agent_task_run import AgentTaskRun
        from server.models.enums.task_enums import TaskRunStatus

        part = MessagePart.objects.filter(tool_call_id=call.pk).first()
        if part is None:
            return  # not part of a conversation — nothing to re-feed

        rt = call.session_version.get_runtime()
        bound = rt.get_tool("catch_approval_denied") or rt.get_task("catch_approval_denied")
        if bound is None:
            return  # report tool not registered — fall back to plain cancel

        tool_name = call.task_definition.name if call.task_definition else "?"
        report_call = bound.delay(
            tool_name=tool_name,
            reason=call.guardrail_reason or "",
            feedback=feedback or "",
        )

        MessagePart.objects.filter(pk=part.pk).update(tool_call=report_call)

        for waiter in AgentTaskRun.objects.filter(
            taskrun_result_references__pk=call.pk,
            status=TaskRunStatus.WAITING_RESULTTASKS,
        ):
            waiter.taskrun_result_references.remove(call)
            waiter.taskrun_result_references.add(report_call)

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
                    # RATE_LIMITED runs are terminal: they never resume (the
                    # run FSM has no transition out of RATE_LIMITED), and the
                    # call is re-dispatched as a brand-new run when capacity
                    # returns.  Counting the abandoned run here would let it
                    # permanently hold the parallel slot and deadlock the call
                    # in WAITING_QUEUE forever.
                    status__in=[_TRS.SUCCESS, _TRS.FAILURE, _TRS.RATE_LIMITED]
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
    def release_waiting_ratelimit_calls(
        session_model: Any, *, repoint: bool = True
    ) -> int:
        """Release this session's ``WAITING_RATELIMIT`` calls after a model or
        provider switch initiated from the UI (rate-limit card).

        When ``repoint`` is True each parked call is first re-pointed — together
        with its entire chain subtree — to the session's *latest* session
        version, so the re-dispatched run *and* every subsequent step of the
        chain (e.g. ``parse_llm_response`` → ``decide_next_step`` and the next
        ``process_turn`` it dispatches) use the newly selected model/key
        instead of the pinned version captured when the call was created.
        Capacity is re-checked with ``RateLimitChecker`` against the session's
        current aimodel in FIFO order; releases stop as soon as a call hits the
        limit again (mirrors ``_release_rate_limited_calls`` in
        ``server.tasks.tick_scheduler``).

        Returns the number of calls released.
        """
        from server.models.enums.task_enums import TaskCallStatusDetail
        from server.models.tasks.agent_task_call import AgentTaskCall
        from runtime.power import battery_gate_blocked
        from runtime.rate_limiter import RateLimitChecker, RateLimitError
        from runtime.session.session import Session
        from runtime.tasks.call_fsm import TaskCallStateMachine

        session = Session(session_model=session_model)
        aimodel = session.aimodel
        if aimodel is None:
            return 0
        latest = session_model.latest_session_version

        calls = list(
            AgentTaskCall.objects.filter(
                session=session_model,
                status_detail=TaskCallStatusDetail.WAITING_RATELIMIT,
            ).order_by("priority", "created_at")
        )
        if not calls:
            return 0

        released = 0
        for call in calls:
            try:
                if battery_gate_blocked(aimodel)[0]:
                    break
                try:
                    RateLimitChecker.check(aimodel, session=session)
                except RateLimitError:
                    break
                if repoint and latest is not None and call.session_version_id != latest.pk:
                    CallScheduler._repoint_chain_to_latest(call, latest)
                if TaskCallStateMachine.release_rate_limit(call.pk):
                    CallScheduler.start_new_taskrun(call.pk)
                    released += 1
            except Exception as exc:  # pragma: no cover - defensive
                print(f"[scheduler] error releasing rate-limited call {call.pk}: {exc}")
        return released

    @staticmethod
    def _repoint_chain_to_latest(call: Any, latest: Any) -> None:
        """Re-point *call* and its whole chain subtree to *latest*.

        The parked call and its siblings (``parse_llm_response``,
        ``ingest_assistant_message``, ``decide_next_step``) were captured
        against the chain's original session version when the turn started.
        Re-pointing only the parked call fixes the immediate retry, but the
        ``decide_next_step`` tail would re-dispatch the next ``process_turn``
        against the *old* version — falling back to the pre-switch key (the
        reported bug).  Moving the entire subtree keeps the whole turn on the
        switched key.

        ``TaskInstance``/``AgentTaskCall`` ``save()`` forbid editing, so the
        re-point is done with ``QuerySet.update()`` (SQL-level).
        """
        from server.models.enums.task_enums import TaskCallStatus
        from server.models.tasks.agent_task_call import AgentTaskCall
        from server.models.tasks.task_instance import TaskInstance

        if latest is None:
            return

        if call.task_instance_id is None:
            AgentTaskCall.objects.filter(pk=call.pk).update(session_version=latest)
            return

        # Walk up to the chain root (parent chain TaskInstance).
        node = call.task_instance
        seen: set[int] = set()
        while node is not None and node.pk not in seen:
            seen.add(node.pk)
            parents = list(node.parent_instances.all())
            if not parents:
                break
            node = parents[0] if parents else node
        root = node

        # Collect the whole subtree (root + all descendant instances).
        subtree: set[int] = set()
        stack = [root]
        while stack:
            node = stack.pop()
            if node.pk in subtree:
                continue
            subtree.add(node.pk)
            stack.extend(node.child_instances.all())

        if not subtree:
            AgentTaskCall.objects.filter(pk=call.pk).update(session_version=latest)
            return

        TaskInstance.objects.filter(pk__in=subtree).update(session_version=latest)
        AgentTaskCall.objects.filter(
            task_instance_id__in=subtree,
            status__in=[
                TaskCallStatus.NEW,
                TaskCallStatus.WAITING,
                TaskCallStatus.HALTED,
            ],
        ).update(session_version=latest)

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
