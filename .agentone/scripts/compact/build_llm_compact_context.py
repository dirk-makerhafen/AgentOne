from __future__ import annotations
from typing import List

from runtime.session.session import Session
from server.models.enums.message_enums import MessageRole
from server.models.message import Message
from server.models.queries.query import Query
from server.models.queries.query_message import QueryMessage
import time
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
<SYSTEM NOTICE>"""


def build_llm_compact_context(
    _session: Session,
    message: Message,
    response=None,
    parts=None,
    compact_attempt: int = 0,
    idle_trigger: bool = False,
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

    
    
    # Session hooks (``pre_compact`` event): fired once per compaction —
    # retries (compact_attempt > 0) do not refire. The fork anchors at the
    # current tail, so it sees the doomed range with no boundary surgery.
    if not compact_attempt:
        try:
            from runtime.hooks import maybe_fire_hooks

            tail = _session.get_last_message()
            maybe_fire_hooks(
                _session,
                "pre_compact",
                {
                    "trigger": "idle" if idle_trigger else "auto",
                    "anchor_message": tail.pk if tail is not None else None,
                    "compact_attempt": compact_attempt,
                },
            )
        except Exception as e:  # pylint: disable=broad-exception-caught
            print(f"[hooks] error firing pre_compact hooks: {e}")
    extra = f" Attempt {compact_attempt+1}" if compact_attempt else ""
    _session.add_user_message(
        {"role": MessageRole.INFO, "content": "Compaction started — summarizing older messages to save context." + extra},
        execute_turn=False,
    )

    if not _session.agent.get_version_model():
        return {"error": "Current agent version not found"}

    # Attempt suffix: SessionModel is get_or_create'd by name, so a retry
    # within the same second must not reuse the dead fork's session.
    session_name = f"p{_session.model.pk}:compaction:{int(time.time())}"
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
        description=f"Session compaction for {_session.name} at {int(time.time())}",
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
                "content": "<SYSTEM NOTICE> IMPORTANT: Context window is running low, the conversation or actions above have been STOPPED and switched to a session compaction agent.  </SYSTEM NOTICE>",
            },
            {
                "role": MessageRole.ASSISTANT,
                "content": "Confirmed, awaiting compaction instructions.",
            },
            _COMPACTION_SYSTEM_PROMPT,
        ]
    )
    return dict(
        child_session_pk=child_session.model.pk,
        boundary_pk=boundary.pk,
        compact_attempt=compact_attempt,
        result=compact_result,
        response=response,
        parts=parts,
        **kwargs,
    )
     
