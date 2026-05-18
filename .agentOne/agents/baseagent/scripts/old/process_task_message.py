from registry.task_decorators import task
from runtime.agents.session import Session
from server.models.content import GenericContent
from server.models.message import Message, MessagePart
from server.models.enums.message_enums import MessageContentType
# old
@task()
def process_task_message(session: Session, **kwargs) -> Message:
    conversationMessage = Message.objects.create(role="user", session_version=session.get_version_model())
    MessagePart.objects.create(
        content = GenericContent.from_data(kwargs),
        content_type = MessageContentType.TEMPLATE,
        content_template = session.task_prompt,
        message = conversationMessage,
    )
    return session.process_message(conversationMessage=conversationMessage)
    