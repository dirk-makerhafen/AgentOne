"""
Dispatches tool calls via BoundTask and records the resulting AgentTaskCall objects.

Receives the dict from parse_llm_response and enriches it with task_calls
so that decide_next_step can link them to the assistant message.
"""

from __future__ import annotations

from typing import Any

from server.models.message import Message
from server.models.queries.response import Response
from runtime.session.session import Session


def ingest_assistant_message(
    session: Session, response: Response, parts: list[dict[str, Any]]
) -> dict[str, Any]:
    """
    For each normalized tool call, create a BoundTask and dispatch it.

    Skips tools not in the session's allowedToolNames. Each dispatched
    call is appended to parsed["task_calls"] as an AgentTaskCall.

    Args:
        session:  The active agent session.
        response: The Response model returned by call_llm.
        parts:    List from parse_llm_response of Parts.
                  Each Part is a dict with minimal keys:
                    type, content_type, content
                  If type is "toolcall", also contains a tool_call key.

    Returns:
        The same dict enriched with a "task_calls" key -- a list of
        AgentTaskCall objects that the framework will execute and resolve.
    """

    prev_message = session.get_messages().filter(next_messages=None).last()

    message = Message.objects.create(
        session_version=session.get_version_model(),
        response=response,
        role="assistant",
        prev_message=prev_message,
    )

    for part in parts:
        if part["type"] == "toolcall":
            bound_task = session.get_tool(part["content"]["name"])
            if bound_task:
                part["tool_call"] = bound_task.delay(**part["content"]["arguments"])

        message.add_part(
            type=part["type"],
            content_type=part["content_type"],
            content=part["content"],
            template_data=part.get("template_data", None),
            tool_call=part.get("tool_call", None),
        )

    return dict(
        response=response,
        parts=parts,
        message=message,
    )
