"""
Celery beat periodic task for at-runtime error recovery and startup cleanups.

Split out of ``tick_scheduler`` — this module only handles *recovery*: things
that pick up errors / leftovers (lost Celery messages, orphaned runs, duplicate
or stale queries) and one-time cleanups.  These run on a 60-second cadence via
``tasks.tick_scheduler_recovery`` instead of every 10s tick, because in a
healthy system they mostly no-op.

Two tasks are defined here:

  ``tasks.tick_scheduler_recovery`` — runs every 60s (config/settings.py
  ``CELERY_BEAT_SCHEDULE``).  Sweeps all six recovery passes.

  ``tasks.startup_cleanup`` — runs once at startup, dispatched by
  ``python3 manage.py server run``.  Cleans leftover state from a previous run
  (e.g. stale runtime folders).
"""

from __future__ import annotations

import datetime
from typing import Any

from celery import shared_task
from django.utils import timezone

# A call parked in WAITING_QUEUE is *about to progress*: the 60s release pass
# (``_release_queued_calls``) and the ``_on_taskcall_ended`` drain pick queued
# calls up within seconds, so a fresh WAITING_QUEUE call is a transient
# transition gap (e.g. the successor ``call_llm`` just after its parent
# sub-call ended — incident 294368), never a deadlock.  Only once a call has
# sat queued far longer than the release cadence is it treated as permanently
# blocked (e.g. a parallel-limit slot held by a non-ending run) and allowed to
# count against tree liveness.  This is the conservative runtime trade-off:
# genuine E5-style deadlocks are broken, healthy-but-slow chains are not.
STALE_WAITING_QUEUE_TIMEOUT = datetime.timedelta(minutes=15)


@shared_task(name="tasks.tick_scheduler_recovery")
def tick_scheduler_recovery() -> None:
    """One-minute recovery pass — each routine is independent."""
    _release_queued_calls()
    _timeout_active_runs()
    _resolve_stuck_waiting_runs()
    _recover_stuck_calls()
    _cancel_duplicate_queries()
    _recover_stale_queries()


def startup_cleanup() -> None:
    """One-time startup cleanup — called when the server starts.

    Runs the recovery passes immediately so orphaned state left over from a
    previous run (lost Celery messages, ACTIVE_QUEUED calls, QUEUED runs) is
    recovered right away instead of waiting up to 60s for the beat pass.
    """
    _cleanup_stale_runtime_folders()
    _release_queued_calls()
    _recover_stuck_calls()
    _recover_stale_queries()


def _release_queued_calls() -> None:
    """Release WAITING_QUEUE calls.  Acts as a fallback for the drain-in-
    ``_on_taskcall_ended`` path — catches queue entries left behind after a
    crash or hang.  The per-TaskInstance parallel limit in
    ``start_new_taskrun`` prevents concurrent ingest calls from the same
    task instance.
    """
    from server.models.tasks.agent_task_call import AgentTaskCall
    from server.models.enums.task_enums import TaskCallStatusDetail
    from runtime.tasks.call_scheduler import CallScheduler

    for call in AgentTaskCall.objects.filter(
        status_detail=TaskCallStatusDetail.WAITING_QUEUE,
    ).order_by("pk"):
        try:
            # A call whose serialized arguments reference a deleted AgentTaskCall
            # can never create a run (AgentTaskRun.create raises DoesNotExist).
            # Cancel it instead of erroring on every recovery pass.
            if _has_dangling_call_refs(call.carguments_json):
                if _force_end_call(call):
                    print(f"[recovery] cancelled WAITING_QUEUE call {call.pk} — dangling arg reference")
                continue
            CallScheduler.start_new_taskrun(call.pk)
        except Exception as e:
            print(f"[recovery] error releasing queued call {call.pk}: {e}")


def _timeout_active_runs() -> None:
    """Fail ACTIVE runs that have exceeded their time_limit (seconds).  0 = no limit."""
    from server.models.tasks.agent_task_run import AgentTaskRun
    from server.models.enums.task_enums import TaskRunStatus
    from runtime.tasks.run_fsm import TaskRunStateMachine
    from runtime.tasks.call_scheduler import CallScheduler

    timed_out = []
    for run in AgentTaskRun.objects.filter(
        status=TaskRunStatus.ACTIVE, time_limit__gt=0
    ).iterator():
        if run.created_at and (timezone.now() - run.created_at).total_seconds() > run.time_limit:
            timed_out.append(run)

    for run in timed_out:
        try:
            if TaskRunStateMachine.fail(run.pk):
                CallScheduler.on_taskrun_ended(run.pk, TaskRunStatus.FAILURE)
                print(
                    f"[recovery] timed out run {run.pk} (limit {run.time_limit}s)"
                )
        except Exception as e:
            print(f"[recovery] error timing out run {run.pk}: {e}")


def _resolve_stuck_waiting_runs() -> None:
    """Resolve WAITING_RESULTTASKS runs whose referenced calls have all ended
    or whose references are stuck in non-progressing states.

    Two cases are handled:

    1. **All refs ended** — normal path (all sub-calls completed successfully
       or terminally; the notification may have been lost).

    2. **No ref is actively executing** — the run's pending result references
       are all stuck in states that will never progress (e.g. WAITING_QUEUE
       permanently blocked by the per-TI limit, forming a circular deadlock).
       We fail the run to break the cycle.

    This is deliberately CONSERVATIVE: a call in WAITING_QUEUE or
    WAITING_DEPENDENCY-with-ended-args is *about to progress* (the release pass
    / ``_on_taskcall_ended`` drain picks it up within seconds), so a fresh
    queued call is a transient transition gap, not a deadlock.  Only a call
    queued far beyond the release cadence (see ``STALE_WAITING_QUEUE_TIMEOUT``)
    counts as permanently blocked.  The whole tree must be quiet for the 30s
    grace period before a run is force-failed — a healthy-but-slow chain is
    never touched here.
    """
    from server.models.tasks.agent_task_run import AgentTaskRun
    from server.models.enums.task_enums import TaskRunStatus, TaskCallStatus, TaskCallStatusDetail
    from server.models.tasks.agent_task_call import AgentTaskCall
    from runtime.tasks.run_scheduler import RunScheduler
    from django.db.models import Q
    import datetime

    stuck = AgentTaskRun.objects.filter(
        status=TaskRunStatus.WAITING_RESULTTASKS,
    ).order_by("updated_at")  # Oldest first

    # Force-failing a run cascades through the dependency graph and releases
    # WAITING_QUEUE calls — pace a small batch per pass so the per-TI parallel
    # limit isn't overwhelmed.
    resolved_this_pass = 0
    max_per_pass = 5

    for run in stuck:
        try:
            pending_calls = AgentTaskCall.objects.filter(
                ~Q(status=TaskCallStatus.ENDED),
                rev_taskrun_result_references=run.pk,
            )
            pending = pending_calls.values_list('status_detail', flat=True)

            # Case 1: all refs ended — resolve immediately (no cascade risk)
            if not pending:
                RunScheduler.all_taskrun_result_references_ended(run.pk)
                print(f"[recovery] recovered stuck WAITING_RESULTTASKS run {run.pk} — all refs ended")
                continue

            # Case 2: none of the pending refs are actively executing.
            #
            # HALTED_APPROVAL is NOT a stuck state: the call is waiting on a
            # human decision and will progress either way once the user acts
            # (approve → WAITING_QUEUE, deny → ENDED_CANCELLED).  A run whose
            # pending refs are halted for approval is a healthy-but-paused
            # chain, never a deadlock.
            active_states = {
                TaskCallStatusDetail.ACTIVE_QUEUED.value,
                TaskCallStatusDetail.ACTIVE_RUNNING.value,
                TaskCallStatusDetail.HALTED_APPROVAL.value,
            }
            pending_details = set(pending)
            if pending_details.isdisjoint(active_states):

                # Deadlock detection: if the entire root task tree has no
                # actively progressing calls, the deadlock spans multiple
                # levels (e.g. A→B→C→A).  No single call's run can progress.
                #
                # This check is conservative: a tree is only declared dead
                # after it has been QUIET (nothing progressing, no fresh
                # WAITING_QUEUE call, no ready dependency) for the 30s grace
                # period below.  A transient transition gap (incident 294368)
                # is protected because a fresh WAITING_QUEUE call counts as
                # progressing.
                #
                # A call counts as *progressing* only if it is ACTIVE
                # (ACTIVE_QUEUED/ACTIVE_RUNNING) AND not itself blocked in
                # WAITING_RESULTTASKS.  An ACTIVE_RUNNING call whose run is
                # WAITING_RESULTTASKS is waiting on its own result refs (e.g.
                # the old process_turn in the E5 circular deadlock) — it is
                # NOT making progress and must not protect the tree.
                #
                # HALTED_APPROVAL also counts as progressing: the chain is
                # paused on a human decision, not deadlocked.
                call = run.agent_task_call

                # The run may be blocked on result references that live in a
                # DIFFERENT session root task tree than its own call — e.g.
                # ``delegate_task`` / ``start_subsession`` spawn a fresh child
                # session whose chain is its own root task (the child's
                # ``ingest_user_message`` is the child tree root).  If we only
                # inspect the run's own tree we see nothing active and wrongly
                # declare a deadlock while the child chain is actually making
                # progress.
                #
                # Walk the waiting graph TRANSITIVELY.  A call parked in
                # WAITING_SUBTASKS_OR_HOOKS has a WAITING_RESULTTASKS run that
                # is itself waiting on further result references — possibly in
                # yet another session (delegate -> subagent -> sub-subagent).
                # A single-level union (own tree + direct pending refs) only
                # protects the run that DIRECTLY references the cross-session
                # call; every ancestor in the calling session still sees only
                # its own tree (all parked calls are invisible to the
                # active-states check) and is wrongly force-failed while the
                # subagent is legitimately working.  Collect the union of every
                # session-root-task tree reachable by following the waiting
                # chain, so a genuinely-executing leaf anywhere in the graph
                # (e.g. the subagent's active ``call_llm``) protects the whole
                # chain.
                root_task_ids: set[int] = set()
                if call and call.session_root_task_id:
                    root_task_ids.add(call.session_root_task_id)
                seen_runs: set[int] = {run.pk}
                frontier: list[AgentTaskRun] = [run]
                while frontier:
                    current = frontier.pop()
                    refs = list(pending_calls) if current.pk == run.pk else list(
                        AgentTaskCall.objects.filter(
                            ~Q(status=TaskCallStatus.ENDED),
                            rev_taskrun_result_references=current.pk,
                        )
                    )
                    for ref in refs:
                        if ref.session_root_task_id:
                            root_task_ids.add(ref.session_root_task_id)
                        waiting_run = AgentTaskRun.objects.filter(
                            agent_task_call=ref,
                            status=TaskRunStatus.WAITING_RESULTTASKS,
                        ).order_by("-pk").first()
                        if waiting_run and waiting_run.pk not in seen_runs:
                            seen_runs.add(waiting_run.pk)
                            frontier.append(waiting_run)

                if root_task_ids:
                    # A call counts as *progressing* when it is on a
                    # deterministic forward-progress path:
                    #
                    #  (a) ACTIVE (ACTIVE_QUEUED/ACTIVE_RUNNING) or
                    #      HALTED_APPROVAL, AND its own run is not
                    #      WAITING_RESULTTASKS.  An ACTIVE_RUNNING call whose
                    #      run is WAITING_RESULTTASKS is the old process_turn
                    #      in the E5 circular deadlock — blocked, not working.
                    #
                    #  (b) WAITING_DEPENDENCY with at least one argument
                    #      reference whose ALL references have ended.  A
                    #      dependency ending fires ``on_arg_reference_task_ended``
                    #      via Celery, so the call is about to move to
                    #      WAITING_QUEUE / HALTED_APPROVAL on its own — e.g. a
                    #      CHAIN step waiting on the just-finished previous
                    #      step.  A call with *no* argument references is NOT
                    #      progressing: nothing will ever notify it, only the
                    #      recovery pass can unstick it.
                    non_ended_statuses = [
                        TaskCallStatus.NEW,
                        TaskCallStatus.WAITING,
                        TaskCallStatus.ACTIVE,
                        TaskCallStatus.HALTED,
                    ]
                    active_or_running = AgentTaskCall.objects.filter(
                        session_root_task_id__in=root_task_ids,
                    ).exclude(
                        status=TaskCallStatus.ENDED,
                    ).filter(
                        status_detail__in=[
                            TaskCallStatusDetail.ACTIVE_QUEUED,
                            TaskCallStatusDetail.ACTIVE_RUNNING,
                            TaskCallStatusDetail.HALTED_APPROVAL,
                        ],
                    ).exclude(
                        related_agent_task_runs__status=TaskRunStatus.WAITING_RESULTTASKS,
                    ).exists()
                    dependency_ready = AgentTaskCall.objects.filter(
                        session_root_task_id__in=root_task_ids,
                        status_detail=TaskCallStatusDetail.WAITING_DEPENDENCY,
                    ).filter(
                        taskcall_arg_references__isnull=False,
                    ).exclude(
                        taskcall_arg_references__status__in=non_ended_statuses,
                    ).exists()
                    queue_releasing = AgentTaskCall.objects.filter(
                        session_root_task_id__in=root_task_ids,
                        status_detail=TaskCallStatusDetail.WAITING_QUEUE,
                        updated_at__gte=timezone.now() - STALE_WAITING_QUEUE_TIMEOUT,
                    ).exists()
                    has_progressing = active_or_running or dependency_ready or queue_releasing
                    if has_progressing:
                        # The root tree still has a call doing real work, a
                        # dependency that is about to release (e.g. a slow
                        # ``call_llm``, or a CHAIN step whose previous step
                        # just ended and is queued for release), or a FRESH
                        # WAITING_QUEUE call the release pass / drain will pick
                        # up within seconds (e.g. the successor ``call_llm`` in
                        # the brief gap after its parent sub-call ends —
                        # incident 294368).  The run's pending refs are waiting
                        # on that chain and will resolve when it ends — do NOT
                        # fail a healthy-but-slow pipeline here.
                        continue

                grace = datetime.timedelta(seconds=30)
                if not (run.updated_at and timezone.now() - run.updated_at > grace):
                    continue  # Not yet eligible for grace-based recovery

                from runtime.tasks.run_fsm import TaskRunStateMachine
                from runtime.tasks.call_scheduler import CallScheduler
                if TaskRunStateMachine.fail(run.pk):
                    CallScheduler.on_taskrun_ended(run.pk, TaskRunStatus.FAILURE)
                    print(f"[recovery] failed stuck WAITING_RESULTTASKS run {run.pk} — no progressing refs ({pending_details})")
                resolved_this_pass += 1
                if resolved_this_pass >= max_per_pass:
                    return  # Pace the cascade
        except Exception as e:
            print(f"[recovery] error recovering WAITING_RESULTTASKS run {run.pk}: {e}")


def _recover_stuck_calls() -> None:
    """Recover calls/runs whose Celery dispatch message was lost on restart."""
    from datetime import timedelta
    from django.db.models import F
    from server.models.tasks.agent_task_call import AgentTaskCall
    from server.models.tasks.agent_task_run import AgentTaskRun
    from server.models.enums.task_enums import TaskCallStatus, TaskCallStatusDetail, TaskRunStatus
    from runtime.tasks.call_fsm import TaskCallStateMachine
    from runtime.tasks.call_scheduler import CallScheduler
    from runtime.tasks.run_scheduler import RunScheduler
    from server.tasks.task_dispatcher import celery_delay

    # 1. ACTIVE_QUEUED calls — recover or cancel:
    #    a. Root task has ended → the call can never start (``start_running``
    #       guard rejects ACTIVE_QUEUED → ACTIVE_RUNNING once the root turn is
    #       done).  Re-queuing would loop forever, so fail its runs and cancel.
    #    b. No run → re-queue and re-dispatch.  pick_up() → AgentTaskRun.create()
    #       is synchronous, so any call stuck in ACTIVE_QUEUED without a run is
    #       immediately orphaned.
    for call in AgentTaskCall.objects.filter(
        status_detail=TaskCallStatusDetail.ACTIVE_QUEUED,
    ).select_related("session_root_task"):
        try:
            root = call.session_root_task
            if root and root.status == TaskCallStatus.ENDED:
                AgentTaskRun.objects.filter(
                    agent_task_call=call,
                ).exclude(
                    status__in=[TaskRunStatus.SUCCESS, TaskRunStatus.FAILURE],
                ).update(
                    status=TaskRunStatus.FAILURE,
                    ended_at=timezone.now(),
                )
                if _force_end_call(call):
                    print(f"[recovery] cancelled ACTIVE_QUEUED call {call.pk} — root task {root.pk} ended")
                continue
            if not AgentTaskRun.objects.filter(agent_task_call=call).exists():
                if TaskCallStateMachine.re_queue(call.pk):
                    CallScheduler.start_new_taskrun(call.pk)
                    print(f"[recovery] recovered ACTIVE_QUEUED call {call.pk} — re-queued")
        except Exception as e:
            print(f"[recovery] error recovering ACTIVE_QUEUED call {call.pk}: {e}")

    # 2. QUEUED runs whose Celery message was lost → re-dispatch.
    timeout = timedelta(minutes=15)
    cutoff = timezone.now() - timeout
    for run in AgentTaskRun.objects.filter(
        status=TaskRunStatus.QUEUED,
        updated_at__lt=cutoff,
    ):
        try:
            print(f"[recovery] re-dispatching stuck QUEUED run {run.pk}")
            celery_delay(RunScheduler._apply_async, run.pk)
        except Exception as e:
            print(f"[recovery] error re-dispatching QUEUED run {run.pk}: {e}")

    # 3. ACTIVE_RUNNING calls with no active run → retry or fail.
    for call in AgentTaskCall.objects.filter(
        status_detail=TaskCallStatusDetail.ACTIVE_RUNNING,
        updated_at__lt=cutoff,
    ):
        try:
            if not AgentTaskRun.objects.filter(
                agent_task_call=call,
                status=TaskRunStatus.ACTIVE,
            ).exists():
                # Fail ALL non-ended runs (QUEUED, WAITING_RESULTTASKS, RATE_LIMITED)
                AgentTaskRun.objects.filter(
                    agent_task_call=call,
                ).exclude(
                    status__in=[TaskRunStatus.SUCCESS, TaskRunStatus.FAILURE],
                ).update(
                    status=TaskRunStatus.FAILURE,
                    ended_at=timezone.now(),
                )
                if call.max_retries > 0 and call.retry_count < call.max_retries:
                    if TaskCallStateMachine.schedule_retry(call.pk, call.retry_delay, call.max_retries):
                        print(f"[recovery] retrying orphaned ACTIVE_RUNNING call {call.pk}")
                        continue
                if TaskCallStateMachine.fail(call.pk):
                    print(f"[recovery] failed orphaned ACTIVE_RUNNING call {call.pk}")
        except Exception as e:
            print(f"[recovery] error recovering ACTIVE_RUNNING call {call.pk}: {e}")

    # 4. WAITING_SUBTASKS_OR_HOOKS calls whose result run ended but the call-level
    #    transition was missed (e.g. notify chain crashed or race).
    for call in AgentTaskCall.objects.filter(
        status_detail=TaskCallStatusDetail.WAITING_SUBTASKS_OR_HOOKS,
    ).select_related("taskcall_result_run"):
        try:
            result_run = call.taskcall_result_run
            if not result_run or result_run.status not in (
                TaskRunStatus.SUCCESS, TaskRunStatus.FAILURE,
            ):
                continue
            if result_run.status == TaskRunStatus.FAILURE:
                if TaskCallStateMachine.fail(call.pk):
                    print(f"[recovery] recovered WAITING_SUBTASKS_OR_HOOKS call {call.pk} — result run failed")
            else:
                pending_hooks = call.taskcall_after_run_hooks.exclude(
                    status=TaskCallStatus.ENDED,
                )
                if not pending_hooks.exists():
                    if TaskCallStateMachine.succeed(call.pk, result_run.pk):
                        print(f"[recovery] recovered WAITING_SUBTASKS_OR_HOOKS call {call.pk} — result run succeeded, hooks done")
        except Exception as e:
            print(f"[recovery] error recovering WAITING_SUBTASKS_OR_HOOKS call {call.pk}: {e}")

    # 5. WAITING_DEPENDENCY calls whose all arg references have ended
    #    but the on_arg_reference_task_ended notification was lost
    #    (e.g. Celery worker crash between _on_taskcall_ended and dispatch).
    for call in AgentTaskCall.objects.filter(
        status_detail=TaskCallStatusDetail.WAITING_DEPENDENCY,
    ):
        try:
            arg_refs = list(call.taskcall_arg_references.all())
            non_ended = [r for r in arg_refs if r.status != TaskCallStatus.ENDED]
            if non_ended:
                continue
            # All deps ended (or none) — check if any failed
            failed_dep = next(
                (r for r in arg_refs if r.status_detail in (
                    TaskCallStatusDetail.ENDED_FAILURE_LOGIC,
                    TaskCallStatusDetail.ENDED_FAILURE_EXCEPTION,
                    TaskCallStatusDetail.ENDED_CANCELLED,
                    TaskCallStatusDetail.ENDED_STOPPED,
                )), None,
            )
            if failed_dep:
                if TaskCallStateMachine.cancel(call.pk, TaskCallStatusDetail.WAITING_DEPENDENCY):
                    print(f"[recovery] recovered WAITING_DEPENDENCY call {call.pk} — dep {failed_dep.pk} failed, cancelled")
            else:
                CallScheduler.on_all_arg_reference_tasks_ended(call.pk)
                print(f"[recovery] recovered WAITING_DEPENDENCY call {call.pk} — all deps succeeded, resumed")
        except Exception as e:
            print(f"[recovery] error recovering WAITING_DEPENDENCY call {call.pk}: {e}")

    # 6. WAITING_QUEUE calls — release per session, preferring the newest
    #    root task.  Without this, an old zombie turn's calls can sit in
    #    WAITING_QUEUE and block fresh user requests from the same session
    #    (since ``start_new_taskrun`` enforces the per-TI parallel limit).
    for session_id in AgentTaskCall.objects.filter(
        status_detail=TaskCallStatusDetail.WAITING_QUEUE,
    ).values_list('session_id', flat=True).distinct():
        try:
            # Find the newest root task in this session that still has
            # WAITING_QUEUE children.  (Root calls have session_root_task
            # pointing to themselves.)
            newest_root = AgentTaskCall.objects.filter(
                session_id=session_id,
                session_root_task=F("pk"),
                session_child_task_calls__status_detail=TaskCallStatusDetail.WAITING_QUEUE,
            ).order_by("-created_at").first()
            if newest_root:
                child = newest_root.session_child_task_calls.filter(
                    status_detail=TaskCallStatusDetail.WAITING_QUEUE,
                ).order_by("created_at").first()
                if child:
                    if _has_dangling_call_refs(child.carguments_json):
                        if _force_end_call(child):
                            print(f"[recovery] cancelled WAITING_QUEUE child {child.pk} — dangling arg reference")
                        continue
                    CallScheduler.start_new_taskrun(child.pk)
                    continue
            # Fallback: release oldest per session
            CallScheduler._release_next_queued_call(session_id)
        except Exception as e:
            print(f"[recovery] error releasing WAITING_QUEUE for session {session_id}: {e}")


def _references_query(json_data: Any, query_pk: int) -> bool:
    """Check if *json_data* contains a ``{"_type": "Query", "pk": query_pk}`` at any nesting level."""
    if isinstance(json_data, dict):
        if json_data.get("_type") == "Query" and json_data.get("pk") == query_pk:
            return True
        return any(_references_query(v, query_pk) for v in json_data.values())
    if isinstance(json_data, (list, tuple)):
        return any(_references_query(v, query_pk) for v in json_data)
    return False


def _has_dangling_call_refs(json_data: Any) -> bool:
    """Check whether *json_data* contains a ``{"_type": "AgentTaskCall", "pk": N}``
    reference to a call that no longer exists.

    Such a call can never create a run — ``AgentTaskRun.create`` raises
    ``DoesNotExist`` when resolving the reference — so recovery cancels it.
    """
    from server.models.tasks.agent_task_call import AgentTaskCall

    if isinstance(json_data, dict):
        if json_data.get("_type") == "AgentTaskCall":
            return not AgentTaskCall.objects.filter(pk=json_data.get("pk")).exists()
        return any(_has_dangling_call_refs(v) for v in json_data.values())
    if isinstance(json_data, (list, tuple)):
        return any(_has_dangling_call_refs(v) for v in json_data)
    return False


def _force_end_call(call: "AgentTaskCall") -> bool:
    """Terminate a call through the FSM where possible; fall back to direct update.

    After termination, propagates the cancellation to dependents via
    ``CallScheduler._on_taskcall_ended`` so that parent runs, dependent
    calls, and hook-parent calls are notified (cascade cancellation).
    """
    from server.models.tasks.agent_task_call import AgentTaskCall
    from server.models.tasks.agent_task_run import AgentTaskRun
    from server.models.enums.task_enums import TaskCallStatus, TaskCallStatusDetail
    from runtime.tasks.call_fsm import TaskCallStateMachine, _publish_call_event
    from runtime.tasks.call_scheduler import CallScheduler

    sd = TaskCallStatusDetail(call.status_detail)
    pk = call.pk

    # Use FSM for all states that now have a valid path to ENDED_CANCELLED
    if sd in (
        TaskCallStatusDetail.WAITING_DEPENDENCY,
        TaskCallStatusDetail.HALTED_APPROVAL,
        TaskCallStatusDetail.WAITING_RATELIMIT,
        TaskCallStatusDetail.WAITING_SUBTASKS_OR_HOOKS,
        TaskCallStatusDetail.WAITING_QUEUE,
        TaskCallStatusDetail.ACTIVE_QUEUED,
        TaskCallStatusDetail.NEW,
        TaskCallStatusDetail.WAITING_RETRY,
    ):
        if not TaskCallStateMachine.transition(
            pk, sd, TaskCallStatusDetail.ENDED_CANCELLED,
            extra={"ended_at": timezone.now()},
        ):
            return False

    elif sd == TaskCallStatusDetail.ACTIVE_RUNNING:
        if not TaskCallStateMachine.fail(pk):
            return False

    else:
        # Fallback for any states not covered by the FSM
        updated = AgentTaskCall.objects.filter(pk=pk).update(
            status=TaskCallStatus.ENDED,
            status_detail=TaskCallStatusDetail.ENDED_CANCELLED,
            ended_at=timezone.now(),
        ) > 0
        if not updated:
            return False
        _publish_call_event(pk)

    # At this point the call is ENDED.  Propagate to dependents so the
    # cancellation cascades through the dependency graph.  Use the last
    # taskrun PK (or 0 if no run exists — _on_taskcall_ended now handles
    # missing runs gracefully).
    last_run = AgentTaskRun.objects.filter(
        agent_task_call=call
    ).order_by("-pk").first()
    last_taskrun_id = last_run.pk if last_run else 0
    CallScheduler._on_taskcall_ended(pk, last_taskrun_id, TaskCallStatusDetail.ENDED_CANCELLED)
    return True


def _cancel_duplicate_queries() -> int:
    """Cancel duplicate WAITING/ACTIVE queries in the same session.

    Keeps the newest query per session, cancels the rest by setting them to
    SUCCESS (terminal — ``call_llm`` cannot transition out of SUCCESS).
    Also cancels the corresponding ``call_llm`` AgentTaskCalls so that
    running or queued chain steps don't resurrect the cancelled query
    (e.g. via the ``FAILURE → ACTIVE`` path in ``call_llm.py:214``).

    Returns the number of duplicate queries cancelled.
    """
    from django.db.models import Count
    from server.models.queries.query import Query, QueryStatus
    from server.models.tasks.agent_task_call import AgentTaskCall
    from server.models.enums.task_enums import TaskCallStatus

    total = 0

    # --- Per-session-version dedup ---
    sv_dupes = (
        Query.objects.filter(
            status__in=[QueryStatus.WAITING, QueryStatus.ACTIVE],
        )
        .values("session_version_id")
        .annotate(cnt=Count("id"))
        .filter(cnt__gt=1)
    )
    for d in sv_dupes:
        sv_id = d["session_version_id"]
        queries = list(
            Query.objects.filter(
                session_version_id=sv_id,
                status__in=[QueryStatus.WAITING, QueryStatus.ACTIVE],
            ).order_by("-created_at")
        )
        keep = queries[0]
        to_cancel = queries[1:]
        total += len(to_cancel)
        print(f"[recovery] SessionVersion {sv_id}: {len(to_cancel)} duplicate queries (keeping {keep.pk})")
        for q in to_cancel:
            _cancel_query_and_call_llm(sv_id, q.pk)

    # --- Per-session dedup (across different session versions) ---
    # Prevents multiple concurrent LLM calls for the same session.
    session_dupes = (
        Query.objects.filter(
            status__in=[QueryStatus.WAITING, QueryStatus.ACTIVE],
        )
        .values("session_version__session_id")
        .annotate(cnt=Count("id"))
        .filter(cnt__gt=1)
    )
    for d in session_dupes:
        session_id = d["session_version__session_id"]
        queries = list(
            Query.objects.filter(
                session_version__session_id=session_id,
                status__in=[QueryStatus.WAITING, QueryStatus.ACTIVE],
            ).order_by("-created_at")
        )
        keep = queries[0]
        to_cancel = queries[1:]
        total += len(to_cancel)
        print(f"[recovery] Session {session_id}: {len(to_cancel)} duplicate queries across SVs (keeping {keep.pk})")
        for q in to_cancel:
            _cancel_query_and_call_llm(q.session_version_id, q.pk)

    if total:
        print(f"[recovery] Cancelled {total} duplicate queries total")
    return total


def _cancel_query_and_call_llm(sv_id: int, query_pk: int) -> None:
    """Mark a query as SUCCESS and force-end its call_llm call chain."""
    from server.models.queries.query import Query, QueryStatus
    from server.models.tasks.agent_task_call import AgentTaskCall
    from server.models.enums.task_enums import TaskCallStatus
    from runtime.events import publish_model_event

    Query.objects.filter(pk=query_pk, status__in=[QueryStatus.WAITING, QueryStatus.ACTIVE]).update(
        status=QueryStatus.SUCCESS,
    )
    q = Query.objects.filter(pk=query_pk).first()
    if q:
        publish_model_event(q, "update")
    print(f"  [recovery] cancelled duplicate query {query_pk}")

    # Find and cancel non-ended call_llm calls for this query.
    candidates = AgentTaskCall.objects.filter(
        session_version_id=sv_id,
        task_definition__name="call_llm",
    ).exclude(status=TaskCallStatus.ENDED)
    for call in candidates:
        if _references_query(call.carguments_json, query_pk):
            if _force_end_call(call):
                print(f"  [recovery] cancelled call_llm {call.pk} for query {query_pk}")


def _recover_stale_queries() -> None:
    """
    Detect and resume/cancel queries stuck in ACTIVE or WAITING after a crash.

    - ACTIVE queries: fail orphaned runs/calls, reset the Query to WAITING,
      and re-dispatch ``call_llm`` so the LLM response is re-generated.
    - WAITING queries: if no live ``call_llm`` will pick them up, fail them
      to unblock ``build_llm_context`` (which refuses to create a new query
      while a WAITING or ACTIVE query exists).
    """
    from datetime import timedelta
    from server.models.queries.query import Query, QueryStatus
    from server.models.queries.response import Response, ResponseStatus
    from server.models.enums.task_enums import TaskRunStatus, TaskCallStatusDetail, TaskCallStatus
    from server.models.tasks.agent_task_run import AgentTaskRun
    from server.models.tasks.agent_task_call import AgentTaskCall
    from runtime.tasks.run_fsm import TaskRunStateMachine
    from runtime.tasks.call_fsm import TaskCallStateMachine
    from runtime.tasks.call_scheduler import CallScheduler
    from runtime.events import publish_model_event
    from server.models.tasks.task_definition import TaskDefinition
    from server.models.tasks.task_instance import TaskInstance

    timeout = timedelta(minutes=15)
    cutoff = timezone.now() - timeout

    # --- Handle stale WAITING queries with no live call_llm ---
    for query in Query.objects.filter(
        status=QueryStatus.WAITING,
        updated_at__lt=cutoff,
    ).select_related("session_version__session").iterator():
        try:
            # Check if any non-ended call_llm specifically references THIS query
            # (not just any call_llm in the session_version).
            has_live_call_llm = any(
                _references_query(call.carguments_json, query.pk)
                for call in AgentTaskCall.objects.filter(
                    session_version=query.session_version,
                    task_definition__name="call_llm",
                ).exclude(
                    status=TaskCallStatus.ENDED,
                ).iterator()
            )
            if has_live_call_llm:
                continue  # This query is still being worked on
            print(f"[recovery] cancelling stale WAITING query {query.pk} (WAITING since {query.updated_at})")
            Query.objects.filter(pk=query.pk, status=QueryStatus.WAITING).update(
                status=QueryStatus.SUCCESS,
            )
            publish_model_event(query, "update")
        except Exception as e:
            print(f"[recovery] error cancelling stale WAITING query {query.pk}: {e}")

    # --- Handle stale ACTIVE queries — resume via re-dispatch ---
    stale = Query.objects.filter(
        status=QueryStatus.ACTIVE,
        updated_at__lt=cutoff,
    ).select_related("session_version__session")

    for query in stale:
        try:
            print(f"[recovery] resuming stale query {query.pk} (ACTIVE since {query.updated_at})")

            # 1. Fail orphaned ACTIVE Responses
            Response.objects.filter(query=query, status=ResponseStatus.ACTIVE).update(
                status=ResponseStatus.FAILURE,
            )

            # 2. Find call_llm calls referencing THIS specific query (not all queries
            #    in the session version).  Uses _references_query for deep JSON matching
            #    so we don't kill healthy concurrent queries.
            query_pk = query.pk
            call_llm_calls = []
            for call in AgentTaskCall.objects.filter(
                status_detail__in=[
                    TaskCallStatusDetail.ACTIVE_QUEUED,
                    TaskCallStatusDetail.ACTIVE_RUNNING,
                ],
                session_version=query.session_version,
                task_definition__name="call_llm",
            ):
                if _references_query(call.carguments_json, query_pk):
                    call_llm_calls.append(call)

            # Capture guardrail state from original call before failing it
            orig_requires_approval = False
            orig_is_approved = None
            orig_guardrail_reason = None
            for call in call_llm_calls:
                if call.requires_approval:
                    orig_requires_approval = True
                    orig_is_approved = call.is_approved
                    orig_guardrail_reason = call.guardrail_reason

            # 3. Fail orphaned ACTIVE runs and calls only for this specific query
            for call in call_llm_calls:
                for run in AgentTaskRun.objects.filter(
                    agent_task_call=call, status=TaskRunStatus.ACTIVE,
                ):
                    if TaskRunStateMachine.fail(run.pk):
                        CallScheduler.on_taskrun_ended(run.pk, TaskRunStatus.FAILURE)
                TaskCallStateMachine.fail(call.pk)

            # 4. Reset the Query back to WAITING so call_llm can pick it up
            updated = Query.objects.filter(pk=query.pk, status=QueryStatus.ACTIVE).update(
                status=QueryStatus.WAITING,
            )
            if not updated:
                continue
            query.refresh_from_db()
            publish_model_event(query, "update")

            # 5. Re-dispatch call_llm for this query, preserving guardrail state
            session_model = query.session_version.session
            call_llm_tdv = TaskDefinition.objects.filter(name="call_llm").first()
            if not call_llm_tdv or not call_llm_tdv.latest_task_version:
                print(f"  [recovery] call_llm task definition not found for query {query.pk}")
                Query.objects.filter(pk=query.pk, status=QueryStatus.WAITING).update(
                    status=QueryStatus.FAILURE,
                )
                publish_model_event(query, "update")
                continue

            ti = TaskInstance.get_or_create(
                task_definition=call_llm_tdv.latest_task_version,
                session_version=query.session_version,
                args=(query,),
                kwargs={},
            )
            taskcall = AgentTaskCall.create(
                task_instance=ti,
                args=(query,),
                requires_approval=orig_requires_approval if orig_requires_approval else None,
            )
            if orig_requires_approval:
                AgentTaskCall.objects.filter(pk=taskcall.pk).update(
                    is_approved=orig_is_approved,
                    guardrail_reason=orig_guardrail_reason,
                )
                taskcall.refresh_from_db()
            taskcall.apply_async()
            print(f"  [recovery] re-dispatched call_llm for query {query.pk} (guardrail: requires_approval={orig_requires_approval})")

        except Exception as e:
            print(f"[recovery] error recovering stale query {query.pk}: {e}")


def _cleanup_stale_runtime_folders() -> None:
    """Remove runtime version folders (``~/.agentone/runtime/<pk>/``) whose
    ``.last_used`` is older than the stale threshold.

    If a version is needed again after cleanup, ``BoundTask.call()``
    automatically re-extracts it from the install repo.
    """
    try:
        from runtime.runtime_folder import RuntimeFolder
        removed = RuntimeFolder.collect_garbage()
        if removed:
            print(f"[recovery] cleaned {removed} stale runtime folder(s)")
    except Exception as e:
        print(f"[recovery] error cleaning runtime folders: {e}")
