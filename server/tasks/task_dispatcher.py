
from celery import shared_task

@shared_task
def _celery_run(classname, fname, parent_ctx_id, *args, **kwargs):
    from server.models.tasks.agent_task_call import AgentTaskCall
    from server.models.tasks.agent_task_run  import AgentTaskRun
    from runtime.task_call_runtime import AgentTaskCallRuntime
    from runtime.task_run_runtime import AgentTaskRunRuntime    
    from runtime.context_manager import ContextTracker
    
    # Restore the parent context on the worker side
    parent_ctx = None

    print("_celery_run", classname, fname, parent_ctx_id)
    if parent_ctx_id:
        parent_ctx = AgentTaskRun.objects.get(pk=parent_ctx_id)

    with ContextTracker(parent_ctx):
        if classname == "AgentTaskCall":
            _class = AgentTaskCall
        elif classname == "AgentTaskRun":
            _class = AgentTaskRun
        elif classname == "AgentTaskCallRuntime":
            _class = AgentTaskCallRuntime
        elif classname == "AgentTaskRunRuntime":
            _class = AgentTaskRunRuntime
        f = getattr(_class, fname)
        f(*args, **kwargs)

def celery_delay(func, *args, **kwargs):
    from runtime.context_manager import ContextTracker
    # Extract Parent PK from the local thread context
    parent_id = ContextTracker.current.pk if ContextTracker.current else None
    class_name, function_name = func.__qualname__.split(".", 1)
    print("celery_delay", class_name, parent_id)
    _celery_run.delay(class_name, function_name, parent_id, *args, **kwargs)
