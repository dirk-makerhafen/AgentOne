
from __future__ import annotations

from runtime.session.session import Session
from server.models.enums.message_enums import MessageContentType, MessagePartType


def ingest(_session: Session, message: str | None = None) -> None:
    """
    ingest message into the wiki

    Args:
        _session: The active agent session.
        message: Optional message to ingest

    Returns:
        Nothing
    """
    
    resultmsg = _session.add_user_message(parts=[{'type': MessagePartType.MESSAGE, "content_type": MessageContentType.TEXT, 'content': f"ingest {message}"}])
    verification_result = _session.get_task("verify").delay(message=resultmsg, original_message=message)
    return _session.get_task("ingest_verification").delay(message=verification_result)


def verify(_session: Session, message, original_message: str | None = None) -> None:
    msg = "".join( part.to_string() for part in message.parts.all())
    return _session.get_tool("delegate_task").delay(prompt=f"The following file has been ingested by a subagent: '{original_message}'\nResult: {msg}\n\nVerify that the ingestion was processed correctly. Correct errors.",blocking=True)


def ingest_verification(_session: Session, message) -> None:
    msg = "".join( part.to_string() for part in message.parts.all())
    return _session.add_user_message(parts=[{'type': MessagePartType.MESSAGE, "content_type": MessageContentType.TEXT, 'content': f"An external agent did a verification run of your last operation, here is its result: '{msg}'"}])

