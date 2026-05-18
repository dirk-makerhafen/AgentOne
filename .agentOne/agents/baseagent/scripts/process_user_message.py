from runtime.agents.session import Session
from server.models.content import GenericContent
from server.models.message import Message, MessagePart
from server.models.enums.message_enums import MessageContentType


def process_user_message(session: Session, message :str, parts) -> Message:
    if parts is None and message is not None:
        parts = [{"content": message, "type": "TEXT"}]
    if not parts:
        raise Exception("No message or message parts provided")

    session.reset_unattended_turn_count()
    session_version = session.get_version_model()
    prev_message = session_version.related_messages.filter(next_messages=None).last()
    
    message = Message.objects.create(
        role = "user", 
        session_version = session_version, 
        prev_message = prev_message
    )
    for part in parts:
        MessagePart.objects.create(
            content = GenericContent.from_text(part["content"]),
            content_type = MessageContentType.TEXT,
            message = message,
        )
    
    return process_message(message=message)



    query = session.create_query.delay(message=message)
    response = session.execute_query.delay(query=query)
    response_parsed = session.parse_response.delay(response=response)
    response_content = session.handle_assistant_message.delay(response=response, parsed_response_data=response_parsed)
    return response_content
