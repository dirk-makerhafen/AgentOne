"""
Assembles the LLM context — system prompt, tool definitions, conversation history.
Creates a Query model that holds the full request to be sent to the API.
"""

import json
import traceback
from runtime.agents.session import Session
from server.models.enums.message_enums import MessagePartType
from server.models.settings import AgentToolCallSyntax
from server.models.message import Message
from server.models.queries.query import Query


def build_llm_context(session: Session, message: Message) -> Query:
    """
    Build a Query with system prompt, tool schemas, and conversation history.

    Steps:
    1. Create a Query record linked to the triggering message.
    2. Inject the system prompt (if set).
    3. For CUSTOM tool syntax, inject tool definitions as a system message.
    4. Load conversation history up to and including the trigger message, apply HistoryLimiter, and repack as QueryMessages with correct roles.

    Args:
        session: The active agent session.
        message: The message that triggered this turn (used as upper bound
                 for history loading).

    Returns:
        A Query model instance, ready for call_llm to compile and send.
    """
    from server.models.queries.query_message import QueryMessage
    from server.models.queries.query_message_part import QueryMessagePart
    from server.history_limiter import HistoryLimiter
    from server.models.content import GenericContent

    try:
        query = Query.objects.create(
            session_version=session.get_version_model(),
            trigger_message=message,
        )

        if session.system_prompt:
            query.add_message(
                role="system",
                content={},
                content_template=session.system_prompt,
            )

        if session.tool_call_syntax == AgentToolCallSyntax.CUSTOM:
            query_message, query_message_part = query.add_message(
                role="system",
                content="Available Tools (use syntax [call:tool_name(arg=val)]):\n",
            )
            for tool in session.allowedTools:
                query_message.add_message_part(
                    content=GenericContent.from_text(
                        f"Tool: {tool.task_definition.name}\nDescription: {tool.description}\n"
                        f"Schema: {json.dumps(tool.function_schema)}\n"
                    ),
                )

        # Load and assemble conversation history
        conversation_messages = session.model.messages.filter(
            pk__lte=message.pk,
            hide_from_context=False,
        ).order_by("-created_at")[:session.max_history_messages + 1]
        all_entries = list(conversation_messages)
        all_loaded_paths = set()
        limiter = HistoryLimiter(session, all_entries, all_loaded_paths)

        cmessages = []
        for entry in all_entries:
            msg_parts = []
            for part in entry.parts.all():
                if part.type == MessagePartType.REASONING:
                    continue
                msg_parts.append(QueryMessagePart(
                    message=entry,
                    message_part=part,
                    tags=["ChatMessage", f"{entry.role}"],
                    content_type=part.content_type,
                ))

            tool_calls = [
                tc for tc in entry.tool_calls.all()
                if not limiter.is_tool_call_limited(tc, entry)
            ]
            tool_responses = [
                x for x in [tc.taskcall_result_run for tc in tool_calls] if x
            ]

            if tool_responses:
                for tool_response in tool_responses:
                    qmsg = QueryMessage.objects.create(
                        role="tool",
                        query=query,
                        message=entry,
                        tool_response=tool_response,
                    )
                    cmessages.append(qmsg)

            if msg_parts or tool_calls:
                qmsg = QueryMessage.objects.create(
                    role=entry.role,
                    query=query,
                    message=entry,
                )
                qmsg.tool_calls.set(tool_calls)
                for i, msg_part in enumerate(msg_parts):
                    msg_part.query_message = qmsg
                    msg_part.index = i
                    msg_part.save()
                cmessages.append(qmsg)
                if limiter.is_general_message_limited(
                    "messages_dont_warn_forget", entry
                ):
                    qmsg.content_prefix = GenericContent.from_text(
                        "@@@TO_BE_FORGOTTEN@@@"
                    )
                    qmsg.save()

        # Assign sequential indices to messages
        messages = reversed(cmessages)
        for index, message in enumerate(messages):
            message.index = index
            message.save()
            if hasattr(message, "_tool_calls"):
                for tc in message.tool_calls.all():
                    message.tool_calls.add(tc)

        return query

    except Exception:
        from server.models.debug_log_entry import DebugLogEntry
        DebugLogEntry.objects.create(
            session=session.model,
            event="exception",
            data={"exception": traceback.format_exc()},
        )
        raise
