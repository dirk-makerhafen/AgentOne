"""
Dispatches tool calls via BoundTask and records the resulting AgentTaskCall objects.

Receives the dict from extract_tool_calls and enriches it with task_calls
so that decide_next_step can link them to the assistant message.
"""

from runtime.agents.bound_task import BoundTask
from runtime.agents.session import Session


def execute_tools(session: Session, parsed: dict) -> dict:
    """
    For each normalized tool call, create a BoundTask and dispatch it.

    Skips tools not in the session's allowedToolNames. Each dispatched
    call is appended to parsed["task_calls"] as an AgentTaskCall.

    Args:
        session: The active agent session.
        parsed:  Dict from extract_tool_calls with keys:
                 content, reasoning, tool_calls.

    Returns:
        The same dict enriched with a "task_calls" key — a list of
        AgentTaskCall objects that the framework will execute and resolve.
    """
    tool_calls = parsed.get("tool_calls", [])
    task_calls = []
    for tc in tool_calls:
        tool_name = tc["name"]
        kwargs = tc["arguments"]
        if tool_name not in session.allowedToolNames:
            continue

        task_definition = session.agent.get_allowed_tool(tool_name)
        if not task_definition:
            continue

        bound_task = BoundTask(
            session_version=session.get_version_model(),
            task_definition_version=task_definition,
        )
        task_call = bound_task.apply_async(kwargs=kwargs)
        task_calls.append(task_call)

    parsed["task_calls"] = task_calls
    return parsed
