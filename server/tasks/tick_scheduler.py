"""
Celery beat periodic task handling the 10-second time-driven wakeups:

  1. Data flow dispatch (streams/sets) and collection propagation
  2. WAITING_QUEUE     - release calls waiting to start (normal-path fallback
                         for the drain-in-``_on_taskcall_ended`` path)
  3. WAITING_RATELIMIT - re-check LLM capacity, release calls in FIFO order
  4. WAITING_RETRY     - release calls whose dont_start_before has passed
  5. NEW (scheduled)   - release calls with dont_start_before in the past
  6. Idle compaction   - dispatch ``compact_turn`` for quiet, oversized
                         sessions before their KV cache expires

Sibling one-minute tasks live in their own modules:

  * ``tasks.cron_scheduler``         - cron job dispatch (``cron_scheduler.py``)
  * ``tasks.sleep_guard_scheduler``  - keep-awake guard (``sleep_guard_scheduler.py``)
  * ``tasks.startup_cleanup``        - one-time startup cleanup (``startup_cleanup.py``)
  * ``tasks.tick_scheduler_recovery``- error recovery (``recovery_scheduler.py``)

Celery beat config (settings.py):

    CELERY_BEAT_SCHEDULE = {
        'agentone-scheduler': {
            'task': 'tasks.tick_scheduler',
            'schedule': 10.0,  # seconds
        },
        'agentone-cron-scheduler': {
            'task': 'tasks.cron_scheduler',
            'schedule': 60.0,  # seconds
        },
        'agentone-sleep-guard-scheduler': {
            'task': 'tasks.sleep_guard_scheduler',
            'schedule': 60.0,  # seconds
        },
    }
"""

from __future__ import annotations

import traceback
from typing import Any

from celery import shared_task
from django.utils import timezone


@shared_task(name="tasks.tick_scheduler")
def tick_scheduler() -> None:
    """Main scheduler tick - each routine is independent.

    Routines are isolated: a recurring error in one (e.g. a broken data-flow
    processor raising on every tick) must never starve the release passes
    behind it.
    """
    for routine in (
        _dispatch_data_flows,
        _propagate_from_collections,
        _release_scheduled_calls,
        _release_rate_limited_calls,
        _release_retry_calls,
        _release_queued_calls,
        _dispatch_work_items,
        _report_work_item_outcomes,
        _verify_work_items,
        _compact_idle_sessions,
    ):
        try:
            routine()
        except Exception as e:
            print(f"[scheduler] error in {routine.__name__}: {e} {traceback.format_exc()}")


def _release_queued_calls() -> None:
    """Release WAITING_QUEUE calls — the normal-path fallback for the
    drain-in-``_on_taskcall_ended`` path.

    Catches queue entries left behind when no ending call triggers the drain
    (e.g. a call parked by the session queue strategy in ``session.py`` while
    another turn is still active, whose blocking calls then never end).  The
    per-TaskInstance parallel limit in ``start_new_taskrun`` prevents
    concurrent runs, so a call that cannot start yet (its TI slot is held)
    simply stays queued and is retried on the next tick.
    """
    from server.models.tasks.agent_task_call import AgentTaskCall
    from server.models.enums.task_enums import TaskCallStatusDetail
    from runtime.tasks.call_scheduler import CallScheduler
    from server.tasks.recovery_scheduler import _is_ancient

    for call in AgentTaskCall.objects.filter(
        status_detail=TaskCallStatusDetail.WAITING_QUEUE,
    ).order_by("priority", "created_at"):
        try:
            # A call whose serialized arguments reference a deleted AgentTaskCall
            # can never create a run (AgentTaskRun.create raises DoesNotExist).
            # Cancel it instead of erroring on every tick.
            if _has_dangling_call_refs(call.carguments_json):
                if _cancel_dangling_queue_call(call.pk):
                    print(f"[scheduler] cancelled WAITING_QUEUE call {call.pk} — dangling arg reference")
                continue
            # Session FIFO: a parked ingest waits while a live turn or an
            # older parked message is ahead of it — releasing everything at
            # once would run turns concurrently and collide on the Query.
            # Ancient rows are left to the recovery pass (see TURN_DEATH_AGE).
            if CallScheduler._session_queue_blocked(call):
                continue
            if _is_ancient(call.updated_at):
                continue
            CallScheduler.start_new_taskrun(call.pk)
        except Exception as e:
            print(f"[scheduler] error releasing queued call {call.pk}: {e} {traceback.format_exc()}")


def _has_dangling_call_refs(json_data: Any) -> bool:
    """Check whether *json_data* contains a ``{"_type": "AgentTaskCall", "pk": N}``
    reference to a call that no longer exists.

    Such a call can never create a run — ``AgentTaskRun.create`` raises
    ``DoesNotExist`` when resolving the reference — so the scheduler cancels it.
    """
    from server.models.tasks.agent_task_call import AgentTaskCall

    if isinstance(json_data, dict):
        if json_data.get("_type") == "AgentTaskCall":
            return not AgentTaskCall.objects.filter(pk=json_data.get("pk")).exists()
        return any(_has_dangling_call_refs(v) for v in json_data.values())
    if isinstance(json_data, (list, tuple)):
        return any(_has_dangling_call_refs(v) for v in json_data)
    return False


def _cancel_dangling_queue_call(call_pk: int) -> bool:
    """Cancel a WAITING_QUEUE call whose args reference a deleted call."""
    from server.models.tasks.agent_task_call import AgentTaskCall
    from server.models.tasks.agent_task_run import AgentTaskRun
    from server.models.enums.task_enums import TaskCallStatusDetail
    from runtime.tasks.call_fsm import TaskCallStateMachine
    from runtime.tasks.call_scheduler import CallScheduler
    from django.utils import timezone

    if not TaskCallStateMachine.transition(
        call_pk, TaskCallStatusDetail.WAITING_QUEUE, TaskCallStatusDetail.ENDED_CANCELLED,
        extra={"ended_at": timezone.now()},
    ):
        return False
    last_run = AgentTaskRun.objects.filter(
        agent_task_call_id=call_pk,
    ).order_by("-pk").first()
    CallScheduler._on_taskcall_ended(
        call_pk, last_run.pk if last_run else 0, TaskCallStatusDetail.ENDED_CANCELLED,
    )
    return True


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
    from runtime.power import battery_gate_blocked

    waiting = (
        AgentTaskCall.objects.filter(
            status_detail=TaskCallStatusDetail.WAITING_RATELIMIT
        )
        .order_by("priority", "created_at")
    )
    blocked_models: set[int] = set()
    from runtime.session.session import Session
    from server.tasks.recovery_scheduler import _is_ancient

    for call in waiting:
        try:
            # Ancient parked turns are left to the recovery pass, which fails
            # them instead of resuming day-old context (see TURN_DEATH_AGE).
            if _is_ancient(call.updated_at):
                continue
            session = Session(
                session_model=call.session,
                pinned_session_version=call.session_version,
            )
            aimodel = session.aimodel
            if aimodel is None or aimodel.pk in blocked_models:
                continue
            # Low-battery pause: keep the call parked until power recovers.
            if battery_gate_blocked(aimodel)[0]:
                blocked_models.add(aimodel.pk)
                continue
            try:
                RateLimitChecker.check(aimodel, session=session)
            except RateLimitError as e:
                print(f"{aimodel} is rate limited" ,e )
                blocked_models.add(aimodel.pk)
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
    from server.tasks.recovery_scheduler import _is_ancient

    for call in due:
        try:
            # Ancient retries are left to the recovery pass, which fails them
            # instead of replaying day-old context (see TURN_DEATH_AGE).
            if _is_ancient(call.updated_at):
                continue
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
    from server.tasks.recovery_scheduler import _is_ancient

    for call in due:
        try:
            # Ancient scheduled calls are left to the recovery pass, which
            # cancels them instead of dispatching day-old work.
            if _is_ancient(call.updated_at):
                continue
            from server.tasks.task_dispatcher import celery_delay

            celery_delay(CallScheduler._apply_async, call.pk)
        except Exception as e:
            print(f"[scheduler] error dispatching scheduled call {call.pk}: {e}")


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

    # Create (or reuse) a TaskInstance for the consumer.
    # We intentionally set iarguments_json to {} — copying it from the source
    # call would double positional args when start_new_taskrun merges
    # iarguments_json["*"] + carguments_json["*"].
    # get_or_create (not objects.create) so repeated dispatches share one
    # instance row instead of violating uniq_taskinstance_dedupe.
    src_ti = call.task_instance
    task_instance = TaskInstance.get_or_create(
        task_definition=tdv.latest_task_version,
        session_version=session_obj.latest_version if hasattr(session_obj, 'latest_version') else session_version,
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
        ti = TaskInstance.get_or_create(
            task_definition=tdv.latest_task_version,
            session_version=session_version,
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


# ---------------------------------------------------------------------------
# Work items — the durable long-term task layer (docs/work-items.md §7)
#
# These routines are the *only* operator of WorkItemStateMachine.  No ATC/Run
# FSM code may write WorkItem.status: the arrow between the two lifecycles
# points one way, and the tick observes a terminal ATC to report in.
#
# They also must never call _is_ancient.  A 24h turn-death guard is right for a
# turn and fatal for a backlog — a work item may legitimately sit in `ready`
# for a month.
# ---------------------------------------------------------------------------

#: Ready items considered per tick.  Bounds the work one tick can do when a
#: large backlog is promoted at once.
WORKITEM_DISPATCH_LIMIT = 20


def _dispatch_work_items() -> None:
    """Dispatch ``ready`` work items to their assigned agent.

    Idempotent by construction: an item is only selected while its ``root_task``
    is unset *and* it is still ``ready``, and the transition to ``in_progress``
    is atomic, so two concurrent ticks cannot both claim it.  Running this
    every 10s is safe.
    """
    from server.models.enums.message_enums import MessageContentType, MessagePartType, MessageRole
    from server.models.enums.session_enums import SessionType
    from server.models.message import Message
    from server.models.workitems.enums import WorkItemStatus
    from server.models.workitems.work_item import WorkItem
    from runtime.events import publish_model_event
    from runtime.session.session import Session
    from runtime.workitems.workitem_fsm import WorkItemStateMachine

    candidates = (
        WorkItem.objects.filter(status=WorkItemStatus.READY, root_task__isnull=True)
        .order_by("-priority", "created_at")[:WORKITEM_DISPATCH_LIMIT]
    )

    for item in candidates:
        try:
            # An unassigned item is blocked, never dispatched.  Guessing an agent
            # here would run work the user never routed.
            if not item.assigned_agent_id:
                WorkItemStateMachine.mark_blocked(
                    item.pk, "no agent assigned — set assigned_agent before it can run"
                )
                continue

            agent_version = item.assigned_agent.get_runtime().get_version_model()
            if not agent_version:
                WorkItemStateMachine.mark_blocked(
                    item.pk, f"agent {item.assigned_agent.name} has no version model"
                )
                continue

            # "workitem:{pk}" is globally unique by construction, which keeps
            # the executor session immune to the name-scoping pitfalls of
            # human-chosen session names (docs/work-items.md §4).
            child_sv = agent_version.get_or_create_session(
                name=f"workitem:{item.pk}",
                display_name=f"Work item #{item.pk}: {item.title}"[:255],
                description=(item.body or "")[:255],
                session_type=SessionType.SUBSESSION,
            )
            executor = Session(
                session_model=child_sv.session, pinned_session_version=child_sv
            )

            # Claim the item before dispatching.  If the claim loses a race, do
            # not dispatch — the winner owns this turn.
            if not WorkItemStateMachine.start_dispatch(
                item.pk,
                executor_session=executor.model,
                dispatch_count=item.dispatch_count + 1,
            ):
                continue

            prompt = item.body or item.title
            executor.reset_unattended_turn_count()
            executor.reset_turn_count()
            version = executor.get_version_model()
            message = Message.objects.create(
                role=MessageRole.USER,
                session=version.session,
                session_version=version,
                prev_message=executor.get_last_message(),
            )
            message.add_part(
                type=MessagePartType.MESSAGE,
                content_type=MessageContentType.TEXT,
                content=prompt,
            )
            publish_model_event(message, "create")

            # Dispatch process_turn directly rather than going through
            # ingest_user_message, for two reasons:
            #
            #  1. It yields the turn's own ATC, which is the row whose ENDED
            #     state marks the whole turn.  The ingest call ends the moment
            #     the message is stored and would report a finished item
            #     before the agent did anything.
            #  2. add_user_message() would apply the session queue strategy,
            #     which parks a message behind a live turn.  The executor
            #     session belongs to exactly one work item, so there is nothing
            #     to serialise against.
            turn_task = executor.get_task("process_turn")
            if turn_task is None:
                raise RuntimeError(
                    f"agent {item.assigned_agent.name} cannot run process_turn "
                    "(missing from its tasks list)"
                )
            turn_call = turn_task.delay(message=message)
            WorkItemStateMachine.attach_root_task(item.pk, turn_call.pk)
        except Exception as e:  # pylint: disable=broad-exception-caught
            print(
                f"[scheduler] error dispatching work item {item.pk}: {e} "
                f"{traceback.format_exc()}"
            )
            WorkItemStateMachine.mark_blocked(item.pk, f"dispatch failed: {e}")


def _report_work_item_outcomes() -> None:
    """Observe finished dispatches and move items to review or blocked.

    Cannot fire twice for one dispatch: the item must be ``in_progress`` and
    its ``root_task`` must be terminal, and every branch ends in a state the
    next tick no longer selects.
    """
    from server.models.enums.task_enums import TaskCallStatus
    from server.models.workitems.enums import WorkItemStatus
    from server.models.workitems.work_item import WorkItem

    for item in WorkItem.objects.filter(status=WorkItemStatus.IN_PROGRESS):
        try:
            if not item.root_task_id:
                # The dispatch claimed the item but died before recording its
                # turn; nothing to observe.  Only an executor-less item can
                # stall here, and it was already failed into `blocked`.
                continue
            if not item.root_task or item.root_task.status != TaskCallStatus.ENDED:
                continue
            _report_outcome(item)
        except Exception as e:  # pylint: disable=broad-exception-caught
            print(
                f"[scheduler] error reporting work item {item.pk}: {e} "
                f"{traceback.format_exc()}"
            )


def _report_outcome(item: Any) -> None:
    """Route a finished dispatch to review or blocked."""
    from server.models.enums.task_enums import TaskCallStatusDetail
    from runtime.workitems.workitem_fsm import WorkItemStateMachine

    detail = item.root_task.status_detail
    outcome = _work_item_outcome_text(item)

    if detail == TaskCallStatusDetail.ENDED_SUCCESS:
        if item.requires_verification:
            WorkItemStateMachine.begin_review(item.pk, outcome)
        else:
            # Success without verification parks for a human.  It must never
            # return to `ready` — see docs/work-items.md §7.4.
            WorkItemStateMachine.report_success(item.pk, outcome)
        return

    WorkItemStateMachine.report_failure(
        item.pk, f"{detail}: {outcome}" if outcome else str(detail)
    )


def _work_item_outcome_text(item: Any) -> str:
    """Summarise the dispatch for ``last_outcome``.

    Prefers the executor's own final_result over the ATC status: §3.1 — a
    crashed tool still ends SUCCESS, so the status alone says nothing about
    whether the work happened.
    """
    from runtime.workitems.work_item_verifier import WorkItemVerifier

    final = WorkItemVerifier._final_result_text(item)  # pylint: disable=protected-access
    detail = item.root_task.status_detail if item.root_task_id and item.root_task else "unknown"
    if final:
        return f"{detail} — final_result: {final}"
    return f"{detail} (no final_result)"


def _verify_work_items() -> None:
    """Dispatch the agent reviewer for items awaiting verification.

    A thin launcher: the review itself runs on a worker so a long LLM turn can
    never stall the tick.

    Only rows with a NULL ``verify_status`` are claimed, and the claim is written
    *before* the worker is dispatched.  That is what makes this idempotent — a
    second tick sees ``pending`` and leaves the in-flight review alone.  It also
    means a reviewer that dies leaves the item pending for a human instead of
    being retried in a loop (``docs/work-items.md`` §8.5).
    """
    from server.models.workitems.enums import WorkItemStatus, WorkItemVerifyStatus
    from server.models.workitems.work_item import WorkItem

    for item in WorkItem.objects.filter(
        status=WorkItemStatus.IN_REVIEW, verify_status__isnull=True
    ):
        try:
            if not item.requires_verification:
                continue
            claimed = WorkItem.objects.filter(
                pk=item.pk, verify_status__isnull=True
            ).update(
                verify_status=WorkItemVerifyStatus.PENDING,
                updated_at=timezone.now(),
            )
            if not claimed:
                continue
            from server.tasks.task_dispatcher import celery_delay
            from runtime.workitems.work_item_verifier import WorkItemVerifier

            celery_delay(WorkItemVerifier.verify, item.pk)
        except Exception as e:  # pylint: disable=broad-exception-caught
            print(
                f"[scheduler] error verifying work item {item.pk}: {e} "
                f"{traceback.format_exc()}"
            )


# Pre-filter floor for the idle-compaction candidate scan: sessions with
# activity newer than this are never eligible. Only a floor — the precise
# per-session ``auto_compact_idle_seconds`` threshold governs firing.
_IDLE_PRECHECK_FLOOR_SECONDS = 60

# Max idle compactions dispatched per tick: drains a backlog of stale
# sessions over several ticks instead of spiking LLM spend at once.
_MAX_IDLE_COMPACTIONS_PER_TICK = 2


def _compact_idle_sessions() -> None:
    """Dispatch ``compact_turn`` for quiet, oversized sessions.

    Proactive compaction: a session sitting at 100k tokens for minutes would
    otherwise pay a full cold prefill on its next turn (KV cache expired)
    just before the reactive ``auto_compact_max_tokens`` trigger fires
    anyway. Compacting while the cache is still warm bills the summarization
    prefill at cache-read rates instead.

    A session is eligible only when all hold:

    - active, with idle compaction configured (min tokens > 0 and
      idle seconds > 0 — both unset mean disabled; ``baseagent`` declares
      the stock 50k/240s so the whole tree inherits it),
    - no live work: no non-ended call outside ``HALTED`` (approval/input
      halts count as idle — the boundary guard keeps the open turn live),
      and never ``HALTED_PAUSED`` (paused means hands off),
    - its newest message is older than its idle threshold,
    - its walked context reaches the min-tokens floor with a real boundary.

    The dispatched chain re-verifies idleness at run time (a turn may have
    started in between) and passes through quietly when stale.
    """
    from datetime import timedelta

    from django.db.models import Max

    from runtime.session.session import Session
    from server.history_limiter import (
        estimate_entries_tokens,
        find_compaction_boundary,
        idle_seconds,
        walk_compaction_entries,
    )
    from server.models.enums.task_enums import TaskCallStatus, TaskCallStatusDetail
    from server.models.sessions.session import SessionModel
    from server.models.tasks.agent_task_call import AgentTaskCall

    floor = timezone.now() - timedelta(seconds=_IDLE_PRECHECK_FLOOR_SECONDS)
    candidates = (
        SessionModel.objects.filter(is_active=True)
        .annotate(last_msg_at=Max("related_messages__created_at"))
        .filter(last_msg_at__lt=floor)
        .order_by("last_msg_at")
    )
    dispatched = 0
    for session_model in candidates:
        if dispatched >= _MAX_IDLE_COMPACTIONS_PER_TICK:
            break
        try:
            live = AgentTaskCall.objects.filter(
                session_id=session_model.pk
            ).exclude(status=TaskCallStatus.ENDED)
            if live.exclude(status=TaskCallStatus.HALTED).exists():
                continue  # live turn, queued work, or retry pending
            if live.filter(
                status_detail=TaskCallStatusDetail.HALTED_PAUSED
            ).exists():
                continue  # paused by user: hands off

            session = Session(session_model=session_model)
            min_tokens = session.auto_compact_min_tokens or 0
            idle_s = session.auto_compact_idle_seconds or 0
            if min_tokens <= 0 or idle_s <= 0:
                continue
            last_message = session.get_last_message()
            if last_message is None:
                continue
            if (idle_seconds(session) or 0) < idle_s:
                continue
            entries = walk_compaction_entries(session, last_message)
            if estimate_entries_tokens(entries) < min_tokens:
                continue
            if find_compaction_boundary(session, last_message) is None:
                continue
            compact_task = session.get_task("compact_turn")
            if compact_task is None:
                continue
            compact_task.delay(message=last_message, idle_trigger=True)
            dispatched += 1
        except Exception as e:  # pylint: disable=broad-exception-caught
            print(
                f"[scheduler] error in _compact_idle_sessions "
                f"for session {session_model.pk}: {e}"
            )
