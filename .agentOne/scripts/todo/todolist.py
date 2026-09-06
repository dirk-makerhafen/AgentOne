"""Session todo list — one focused tool per action, event-sourced state.

State lives NOWHERE in the DB.  It is event-sourced from the shared history
of the hidden ``todolist_store`` task (registered as TASK-type, so the LLM
never sees it): every store call returns the full item list in its result
under the ``"items"`` key, and the current list is the payload of the most
recent successful store call.  The in-flight call is never ``ENDED_SUCCESS``
yet, so reading the history always yields the *previous* state.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from runtime.session.session import Session


# ---------------------------------------------------------------------------
# Pure state transitions (no DB — unit-tested directly).
# ---------------------------------------------------------------------------

'''


def _pending(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [it for it in items if it["status"] == "pending"]

def is_todo_auto(_session: Any) -> bool:
    """Return whether user-enabled auto-processing is on for the session."""
    try:
        return bool(_session._get_session_setting("todo_auto_process"))
    except Exception:  # pylint: disable=broad-exception-caught
        return False


def set_todo_auto(_session: Any, enabled: bool) -> None:
    """Persist the user-controlled auto-processing flag."""
    try:
        _session._set_session_setting("todo_auto_process", bool(enabled))
    except Exception:  # pylint: disable=broad-exception-caught
        pass
'''

def _load_todolist_items(_session: Session) ->list:
    action_task = _session.get_task("todolist_action")
    if not action_task:
        return []
    
    latest_response = action_task.lastest_result()
    if not latest_response:
        return []
    return latest_response.get("items",[])


def todolist_action(_session: Any, action: str , **kwargs: Any) -> dict:
    """Shared-history anchor (TASK-type — never shown to the LLM).

    Replays one recorded action against the latest recorded state and
    returns the full list, so the call history IS the todo list.  All agent
    tools and the user command funnel through here for persistence.
    """
    items = _load_todolist_items(_session)

    if action == "clear":
        return {
            "status": "success",
            "action": action,
            "message" : f"{len(items)} tasks deleted",
            "items": [],
        }


    if action == "append":
        task_id =  max([it["task_id"] for it in items] or [0]) + 1
        task = { "task_id": task_id}
        if text := kwargs.get("text", None):
            task["text"] = text
        if status := kwargs.get("status", None):
            task["status"] = status
        if depends_on := kwargs.get("depends_on", None):
            task["depends_on"] = depends_on
        items.append(task)

        return {
            "status": "success",
            "action": action,
            "message" : f'task { task_id} created',
            "items": items,
        }

    if action == "update":
        task_id = kwargs.get("task_id")
        try:
            task = [i for i in items if i["task_id"] == task_id][0]
            if text := kwargs.get("text", None):
                task["text"] = text
            if status := kwargs.get("status", None):
                task["status"] = status
            if depends_on := kwargs.get("depends_on", None):
                task["depends_on"] = depends_on

            return {
                "status": "success",
                "action": action,
                "message" : f"task {task_id} updated",
                "items": items,
            }
        
        except Exception as e:
            return {
                "status": "exception",
                "action": action,
                "message" : f"{e}",
                "items": items,
            }

    if action == "delete":
        task_ids = set(kwargs.get("task_ids", []))
        i=0
        del_cnt = 0
        olen = len(items)
        while i < len(items):
            while i < len(items) and items[i]["id"] in task_ids:
                del items[i]
                del_cnt += 1
            i += 1
        return {
            "status": "success",
            "action": action,
            "message": f"{del_cnt} of {olen} tasks deleted, {len(items)} remaining.",
            "items": items,
        }
    
    return {
        "status": "error",
        "action": action,
        "message": "Unknown action '{action}'",
        "items": items,
    }


def todolist_action_response(_session: Any, store_function_response:dict) -> dict:
    return {
        "status": store_function_response.get("status"),
        "action":  store_function_response.get("action"),
        "message":  store_function_response.get("message"),
    }
    

def todo_append(_session: Any, text: str, depends_on: Optional[str|list] = None) -> Dict[str, Any]:
    """Add todo item(s) to the session list.

    Break a larger request into trackable steps with this, work them one at
    a time, and mark them via todo_pop/todo_done as you finish.  If the user
    enabled auto-processing, the next pending item is fed automatically after
    you call final_result.

    Args:
        description: Detailed instructions or context for the task.
        depends_on: The task_id, or a list of task_ids of prerequisite task(s) that must be completed first.


    Returns:
        (True, result) with ``added`` items plus the full ``items`` list.
    """
    action_task =  _session.get_task("todolist_action")
    store_function_response = action_task.delay(action="append", text=text, depends_on=depends_on)
    return _session.get_task("todolist_action_response").delay(store_function_response=store_function_response)


def todo_update(_session: Any, task_id: str, text: Optional[str] = None, status: Optional[str] = None,  depends_on: Optional[str|list] = None) ->  tuple[bool, dict[str,Any]]:
    action_task =  _session.get_task("todolist_action")
    store_function_response = action_task.delay(action="update", task_id=task_id, text=text, status=status, depends_on=depends_on)
    return _session.get_task("todolist_action_response").delay(store_function_response=store_function_response)


def todo_delete(_session: Any, task_ids: Optional[str|list] = None) -> tuple[bool, dict]:
    action_task =  _session.get_task("todolist_action")
    store_function_response = action_task.delay(action="delete", task_ids=task_ids)
    return _session.get_task("todolist_action_response").delay(store_function_response=store_function_response)


def todo_clear(_session: Any) ->  tuple[bool, dict[str,Any]]:
    action_task =  _session.get_task("todolist_action")
    store_function_response = action_task.delay(action="clear")
    return _session.get_task("todolist_action_response").delay(store_function_response=store_function_response)


def todo_list(_session: Any, status: Optional[str]=None, search_text: Optional[str]=None, limit:int = 1, offset: int = 0) -> tuple[bool, dict[str,Any]]:
    """Show the session todo list (paginated).

    Args:
        status: Filter tasks by state. Options: 'pending', 'completed'.
        search_text: search in task text
        limit: max items returned (default 1, max 50).
        offset: skip N items.
    
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
    filtered_items = [i for i in items if (not status or status == i["status"]) and (not search_text or i["text"].contains(search_text) ) ]
    paginated_items =  items[offset:offset + limit]
    result: dict[str, Any] = {
        "status": "success",
        "action": "list",
        "limit": limit,
        "offset": offset,
        "message": f"Matched {len(filtered_items)} of {len(items)} items, {len(paginated_items)} shown",
        "items": paginated_items,
    }

    return (True, result)
    




# ---------------------------------------------------------------------------
# User-only slash command — never exposed to the LLM as a tool.
# ---------------------------------------------------------------------------
def todo_command(_session: Any, action: str = "list", enabled: bool | None = None) -> dict:
    pass


if __name__ == "__main__":
    import argparse
    import json

    parser = argparse.ArgumentParser(description="Session todo list (stateless demo).")
    parser.add_argument("action", nargs="?", default="list")
    parser.add_argument("--text", default=None)
    parser.add_argument("--count", type=int, default=1)
    args = parser.parse_args()

    demo, extra = apply_todo_action([], args.action, text=args.text, count=args.count)
    print(json.dumps({"items": demo, **extra}, indent=2))
