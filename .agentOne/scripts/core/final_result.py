def final_result(_session, content=""):
    """Return your final answer and end the current task.

    Use this tool when you have completed all work and are ready to return
    your result. Calling this terminates the agent loop.

    When to use:
    - Subtask completion: You were spawned to do work for another agent.
      Call this to return your result to the parent.
    - Chat completion: You have answered the user's question or finished
      the requested task. Call this to end the turn.

    You MUST use this tool to finish — do not end with a text-only message.

    Args:
        content: Your final answer or result message
    """
    return None