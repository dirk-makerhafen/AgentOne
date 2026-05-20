"""
Entry point for user messages into the agent loop.
Normalizes raw input into a Message model, then chains into process_turn.
"""

from runtime.agents.session import Session
from server.models.content import GenericContent
from server.models.message import Message, MessagePart
from server.models.enums.message_enums import MessageContentType

'''
:
    list of Parts

    Parts is dict with minimal keys:
        type: message, reasoning, toolcall
        content_type: text|image|template|json
        content: str|dict
    In case Part.content_type is template the following keys are also needed:
        template_data: dict
'''
def ingest_user_message(session: Session, parts) -> Message:
    """
    Normalize user input, persist as a Message, and start the agent loop.

    Called via session.ingest_user_message.delay(message=..., parts=...)
    from the framework when the user sends a chat message.

    Args:
        session:  The active agent session.
        message:  Raw text input (used when parts is None).
        parts:    List of dicts with "content" and "type" keys.

    Returns:
        An AgentTaskCall for process_turn — the framework resolves this
        through the chain until decide_next_step returns the final Message.
    """
    
    session.reset_unattended_turn_count()
    session_version = session.get_version_model()
    prev_message = session.get_messages().filter(next_messages=None).last()

    message = Message.objects.create(
        role = "user",
        session_version = session_version,
        prev_message = prev_message,
    )

    for part in parts:
        message.add_part(
            type = part["type"],
            content_type = part["content_type"],
            content = part["content"],
            template_data = part.get("template_data", None),
            tool_call = part.get("tool_call", None),
        )
       
    return session.get_task("process_turn").delay(message = message)
