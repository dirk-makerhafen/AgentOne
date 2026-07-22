"""
Handle slash commands from the user (e.g. /help, /reset).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from runtime.session.session import Session
from server.models.content import GenericContent
from server.models.message import Message, MessagePart
from server.models.enums.message_enums import MessageContentType, MessagePartType


def process_slashcommand(session: Session, name: str, **kwargs: Any) -> dict[str, Any]:
    """
    Look up and dispatch a slash command, recording a user Message.

    Args:
        session: The active agent session.
        name:    The command name (without leading slash).
        **kwargs: Arguments forwarded to the command's BoundTask.

    Returns:
        A dict with keys:
            message      (Message)   -- The user Message recording this command.
            tool_reponse (AgentTaskCall) -- The dispatched task call.
    """
    bound_task = session.get_command(name)
    if not bound_task:
        raise Exception(f"Task {name} not found")

    session_version = session.get_version_model()
    message = Message.objects.create(role="user", session_version=session_version)

    task_call = bound_task.delay(**kwargs)

    message.add_part(
        type=MessagePartType.TOOLCALL,
        content_type=MessageContentType.JSON,
        content=f"/{name} {json.dumps(kwargs)}",
        tool_call=task_call,
    )

    from runtime.events import publish_model_event
    publish_model_event(message, "create")

    return dict(message=message, tool_reponse=task_call)


def handle_slashcommand_response(
    session: Session, message: Message, tool_reponse: Any
) -> Any:
    """
    Create an assistant Message wrapping the slash command result.

    Args:
        session:      The active agent session.
        message:      The original user Message for the slash command.
        tool_reponse: The result returned by the dispatched command task.

    Returns:
        The raw tool response value.
    """
    conv_msg = Message.objects.create(
        role="assistant", session_version=session.get_version_model()
    )

    def _serialize_result(obj: Any) -> Any:
        """JSON-serialise a tool result, handling Message / Path model references."""
        if obj is None or isinstance(obj, (str, int, float, bool)):
            return obj
        if isinstance(obj, dict):
            return {k: _serialize_result(v) for k, v in obj.items()}
        if isinstance(obj, (list, set, tuple)):
            return type(obj)(_serialize_result(item) for item in obj)
        if isinstance(obj, Message):
            return "".join(
                part.to_string()
                for part in obj.parts.filter(type=MessagePartType.MESSAGE)
            )
        if isinstance(obj, Path):
            return obj.as_posix()
        raise TypeError(f"Cannot serialize {type(obj).__name__}")

    MessagePart.objects.create(
        message=conv_msg,
        content=GenericContent.from_data(_serialize_result(tool_reponse)),
        content_type=MessageContentType.JSON,
    )

    from runtime.events import publish_model_event
    publish_model_event(conv_msg, "create")

    return tool_reponse
