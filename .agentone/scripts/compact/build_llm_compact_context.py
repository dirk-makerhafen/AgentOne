from __future__ import annotations
from typing import List

from runtime.session.session import Session
from server.models.enums.message_enums import MessageRole, MessageType
from server.models.message import Message
from server.models.queries.query import Query
from server.models.queries.query_message import QueryMessage
import time
from datetime import datetime
from server.models.enums.session_enums import SessionType

_COMPACTION_SYSTEM_PROMPT = """<SYSTEM NOTICE>
Your job is to produce a concise, information-dense summary that preserves key context from the existing summary and incorporates relevant new information from the conversation above so the AI agent can continue working without losing important context.

Focus on:
- Key decisions made and their rationale
- Current constraints and requirements
- What has been accomplished so far
- What remains to be done
- Important context the model must remember
- File paths, function names, and specific technical details
- Do NOT restate workspace guidance files (AGENTS.md/CLAUDE.md etc.) in the summary — they are re-loaded automatically after compaction.

Format as a clear, structured summary. Be specific — avoid generic statements.

Call final_result tool with your summary as its content argument, don't output raw text.
</SYSTEM NOTICE>"""


def _format_seconds(seconds: float | int | None) -> str:
    """Format a duration compactly (e.g. 90 -> '90s', 150 -> '2m30s', 8100 -> '2h15m')."""
    if seconds is None:
        return "?"
    try:
        total = int(seconds)
    except (TypeError, ValueError):
        return "?"
    if total < 60:
        return f"{total}s"
    minutes, secs = divmod(total, 60)
    if minutes < 60:
        return f"{minutes}m{secs:02d}s" if secs else f"{minutes}m"
    hours, minutes = divmod(minutes, 60)
    return f"{hours}h{minutes:02d}m"


def _describe_trigger(
    _session: Session,
    *,
    trigger: str | None,
    idle_trigger: bool,
    response=None,
    prompt_tokens_hint: int | None = None,
    auto_limit_hint: int | None = None,
) -> str:
    """Build a short human-readable hint why this compaction was started.

    Never raises: reason computation must not break the compaction itself.
    """
    try:
        resolved = (trigger or "").strip().lower() or None
        if resolved not in ("idle", "auto", "manual", None):
            resolved = None
        if resolved is None:
            if idle_trigger:
                resolved = "idle"
            elif response is not None and getattr(response, "prompt_tokens", None):
                resolved = "auto"
            elif prompt_tokens_hint:
                resolved = "auto"
            else:
                # No response context and no idle flag: only the manual
                # /compact path dispatches this way.
                resolved = "manual"
        if resolved == "idle":
            from runtime.history_limiter import (
                estimate_entries_tokens,
                idle_seconds,
                walk_compaction_entries,
            )

            idle_s = _session.auto_compact_idle_seconds or 0
            min_tokens = _session.auto_compact_min_tokens or 0
            last_message = _session.get_last_message()
            idle_s_actual = idle_seconds(_session)
            tokens = estimate_entries_tokens(
                walk_compaction_entries(_session, last_message)
            )
            return (
                f"Trigger: idle timeout — no new messages for "
                f"{_format_seconds(idle_s_actual)} (threshold {_format_seconds(idle_s)}), "
                f"~{tokens} context tokens (floor {min_tokens})."
            )
        if resolved == "auto":
            prompt_tokens = prompt_tokens_hint
            if prompt_tokens is None and response is not None:
                prompt_tokens = getattr(response, "prompt_tokens", None)
            auto_limit = auto_limit_hint
            if auto_limit is None:
                try:
                    auto_limit = _session.auto_compact_max_tokens
                except Exception:  # pylint: disable=broad-exception-caught
                    auto_limit = None
            if prompt_tokens is not None and auto_limit:
                return (
                    f"Trigger: context limit — last response used "
                    f"{prompt_tokens} prompt tokens (limit {auto_limit})."
                )
            return "Trigger: context limit — response exceeded auto-compact threshold."
        return "Trigger: manual — via /compact command."
    except Exception:  # pylint: disable=broad-exception-caught
        return "Trigger: compaction requested."


def build_llm_compact_context(
    _session: Session,
    message: Message,
    response=None,
    parts=None,
    compact_attempt: int = 0,
    idle_trigger: bool = False,
    trigger: str | None = None,
    prompt_tokens: int | None = None,
    auto_limit: int | None = None,
    **kwargs,
) -> dict:

    from runtime.history_limiter import (
        estimate_entries_tokens,
        find_compaction_boundary,
        idle_seconds,
        walk_compaction_entries,
    )

    # Query-free: compute the newest message to compact from the message
    # chain, so the compaction fork only summarizes the old (compacted) range.
    boundary = find_compaction_boundary(_session, _session.get_last_message())
    if not boundary:
        return dict(response=response, parts=parts, message=message, **kwargs)

    if idle_trigger:
        # Re-verify at run time: a turn may have started (or settings may
        # have changed) between the tick's dispatch and this run.  A stale
        # trigger passes through quietly — same shape as "nothing to
        # compact" — before any side effect (no INFO, no fork).
        idle_s = _session.auto_compact_idle_seconds or 0
        min_tokens = _session.auto_compact_min_tokens or 0
        last_message = _session.get_last_message()
        if (
            idle_s <= 0
            or min_tokens <= 0
            or (idle_seconds(_session) or 0) < idle_s
            or estimate_entries_tokens(walk_compaction_entries(_session, last_message)) < min_tokens
        ):
            return dict(response=response, parts=parts, message=message, **kwargs)

    
    extra = f" Attempt {compact_attempt+1}" if compact_attempt else ""
    reason = _describe_trigger(
        _session,
        trigger=trigger,
        idle_trigger=idle_trigger,
        response=response,
        prompt_tokens_hint=prompt_tokens,
        auto_limit_hint=auto_limit,
    )
    _session.add_user_message(
        {"role": MessageRole.INFO, "message_type": MessageType.INFO, "content": "Compaction started — summarizing older messages to save context. " + reason + extra},
        execute_turn=False,
    )

    if not _session.agent.get_version_model():
        return {"error": "Current agent version not found"}

    # Attempt suffix: SessionModel is get_or_create'd by name, so a retry
    # within the same second must not reuse the dead fork's session.
    session_name = f"p{_session.model.pk}:compaction:{datetime.now().strftime('%Y.%m.%d-%H:%M:%S')}"
    if compact_attempt:
        session_name += f":a{compact_attempt}"

    # The compaction fork carries the same (oversized) context that triggered
    # *this* compaction — so it would immediately exceed the auto-compact
    # limit itself and spawn yet another compaction fork (infinite chain).
    # Fork off the inherited session settings but pin auto_compact_max_tokens
    # to 0.  Also pin auto_compact_idle_seconds to 0: the fork must never
    # idle-compact itself while it works through the oversized context.
    # Also pin tool_call_allowlist to ["final_result"]: the advertised tools
    # stay identical (KV/prompt cache preserved), but any other attempted
    # call aborts the fork instead of letting it wander the old task — the
    # parent then reforks cache-hot.
    child_session = _session.fork(
        name=session_name,
        description=f"Session compaction for {_session.name} at {datetime.now().strftime('%Y.%m.%d-%H:%M:%S')}",
        session_type=SessionType.SUBTASK_COMPACT,
        anchor=boundary,
        auto_compact_max_tokens=0,
        auto_compact_idle_seconds=0,
        tool_call_allowlist=["final_result"],
    )
    compact_result = child_session.add_user_message(
        [
            {
                "role": MessageRole.USER,
                "message_type": MessageType.SYSTEM_NOTICE,
                "content": "<SYSTEM NOTICE> IMPORTANT: Context window is running low, the conversation or actions above have been STOPPED and switched to a session compaction agent.  </SYSTEM NOTICE>",
            },
            {
                "role": MessageRole.ASSISTANT,
                "message_type": MessageType.ASSISTANT_MESSAGE,
                "content": "Confirmed, awaiting compaction instructions.",
            },
            {
                "role": MessageRole.USER,
                "message_type": MessageType.SYSTEM_NOTICE,
                "message": _COMPACTION_SYSTEM_PROMPT,
            },
        ]
    )
    return dict(
        child_session_pk=child_session.model.pk,
        boundary_pk=boundary.pk,
        compact_attempt=compact_attempt,
        result=compact_result,
        response=response,
        parts=parts,
        trigger=trigger,
        idle_trigger=idle_trigger,
        **kwargs,
    )
     
