

# HANDLE SLASH COMMANDS
from runtime.agents.agent import Agent
from runtime.agents.session import Session
from server.models.content import GenericContent
from server.models.message import Message, MessagePart
from server.models.enums.message_enums import MessageContentType


def has_slash_command(session: Session, name:str):
    taskdefinition = session.commands().filter(trigger=name).first()
    if not taskdefinition:
        taskdefinition = session.commands().filter(name=name).first()
    if not taskdefinition:
        taskdefinition = session.tools().filter(name=name).first()
    if not taskdefinition:
        taskdefinition = session.tasks().filter(name=name).first()
    return taskdefinition is not None
        

def run_slash_command(session: Session, name:str, args:list, kwargs:dict):
    taskdefinition = session.commands().filter(trigger=name).first()
    if not taskdefinition:
        taskdefinition = session.commands().filter(name=name).first()
    if not taskdefinition:
        taskdefinition = session.tools().filter(name=name).first()
    if not taskdefinition:
        taskdefinition = session.tasks().filter(name=name).first()

    if taskdefinition:
        # Schedule command Tool Call add toolcall to user message
        command_tool_call = session.__getattribute__(name).delay(*args, **kwargs)
        conversation_msg.tool_calls.add(command_tool_call)
    return session.handle_command_response.delay(command_response=command_tool_call)


def finish_slash_command(agent: Agent, command_response):
    conv_msg = Message.objects.create(role = "assistant", session_version = session.session_version)
    MessagePart.objects.create(
        message=conv_msg,
        #content=GenericContent.from_data(AgentTaskCall.callargs_to_json(command_response)[0]),
        content=GenericContent.from_data(command_response),
        content_type=MessageContentType.TEXT,
    )
    return conv_msg