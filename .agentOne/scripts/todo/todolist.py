"""Session todo list — one focused tool per action, event-sourced state.

State lives NOWHERE in the DB. It is event-sourced from the shared history
of the hidden ``todolist_action`` task (registered as TASK-type, so the LLM
never sees it): every store call returns the full item list in its result
under the ``"items"`` key, and the current list is the payload of the most
recent successful store call. The in-flight call is never ``ENDED_SUCCESS``
yet, so reading the history always yields the *previous* state.

Each todo item is a dict with this shape::

    {"task_id": 1, "text": "Do the thing", "status": "pending",
     "depends_on": [2]}  # "depends_on" only when set

``status`` is one of ``"pending"``, ``"in_progress"``, ``"completed"``.
New items default to ``"pending"``. ``task_id`` is an auto-incremented
integer unique within the session.
"""

from __future__ import annotations

from typing import Any, List, Literal, Optional, Union

from runtime.session.session import Session

# NOTE: hints below deliberately use typing.Optional/Union instead of the
# ``X | Y`` syntax. The manifest loader (generate_schema_for_function) only
# recognises ``typing.Union`` as a union — a PEP 604 ``types.UnionType``
# silently degrades to {"type": "string"} in the LLM tool schema.


# Status values the tools understand. Exposed through the JSON schema as an
# enum (the manifest loader turns Literal into "enum"), so the LLM can only
# send valid states.
TodoStatus = Literal["pending", "in_progress", "completed"]

# Store-call envelope returned by AgentTaskCall.get_result() in production:
# a ``[ok, payload]`` pair. The loader unwraps it defensively because fakes
# and older records may hand over the bare payload dict instead.
Envelope = list[Any] | tuple[Any, ...] | dict[str, Any]


def _load_todolist_items(_session: Session) -> list[dict[str, Any]]:
    """Return the current todo items from the latest stored call payload.

    Reads the most recent successful ``todolist_action`` call and returns
    its ``"items"`` list. Returns an empty list when no call was recorded
    yet or the payload carries no items. Never raises: unusable payloads
    (missing anchor, malformed envelope) read as an empty list.
    """
    action_task = _session.get_task("todolist_action")
    if not action_task:
        return []
    raw = action_task.lastest_result()
    if isinstance(raw, (list, tuple)) and len(raw) == 2 and isinstance(raw[1], dict):
        payload = raw[1]
    elif isinstance(raw, dict):
        payload= raw
    else:
        payload = {}
    items = payload.get("items", [])
    return [it for it in items if isinstance(it, dict)]


def _coerce_task_id(task_id: Any) -> int | None:
    """Coerce a task id to int, returning None when it is not numeric."""
    try:
        return int(task_id)
    except (TypeError, ValueError):
        return None


def _coerce_task_ids(task_ids: int | list[int] | None) -> set[int]:
    """Normalize the delete selector to a set of ints.

    Accepts a single id, a list of ids, or None (deletes nothing).
    Non-numeric entries are ignored.
    """
    if task_ids is None:
        return set()
    if isinstance(task_ids, int):
        task_ids = [task_ids]
    if isinstance(task_ids, str):
        tmp = task_ids.split(",") if "," in task_ids else [task_ids]
        task_ids = [i for i in (_coerce_task_id(t) for t in tmp) if i is not None]   
    return {i for i in (_coerce_task_id(t) for t in task_ids) if i is not None}


def todolist_action(_session: Session, action: str, **kwargs: Any) -> dict[str, Any]:
    """Shared-history anchor (TASK-type — never shown to the LLM).

    Replays one recorded action against the latest recorded state and
    returns the full list, so the call history IS the todo list. All agent
    tools funnel through here for persistence; each public tool replays its
    action and then resolves the slim ``todolist_action_response`` task so
    the anchor history stays append-only while the LLM only sees the
    status/action/message triple.

    Supported actions (all extra arguments arrive via kwargs):

    - ``clear``: drop every item.
    - ``append``: add one item (``text``, optional ``status`` defaulting to
      ``"pending"``, optional ``depends_on``). Assigns the next integer
      ``task_id``.
    - ``update``: patch ``text``/``status``/``depends_on`` of ``task_id``.
    - ``delete``: remove every item whose ``task_id`` is in ``task_ids``.

    Always returns the full ``items`` list alongside ``status``,
    ``action`` and a human-readable ``message``.
    """
    items = _load_todolist_items(_session)

    if action == "clear":
        return {
            "action": action,
            "message": f"{len(items)} tasks deleted",
            "items": [],
        }

    if action == "append":
        known = [it.get("task_id") for it in items]
        task_id = max([i for i in known if isinstance(i, int)] or [0]) + 1
        task: dict[str, Any] = {"task_id": task_id}
        if text := kwargs.get("text", None):
            task["text"] = text
        task["status"] = kwargs.get("status", None) or "pending"
        if depends_on := kwargs.get("depends_on", None):
            task["depends_on"] = depends_on
        items.append(task)

        return {
            "action": action,
            "message": f"task {task_id} created",
            "items": items,
        }

    if action == "update":
        task_id = _coerce_task_id(kwargs.get("task_id"))
        matches = [i for i in items if i.get("task_id") == task_id]
        if task_id is None or not matches:
            return {
                "action": action,
                "message": f"no task with task_id {kwargs.get('task_id')!r}",
                "items": items,
            }
        task = matches[0]
        if text := kwargs.get("text", None):
            task["text"] = text
        if status := kwargs.get("status", None):
            task["status"] = status
        if depends_on := kwargs.get("depends_on", None):
            task["depends_on"] = depends_on

        return {
            "action": action,
            "message": f"task {task_id} updated",
            "items": items,
        }

    if action == "delete":
        wanted = _coerce_task_ids(kwargs.get("task_ids", []))
        kept = [it for it in items if it.get("task_id") not in wanted]
        removed = len(items) - len(kept)
        return {
            "action": action,
            "message": f"{removed} of {len(items)} tasks deleted, {len(kept)} remaining.",
            "items": kept,
        }

    return {
        "action": action,
        "message": f"Unknown action '{action}'",
        "items": items,
    }


def todolist_action_response(_session: Session, store_function_response: dict[str, Any]) -> dict[str, Any]:
    """Slim resolver for the anchor call (TASK-type — never shown to the LLM).

    Runs after ``todolist_action`` and returns only the
    status/action/message triple to the caller. The full ``items`` list is
    deliberately dropped here so response records stay small — the list
    itself remains readable from the anchor's stored payload.
    """
    return {
        "action": store_function_response.get("action"),
        "message": store_function_response.get("message"),
    }


def todo_append(_session: Session, text: str, depends_on: Optional[Union[int, List[int]]] = None, **kwargs) -> tuple[bool, dict[str, Any]]:
    """Add one todo item to the session list.

    Break a larger request into trackable steps with this: append one item
    per step, work them one at a time, and advance each via todo_update
    (``"in_progress"`` when you start it, ``"completed"`` when it is done).
    The new item gets the next integer ``task_id`` and starts as
    ``"pending"``. Re-check remaining work with todo_list as you go.

    Args:
        text: Detailed instructions or context for the task. Be specific
            enough that the step is executable on its own.
        depends_on: Integer task id, or list of integer task ids, of
            prerequisite task(s) that must be completed first.
            Informational ordering hint; not enforced.

    Returns:
        (True, result) with the created ``task_id``, a ``message``, and
        the full ``items`` list.
    """
    action_task = _session.get_task("todolist_action")
    store_function_response = action_task.delay(
        action="append", text=text, depends_on=depends_on
    )
    return _session.get_task("todolist_action_response").delay(
        store_function_response=store_function_response
    )


def todo_update(
    _session: Session,
    task_id: int,
    text: Optional[str] = None,
    status: Optional[TodoStatus] = None,
    depends_on: Optional[Union[int, List[int]]] = None,
) -> tuple[bool, dict[str, Any]]:
    """Update the text, status, or dependencies of one todo item.

    Use this to advance items through their lifecycle: set ``"in_progress"``
    when you start working an item and ``"completed"`` as soon as it is
    done. Only the arguments you pass are changed; the rest stays as-is.

    Args:
        task_id: Integer id of the item (as shown by todo_list).
        text: Replacement instructions or context for the task.
        status: New lifecycle state. One of ``"pending"``,
            ``"in_progress"``, ``"completed"``.
        depends_on: Replacement prerequisite integer task id(s).

    Returns:
        (True, result) with a ``message`` and the full ``items`` list.
        When no item carries ``task_id``, the stored status is
        ``"exception"`` and the message names the missing id.
    """
    action_task = _session.get_task("todolist_action")
    store_function_response = action_task.delay(
        action="update",
        task_id=task_id,
        text=text,
        status=status,
        depends_on=depends_on,
    )
    return _session.get_task("todolist_action_response").delay(
        store_function_response=store_function_response
    )


def todo_delete(
    _session: Session, task_ids: Optional[Union[int, List[int]]] = None
) -> tuple[bool, dict[str, Any]]:
    """Delete todo items by id.

    Prefer completing items with todo_update over deleting them, so the
    session history keeps a record of finished work. Use this to drop
    steps that turned out unnecessary, or were created by mistake.

    Args:
        task_ids: One integer task id, or a list of them. When omitted,
            nothing is deleted.

    Returns:
        (True, result) with a ``message`` like ``"2 of 5 tasks deleted,
        3 remaining."`` and the remaining full ``items`` list.
    """
    action_task = _session.get_task("todolist_action")
    store_function_response = action_task.delay(action="delete", task_ids=task_ids)
    return _session.get_task("todolist_action_response").delay(
        store_function_response=store_function_response
    )


def todo_clear(_session: Session,  **kwargs) -> tuple[bool, dict[str, Any]]:
    """Delete every todo item in the session.

    This wipes the whole list at once and cannot be undone. Only use it
    when the tracked work is fully done or the list no longer reflects
    reality — otherwise prefer todo_update or todo_delete.

    Returns:
        (True, result) with a ``message`` like ``"4 tasks deleted"`` and
        an empty ``items`` list.
    """
    action_task = _session.get_task("todolist_action")
    store_function_response = action_task.delay(action="clear")
    return _session.get_task("todolist_action_response").delay(
        store_function_response=store_function_response
    )


def todo_list(
    _session: Session,
    status: Optional[TodoStatus] = None,
    search_text: str | None = None,
    limit: int = 1,
    offset: int = 0,
) -> tuple[bool, dict[str, Any]]:
    """Show the session todo list (paginated, read-only).

    This never records anything: call it freely to check what is next.
    Items come back in creation order with their integer ``task_id``,
    ``text``, ``status`` and optional ``depends_on``.

    Args:
        status: Keep only items in this state. One of ``"pending"``,
            ``"in_progress"``, ``"completed"``. When omitted, all items
            match.
        search_text: Keep only items whose text contains this (case-insensitive
            substring). When omitted, all items match.
        limit: Max items returned (default 1, max 50).
        offset: Skip N matching items before returning.

    Returns:
        (True, result) with ``limit``, ``offset``, a ``message`` like
        ``"Matched 3 of 5 items, 1 shown"``, and the page under ``items``.
    """
    try:
        limit = max(1, min(int(limit), 50))
    except (TypeError, ValueError):
        limit = 1
    try:
        offset = max(0, int(offset))
    except (TypeError, ValueError):
        offset = 0

    items = _load_todolist_items(_session)
    needle = search_text.lower() if search_text else None
    filtered_items = [
        i
        for i in items
        if (not status or status == i.get("status"))
        and (not needle or needle in str(i.get("text", "")).lower())
    ]
    paginated_items = filtered_items[offset : offset + limit]
    result: dict[str, Any] = {
        "status": "success",
        "action": "list",
        "limit": limit,
        "offset": offset,
        "message": (
            f"Matched {len(filtered_items)} of {len(items)} items, "
            f"{len(paginated_items)} shown"
        ),
        "items": paginated_items,
    }

    return (True, result)


# ---------------------------------------------------------------------------
# User-only slash command — never exposed to the LLM as a tool.
# ---------------------------------------------------------------------------
def todo_command(_session: Session, action: str = "list") -> None:
    """Reserved entry point for the user-only /todo slash command.

    Not registered in scripts.md and never exposed to the LLM. Currently
    unimplemented (no-op); kept as the future home for user-side controls
    such as auto-processing toggles.
    """


if __name__ == "__main__":
    import argparse
    import ast
    import sys

    parser = argparse.ArgumentParser(
        description="Check tool hygiene: every public function needs "
        "a docstring and full type annotations (the manifest loader "
        "turns both into the LLM tool schema)."
    )
    parser.parse_args()

    tree = ast.parse(open(__file__).read())
    failures: list[str] = []
    checked = 0
    # TASK-type anchors are never shown to the LLM, so their **kwargs
    # dispatch mechanism is exempt from the no-varargs rule.
    internal = frozenset({"todolist_action", "todolist_action_response"})
    for node in tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if node.name.startswith("_"):
            continue
        checked += 1
        if not ast.get_docstring(node):
            failures.append(f"{node.name}: missing docstring")
        arg_names = [a.arg for a in node.args.args + node.args.kwonlyargs]
        missing = [
            a.arg
            for a in node.args.args + node.args.kwonlyargs
            if a.annotation is None
        ]
        # *args/**kwargs carry no usable schema type — flag them on tools.
        if node.name not in internal:
            if node.args.vararg is not None:
                missing.append("*" + node.args.vararg.arg)
            if node.args.kwarg is not None:
                missing.append("**" + node.args.kwarg.arg)
        if missing:
            failures.append(f"{node.name}: unannotated params: {missing}")
        if node.returns is None:
            failures.append(f"{node.name}: missing return annotation")
        _ = arg_names  # documented via docstring, not AST

    if failures:
        print(f"FAIL ({checked} functions checked):")
        print("\n".join(f" - {f}" for f in failures))
        sys.exit(1)
    print(f"OK ({checked} functions checked)")
