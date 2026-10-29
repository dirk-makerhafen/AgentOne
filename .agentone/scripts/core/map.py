"""Map a list of items over a task, tool, or command.

``map`` is the batch primitive scripts use to fan a call out over a list
without hand-writing ``.get_task(...).delay(...)`` loops:

    map_task = _session.get_task("map")
    return map_task.delay(
        target="update_timeline_item",
        list_of_kwargs=[{"path": item["file"]} for item in items],
        concurrency=1,
    )

Every item is a call on **one shared TaskInstance**, so admission is
governed by a single ``limit_per_instance_parallel_runs`` value:

* ``concurrency=1`` (default) -> one item at a time, in list order.
  Because an item's call only ends after the tasks it returned end, item
  N+1 starts after item N's whole subtree -- depth-first per item.
* ``concurrency=0`` -> unlimited; ``concurrency=N`` -> at most N items
  admitted at once. The calls themselves are always created in list order.

Caveat: batches of the *same* target task in the same session share a
TaskInstance, so their admissions interleave. Keep one batch at a time per
target when ordering matters.
"""
from __future__ import annotations

from typing import Any, List, Literal

from runtime.session.session import Session

#: Resolution order when ``kind`` is not passed explicitly.
_KIND_ORDER: tuple[str, ...] = ("task", "tool", "command")


def _resolve(session: Session, target: str, kind: str | None) -> Any:
    """Return the BoundTask for *target*, resolving task -> tool -> command."""
    if kind is not None:
        if kind not in _KIND_ORDER:
            raise ValueError(
                f"map: unknown kind {kind!r}; expected one of {list(_KIND_ORDER)}"
            )
        getter = getattr(session, f"get_{kind}")
        bound = getter(target)
        if bound is not None:
            return bound
        raise ValueError(
            f"map: {kind} {target!r} is not available in this session. "
            f"Allowed {kind}s: {_allowed_names(session, kind)}"
        )

    for candidate in _KIND_ORDER:
        bound = getattr(session, f"get_{candidate}")(target)
        if bound is not None:
            return bound

    raise ValueError(
        f"map: target {target!r} is not an allowed task, tool, or command in "
        f"this session. Add it to the agent's tasks:/tools:/commands: list. "
        f"Allowed tasks: {_allowed_names(session, 'task')}; "
        f"allowed tools: {_allowed_names(session, 'tool')}; "
        f"allowed commands: {_allowed_names(session, 'command')}"
    )


def _allowed_names(session: Session, kind: str) -> list[str]:
    """Concrete allowed names for *kind* (``task`` / ``tool`` / ``command``)."""
    return sorted(getattr(session, f"allowed{kind.capitalize()}Names", []) or [])


def map(
    _session: Session,
    target: str,
    list_of_kwargs: List[Any],
    concurrency: int = 1,
    kind: Literal["task", "tool", "command"] | None = None,
) -> list:
    """Call *target* once per item in *list_of_kwargs*.

    Args:
        target: Name of the task, tool, or command to call.
        list_of_kwargs: One entry per call. A dict is passed as kwargs
            (``{"path": "x"}`` -> ``target(path="x")``); anything else is
            passed as the single positional argument (``["x"]`` ->
            ``target("x")``).
        concurrency: Maximum number of item calls admitted at once on the
            shared TaskInstance. ``1`` = strictly sequential in list order,
            ``0`` = unlimited.
        kind: Force ``"task"``, ``"tool"``, or ``"command"`` instead of
            resolving task -> tool -> command by name.

    Returns:
        The list of created AgentTaskCall objects, in input order. Return it
        from the dispatching task to wait for the whole batch to finish.
    """
    if list_of_kwargs is None:
        return []
    if isinstance(list_of_kwargs, (list, tuple)):
        items = list(list_of_kwargs)
    else:
        raise ValueError(
            "map: list_of_kwargs must be a list or tuple of per-call items, "
            f"got {type(list_of_kwargs).__name__}"
        )
    if not items:
        return []

    bound = _resolve(_session, target, kind)
    task_instance = bound.instance()

    calls = []
    for item in items:
        if isinstance(item, dict):
            call = task_instance.apply_async(
                kwargs=item,
                limit_per_instance_parallel_runs=concurrency,
            )
        else:
            call = task_instance.apply_async(
                args=[item],
                limit_per_instance_parallel_runs=concurrency,
            )
        calls.append(call)
    return calls
