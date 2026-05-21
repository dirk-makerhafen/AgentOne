"""
Assembles the LLM context — system prompt, tool definitions, conversation history.
Creates a Query model that holds the full request to be sent to the API.
"""

import json
import traceback
from runtime.agents.session import Session
from server.models.enums.message_enums import MessageContentType, MessagePartType
from server.models.settings import AgentToolCallSyntax
from server.models.message import Message, MessagePart
from server.models.queries.query import Query
from server.models.queries.query_message import QueryMessage
from server.models.queries.query_message_part import QueryMessagePart
from server.history_limiter import HistoryLimiter
from server.models.content import GenericContent

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
        A Query model instance, ready for call_llm to_openai_message and send.
    """


    try:
        query = Query.objects.create(session_version=session.get_version_model(), trigger_message=message)

        # SYSTEM PROMPT
        if session.system_prompt:
            query.add_message(role = "system", content_type=MessageContentType.TEMPLATE , content =  session.system_prompt, template_data = {})

        # CUSTOM TOOLS
        if session.tool_call_syntax == AgentToolCallSyntax.CUSTOM:
            allowed_tools = list(session.allowedTools)
            if allowed_tools:
                tools_msg = "Available Tools (use syntax [call:tool_name(arg=val)]):\n"
                query_message = query.add_message(role = "system", content_type=MessageContentType.TEXT, content = tools_msg)
                for tool in allowed_tools:
                    if not tool.task_definition:
                        raise Exception("No task_definition should never happen")
                    query_message.add_part(
                        content_type = MessageContentType.TEXT,
                        content = f"Tool: {tool.task_definition.name}\nDescription: {tool.description}\nSchema: {json.dumps(tool.function_schema)}\n",
                    )

        # Load and assemble conversation history
        messages:list[Message] = session.model.messages.filter(pk__lte=message.pk, hide_from_context=False).order_by("-created_at")[:session.max_history_messages + 1]
        limiter = HistoryLimiter(session, messages)

        cmessages = []
        for message in messages:
            query_message_parts = []
            for part in message.parts.all():
                part: MessagePart
                if part.type == MessagePartType.REASONING:
                    continue
                if part.type == MessagePartType.TOOLCALL and part.tool_call:
                    if limiter.is_tool_call_limited(part.tool_call, message):
                        continue
                query_message_parts.append(QueryMessagePart(source_message_part = part, tags = ["ChatMessage", f"{message.role}"]))

            tool_call_parts = []
            for query_message_part in query_message_parts:
                if query_message_part.source_message_part and query_message_part.source_message_part.tool_call:
                    tool_call_parts.append(query_message_part.source_message_part)
            
            if tool_call_parts:
                for tool_call_part in tool_call_parts:
                    qmsg = QueryMessage.objects.create(role = "tool", query = query, source_message=message)
                    qmsg.add_part(source_message_part=tool_call_part)
                    cmessages.append(qmsg)

            if query_message_parts or tool_call_parts:
                query_message = QueryMessage.objects.create(role = message.role, query = query, source_message = message)
                for i, query_message_part in enumerate(query_message_parts):   # Save query parts from above
                    query_message_part.query_message = query_message
                    query_message_part.save()
                cmessages.append(query_message)
                if limiter.is_general_message_limited("messages_dont_warn_forget", message):
                    query_message.content_prefix = GenericContent.from_text("@@@TO_BE_FORGOTTEN@@@")
                    query_message.save()

        # Assign sequential indices to messages
        messages = reversed(cmessages)
        for index, message in enumerate(messages):
            message.save()
            #if hasattr(message, "_tool_calls"):
            #    for tc in message.tool_calls.all():
            #        message.tool_calls.add(tc)

        return query

    except Exception:
        from server.models.debug_log_entry import DebugLogEntry
        DebugLogEntry.objects.create(session = session.model, event = "exception", data = {"exception": traceback.format_exc()})
        raise
