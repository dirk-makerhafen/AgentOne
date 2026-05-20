"""
Dispatches tool calls via BoundTask and records the resulting AgentTaskCall objects.

Receives the dict from parse_llm_response and enriches it with task_calls
so that decide_next_step can link them to the assistant message.
"""

from ast import Dict
from typing import TYPE_CHECKING, NotRequired, TypedDict

from server.models.message import Message


from server.models.queries.response import Response
from runtime.agents.session import Session

    
def ingest_assistant_message(session: Session, response: Response, parts: list[dict]) -> dict:
    """
    For each normalized tool call, create a BoundTask and dispatch it.

    Skips tools not in the session's allowedToolNames. Each dispatched
    call is appended to parsed["task_calls"] as an AgentTaskCall.

    Args:
        session: The active agent session.
        response: The Response model returned by call_llm.
        parts:  list from parse_llm_response of Parts
            Parts is dict with minimal keys:
                type: message, reasoning, toolcall
                content_type: text|image|template|json
                content: str|dict
            In case Part.content_type is template the following keys are also needed:
                template_data: dict
            if case Part.type is "toolcall":
                tool_call: ToolCall

    Returns:
        The same dict enriched with a "task_calls" key — a list of
        AgentTaskCall objects that the framework will execute and resolve.
    """


    prev_message = session.get_messages().filter(next_messages=None).last()

    message = Message.objects.create(
        session_version = session.get_version_model(),
        response = response,
        role = "assistant",
        prev_message = prev_message,
    )
    
    for part in parts:
        if part["type"] == "toolcall":
            # start tool calls 
            tool_name = part["content"]["name"]
            tool_args = part["content"]["arguments"]
            bound_task = session.get_tool(tool_name)
            if bound_task:
                part["tool_call"] = bound_task.delay(**tool_args)
                
        message.add_part(
            type = part["type"],
            content_type = part["content_type"],
            content =  part["content"],
            template_data =  part.get("template_data", None),
            tool_call = part.get("tool_call", None),
        )

    return dict(
        response = response,
        parts = parts,
        message = message
    )
   