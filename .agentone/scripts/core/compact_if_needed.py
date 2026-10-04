from __future__ import annotations
from typing import Any

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
    compact_call = compact_task.delay(
        message=message,
        has_final_result=kwargs.get("has_final_result"),
        tool_allowlist_violated=kwargs.get("tool_allowlist_violated"),
        has_tool_calls=kwargs.get("has_tool_calls"),
        has_message=kwargs.get("has_message"),
    )
    return dict(response=response, parts=parts, message=message, compact_call=compact_call, **kwargs)
