import traceback
from registry.task_decorators import task
from runtime.agents.session import Session
from server.models.settings import AgentToolCallSyntax
from server.models.message import Message
from server.models.queries.query import Query


@task()
def create_query(session: Session, message: Message) -> Query:
    from server.models.queries.query_message import QueryMessage
    from server.models.queries.query_message_part import QueryMessagePart
    from server.history_limiter import HistoryLimiter
    from server.models.content import GenericContent
    from jinja2 import Template

    try:
        query = Query.objects.create(
            session_version = session.get_version_model(),
            trigger_message = message,
        )

        # System Prompt
        if session.system_prompt:
            query.add_message(role = "system", content = {}, content_template = session.system_prompt )
          
        # Inject Tool Definitions if CUSTOM syntax is used
        if session.tool_call_syntax == AgentToolCallSyntax.CUSTOM:
            query_message, query_message_part = query.add_message(role = "system", content = 'Available Tools (use syntax [call:tool_name(arg=val)]):\n')
            for toolname in session.toolNames:
                tdefs = getattr(session, toolname)
                query_message.add_message_part(
                    content = GenericContent.from_text(f"Tool: {tdef.name}\nDescription: {tdef.description}\nSchema: {json.dumps(tdef.function_schema)}\n"),
                )

        print("FOOOOOooooo", message)
        # 2. Conversation History
        conversation_messages = session.model.messages.filter(pk__lte=message.pk, hide_from_context=False).order_by('-created_at')[:session.max_history_messages + 1]
        # Sort chronological
        print(conversation_messages)
        all_entries = list(conversation_messages) # sorted(conversation_messages, key=lambda x: -x.created_at if hasattr(x, "created_at") else -x.updated_at)
        print("all_entriesall_entriesall_entries", all_entries)
        # TODO: Track all loaded paths for HistoryLimiter or similar
        all_loaded_paths = set()
        limiter = HistoryLimiter(session, all_entries, all_loaded_paths)

        cmessages = []
        for entry in all_entries:
                msg_parts = []
                for part in entry.parts.all():
                    msg_parts.append(QueryMessagePart(
                        message=entry,
                        message_part=part,
                        tags=["ChatMessage", f"{entry.role}"],
                        content_type=part.content_type,
                    ))

                tool_calls = [tc for tc in entry.tool_calls.all() if not limiter.is_tool_call_limited(tc, entry)]
                tool_responses = [x for x in [tc.taskcall_result_run for tc in tool_calls] if x]

                if tool_responses:
                    for tool_response in tool_responses:
                        qmsg = QueryMessage.objects.create(role="tool", query=query, message=entry, tool_response=tool_response)
                        cmessages.append(qmsg)

                if msg_parts or tool_calls:
                    print("query", query)
                    qmsg = QueryMessage.objects.create(role=entry.role, query=query, message=entry)
                    qmsg.tool_calls.set(tool_calls)
                    for i, msg_part in enumerate(msg_parts):
                        msg_part.query_message = qmsg
                        msg_part.index = i
                        msg_part.save()
                    cmessages.append(qmsg)
                    if limiter.is_general_message_limited('messages_dont_warn_forget', entry):
                        qmsg.content_prefix = GenericContent.from_text('@@@TO_BE_FORGOTTEN@@@')
                        qmsg.save()

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
        DebugLogEntry.objects.create(session=session.model, event='exception', data={"exception": traceback.format_exc()})
        raise
