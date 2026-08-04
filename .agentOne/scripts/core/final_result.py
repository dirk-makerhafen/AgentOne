def final_result(_session, content=""):
    """Return your final answer and end the current task.

    Call this tool DIRECTLY as the last action of your own turn. It
    terminates the agent loop and returns your result to the caller.

    When to use:
    - Subtask completion: You were spawned to do work for another agent.
      Call this to return your result to the parent.
    - Chat completion: You have answered the user's question or finished
      the requested task. Call this to end the turn.

    CRITICAL rules:
    - Call this tool yourself. Do NOT delegate it to another agent.
    - Do NOT pass this tool call as text into another tool's arguments
      (e.g. do not use it as the prompt of delegate_task or spawn_subtask).
    - Do NOT wrap your answer in tool-call syntax inside a message; invoke
      the tool so the system can detect it.

    Args:
        content: Your final answer or result message
    """
    return None