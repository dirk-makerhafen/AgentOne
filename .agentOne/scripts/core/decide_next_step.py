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

from typing import Any

from runtime.session.session import Session
from server.models.enums.message_enums import MessageContentType, MessagePartType, MessageRole
from server.models.message import Message
from server.models.queries.response import Response
from server.models.enums.task_enums import TaskRunStatus


def _is_subtask_execution(_session: Session) -> bool:
    """Check if the current turn is a subtask being awaited by a parent session."""
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


def decide_next_step(_session: Session, response: Response, parts: list[dict[str, Any]], message: Message, **kwargs: Any) -> Message:
    _session.count_turn()
    _session.count_unattended_turn()

    if _session.max_turns and _session.current_turn_count >= _session.max_turns:
        return message

    if _session.max_unattended_turns and _session.current_unattended_turn_count >= _session.max_unattended_turns:
        return message

    if kwargs.get("has_final_result"):
        return message


    MAX_NO_TOOL_ASSISTANT_TURNS = 5
    warn_no_toolcall_loop = True
    pmessage = message
    for _ in range(MAX_NO_TOOL_ASSISTANT_TURNS):
        if not pmessage or (pmessage.role != MessageRole.ASSISTANT and pmessage.role != MessageRole.TOOL) or (pmessage.response and pmessage.response.tool_calls):
            warn_no_toolcall_loop = False
            break
        pmessage = pmessage.prev_message

    if warn_no_toolcall_loop:
        prev_message = message
        sv = _session.get_version_model()
        message = Message.objects.create(
            role= MessageRole.USER,
            session=sv.session,
            session_version=sv,
            prev_message=prev_message,
        )
        hint_prompt = f"<SYSTEM HINT>Possible looping or inefficient behavior detected. You did multiple turns without any tool calling. Take a step back and correct if needed, or call final_result(message='..your final result message..') to finish and return your results.</SYSTEM HINT>"

        message.add_part(
            type=MessagePartType.MESSAGE,
            content_type=MessageContentType.TEXT,
            content=hint_prompt,
        )

    #if _is_subtask_execution(_session):
    #    return _session.get_task("process_turn").delay(message=message)

    #if not any(True for part in parts if "tool_call" in part) and any(True for part in parts if part["type"] == MessagePartType.MESSAGE):
    #    return message

    return _session.get_task("process_turn").delay(message=message)
