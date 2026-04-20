from __future__ import annotations
"""
runtime/scheduler.py

Celery beat periodic task handling all time-driven wakeups:

  1. WAITING_RATELIMIT — re-check LLM capacity, release calls in FIFO order
  2. WAITING_RETRY     — release calls whose dont_start_before has passed
  3. NEW (scheduled)   — release calls with dont_start_before in the past
  4. Active run timeout — fail runs that exceeded their time_limit

Celery beat config (settings.py):

    CELERY_BEAT_SCHEDULE = {
        'agentone-scheduler': {
            'task': 'tasks.tick_scheduler',
            'schedule': 10.0,  # seconds
        },
    }
"""

from celery import shared_task
from django.utils import timezone
from django.db.models import Q, F, DurationField, ExpressionWrapper, Func
from django.db import models
from datetime import timedelta


@shared_task(name='tasks.tick_scheduler')
def tick_scheduler():
    """Main scheduler tick — each routine is independent."""
    _release_rate_limited_calls()
    _release_retry_calls()
    _release_scheduled_calls()
    _timeout_active_runs()


def _release_rate_limited_calls():
    """
    For each model that now has capacity, release WAITING_RATELIMIT calls in
    FIFO order. Stops releasing once a model hits its limit again this tick.
    """
    from server.models.tasks.agent_task_call import AgentTaskCall
    from server.models.enums.task_enums import TaskCallStatusDetail
    from runtime.rate_limiter import RateLimitChecker, RateLimitError
    from runtime.tasks.call_fsm import TaskCallStateMachine
    from runtime.tasks.call_scheduler import CallScheduler

    waiting = (
        AgentTaskCall.objects
        .filter(status_detail=TaskCallStatusDetail.WAITING_RATELIMIT)
        .order_by('priority', 'created_at')
    )
    exhausted_models: set[int] = set()

    for call in waiting:
        try:
            aimodel = call.agent_instance_version.agent_version.profile.aimodel
            if aimodel is None or aimodel.pk in exhausted_models:
                continue
            try:
                RateLimitChecker.check(aimodel)
            except RateLimitError:
                exhausted_models.add(aimodel.pk)
                continue

            if TaskCallStateMachine.release_rate_limit(call.pk):
                CallScheduler.start_new_taskrun(call.pk)

        except Exception as e:
            print(f"[scheduler] error releasing rate-limited call {call.pk}: {e}")


def _release_retry_calls():
    return
    """Release WAITING_RETRY calls whose dont_start_before has passed."""
    from server.models.tasks.agent_task_call import AgentTaskCall
    from server.models.enums.task_enums import TaskCallStatusDetail
    from runtime.tasks.call_fsm import TaskCallStateMachine
    from runtime.tasks.call_scheduler import CallScheduler
    due = AgentTaskCall.objects.filter(status_detail=TaskCallStatusDetail.WAITING_RETRY, dont_start_before__lte=timezone.now()).order_by("priority",'dont_start_before')
    for call in due:
        try:
            if TaskCallStateMachine.enter_dependency_wait(call.pk):
                CallScheduler.on_all_arg_reference_tasks_ended(call.pk)
        except Exception as e:
            print(f"[scheduler] error releasing retry call {call.pk}: {e}")


def _release_scheduled_calls():
    """Dispatch NEW calls whose dont_start_before has now passed."""
    from server.models.tasks.agent_task_call import AgentTaskCall
    from server.models.enums.task_enums import TaskCallStatusDetail
    from server.tasks.task_dispatcher import celery_delay
    from runtime.tasks.call_scheduler import CallScheduler
    due = AgentTaskCall.objects.filter(status_detail=TaskCallStatusDetail.NEW, dont_start_before__lte=timezone.now()).order_by("priority",'dont_start_before')
    for call in due:
        try:
            celery_delay(CallScheduler._apply_async, call.pk)
        except Exception as e:
            print(f"[scheduler] error dispatching scheduled call {call.pk}: {e}")


def _timeout_active_runs():
    """Fail ACTIVE runs that have exceeded their time_limit (seconds). 0 = no limit."""
    from server.models.tasks.agent_task_run import AgentTaskRun
    from server.models.enums.task_enums import TaskRunStatus
    from runtime.tasks.run_fsm import TaskRunStateMachine
    from runtime.tasks.call_scheduler import CallScheduler

    timed_out = (
        AgentTaskRun.objects
        .filter(status=TaskRunStatus.ACTIVE, time_limit__gt=0)
        .extra(
            where=["created_at < NOW() - INTERVAL time_limit SECOND"]
        )
    )
   
    for run in timed_out:
        try:
            if TaskRunStateMachine.fail(run.pk):
                CallScheduler.on_taskrun_ended(run.pk, TaskRunStatus.FAILURE)
                print(f"[scheduler] timed out run {run.pk} (limit {run.time_limit}s)")
        except Exception as e:
            print(f"[scheduler] error timing out run {run.pk}: {e}")