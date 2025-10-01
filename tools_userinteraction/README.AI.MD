# AI Agent Documentation (`tools_userinteraction/README.AI.MD`) [Code-Verified]

This directory provides the agent with a crucial capability: to explicitly pause its autonomous operation and await input or instructions from the user. This is essential for collaborative tasks, seeking clarification, or getting approval for potentially impactful actions.

## Overview of Components

*   **`tool.py`**: Implements the `UserInteractionTool`, which exposes the `await_user_input` function for LLM interaction.
*   **`prompts.py`**: Stores the static prompt templates for the User Interaction tool's description and function definitions.
*   **`apps.py`**: Standard Django application configuration, handling prompt string registration.

---

## User Interaction Tool (`tools_userinteraction/tool.py`)

### `tools_userinteraction.tool.UserInteractionTool` (`tools_userinteraction/tool.py:7`)
*   **Purpose**: Implements the `await_user_input` function exposed to the LLM. Inherits from `tools_common.models.BaseTool`.
*   **`functions` Dictionary (`tools_userinteraction/tool.py:8`)**: Defines the `await_user_input` function and its parameters, sourced from `tools_userinteraction.prompts.FUNCTIONS`.
*   **`get_header_parts()` (`tools_userinteraction/tool.py:11`)**:
    *   **Context Injection**: Injects the User Interaction tool's `Description` and `Functions` (definitions) into the LLM's context using `PromptString` templates.
*   **`await_user_input(self, toolCall, reason="")` (`tools_userinteraction/tool.py:19`)**:
    *   **Action**: Sets the `require_user_interaction` flag on the current `AgentInstance` to `True`.
    *   **State Machine Integration**: This flag is critical for the agent's state machine (`agent.tasks.decide_next_step`) to transition the agent into an `AWAITING_USER_INPUT` status, effectively pausing its autonomous execution.
    *   **Return Value**: Returns `(True, 'Successfully paused. Awaiting user input.')` on success.
*   **`get_history_limiting_rules()` (`tools_userinteraction/tool.py:29`)**:
    *   Defines rules for the `HistoryLimiter` to manage the visibility of `await_user_input` tool calls in the LLM's context.
    *   Includes a general limit for these calls to prevent context overflow from repeated pause requests.

---

## User Interaction Prompts (`tools_userinteraction/prompts.py`)

*   **`DESCRIPTION`**: Explains the purpose of the User Interaction tool, the `await_user_input()` function, its effect (pausing the agent), and when to use it (clarification, decisions, further instructions). Includes an example.
*   **`FUNCTIONS`**: A dictionary defining the schema for the `await_user_input` tool call, including an optional `reason` parameter.

---

## Application Configuration

### `tools_userinteraction.apps.py` (`tools_userinteraction/apps.py:3`)
*   **Prompt Registration (`tools_userinteraction/apps.py:9`):** In its `ready()` method, it uses `common.models.PromptString.objects.get_or_create()` to seed the database with the tool's `Description` and `Functions` prompt templates.
