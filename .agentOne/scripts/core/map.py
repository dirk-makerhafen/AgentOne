"""Map a list over a task function."""
from __future__ import annotations
from runtime.session.session import Session
from server.models.tasks.task_instance import TaskInstance

def map(_session: Session, items: list, target_pk: int) -> list:
    """Execute the task identified by *target_pk* for each *item* in parallel."""
    results = []
    if not items:
        return results
    task_instance = TaskInstance.objects.get(pk=target_pk)
    for item in items:
        results.append(task_instance.delay(item))
    return results
