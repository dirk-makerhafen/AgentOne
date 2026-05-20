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


def decide_next_step(session: Session, response: Response, parts: list[dict], message:Message) -> Message:
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
        parts:  list from parse_llm_response of Parts
            Parts is dict with minimal keys:
                type: message, reasoning, toolcall
                content_type: text|image|template|json
                content: str|dict
            In case Part.content_type is template the following keys are also needed:
                template_data: dict
            if case Part.type is "toolcall":
                tool_call: ToolCall 
        message: The convesation Message object created by ingest_assistant_message
    Returns:
        A Message if the turn ends, or an AgentTaskCall for process_turn
        to continue the loop. The framework resolves the AgentTaskCall
        reference recursively via WAITING_RESULTTASKS.
    """


    session.count_turn()
    session.count_unattended_turn()

    if session.max_turns and session.current_turn_count >= session.max_turns:
        return message

    if session.max_unattended_turns and session.current_unattended_turn_count >= session.max_unattended_turns:
        return message
    
    if not any([True for part in parts if "tool_call" in part]):
        return message

    return session.get_task("process_turn").delay(message=message)
