"""Session todo list — one focused tool per action, event-sourced state.

State lives NOWHERE in the DB.  It is event-sourced from the shared history
of the hidden ``todolist_store`` task (registered as TASK-type, so the LLM
never sees it): every store call returns the full item list in its result
under the ``"items"`` key, and the current list is the payload of the most
recent successful store call.  The in-flight call is never ``ENDED_SUCCESS``
yet, so reading the history always yields the *previous* state.

Why an anchor task?  Each manifest entry gets its own TaskDefinition, so the
seven tools below can NOT share one call history.  Instead each thin tool:

  1. reads the previous list from the anchor history (synchronous DB read),
  2. applies its action purely and returns the predicted list to the LLM
     immediately,
  3. records the action on the anchor via fire-and-forget ``.delay()``.

The anchor replays each recorded action against its own latest state at
execution time (FIFO), so the stored truth converges without lost updates
even if a tool's synchronous prediction briefly lags under rapid parallel
calls.

Only the auto-processing flag lives in the DB (``SettingsModel``) — it is
user-controlled via the ``todo`` slash command or the Todos rightbar tab
and never exposed to the agent.

Item shape: ``{"id": int, "text": str, "status": "pending" | "done"}``.
``pop``/``done`` mark items ``done`` (kept for history); ``remove``/``clear``
drop rows entirely.
"""

from __future__ import annotations

from typing import Any

from runtime.session.session import Session


# ---------------------------------------------------------------------------
# Pure state transitions (no DB — unit-tested directly).
# ---------------------------------------------------------------------------

def _empty_items() -> list[dict[str, Any]]:
    return []


def coerce_items(raw: Any) -> list[dict[str, Any]]:
    """Coerce a stored payload into a well-formed item list."""
    if not isinstance(raw, list):
        return _empty_items()
    clean: list[dict[str, Any]] = []
    for it in raw:
        if not isinstance(it, dict):
            continue
        try:
            text = str(it.get("text", "")).strip()
            if not text:
                continue
            clean.append({
                "id": int(it.get("id", 0)),
                "text": text,
                "status": "done" if it.get("status") == "done" else "pending",
            })
        except (TypeError, ValueError):
            continue
    return clean


def _next_id(items: list[dict[str, Any]]) -> int:
    return max([it["id"] for it in items] or [0]) + 1


def _pending(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [it for it in items if it["status"] == "pending"]


def apply_todo_action(items: list[dict[str, Any]], action: str, **kwargs: Any) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Apply *action* to *items* (pure — no DB access).

    Returns ``(new_items, extra)`` where ``extra`` holds action-specific
    result keys (``added``, ``popped``, ``items`` slice, ...).  Raises
    ``ValueError`` on unknown actions / bad arguments.
    """
    action = (action or "list").strip().lower()
    items = [dict(it) for it in coerce_items(items)]
    extra: dict[str, Any] = {}

    if action == "append":
        texts: list[str] = []
        text = kwargs.get("text")
        if isinstance(text, str) and text.strip():
            texts.append(text.strip())
        raw_texts = kwargs.get("texts")
        if isinstance(raw_texts, (list, tuple)):
            texts.extend(str(t).strip() for t in raw_texts if str(t).strip())
        if not texts:
            raise ValueError("append needs 'text' or non-empty 'texts'")
        nid = _next_id(items)
        added = []
        for t in texts:
            item = {"id": nid, "text": t, "status": "pending"}
            items.append(item)
            added.append(dict(item))
            nid += 1
        extra["added"] = added

    elif action in ("list", "peek"):
        # NOTE: the slice goes under "selection", never "items" — recorded
        # results double as history, and "items" must always hold the FULL
        # list or later reads would see a truncated state.
        if action == "peek":
            try:
                count = max(1, int(kwargs.get("count", 1)))
            except (TypeError, ValueError):
                count = 1
            extra["selection"] = [dict(it) for it in _pending(items)[:count]]
        else:
            try:
                limit = max(1, min(int(kwargs.get("limit", 50)), 200))
            except (TypeError, ValueError):
                limit = 50
            try:
                offset = max(0, int(kwargs.get("offset", 0)))
            except (TypeError, ValueError):
                offset = 0
            extra["selection"] = [dict(it) for it in items[offset:offset + limit]]
            extra["total"] = len(items)

    elif action == "pop":
        try:
            count = max(1, int(kwargs.get("count", 1)))
        except (TypeError, ValueError):
            count = 1
        popped = []
        for it in items:
            if len(popped) >= count:
                break
            if it["status"] == "pending":
                it["status"] = "done"
                popped.append(dict(it))
        extra["popped"] = popped

    elif action in ("done", "remove"):
        raw_ids = kwargs.get("ids", [])
        if isinstance(raw_ids, (int, str)):
            raw_ids = [raw_ids]
        try:
            ids = {int(i) for i in (raw_ids or [])}
        except (TypeError, ValueError):
            raise ValueError(f"{action} needs 'ids' as int id(s)")
        if not ids:
            raise ValueError(f"{action} needs 'ids' as int id(s)")
        if action == "done":
            updated = []
            for it in items:
                if it["id"] in ids and it["status"] != "done":
                    it["status"] = "done"
                    updated.append(dict(it))
            extra["updated"] = updated
        else:
            before = len(items)
            items = [it for it in items if it["id"] not in ids]
            extra["removed"] = before - len(items)

    elif action == "clear":
        include_done = bool(kwargs.get("include_done", False))
        if include_done:
            extra["cleared"] = len(items)
            items = []
        else:
            extra["cleared"] = len(_pending(items))
            items = [it for it in items if it["status"] != "pending"]

    else:
        raise ValueError(
            f"unknown action '{action}'; use append|list|pop|peek|done|remove|clear"
        )

    extra["pending"] = len(_pending(items))
    return items, extra


# ---------------------------------------------------------------------------
# Shared history (anchor task) + user flag (session settings).
# ---------------------------------------------------------------------------

_ANCHOR_TASK = "todolist_store"


def _anchor(_session: Session) -> Any | None:
    """Return the shared-history anchor task, or *None* if unavailable."""
    try:
        return _session.get_task(_ANCHOR_TASK) or _session.get_tool(_ANCHOR_TASK)
    except Exception:  # pylint: disable=broad-exception-caught
        return None


def unwrap_result(raw: Any) -> Any:
    """Strip the ``(success, payload)`` envelope from a stored call result.

    ``AgentTaskCall.get_result()`` returns the tool function's raw return
    value, i.e. the ``[True, {...}]`` pair — NOT the payload dict.  Forgetting
    this makes every history read silently empty (the payload dict has no
    ``id``/``text`` keys, so coercion drops it).
    """
    if isinstance(raw, (list, tuple)) and len(raw) == 2 and isinstance(raw[1], dict):
        return raw[1]
    return raw


def load_todo_items(_session: Any) -> list[dict[str, Any]]:
    """Return the current todo items from the anchor history (never raises)."""
    try:
        anchor = _anchor(_session)
        raw = anchor.lastest_result() if anchor is not None else None
    except Exception:  # pylint: disable=broad-exception-caught
        return _empty_items()
    raw = unwrap_result(raw)
    if isinstance(raw, dict) and "items" in raw:
        return coerce_items(raw["items"])
    return coerce_items(raw)


def _record(_session: Any, action: str, **params: Any) -> None:
    """Record *action* on the shared history (fire-and-forget).

    Read-only actions (list/peek) are NOT recorded: they mutate nothing, and
    persisting their prediction would let a stale read permanently shadow
    newer state (latest record wins).
    """
    if (action or "").strip().lower() in ("list", "peek"):
        return
    try:
        anchor = _anchor(_session)
        if anchor is not None:
            anchor.delay(action=action, **params)
    except Exception:  # pylint: disable=broad-exception-caught
        pass


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


def _run(action: str, _session: Any, **kwargs: Any) -> tuple[bool, dict]:
    """Execute one todo action: predict synchronously, record async.

    The returned list is predicted from the last recorded state; the same
    action is replayed on the anchor so the shared history converges.
    """
    try:
        items, extra = apply_todo_action(load_todo_items(_session), action, **kwargs)
        _record(_session, action, **kwargs)
        result: dict[str, Any] = {
            "status": "success",
            "action": action,
            #"items": items,
            #"auto": is_todo_auto(_session),
        }
        result.update(extra)
        return (True, result)
    except ValueError as e:
        return (False, {"status": "error", "message": str(e)})
    except Exception as e:  # pylint: disable=broad-exception-caught
        import traceback
        return (False, {"status": "error", "message": f"todo_{action} failed: {e}\n{traceback.format_exc()}"})


def todolist_store(_session: Any, action: str = "list", **kwargs: Any) -> tuple[bool, dict]:
    """Shared-history anchor (TASK-type — never shown to the LLM).

    Replays one recorded action against the latest recorded state and
    returns the full list, so the call history IS the todo list.  All agent
    tools and the user command funnel through here for persistence.
    """
    try:
        items, extra = apply_todo_action(load_todo_items(_session), action, **kwargs)
        result: dict[str, Any] = {
            "status": "success",
            "action": (action or "list").strip().lower(),
            "items": items,
        }
        result.update(extra)
        return (True, result)
    except ValueError as e:
        return (False, {"status": "error", "message": str(e)})
    except Exception as e:  # pylint: disable=broad-exception-caught
        import traceback
        return (False, {"status": "error", "message": f"todolist_store failed: {e}\n{traceback.format_exc()}"})


# ---------------------------------------------------------------------------
# Agent tools — one function per action.  No auto flag here on purpose:
# automatic processing is user-controlled (Todos tab / /todo command).
# ---------------------------------------------------------------------------

def todo_append(_session: Any, text: str | None = None, texts: list[str] | None = None) -> tuple[bool, dict]:
    """Add todo item(s) to the session list.

    Break a larger request into trackable steps with this, work them one at
    a time, and mark them via todo_pop/todo_done as you finish.  If the user
    enabled auto-processing, the next pending item is fed automatically after
    you call final_result.

    Args:
        text: single item text.
        texts: multiple item texts at once.

    Returns:
        (True, result) with ``added`` items plus the full ``items`` list.
    """
    return _run("append", _session, text=text, texts=texts)


def todo_list(_session: Any, limit: int = 5, offset: int = 0) -> tuple[bool, dict]:
    """Show the session todo list (paginated).

    Args:
        limit: max items returned (default 5, max 200).
        offset: skip N items.

    Returns:
        (True, result) with ``selection`` slice, ``total`` and ``pending``
        counts, plus the full ``items`` list.
    """
    return _run("list", _session, limit=limit, offset=offset)


def todo_pop(_session: Any, count: int = 1) -> tuple[bool, dict]:
    """Take the next ``count`` pending items and mark them done.

    Use this to pull work: it returns the oldest pending items first.  When
    auto-processing is on you rarely need it — items arrive on their own.

    Args:
        count: how many items to take (default 1; raise it to pull several
            small todos at once).

    Returns:
        (True, result) with ``popped`` items (empty list when none pending).
    """
    return _run("pop", _session, count=count)


def todo_peek(_session: Any, count: int = 1) -> tuple[bool, dict]:
    """Preview the next ``count`` pending items without marking them done.

    Args:
        count: how many items to preview (default 1).

    Returns:
        (True, result) with the preview under ``selection``.
    """
    return _run("peek", _session, count=count)


def todo_done(_session: Any, ids: Any = None) -> tuple[bool, dict]:
    """Mark todo item(s) done by id (kept in history).

    Args:
        ids: item id or list of ids (see todo_list).
    """
    return _run("done", _session, ids=ids)


def todo_remove(_session: Any, ids: Any = None) -> tuple[bool, dict]:
    """Delete todo item(s) by id entirely (no history kept).

    Args:
        ids: item id or list of ids (see todo_list).
    """
    return _run("remove", _session, ids=ids)


def todo_clear(_session: Any, include_done: bool = False) -> tuple[bool, dict]:
    """Drop all pending items (``include_done=True`` drops everything).

    Args:
        include_done: also drop done items.
    """
    return _run("clear", _session, include_done=include_done)


# ---------------------------------------------------------------------------
# User-only slash command — never exposed to the LLM as a tool.
# ---------------------------------------------------------------------------

def todo_command(_session: Any, action: str = "list", enabled: bool | None = None) -> dict:
    """User slash command: inspect and control todo auto-processing.

    Usage: /todo [list|auto-on|auto-off|clear] — e.g. ``/todo auto-on``.
    Agents cannot call this; they manage items via the todo_* tools while
    the user owns the auto flag here (or in the Todos rightbar tab).

    Args:
        action: list|auto-on|auto-off|clear (default: list).
        enabled: explicit flag override for auto.

    Returns:
        Dict with status, items, pending count and auto flag.
    """
    action = (action or "list").strip().lower().replace("_", "-")
    if action in ("auto-on", "auto") or (action == "list" and enabled is True):
        set_todo_auto(_session, True)
    elif action in ("auto-off",) or (action == "list" and enabled is False):
        set_todo_auto(_session, False)
    elif action == "clear":
        _record(_session, "clear")
    elif action != "list":
        return {"status": "error", "message": f"unknown action '{action}'; use list|auto-on|auto-off|clear"}
    items = load_todo_items(_session)
    return {
        "status": "success",
        "action": action,
        "items": len(items),
        "pending": len(_pending(items)),
        "auto": is_todo_auto(_session),
    }


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
