"""
Saves the assistant's response message, links tool calls, and decides
whether to continue the agent loop or end the turn.

Decision logic:
  - final_result called? -> stop (return message)
  - Max turns reached? -> stop (return message)
  - Max unattended turns reached? -> stop (return message)
  - Root task has cross-session parent still waiting? -> requires final_result
    (text-only without final_result continues loop)
  - Otherwise (no tool calls, text only) -> stop (return message)
"""

from __future__ import annotations

import re
from typing import Any

from runtime.session.session import Session
from server.models.enums.message_enums import MessageContentType, MessagePartType, MessageRole
from server.models.enums.session_enums import SessionType
from server.models.message import Message
from server.models.queries.response import Response
from server.models.enums.task_enums import TaskRunStatus


def _is_subtask_execution(_session: Session) -> bool:
    """Return whether this is a single-use subtask session (delegate/fork).

    Uses the ``session_type`` classification set at session creation. Falls
    back to the legacy parent-awaiting heuristic for sessions recorded before
    ``session_type`` was populated, so a subtask never skips ``final_result``.
    """
    return _session.session_type in (
        SessionType.SUBTASK_DELEGATE,
        SessionType.SUBTASK_FORK,
    )


def _looks_like_markdown(content: str) -> bool:
    """Heuristic: does the assistant text look like a formatted markdown answer?

    Counts structural markdown markers (headings, list items, code fences,
    tables, blockquotes, bold, horizontal rules). A formatted final answer
    usually carries several of these; a plain sentence mid-task carries none.
    """
    if not content or not content.strip():
        return False
    markers = 0
    has_heading = False
    has_code_fence = False
    for line in content.strip().splitlines():
        s = line.strip()
        if re.match(r"^#{1,6}\s", s):
            has_heading = True
            markers += 1
        elif re.match(r"^```", s):
            has_code_fence = True
            markers += 1
        elif re.match(r"^([-*+])\s", s) or re.match(r"^\d{1,3}[.)]\s", s):
            markers += 1
        elif re.match(r"^\|.*\|$", s):
            markers += 1
        elif s.startswith("> ") or s == "---":
            markers += 1
        elif re.search(r"\*\*[^*]+\*\*", s):
            markers += 1
    if has_heading or has_code_fence:
        return True
    return markers >= 2


def _mark_subsession_complete(_session: Session) -> None:
    """A subsession that called ``final_result`` is done — mark it inactive.

    Main (parentless) sessions stay active; only child sessions are
    deactivated so the sidebar and ``list_subsessions`` can drop them once
    they fall out of the recent window.
    """
    if not _is_subtask_execution(_session):
        return
    from django.utils import timezone
    from runtime.events import publish_model_event
    from server.models.sessions.session import SessionModel

    SessionModel.objects.filter(pk=_session.model.pk).update(
        is_active=False,
        last_active_at=timezone.now(),
    )
    _session.model.is_active = False
    publish_model_event(_session.model, "update")


def decide_next_step(_session: Session, response: Response, parts: list[dict[str, Any]], message: Message, **kwargs: Any) -> Message:
    _session.count_turn()
    _session.count_unattended_turn()

    if _session.max_turns and _session.current_turn_count >= _session.max_turns:
        return message

    if _session.max_unattended_turns and _session.current_unattended_turn_count >= _session.max_unattended_turns:
        return message

    if kwargs.get("has_final_result"):
        _mark_subsession_complete(_session)
        return message


    MAX_NO_TOOL_ASSISTANT_TURNS = 3
    warn_no_toolcall_loop = True
    no_tool_turn_count = 0
    pmessage = message
    for _ in range(MAX_NO_TOOL_ASSISTANT_TURNS):
        if not pmessage or (pmessage.role != MessageRole.ASSISTANT and pmessage.role != MessageRole.TOOL) or (pmessage.response and pmessage.response.tool_calls):
            warn_no_toolcall_loop = False
            break
        no_tool_turn_count += 1
        pmessage = pmessage.prev_message

    if warn_no_toolcall_loop:
        prev_message = message
        sv = _session.get_version_model()
        message = Message.objects.create(
            role=MessageRole.USER,
            session=sv.session,
            session_version=sv,
            prev_message=prev_message,
        )
        hint_prompt = (
            f"<SYSTEM NOTICE>You have responded {no_tool_turn_count} times in a row without using any tools. "
            "If your task is complete, call final_result(content='your answer') to finish. "
            "If you need to continue working, use a tool in your next response.</SYSTEM NOTICE>"
        )

        message.add_part(
            type=MessagePartType.MESSAGE,
            content_type=MessageContentType.TEXT,
            content=hint_prompt,
        )

    if not _is_subtask_execution(_session) and not any(True for part in parts if "tool_call" in part) and any(True for part in parts if part["type"] == MessagePartType.MESSAGE):
        message_parts = [ part for part in parts if part["type"] == MessagePartType.MESSAGE]
        last_content = str(message_parts[-1].get("content", "")).strip()
        if last_content.endswith("?"): # the agent ended with a question, return to user
            return message
        all_content = "\n".join(str(part.get("content", "")) for part in message_parts).strip()
        if _looks_like_markdown(all_content): # the result is markdown formatted, return to user
            return message



    return _session.get_task("process_turn").delay(message=message)
