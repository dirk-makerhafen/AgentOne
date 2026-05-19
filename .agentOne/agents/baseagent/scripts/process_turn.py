"""
Orchestrator for a single agent turn.
Submits the chain of tasks that compose one LLM interaction cycle.
"""

from runtime.agents.session import Session
from server.models.message import Message


def process_turn(session: Session, message: Message):
    """
    Run one full agent turn: build context → call LLM → parse → execute tools → decide next.

    Each step is submitted via .delay() which returns an AgentTaskCall.
    The framework resolves AgentTaskCall references to actual results
    before calling the next function, so chaining is implicit.

    Called from ingest_user_message (start of a turn) and from
    decide_next_step (loop continuation when tools were used).

    Args:
        session: The active agent session.
        message: The Message that triggered this turn (user or loop-continuation).

    Returns:
        An AgentTaskCall for decide_next_step, which itself returns either
        a final Message (turn ends) or another process_turn AgentTaskCall (loop).
    """
    query_call = session.build_llm_context.delay(message=message)
    response_call = session.call_llm.delay(query=query_call)
    parsed_call = session.extract_tool_calls.delay(response=response_call)
    tools_call = session.execute_tools.delay(parsed=parsed_call)
    return session.decide_next_step.delay(response=response_call, parsed=tools_call)
