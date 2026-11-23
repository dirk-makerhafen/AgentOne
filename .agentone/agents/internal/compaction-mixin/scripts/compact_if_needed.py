from __future__ import annotations
from typing import Any

from runtime.session.compaction_guard import current_root_id, set_compaction_call, stop_other_roots, try_begin_compaction
from runtime.session.session import Session
from server.models.message import Message
from server.models.queries.response import Response


def compact_if_needed(
    _session: Session,
    response: Response,
    parts: list[dict[str, Any]],
    message: Message,
    **kwargs: Any,
) -> dict[str, Any]:
    auto_limit = _session.auto_compact_max_tokens
    if auto_limit <= 0 or response.prompt_tokens < auto_limit:
        return dict(response=response, parts=parts, message=message, **kwargs)

    compact_task = _session.get_task("compact_turn")
    if not compact_task:
        return dict(response=response, parts=parts, message=message, **kwargs)

    # Turn-outcome flags travel into the fork chain (JSON-safe, no live
    # futures) so a retried compaction can re-emit them: after the
    # continuation-repoint flattening, the wrapper's dict *replaces* this
    # step's result, and anything not threaded here is lost to
    # decide_next_step (see parts_vs_message.md §8).
    # Open the session-wide fence before dispatch: the compact_turn call does
    # not exist yet, but a sibling root could otherwise persist a message in
    # the dispatch window.  Stop those sibling roots first so the conversation
    # and tool work above the boundary cannot continue under compaction.
    root_id = current_root_id(_session)
    if not try_begin_compaction(_session, root_call_id=root_id):
        # Another compaction already owns this session.  Never start a second
        # fork (and never overwrite its tracked call); let that one finish.
        return dict(response=response, parts=parts, message=message, **kwargs)
    stop_other_roots(_session, root_id)
    try:
        compact_call = compact_task.delay(
            message=message,
            has_final_result=kwargs.get("has_final_result"),
            tool_allowlist_violated=kwargs.get("tool_allowlist_violated"),
            has_tool_calls=kwargs.get("has_tool_calls"),
            has_message=kwargs.get("has_message"),
            trigger="auto",
            idle_trigger=False,
            prompt_tokens=response.prompt_tokens,
            auto_limit=auto_limit,
        )
    except Exception:
        # Never leave the session fenced if dispatch itself failed.
        from runtime.session.compaction_guard import end_compaction

        end_compaction(_session.model.pk)
        raise
    set_compaction_call(_session, compact_call)
    return dict(response=response, parts=parts, message=message, compact_call=compact_call, **kwargs)
