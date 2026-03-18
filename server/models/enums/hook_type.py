from django.db import models

class HookType(models.TextChoices):
    BEFORE_TOOL_CALL = "BEFORE_TOOL_CALL"
    """Called before any tool is invoked.
    
    Receives:
        tool_name: str
        args: tuple
        kwargs: dict
    Should return:
        args, kwargs (possibly modified)
    """

    AFTER_TOOL_CALL = "AFTER_TOOL_CALL"
    """Called after any tool completes.
    
    Receives:
        tool_name: str
        result: Any
    Should return:
        result (possibly modified)
    """

    BEFORE_LLM_RESPONSE = "BEFORE_LLM_RESPONSE"
    """Called before sending a prompt to the LLM.
    
    Receives:
        prompt: str
    Should return:
        prompt (possibly modified)
    """

    AFTER_LLM_RESPONSE = "AFTER_LLM_RESPONSE"
    """Called after receiving the LLM response.
    
    Receives:
        response: str
    Should return:
        response (possibly sanitized or transformed)
    """

    ON_TASK_START = "ON_TASK_START"
    """Called whenever a task starts execution.
    
    Receives:
        task_call: AgentTaskCall
    Can be used for logging, metrics, or pre-processing.
    """

    ON_TASK_COMPLETE = "ON_TASK_COMPLETE"
    """Called when a task finishes execution (success or failure).
    
    Receives:
        task_run: AgentTaskRun
    """

    ON_TASK_SUCCESS = "ON_TASK_SUCCESS"
    """Called only when a task completes successfully.
    
    Receives:
        task_run: AgentTaskRun
    """

    ON_TASK_FAILURE = "ON_TASK_FAILURE"
    """Called only when a task fails.
    
    Receives:
        task_run: AgentTaskRun
    """

    BEFORE_ENTRY = "BEFORE_ENTRY"
    """Called before the entry (@entry) task starts.
    
    Receives:
        message: any input to the agent
    Can modify the input or abort execution.
    """

    AFTER_ENTRY = "AFTER_ENTRY"
    """Called after the entry (@entry) task completes.
    
    Receives:
        result: Any
    Can modify the final result before returning to the user.
    """

