

# HANDLE SLASH COMMANDS
import json
from runtime.agents.agent import Agent
from runtime.agents.session import Session
from server.models.content import GenericContent
from server.models.message import Message, MessagePart
from server.models.enums.message_enums import MessageContentType, MessagePartType


def process_slashcommand(session: Session, name:str, **kwargs):
    bound_task = session.get_command(name)
    if not bound_task:
        raise Exception(f"Task {name} not found")
    
    session_version = session.get_version_model()
    message = Message.objects.create(role = "user", session_version = session_version)

    task_call = bound_task.delay(**kwargs)

    message.add_part(
        type = MessagePartType.TOOLCALL,
        content_type = MessageContentType.JSON,
        content = f"/{name} {json.dumps(kwargs)}", 
        tool_call = task_call,
    )

    return dict(message = message, tool_reponse = task_call)


def handle_slashcommand_response(session: Session, message:Message, tool_reponse):
    conv_msg = Message.objects.create(role = "assistant", session_version = session.get_version_model())
    MessagePart.objects.create(message = conv_msg, content = GenericContent.from_data(tool_reponse), content_type = MessageContentType.JSON)
    return tool_reponse