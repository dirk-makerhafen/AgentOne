# AI Agent Documentation (`agent/README.AI.MD`) [Code-Verified]

This directory contains the core Django models that define the structure and state of AI agents. This documentation is based on a full review of the source code.

## Core Architectural Principles

1.  **Blueprint vs. Instance Separation:**
    *   `models/agent.py -> Agent`: A static **blueprint**. Defines an agent's name, owners, and default model.
    *   `models/agent.py -> AgentInstance`: The **live, stateful runtime** of an `Agent`. All dynamic data—conversation history, status, memory, tools, and working directory—is tied to an `AgentInstance`. This is the primary object for any active session.

2.  **State Machine & Lifecycle:**
    *   The `AgentInstance.status` field is the central state machine (`IDLE`, `THINKING`, etc.).
    *   **The agent's "thinking" loop is managed by Celery.** The `AgentInstance.start_or_continue()` method initiates a background task via `celery_create_query`. This decouples the agent's long-running processes from the web server.

3.  **Tool Registration and Dispatch:**
    *   The list of available tools is **hardcoded** in `AgentInstance.__init__`.
    *   On initialization, a `toolname_to_class` dictionary is created, mapping each tool function name (e.g., `"fs_load"`) to its parent `Tool` class.
    *   The `AgentInstance.get_tool_function()` method uses this map to instantiate the correct tool and retrieve the callable method for execution.

4.  **Prompt Compilation Engine:**
    *   `models/llm.py -> LLMQuery`: This model acts as a powerful prompt compiler, not just a data container.
    *   The `compile()` method assembles the final prompt by rendering parts from various sources:
        *   **Jinja2 Templates (`tpId`):** Renders `PromptString` templates.
        *   **Dynamic Data Injection:** Fetches and injects content from `MemoryItem`, `ToolResponse`, and `FsLogEntry` models directly into the prompt templates.
        *   **Conversation History (`cmId`):** Transcludes content directly from `ConversationMessage` parts.
    *   This compilation step is the "brain" that assembles all context before sending it to the LLM.

5.  **Token Accounting and Self-Correction:**
    *   `models/llm.py -> LLMResponse`: This model contains a **token self-correction mechanism**.
    *   In its `save()` method, it compares the `prompt_tokens` reported by the LLM API with the initial estimate calculated by `LLMQuery.compile()`.
    *   It then calculates a `correction_factor` and applies it back to all the individual parts of the `LLMQuery`, resulting in highly accurate token usage statistics.

6.  **Conversation and Context Management:**
    *   `models/conversation.py -> ConversationMessage`: Represents a single message in the log.
    *   **Business Rule:** The `save()` method contains a critical rule: `if self.hide_from_context is True and self.pin_to_context is True: self.pin_to_context = False`. Hiding a message from context overrides pinning it. This must be respected.

7.  **Real-time Frontend Updates:**
    *   A common pattern in model `save()` methods is to call `dashboard.tasks.send_object_to_clients`. This triggers a WebSocket message, ensuring the UI is updated in real-time whenever a core model's state changes.

## Guidelines for Modification

*   **Adding a New Tool:** You must add the new tool's class to the `self.available_tools` list in `AgentInstance.__init__` for it to be recognized by the system.
*   **Changing Agent Behavior:** Modifications to the agent's core thinking loop should be made in the Celery tasks defined in `agent/tasks.py`.
*   **Modifying Prompt Context:** To add a new type of data to the prompt, you must modify the `LLMQuery.compile()` method to handle a new part type or inject new data into the Jinja2 context.
