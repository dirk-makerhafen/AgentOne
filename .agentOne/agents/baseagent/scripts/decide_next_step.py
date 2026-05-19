"""
Saves the assistant's response message, links tool calls, and decides
whether to continue the agent loop or end the turn.

If the LLM requested tool calls and limits haven't been reached,
chains back to process_turn for the next iteration.
Otherwise returns the final Message (chain terminates).
"""

from registry.task_decorators import task
from runtime.agents.session import Session
from server.models.message import Message
from server.models.queries.response import Response


def decide_next_step(session: Session, response: Response, parsed: dict) -> Message:
    """
    Persist the assistant message and determine if the loop should continue.

    Decision logic:
        - Max turns reached? → stop (return message)
        - Max unattended turns reached? → stop
        - No tool calls in the response? → stop (conversation turn finished)
        - Otherwise → continue: chain back to process_turn.delay()

    Args:
        session:  The active agent session.
        response: The Response from call_llm.
        parsed:   Enriched dict from execute_tools with keys:
                  content, reasoning, tool_calls, task_calls.

    Returns:
        A Message if the turn ends, or an AgentTaskCall for process_turn
        to continue the loop. The framework resolves the AgentTaskCall
        reference recursively via WAITING_RESULTTASKS.
    """
    content = parsed.get("content", "")
    tool_calls = parsed.get("tool_calls", [])
    task_calls = parsed.get("task_calls", [])

    session_version = session.get_version_model()
    prev_message = session_version.related_messages.filter(
        next_messages=None
    ).last()

    message = Message.objects.create(
        session_version=session_version,
        response=response,
        role="assistant",
        prev_message=prev_message,
    )

    if content:
        message.add_part(content)

    if task_calls:
        message.tool_calls.set(task_calls)

    session.count_turn()

    if session.max_turns and session.current_turn_count >= session.max_turns:
        return message

    if (
        session.max_unattended_turns
        and session.current_unattended_turn_count >= session.max_unattended_turns
    ):
        return message

    if not tool_calls:
        return message

    session.count_unattended_turn()
    return session.process_turn.delay(message=message)
