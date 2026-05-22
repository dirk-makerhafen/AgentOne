"""Celery task dispatcher bridging runtime method calls to async workers."""

from __future__ import annotations

from typing import Any, Callable

from celery import shared_task


@shared_task
def _celery_run(
    classname: str,
    fname: str,
    parent_ctx_id: int | None,
    *args: Any,
    **kwargs: Any,
) -> None:
    """Execute a runtime method inside a restored parent context on a worker."""
    from server.models.tasks.agent_task_call import AgentTaskCall
    from server.models.tasks.agent_task_run import AgentTaskRun
    from runtime.context_manager import ContextTracker
    from runtime.tasks.call_scheduler import CallScheduler
    from runtime.tasks.run_scheduler import RunScheduler

    parent_ctx = None

    print("_celery_run", classname, fname, parent_ctx_id)
    if parent_ctx_id:
        parent_ctx = AgentTaskRun.objects.get(pk=parent_ctx_id)

    with ContextTracker(parent_ctx):
        if classname == "AgentTaskCall":
            _class = AgentTaskCall
        elif classname == "AgentTaskRun":
            _class = AgentTaskRun
        elif classname == "CallScheduler":
            _class = CallScheduler
        elif classname == "RunScheduler":
            _class = RunScheduler
        print("HEHREHR23")
        f = getattr(_class, fname)

        f(*args, **kwargs)
        print("FOND")


def celery_delay(func: Callable[..., Any], *args: Any, **kwargs: Any) -> None:
    """Dispatch *func* to Celery, capturing the current parent context PK."""
    from runtime.context_manager import ContextTracker

    parent_id = ContextTracker.current.pk if ContextTracker.current else None
    class_name, function_name = func.__qualname__.split(".", 1)
    print("celery_delay", class_name, parent_id)
    _celery_run.delay(class_name, function_name, parent_id, *args, **kwargs)
