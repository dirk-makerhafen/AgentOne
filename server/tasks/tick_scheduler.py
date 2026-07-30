"""
Celery beat periodic task handling all time-driven wakeups:

  1. WAITING_RATELIMIT – re-check LLM capacity, release calls in FIFO order
  2. WAITING_RETRY     – release calls whose dont_start_before has passed
  3. NEW (scheduled)   – release calls with dont_start_before in the past
  4. Active run timeout – fail runs that exceeded their time_limit

Celery beat config (settings.py):

    CELERY_BEAT_SCHEDULE = {
        'agentone-scheduler': {
            'task': 'tasks.tick_scheduler',
            'schedule': 10.0,  # seconds
        },
    }
"""

from __future__ import annotations

from typing import Any

from celery import shared_task
from django.utils import timezone
import random

@shared_task(name="tasks.tick_scheduler")
def tick_scheduler() -> None:
    """Main scheduler tick — each routine is independent."""

   
    _dispatch_data_flows()
    _propagate_from_collections()
    _release_scheduled_calls()
    _release_rate_limited_calls()
    _release_retry_calls()
    
    _process_cron_jobs()

    if random.randint(0,10) == 5:
        _release_queued_calls()
        _timeout_active_runs()
        _recover_stuck_calls()
        _cancel_duplicate_queries()
        _recover_stale_queries()
        _cleanup_stale_runtime_folders()
        _resolve_stuck_waiting_runs()



def _release_rate_limited_calls() -> None:
    """
    For each model that now has capacity, release WAITING_RATELIMIT calls in
    FIFO order.  Stops releasing once a model hits its limit again this tick.
    """
    from server.models.tasks.agent_task_call import AgentTaskCall
    from server.models.enums.task_enums import TaskCallStatusDetail
    from runtime.rate_limiter import RateLimitChecker, RateLimitError
    from runtime.tasks.call_fsm import TaskCallStateMachine
    from runtime.tasks.call_scheduler import CallScheduler

    waiting = (
        AgentTaskCall.objects.filter(
            status_detail=TaskCallStatusDetail.WAITING_RATELIMIT
        )
        .order_by("priority", "created_at")
    )
    exhausted_models: set[int] = set()
    from runtime.session.session import Session

    for call in waiting:
        try:
            aimodel = Session(
                session_model=call.session,
                pinned_session_version=call.session_version,
            ).aimodel
            if aimodel is None or aimodel.pk in exhausted_models:
                continue
            try:
                RateLimitChecker.check(aimodel)
            except RateLimitError as e:
                print(f"{aimodel} is rate limited" ,e )
                exhausted_models.add(aimodel.pk)
                continue

            if TaskCallStateMachine.release_rate_limit(call.pk):
                CallScheduler.start_new_taskrun(call.pk)

        except Exception as e:
            print(f"[scheduler] error releasing rate-limited call {call.pk}: {e}")


def _release_retry_calls() -> None:
    """Release WAITING_RETRY calls whose dont_start_before has passed."""
    from server.models.tasks.agent_task_call import AgentTaskCall
    from server.models.enums.task_enums import TaskCallStatus, TaskCallStatusDetail
    from runtime.tasks.call_fsm import TaskCallStateMachine
    from runtime.tasks.call_scheduler import CallScheduler

    due = AgentTaskCall.objects.filter(
        status_detail=TaskCallStatusDetail.WAITING_RETRY,
        dont_start_before__lte=timezone.now(),
    ).order_by("priority", "dont_start_before")
    for call in due:
        try:
            if TaskCallStateMachine.enter_dependency_wait(call.pk):
                tc = AgentTaskCall.objects.get(pk=call.pk)
                if tc.taskcall_arg_references.exclude(status=TaskCallStatus.ENDED).exists():
                    continue  # Still waiting for dependencies
                CallScheduler.on_all_arg_reference_tasks_ended(call.pk)
        except Exception as e:
            print(f"[scheduler] error releasing retry call {call.pk}: {e}")


def _release_scheduled_calls() -> None:
    """Dispatch NEW calls whose dont_start_before has now passed."""
    from server.models.tasks.agent_task_call import AgentTaskCall
    from server.models.enums.task_enums import TaskCallStatusDetail
    from runtime.tasks.call_scheduler import CallScheduler

    due = AgentTaskCall.objects.filter(
        status_detail=TaskCallStatusDetail.NEW,
        dont_start_before__lte=timezone.now(),
    ).order_by("priority", "dont_start_before")
    for call in due:
        try:
            from server.tasks.task_dispatcher import celery_delay

            celery_delay(CallScheduler._apply_async, call.pk)
        except Exception as e:
            print(f"[scheduler] error dispatching scheduled call {call.pk}: {e}")


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
            CallScheduler.start_new_taskrun(call.pk)
        except Exception as e:
            print(f"[scheduler] error releasing queued call {call.pk}: {e}")


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
                    f"[scheduler] timed out run {run.pk} (limit {run.time_limit}s)"
                )
        except Exception as e:
            print(f"[scheduler] error timing out run {run.pk}: {e}")


def _resolve_stuck_waiting_runs() -> None:
    """Resolve WAITING_RESULTTASKS runs whose referenced calls have all ended
    or whose references are stuck in non-progressing states.

    Two cases are handled:

    1. **All refs ended** — normal path (all sub-calls completed successfully
       or terminally; the notification may have been lost).

    2. **No ref is actively executing** — the run's pending result references
       are all stuck in states that will never progress (e.g. WAITING_QUEUE
       blocked by the per-TI limit held by this very run, forming a circular
       deadlock).  We fail the run to break the cycle.
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

    for run in stuck:
        try:
            pending = AgentTaskCall.objects.filter(
                ~Q(status=TaskCallStatus.ENDED),
                rev_taskrun_result_references=run.pk,
            ).values_list('status_detail', flat=True)

            # Case 1: all refs ended — resolve immediately (no cascade risk)
            if not pending:
                RunScheduler.all_taskrun_result_references_ended(run.pk)
                print(f"[scheduler] recovered stuck WAITING_RESULTTASKS run {run.pk} — all refs ended")
                continue

            # Case 2: none of the pending refs are actively executing.
            # Force-failing a run can cascade through the dependency graph and
            # release WAITING_QUEUE calls — pace these one-per-tick so the
            # per-TI parallel limit isn't overwhelmed.
            active_states = {
                TaskCallStatusDetail.ACTIVE_QUEUED.value,
                TaskCallStatusDetail.ACTIVE_RUNNING.value,
            }
            pending_details = set(pending)
            if pending_details.isdisjoint(active_states):
                grace = datetime.timedelta(seconds=30)
                if run.updated_at and timezone.now() - run.updated_at > grace:
                    from runtime.tasks.run_fsm import TaskRunStateMachine
                    from runtime.tasks.call_scheduler import CallScheduler
                    if TaskRunStateMachine.fail(run.pk):
                        CallScheduler.on_taskrun_ended(run.pk, TaskRunStatus.FAILURE)
                        print(f"[scheduler] failed stuck WAITING_RESULTTASKS run {run.pk} — no active refs ({pending_details})")
                    return  # One per tick — pace the cascade
        except Exception as e:
            print(f"[scheduler] error recovering WAITING_RESULTTASKS run {run.pk}: {e}")


def _recover_stuck_calls() -> None:
    """Recover calls/runs whose Celery dispatch message was lost on restart."""
    from datetime import timedelta
    from server.models.tasks.agent_task_call import AgentTaskCall
    from server.models.tasks.agent_task_run import AgentTaskRun
    from server.models.enums.task_enums import TaskCallStatus, TaskCallStatusDetail, TaskRunStatus
    from runtime.tasks.call_fsm import TaskCallStateMachine
    from runtime.tasks.call_scheduler import CallScheduler
    from runtime.tasks.run_scheduler import RunScheduler
    from server.tasks.task_dispatcher import celery_delay

    # 1. ACTIVE_QUEUED calls with no run → re-queue and re-dispatch.
    #    pick_up() → AgentTaskRun.create() is synchronous, so any call
    #    stuck in ACTIVE_QUEUED without a run is immediately orphaned.
    for call in AgentTaskCall.objects.filter(
        status_detail=TaskCallStatusDetail.ACTIVE_QUEUED,
    ):
        try:
            if not AgentTaskRun.objects.filter(agent_task_call=call).exists():
                if TaskCallStateMachine.re_queue(call.pk):
                    CallScheduler.start_new_taskrun(call.pk)
                    print(f"[scheduler] recovered ACTIVE_QUEUED call {call.pk} — re-queued")
        except Exception as e:
            print(f"[scheduler] error recovering ACTIVE_QUEUED call {call.pk}: {e}")

    # 2. QUEUED runs whose Celery message was lost → re-dispatch.
    timeout = timedelta(minutes=15)
    cutoff = timezone.now() - timeout
    for run in AgentTaskRun.objects.filter(
        status=TaskRunStatus.QUEUED,
        updated_at__lt=cutoff,
    ):
        try:
            print(f"[scheduler] re-dispatching stuck QUEUED run {run.pk}")
            celery_delay(RunScheduler._apply_async, run.pk)
        except Exception as e:
            print(f"[scheduler] error re-dispatching QUEUED run {run.pk}: {e}")

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
                        print(f"[scheduler] retrying orphaned ACTIVE_RUNNING call {call.pk}")
                        continue
                if TaskCallStateMachine.fail(call.pk):
                    print(f"[scheduler] failed orphaned ACTIVE_RUNNING call {call.pk}")
        except Exception as e:
            print(f"[scheduler] error recovering ACTIVE_RUNNING call {call.pk}: {e}")

    # 4. WAITING_SUBTASK calls whose result run ended but the call-level
    #    transition was missed (e.g. notify chain crashed or race).
    for call in AgentTaskCall.objects.filter(
        status_detail=TaskCallStatusDetail.WAITING_SUBTASK,
    ).select_related("taskcall_result_run"):
        try:
            result_run = call.taskcall_result_run
            if not result_run or result_run.status not in (
                TaskRunStatus.SUCCESS, TaskRunStatus.FAILURE,
            ):
                continue
            if result_run.status == TaskRunStatus.FAILURE:
                if TaskCallStateMachine.fail(call.pk):
                    print(f"[scheduler] recovered WAITING_SUBTASK call {call.pk} — result run failed")
            else:
                pending_hooks = call.taskcall_after_run_hooks.exclude(
                    status=TaskCallStatus.ENDED,
                )
                if not pending_hooks.exists():
                    if TaskCallStateMachine.succeed(call.pk, result_run.pk):
                        print(f"[scheduler] recovered WAITING_SUBTASK call {call.pk} — result run succeeded, hooks done")
        except Exception as e:
            print(f"[scheduler] error recovering WAITING_SUBTASK call {call.pk}: {e}")

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
                    print(f"[scheduler] recovered WAITING_DEPENDENCY call {call.pk} — dep {failed_dep.pk} failed, cancelled")
            else:
                CallScheduler.on_all_arg_reference_tasks_ended(call.pk)
                print(f"[scheduler] recovered WAITING_DEPENDENCY call {call.pk} — all deps succeeded, resumed")
        except Exception as e:
            print(f"[scheduler] error recovering WAITING_DEPENDENCY call {call.pk}: {e}")

    # 6. WAITING_QUEUE calls — release the oldest per session.
    #    The per-TaskInstance parallel limit in ``start_new_taskrun`` prevents
    #    concurrent ingest calls from the same task instance, so the old
    #    ``has_active`` guard (which missed higher-PK active calls and also
    #    counted WAITING_QUEUE calls themselves) is no longer needed.
    for session_id in AgentTaskCall.objects.filter(
        status_detail=TaskCallStatusDetail.WAITING_QUEUE,
    ).values_list('session_id', flat=True).distinct():
        try:
            CallScheduler._release_next_queued_call(session_id)
        except Exception as e:
            print(f"[scheduler] error releasing WAITING_QUEUE for session {session_id}: {e}")


def _references_query(json_data: Any, query_pk: int) -> bool:
    """Check if *json_data* contains a ``{"_type": "Query", "pk": query_pk}`` at any nesting level."""
    if isinstance(json_data, dict):
        if json_data.get("_type") == "Query" and json_data.get("pk") == query_pk:
            return True
        return any(_references_query(v, query_pk) for v in json_data.values())
    if isinstance(json_data, (list, tuple)):
        return any(_references_query(v, query_pk) for v in json_data)
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
        TaskCallStatusDetail.WAITING_SUBTASK,
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
    from runtime.events import publish_model_event

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
        print(f"[scheduler] SessionVersion {sv_id}: {len(to_cancel)} duplicate queries (keeping {keep.pk})")
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
        print(f"[scheduler] Session {session_id}: {len(to_cancel)} duplicate queries across SVs (keeping {keep.pk})")
        for q in to_cancel:
            _cancel_query_and_call_llm(q.session_version_id, q.pk)

    if total:
        print(f"[scheduler] Cancelled {total} duplicate queries total")
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
    print(f"  [scheduler] cancelled duplicate query {query_pk}")

    # Find and cancel non-ended call_llm calls for this query.
    candidates = AgentTaskCall.objects.filter(
        session_version_id=sv_id,
        task_definition__name="call_llm",
    ).exclude(status=TaskCallStatus.ENDED)
    for call in candidates:
        if _references_query(call.carguments_json, query_pk):
            if _force_end_call(call):
                print(f"  [scheduler] cancelled call_llm {call.pk} for query {query_pk}")


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
            print(f"[scheduler] cancelling stale WAITING query {query.pk} (WAITING since {query.updated_at})")
            Query.objects.filter(pk=query.pk, status=QueryStatus.WAITING).update(
                status=QueryStatus.SUCCESS,
            )
            publish_model_event(query, "update")
        except Exception as e:
            print(f"[scheduler] error cancelling stale WAITING query {query.pk}: {e}")

    # --- Handle stale ACTIVE queries — resume via re-dispatch ---
    stale = Query.objects.filter(
        status=QueryStatus.ACTIVE,
        updated_at__lt=cutoff,
    ).select_related("session_version__session")

    for query in stale:
        try:
            print(f"[scheduler] resuming stale query {query.pk} (ACTIVE since {query.updated_at})")

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
                print(f"  [scheduler] call_llm task definition not found for query {query.pk}")
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
            print(f"  [scheduler] re-dispatched call_llm for query {query.pk} (guardrail: requires_approval={orig_requires_approval})")

        except Exception as e:
            print(f"[scheduler] error recovering stale query {query.pk}: {e}")


def _process_cron_jobs() -> None:
    """Dispatch due cron jobs to Celery workers."""
    from runtime.cron.execute import execute_cron_job
    from runtime.cron.crons import Cronjobs

    for cronjob in Cronjobs().due():
        try:
            execute_cron_job(cronjob.pk)
            print(f"[scheduler] dispatched cron job {cronjob.pk} ({cronjob.name})")
        except Exception as e:
            print(f"[scheduler] error dispatching cron job {cronjob.pk}: {e}")


def _check_agent_pattern(call_agent_name: str, pattern: str) -> bool:
    """Check if a call's agent name matches a pattern.
    
    Supports:
    - Exact match: ``"agentFoo"``
    - Glob: ``"some*"``, ``*bar``, ``*middle*``
    - ``"*"`` — matches everything
    """
    if pattern == "*":
        return True
    if "*" in pattern:
        import fnmatch
        return fnmatch.fnmatch(call_agent_name, pattern)
    return call_agent_name == pattern


def _matches_data_flow_source(call, source_def):
    """Check whether *call* matches a single source definition.

    Source definitions (from a DataCollection's ``sources`` JSON) can be:
    - ``{"type": "query", "project": ..., "agent": ..., "session": ..., "function": ...}``
    - ``{"type": "stream", "stream": "..."}`` — matched via *call*'s pipe-output history
      (legacy; will be replaced by ``CollectionItem`` propagation)
    """
    source_type = source_def.get("type", "query")

    if source_type == "query":
        project_name = source_def.get("project") or ""
        agent_patterns = source_def.get("agent", [])
        if isinstance(agent_patterns, str):
            agent_patterns = [agent_patterns]
        session_patterns = source_def.get("session", [])
        if isinstance(session_patterns, str):
            session_patterns = [session_patterns]
        function_patterns = source_def.get("function", [])
        if isinstance(function_patterns, str):
            function_patterns = [function_patterns]

        # Resolve the call's properties for matching
        try:
            call_agent_name = call.task_instance.task_definition_version.task_definition.parent_agent.name if call.task_instance and call.task_instance.task_definition_version and call.task_instance.task_definition_version.task_definition and call.task_instance.task_definition_version.task_definition.parent_agent else ""
            call_session_name = call.session.name if call.session else ""
            call_function_name = call.task_instance.task_definition_version.task_definition.name if call.task_instance and call.task_instance.task_definition_version and call.task_instance.task_definition_version.task_definition else ""
            call_project_name = call.session_version.agent.parent_project.name if call.session_version and call.session_version.agent and call.session_version.agent.parent_project else ""
        except Exception:
            return False

        # Project (if specified)
        if project_name and project_name != call_project_name:
            return False

        # Agent (if specified — at least one pattern must match)
        if agent_patterns:
            if not any(_check_agent_pattern(call_agent_name, p) for p in agent_patterns):
                return False

        # Session (if specified)
        if session_patterns:
            if not any(_check_agent_pattern(call_session_name, p) for p in session_patterns):
                return False

        # Function (if specified)
        if function_patterns:
            if not any(_check_agent_pattern(call_function_name, p) for p in function_patterns):
                return False

        return True

    if source_type == "stream":
        # Stream sources are handled by _propagate_from_collections,
        # which matches items by collection name.
        return False

    if source_type == "set":
        # For set sources we rely on CollectionItem propagation
        # (handled in _propagate_from_collections).
        return False

    return False


def _dispatch_processor(flow, call, source_item=None):
    """Execute one data-flow processor for a source call.

    Creates a new ``CollectionItem`` in the target stream/set.

    When *source_item* is provided (propagation from another collection),
    the new item is linked to it via ``source_item`` FK for cascade deletion.

    Returns the ``member`` string of the created/updated item, or ``None``
    if the processor returned None (item filtered out).
    """
    from server.models.collections import CollectionItem
    from server.models.tasks.agent_task_call import AgentTaskCall
    from server.models.tasks.task_instance import TaskInstance
    from server.models.sessions.session import SessionModel
    from server.models.sessions.session_version import SessionVersionModel
    from runtime.session.session import Session
    print("_dispatch_processor", flow, call, source_item)
    processor = flow.processor
    if not processor or not isinstance(processor, dict):
        return

    agent_name = processor.get("agent", "")
    function_name = processor.get("function", "")
    session_template = processor.get("session", "") or flow.name

    if not agent_name or not function_name:
        return

    # Resolve agent
    from server.models.agents.agent import AgentModel
    agent = AgentModel.objects.filter(name=agent_name).first()
    if not agent:
        print(f"[dataflow] agent '{agent_name}' not found for flow '{flow.name}'")
        return

    # Resolve function / task-definition-version
    from server.models.tasks.task_definition import TaskDefinition
    tdv = TaskDefinition.objects.filter(
        name=function_name,
    ).first()
    if not tdv or not tdv.latest_task_version:
        print(f"[dataflow] task '{function_name}' not found for flow '{flow.name}'")
        return

    # Build session name (allow template vars from the source call)
    session_name = session_template.format(
        source_agent=AgentModel.objects.get(
            pk=call.task_instance.task_definition_version.task_definition.parent_agent_id,
        ).name if call.task_instance and call.task_instance.task_definition_version and call.task_instance.task_definition_version.task_definition and call.task_instance.task_definition_version.task_definition.parent_agent_id else "",
        source_session=call.session.name if call.session else "",
        source_function=call.task_instance.task_definition_version.task_definition.name if call.task_instance and call.task_instance.task_definition_version and call.task_instance.task_definition_version.task_definition else "",
    ) if "{" in session_template else session_template

    # Create or get session
    session_model, _ = SessionModel.objects.get_or_create(name=session_name)
    if session_model.latest_session_version_id:
        session_version = session_model.latest_session_version
    else:
        # Create a minimal session version
        session_version = SessionVersionModel.objects.create(
            session=session_model,
            agent=agent,
            pinned_agent_version=agent.latest_agent_version if hasattr(agent, 'latest_agent_version') and agent.latest_agent_version else None,
        )
        SessionModel.objects.filter(pk=session_model.pk).update(
            latest_session_version=session_version,
        )
    session_obj = Session(
        session_model=session_model,
        pinned_session_version=session_version,
    )

    # Determine member BEFORE creating the processor call so we can persist
    # a CollectionItem (dedup token) immediately — even if the processor
    # fails or this function throws an exception later.
    member = _extract_member(flow, None, call)
    score = _extract_score(flow, None, call)

    # Upsert the dedup token right away so the source call won't be
    # re-dispatched on the next tick regardless of what happens below.
    CollectionItem.objects.update_or_create(
        collection=flow,
        member=member,
        defaults={
            "score": score,
            "value": call.carguments_json,
        },
    )

    # Create a TaskInstance for the consumer.
    # We intentionally set iarguments_json to {} — copying it from the source
    # call would double positional args when start_new_taskrun merges
    # iarguments_json["*"] + carguments_json["*"].
    src_ti = call.task_instance
    task_instance = TaskInstance.objects.create(
        task_definition_version=tdv.latest_task_version,
        session=session_model,
        session_version=session_obj.latest_version if hasattr(session_obj, 'latest_version') else session_version,
        iarguments_json={},
        requires_approval=src_ti.requires_approval if src_ti else False,
        max_subtask_errors=src_ti.max_subtask_errors if src_ti else 0,
        max_subtask_error_rate=src_ti.max_subtask_error_rate if src_ti else 0,
        limit_subtask_parallel_runs=src_ti.limit_subtask_parallel_runs if src_ti else 0,
        limit_per_instance_parallel_runs=src_ti.limit_per_instance_parallel_runs if src_ti else 1,
        max_retries=0,
        retry_delay=src_ti.retry_delay if src_ti else 10,
        retry_requires_approval=src_ti.retry_requires_approval if src_ti else True,
    )

    # Create and dispatch the processor call
    processor_call = AgentTaskCall.create(
        task_instance=task_instance,
        kwargs=call.carguments_json,
    )
    processor_call.apply_async()

    # Try to capture the processor function's return value (eager mode only).
    # In non-eager (production) mode the call hasn't completed yet, so we fall
    # back to the raw input arguments for backward compatibility.
    from server.models.enums.task_enums import TaskCallStatusDetail, TaskRunStatus
    from server.models.tasks.agent_task_run import AgentTaskRun

    processor_call.refresh_from_db()
    processor_result = None
    completed_run = None
    if processor_call.status_detail == TaskCallStatusDetail.ENDED_SUCCESS:
        completed_run = processor_call.related_agent_task_runs.filter(
            status=TaskRunStatus.SUCCESS
        ).first()
        if completed_run and completed_run.result_json is not None:
            processor_result = completed_run.result_json

    # Update the CollectionItem with the actual processor call and result
    defaults: dict = {
        "source_call": processor_call,
        "score": score,
        "value": processor_result if processor_result is not None else call.carguments_json,
    }
    if source_item is not None:
        defaults["source_item"] = source_item
    CollectionItem.objects.update_or_create(
        collection=flow,
        member=member,
        defaults=defaults,
    )
    return member


def _extract_member(flow, processor_call, source_call, processor_result=None):
    """Extract the collection-item ``member`` value."""
    if flow.collection_type == "stream":
        # Auto: hash(content + timestamp)
        import hashlib
        raw = f"{source_call.pk}{source_call.created_at}"
        return hashlib.sha256(raw.encode()).hexdigest()[:32]
    # set: user-defined lambda
    expr = flow.member_field.strip()
    if not expr:
        return str(source_call.pk)
    try:
        item = processor_result if processor_result is not None else source_call.carguments_json
        result = eval(expr, {"__builtins__": {}, "str": str, "float": float, "int": int}, {"item": item})
        return str(result)
    except Exception as ex:
        print(f"[dataflow] member_field eval error for '{flow.name}': {ex}")
        return str(source_call.pk)


def _extract_score(flow, processor_call, source_call, processor_result=None):
    """Extract the collection-item ``score`` value."""
    if flow.collection_type == "stream":
        # Auto: timestamp
        from django.utils import timezone
        return timezone.now().timestamp()
    # set: user-defined lambda
    expr = flow.score_field.strip()
    if not expr:
        from django.utils import timezone
        return timezone.now().timestamp()
    try:
        item = processor_result if processor_result is not None else source_call.carguments_json
        result = eval(expr, {"__builtins__": {}, "str": str, "float": float, "int": int}, {"item": item})
        return float(result)
    except Exception as ex:
        print(f"[dataflow] score_field eval error for '{flow.name}': {ex}")
        from django.utils import timezone
        return timezone.now().timestamp()


def _trigger_on_removed(collection, source_calls):
    """Dispatch the ``on_removed`` handler for removed items."""
    from server.models.tasks.task_instance import TaskInstance
    from server.models.tasks.agent_task_call import AgentTaskCall
    from server.models.sessions.session import SessionModel
    from server.models.agents.agent import AgentModel

    on_removed_cfg = collection.on_removed
    if not on_removed_cfg or not isinstance(on_removed_cfg, dict):
        return

    agent_name = on_removed_cfg.get("agent", "")
    function_name = on_removed_cfg.get("function", "")
    session_name = on_removed_cfg.get("session", "") or collection.name

    if not agent_name or not function_name:
        return

    agent = AgentModel.objects.filter(name=agent_name).first()
    if not agent:
        print(f"[dataflow] on_removed agent '{agent_name}' not found")
        return

    from server.models.tasks.task_definition import TaskDefinition
    tdv = TaskDefinition.objects.filter(name=function_name).first()
    if not tdv or not tdv.latest_task_version:
        print(f"[dataflow] on_removed task '{function_name}' not found")
        return

    from server.models.sessions.session_version import SessionVersionModel

    session_model, _ = SessionModel.objects.get_or_create(name=session_name)
    if not session_model.latest_session_version_id:
        sv = SessionVersionModel.objects.create(
            session=session_model,
            agent=agent,
            pinned_agent_version=agent.latest_agent_version if agent.latest_agent_version else None,
        )
        SessionModel.objects.filter(pk=session_model.pk).update(latest_session_version=sv)

    session_version = session_model.latest_session_version

    for call in source_calls:
        src_ti = call.task_instance
        ti = TaskInstance.objects.create(
            task_definition_version=tdv.latest_task_version,
            session=session_model,
            session_version=session_version,
            iarguments_json={},
            requires_approval=src_ti.requires_approval if src_ti else False,
            max_subtask_errors=src_ti.max_subtask_errors if src_ti else 0,
            max_subtask_error_rate=src_ti.max_subtask_error_rate if src_ti else 0,
            limit_subtask_parallel_runs=src_ti.limit_subtask_parallel_runs if src_ti else 0,
            limit_per_instance_parallel_runs=src_ti.limit_per_instance_parallel_runs if src_ti else 1,
            max_retries=src_ti.max_retries if src_ti else 0,
            retry_delay=src_ti.retry_delay if src_ti else 10,
            retry_requires_approval=src_ti.retry_requires_approval if src_ti else True,
        )
        oc = AgentTaskCall.create(
            task_instance=ti,
            kwargs=call.carguments_json,
        )
        oc.apply_async()


def _dispatch_data_flows() -> None:
    """Dispatch new source items to active data flows (streams and sets).

    For each active ``DataCollection``, finds recently completed
    ``AgentTaskCall`` records matching the flow's query-type sources,
    then runs the processor task and stores the result as a
    ``CollectionItem``.

    Dedup is handled by checking whether a ``CollectionItem`` with the
    same ``(collection, member)`` already exists — the member is derived
    from the source call's PK and timestamp, so each source call produces
    exactly one downstream item.
    """
    from server.models.collections import DataCollection, CollectionItem
    from server.models.tasks.agent_task_call import AgentTaskCall
    from server.models.enums.task_enums import TaskCallStatusDetail

    # Fetch the most recent completed calls and process them
    # from oldest to newest so data-flow items are created
    # in chronological order.
    calls = list(
        AgentTaskCall.objects.filter(
            status_detail=TaskCallStatusDetail.ENDED_SUCCESS,
        ).select_related(
            "session",
            "task_instance__task_definition_version__task_definition__parent_agent",
            "session_version__agent__parent_project",
        ).order_by("-pk")[:500]
    )
    if not calls:
        return

    # Oldest of this batch first
    calls.reverse()

    for flow in DataCollection.objects.filter(is_active=True):
        flow_sources = flow.sources
        if not flow_sources:
            continue

        # Only process query-type sources here; stream/set sources
        # are handled via _propagate_from_collections.
        has_query_source = any(
            s.get("type", "query") == "query" for s in flow_sources
        )
        if not has_query_source:
            continue

        for call in calls:
            if any(_matches_data_flow_source(call, s) for s in flow_sources):
                member = _extract_member(flow, None, call)
                if CollectionItem.objects.filter(collection=flow, member=member).exists():
                    continue  # Already dispatched
                _dispatch_processor(flow, call)


def _propagate_from_collections(collection: Any = None) -> None:
    """Propagate new ``CollectionItem`` additions to derived data flows.

    When a stream/set adds an item, any flow that sources from that
    collection should run its processor and create/update a downstream item.
    The downstream item is linked via ``source_item`` FK for cascade deletion.

    Parameters
    ----------
    collection : DataCollection or None
        If provided, only propagate from this specific collection's items.
        If None (the default), propagate from all recent items across all
        collections (called on every scheduler tick).
    """

    from django.utils import timezone
    import datetime
    from server.models.collections import DataCollection, CollectionItem

    # Recent items (last 2 ticks = 20s window)
    threshold = timezone.now() - datetime.timedelta(seconds=30)
    recent_items = list(
        CollectionItem.objects.filter(created_at__gte=threshold)
        .select_related("collection", "source_call")
        .order_by("-created_at")[:100]
    )
    if not recent_items:
        return

    # Process oldest items first so downstream items are created in order.
    recent_items.reverse()

    # Fetch all active flows that source from a stream or set
    # (we do this in Python to work around MySQL JSON query limits)
    if collection is not None:
        all_flows = [collection]
    else:
        all_flows = list(DataCollection.objects.filter(is_active=True))
    if not all_flows:
        return

    for item in recent_items:
        source_collection_name = item.collection.name
        for flow in all_flows:
            for source_def in flow.sources:
                src_type = source_def.get("type", "query")
                if src_type == "stream" and source_def.get("stream") == source_collection_name:
                    if item.source_call:
                        if CollectionItem.objects.filter(collection=flow, source_item=item).exists():
                            break
                        _dispatch_processor(flow, item.source_call, source_item=item)
                    break
                if src_type == "set" and source_def.get("set") == source_collection_name:
                    if item.source_call:
                        if CollectionItem.objects.filter(collection=flow, source_item=item).exists():
                            break
                        _dispatch_processor(flow, item.source_call, source_item=item)
                    break


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
            print(f"[scheduler] cleaned {removed} stale runtime folder(s)")
    except Exception as e:
        print(f"[scheduler] error cleaning runtime folders: {e}")
