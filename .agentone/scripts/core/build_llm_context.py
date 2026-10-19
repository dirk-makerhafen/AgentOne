"""
Assembles the LLM context — system prompt, tool definitions, conversation history.
Creates a Query model that holds the full request to be sent to the API.
"""

from __future__ import annotations

import json
import traceback
from typing import Any
import datetime
from runtime.session.session import Session
from server.models.enums.message_enums import MessageContentType, MessagePartType, MessageRole, MessageType
from server.models.enums.task_enums import TaskCallStatus
from server.models.settings import AgentToolCallSyntax
from server.models.message import Message, MessagePart
from server.models.queries.query import Query, QueryStatus
from server.models.queries.query_message import QueryMessage
from server.models.queries.query_message_part import QueryMessagePart


def build_llm_context(_session: Session, message: Message, **kwargs: Any) -> Query:
    """
    Build a Query with system prompt, tool schemas, and conversation history.

    Steps:
    1. Create a Query record linked to the triggering message.
    2. Inject the system prompt (if set).
    3. For CUSTOM tool syntax, inject tool definitions as a system message.
    4. Load conversation history up to and including the trigger message, and repack as QueryMessages with correct roles.

    Args:
        _session: The active agent session.
        message: The message that triggered this turn (used as upper bound
                 for history loading).

    Returns:
        A Query model instance, ready for call_llm to_openai_message and send.
    """

    try:
        sv = _session.get_version_model()
        existing = Query.objects.filter(
            session_version=sv,
            status__in=[QueryStatus.WAITING, QueryStatus.ACTIVE],
        ).exists()
        if existing:
            raise RuntimeError(f"Session {sv.pk} already has a WAITING or ACTIVE query - refusing to create a duplicate")
        query = Query.objects.create(
            session=sv.session,
            session_version=sv,
            trigger_message=message,
        )

        # SYSTEM PROMPT
        if _session.system_prompt_chain:
            if _session.inherit_system_prompt and len(_session.system_prompt_chain) > 1:
                # Add each parent prompt as a separate system message (parent first)
                for prompt in _session.system_prompt_chain:
                    query.add_message(
                        role=MessageRole.SYSTEM,
                        content_type=MessageContentType.TEMPLATE,
                        content=prompt,
                        template_data={},
                    )
            else:
                # Single system prompt (default behavior)
                query.add_message(
                    role=MessageRole.SYSTEM,
                    content_type=MessageContentType.TEMPLATE,
                    content=_session.system_prompt,
                    template_data={},
                )

        # ONE-TIME SESSION BOOTSTRAP (replaces per-turn prefix injection).
        # Guidance-file autoload + index, start time, workspace path and the
        # private-folder announcement used to be re-injected here as fresh
        # QueryMessages on every turn, ahead of history — any byte change
        # invalidated the whole prompt-cache (KV-cache) prefix.  They are now
        # persisted once as normal history Messages at the start of the
        # current compaction segment (runtime/session_bootstrap.py), so later
        # turns load frozen bytes via the history walk below and the prefix
        # stays cache-hot.  After a compaction the marker itself carries the
        # repinned content, so this is a no-op there.
        try:
            from runtime.session_bootstrap import ensure_session_bootstrap

            ensure_session_bootstrap(_session, message)
        except Exception:
            from server.models.debug_log_entry import DebugLogEntry

            DebugLogEntry.objects.create(
                session=_session.model,
                event="bootstrap_skip",
                data={"exception": traceback.format_exc()},
            )

        # CUSTOM TOOLS
        if _session.tool_call_syntax == AgentToolCallSyntax.CUSTOM:
            allowed_tools: list[Any] = list(_session.allowedTools)
            if allowed_tools:
                tools_msg = "Available Tools (use syntax [call:tool_name(arg=val)]):\n"
                query_message = query.add_message(role=MessageRole.SYSTEM, content_type=MessageContentType.TEXT, content=tools_msg)
                for tool in allowed_tools:
                    if not tool.task_definition:
                        raise Exception("No task_definition should never happen")
                    query_message.add_part(
                        content_type=MessageContentType.TEXT,
                        content=(
                            f"Tool: {tool.task_definition.name}\n"
                            f"Description: {tool.description}\n"
                            f"Schema: {json.dumps(tool.function_schema)}\n"
                        ),
                    )

        # Walk the prev_message linked list from the trigger message backwards.
        # Stop at the first message with a COMPACTION part (boundary marker).
        # This handles injected compaction messages and forks naturally.
        # Extended phase: when same-session pin_to_context messages exist, keep
        # walking past max_history_messages to collect them (the one-time
        # bootstrap lives at the start of the segment and slides outside the
        # window in long pre-compaction histories).  Pinned bytes are frozen,
        # so the prefix stays cache-hot while guidance is never silently
        # dropped.  Chain order (not pk order) decides positions: bootstraps
        # are spliced at the front after creation, so their pks are newer
        # than their position.  Without pins the walk stays window-bounded as
        # before.  Must never break context assembly.
        messages: list[Message] = []
        pinned_beyond_window: list[Message] = []
        current = message
        try:
            _window = _session.max_history_messages + 1
        except Exception:
            _window = 1
        try:
            _has_pins = Message.objects.filter(
                session_id=sv.session.pk, pin_to_context=True
            ).exists()
        except Exception:
            _has_pins = False
        while current:
            if not current.hide_from_context and current.role != MessageRole.INFO:
                if len(messages) < _window:
                    messages.append(current)
                elif (
                    _has_pins
                    and current.pin_to_context
                    and getattr(current, "session_id", None) == sv.session.pk
                ):
                    pinned_beyond_window.append(current)
                if current.message_type == MessageType.COMPACTION:
                    break
            if len(messages) >= _window and not _has_pins:
                break
            current = current.prev_message
        # `messages` is newest-first; beyond-window pins were met going back,
        # i.e. already newest-first — append at the end (the reversal below
        # restores oldest-first order).
        messages.extend(pinned_beyond_window)
        
        cmessages: list[Any] = []
        fmessages = []
        for message in messages:
            query_message_parts: list[QueryMessagePart] = []
            tool_call_parts = []
            # pk order == part creation order; explicit ORDER BY so prompt
            # bytes are deterministic (undefined order per SQL, esp. MySQL).
            for part in message.parts.order_by("pk"):
                part: MessagePart
                if (_session.aimodel and not _session.aimodel.requires_reasoning_echo) and part.type == MessagePartType.REASONING:
                    continue
                query_message_parts.append(QueryMessagePart(source_message_part=part))
                if part.tool_call and part.tool_call.status == TaskCallStatus.ENDED:
                    tool_call_parts.append(part)
            fmessages.append((message, query_message_parts,tool_call_parts))

        # undo reverse order and assemble
        for fmessage in reversed(fmessages):
            message, query_message_parts, tool_call_parts = fmessage
            if query_message_parts or query_message_parts:
                query_message = QueryMessage.objects.create(role=message.role, query=query, source_message=message)
                for i, query_message_part in enumerate(query_message_parts):
                    query_message_part.query_message = query_message
                    query_message_part.save()
                cmessages.append(query_message)

            if tool_call_parts:
                for tool_call_part in tool_call_parts:
                    qmsg = QueryMessage.objects.create(role="tool", query=query, source_message=message)
                    qmsg.add_part(source_message_part=tool_call_part)
                    cmessages.append(qmsg)

        messages = cmessages
        
        for index, message in enumerate(messages):
            # Internal re-save during context build — no view needs an event.
            message.save(publish=False)

        return query

    except Exception:
        from server.models.debug_log_entry import DebugLogEntry

        DebugLogEntry.objects.create(
            session=_session.model, event="exception", data={"exception": traceback.format_exc()}
        )
        raise
