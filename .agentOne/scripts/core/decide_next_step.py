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
    if _session.session_type in (
        SessionType.SUBTASK_DELEGATE,
        SessionType.SUBTASK_FORK,
    ):
        return True
    current_taskrun = getattr(_session, '_current_taskrun', None)
    if not current_taskrun or not current_taskrun.agent_task_call_id:
        return False
    root = current_taskrun.agent_task_call.session_root_task
    if not root or not root.parent_taskrun_id:
        return False
    parent = root.parent_taskrun
    if parent.session_version.session_id != _session.model.pk and parent.status == TaskRunStatus.WAITING_RESULTTASKS:
        return True
    return False


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


def decide_next_step(_session: Session, response: Response, parts: list[dict[str, Any]], message: Message, **kwargs: Any) -> Message:
    _session.count_turn()
    _session.count_unattended_turn()

    if _session.max_turns and _session.current_turn_count >= _session.max_turns:
        return message

    if _session.max_unattended_turns and _session.current_unattended_turn_count >= _session.max_unattended_turns:
        return message

    if kwargs.get("has_final_result"):
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
