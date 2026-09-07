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
import json
from runtime.session.session import Session
from server.models.enums.message_enums import MessageContentType, MessagePartType, MessageRole
from server.models.enums.session_enums import SessionType
from server.models.message import Message
from server.models.queries.response import Response
from server.models.enums.task_enums import TaskRunStatus



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


def _pop_next_todo_message(_session: Session, message: Message) -> tuple[Message | None , Any]:
    """If todo auto-processing is on and items remain, inject the next one.

    Called when the current task just finished (``final_result`` was seen).
    The list is event-sourced from the ``todolist_action`` anchor history;
    the pop is recorded via an async dispatch and the oldest pending item
    read just before is wrapped as a USER message, so the loop continues
    with the next item instead of returning to the user.  The auto flag is
    user-controlled (session settings) and never settable by the agent.

    Returns the new message, or *None* when there is nothing to do (auto
    off, list empty, subtask session, anchor unavailable).  Kept
    dependency-free on purpose: scripts run from isolated runtime folders,
    so the state is (re-)read inline instead of importing the todo group.
    """



    if not _session._get_session_setting("todo_auto_process"):
        return None
     
    items = _load_todolist_items(_session)
    pending = [it for it in items if it.get("status") == "pending"]
    if not pending:
        return None
    first = pending[0]
    remaining = len(pending) - 1


    action_task = _session.get_task("todolist_action")
    store_function_response = action_task.delay(
        action="update",
        task_id=first.get("task_id"),
        text=first.get("text"),
        status="in_progress",
        **(dict(depends_on=first.get("depends_on")) if first.get("depends_on") else {}),
    )
    todolist_task_result = _session.get_task("todolist_action_response").delay(store_function_response=store_function_response)

    sv = _session.get_version_model()
    next_message = Message.objects.create(
        role=MessageRole.USER,
        session=sv.session,
        session_version=sv,
        prev_message=message,
    )
    next_message.add_part(
        type=MessagePartType.MESSAGE,
        content_type=MessageContentType.TEXT,
        content=(
            f"<SYSTEM NOTICE>Todo list auto-processing is enabled."
            f"Next item: {json.dumps(first)}\n"
            f"({remaining} remaining after this one)\n"
            f"Work on this now. When done with this task, call final_result(content='...') "
            f"and the next task will be fed automatically from the todo list</SYSTEM NOTICE>"
        ),
    )
    from runtime.events import publish_model_event
    publish_model_event(next_message, "create")
    return next_message, todolist_task_result


def decide_next_step(_session: Session, response: Response, parts: list[dict[str, Any]], message: Message, **kwargs: Any) -> Message:
    violated = kwargs.get("tool_allowlist_violated")
    if violated:
        # Strict allowlist breach (see SettingsModel.tool_call_allowlist):
        # the off-task session (e.g. a compaction fork that kept working
        # instead of summarizing) ends here — no turn counted, no
        # process_turn dispatched.  The parent sees no usable result and
        # reforks cache-hot.  This deliberately wins over a co-emitted
        # final_result: a mixed response proves the fork is off-task, and a
        # fresh cache-hot fork is cheaper than trusting it.
        _session.set_is_active(False)
        return message

    _session.count_turn()
    _session.count_unattended_turn()
    is_final_result = False

    if _session.max_turns and _session.current_turn_count >= _session.max_turns:
        return message

    if _session.max_unattended_turns and _session.current_unattended_turn_count >= _session.max_unattended_turns:
        return message

    has_tool_calls = any(True for part in parts if "tool_call" in part)
    has_message =  any(True for part in parts if part["type"] == MessagePartType.MESSAGE)

    if kwargs.get("has_final_result"):  # agent did call final_result tool
        is_final_result = True


    elif has_message and not has_tool_calls and _session.session_type in (SessionType.SESSION, SessionType.SUBSESSION, SessionType.SUBTASK_COMPACT):  
        # Heuristic guestimation if session is over
        message_parts = [ part for part in parts if part["type"] == MessagePartType.MESSAGE]
        last_content = str(message_parts[-1].get("content", "")).strip()
        if last_content.endswith("?"): # the agent ended with a question, return to user
            is_final_result = True
        else:
            all_content = "\n".join(str(part.get("content", "")) for part in message_parts).strip()
            if _looks_like_markdown(all_content): # the result is markdown formatted, return to user
                is_final_result = True
 
    if is_final_result:
        # return final result, add new task from todo list of needed/possible
        next_todo = _pop_next_todo_message(_session, message)
        if next_todo is not None:
            next_message, todolist_task_result = next_todo
            _session.get_task("process_turn").delay(message=next_message, todolist_task_result_to_ignore=todolist_task_result) # chain these, process_turn ignores kwargs anyway
        return message


    # Check empty/dumm assistant responses, insert hint if needed
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

    return _session.get_task("process_turn").delay(message=message)
