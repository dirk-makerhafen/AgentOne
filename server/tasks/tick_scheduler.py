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

from celery import shared_task
from django.utils import timezone


@shared_task(name="tasks.tick_scheduler")
def tick_scheduler() -> None:
    """Main scheduler tick — each routine is independent."""
    _release_rate_limited_calls()
    _release_retry_calls()
    _release_scheduled_calls()
    _release_queued_calls()
    _timeout_active_runs()
    _resolve_stuck_waiting_runs()
    _cleanup_stale_runtime_folders()
    _process_cron_jobs()
    _dispatch_data_flows()
    _propagate_from_collections()


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
    from server.models.enums.task_enums import TaskCallStatusDetail
    from runtime.tasks.call_fsm import TaskCallStateMachine
    from runtime.tasks.call_scheduler import CallScheduler

    due = AgentTaskCall.objects.filter(
        status_detail=TaskCallStatusDetail.WAITING_RETRY,
        dont_start_before__lte=timezone.now(),
    ).order_by("priority", "dont_start_before")
    for call in due:
        try:
            if TaskCallStateMachine.enter_dependency_wait(call.pk):
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
    """Release WAITING_QUEUE calls whose session has no active ingest calls.

    Acts as a fallback for the drain-in-_on_taskcall_ended path — catches
    queue entries left behind after a crash or hang.
    """
    from server.models.tasks.agent_task_call import AgentTaskCall
    from server.models.enums.task_enums import TaskCallStatusDetail, TaskCallStatus
    from runtime.tasks.call_scheduler import CallScheduler

    queued = AgentTaskCall.objects.filter(
        status_detail=TaskCallStatusDetail.WAITING_QUEUE,
    ).order_by("pk")

    for call in queued:
        try:
            has_active = AgentTaskCall.objects.filter(
                session=call.session,
                task_definition__name__in=["ingest_user_message", "ingest_slash_command"],
                pk__lt=call.pk
            ).exclude(status=TaskCallStatus.ENDED).exists()
            if not has_active:
                CallScheduler.start_new_taskrun(call.pk)
        except Exception as e:
            print(f"[scheduler] error releasing queued call {call.pk}: {e}")


def _timeout_active_runs() -> None:
    """Fail ACTIVE runs that have exceeded their time_limit (seconds).  0 = no limit."""
    from server.models.tasks.agent_task_run import AgentTaskRun
    from server.models.enums.task_enums import TaskRunStatus
    from runtime.tasks.run_fsm import TaskRunStateMachine
    from runtime.tasks.call_scheduler import CallScheduler

    timed_out = (
        AgentTaskRun.objects.filter(
            status=TaskRunStatus.ACTIVE, time_limit__gt=0
        ).extra(where=["created_at < NOW() - INTERVAL time_limit SECOND"])
    )

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
    """Resolve WAITING_RESULTTASKS runs whose referenced calls have all ended.

    Recovery path for runs that were missed by the normal
    ``taskrun_result_reference_ended`` callback (e.g. race, crash after
    ``_apply_async``, or referenced calls that already ended before the
    parent run entered ``WAITING_RESULTTASKS``).
    """
    from server.models.tasks.agent_task_run import AgentTaskRun
    from server.models.enums.task_enums import TaskRunStatus, TaskCallStatus
    from server.models.tasks.agent_task_call import AgentTaskCall
    from runtime.tasks.run_scheduler import RunScheduler
    from django.db.models import Q

    stuck = AgentTaskRun.objects.filter(status=TaskRunStatus.WAITING_RESULTTASKS)
    for run in stuck:
        try:
            pending = AgentTaskCall.objects.filter(
                ~Q(status=TaskCallStatus.ENDED),
                rev_taskrun_result_references=run.pk,
            )
            if not pending.exists():
                RunScheduler.all_taskrun_result_references_ended(run.pk)
                print(
                    f"[scheduler] recovered stuck WAITING_RESULTTASKS run {run.pk}"
                )
        except Exception as e:
            print(
                f"[scheduler] error recovering WAITING_RESULTTASKS run {run.pk}: {e}"
            )


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

    # Create a TaskInstance for the consumer
    src_ti = call.task_instance
    task_instance = TaskInstance.objects.create(
        task_definition_version=tdv.latest_task_version,
        session=session_model,
        session_version=session_obj.latest_version if hasattr(session_obj, 'latest_version') else session_version,
        iarguments_json=call.carguments_json,
        requires_approval=src_ti.requires_approval if src_ti else False,
        max_subtask_errors=src_ti.max_subtask_errors if src_ti else 0,
        max_subtask_error_rate=src_ti.max_subtask_error_rate if src_ti else 0,
        limit_subtask_parallel_runs=src_ti.limit_subtask_parallel_runs if src_ti else 0,
        limit_per_instance_parallel_runs=src_ti.limit_per_instance_parallel_runs if src_ti else 1,
        max_retries=src_ti.max_retries if src_ti else 0,
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

    # Processor explicitly returned None → filter this item out
    if completed_run and processor_result is None:
        return

    # Determine value / member / score from processor result or raw args
    if processor_result is not None:
        value = processor_result
        member = _extract_member(flow, processor_call, call, processor_result=processor_result)
        score = _extract_score(flow, processor_call, call, processor_result=processor_result)
    else:
        value = call.carguments_json
        member = _extract_member(flow, processor_call, call)
        score = _extract_score(flow, processor_call, call)

    defaults: dict = {
        "source_call": processor_call,
        "score": score,
        "value": value,
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
            iarguments_json=call.carguments_json,
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
    """
    from server.models.collections import DataCollection
    from server.models.tasks.agent_task_call import AgentTaskCall
    from server.models.enums.task_enums import TaskCallStatusDetail

    # Find recently completed calls
    recent_calls = list(
        AgentTaskCall.objects.filter(
            status_detail=TaskCallStatusDetail.ENDED_SUCCESS,
        ).select_related(
            "session",
            "task_instance__task_definition_version__task_definition__parent_agent",
            "session_version__agent__parent_project",
        ).order_by("-pk")[:200]
    )
    if not recent_calls:
        return

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

        for call in recent_calls:
            if any(_matches_data_flow_source(call, s) for s in flow_sources):
                _dispatch_processor(flow, call)
                break  # One item per tick per flow is enough


def _propagate_from_collections() -> None:
    """Propagate new ``CollectionItem`` additions to derived data flows.

    When a stream/set adds an item, any flow that sources from that
    collection should run its processor and create/update a downstream item.
    The downstream item is linked via ``source_item`` FK for cascade deletion.
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

    # Fetch all active flows that source from a stream or set
    # (we do this in Python to work around MySQL JSON query limits)
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
                        _dispatch_processor(flow, item.source_call, source_item=item)
                    break
                if src_type == "set" and source_def.get("set") == source_collection_name:
                    if item.source_call:
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
