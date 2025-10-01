# AI Agent Documentation (`tools_subscriptions/README.AI.MD`) [Code-Verified]

This directory introduces a powerful, generic mechanism for agents to subscribe to recurring tool executions. This allows agents to continuously monitor specific aspects of their environment or internal state without needing to explicitly call tools repeatedly in every turn.

## Overview of Components

*   **`models.py`**: Defines the `ToolSubscription` Django model for storing active subscriptions.
*   **`tool.py`**: Implements the `SubscriptionsTool`, which exposes the `unsubscribe` function for LLM interaction.
*   **`prompts.py`**: Stores static prompt templates for tool subscription instructions, function definitions, and the structured format for injecting subscription results into the LLM's context.
*   **`apps.py`**: Standard Django application configuration, handling prompt string registration.

---

## Core Models and Data Management

### `tools_subscriptions.models.ToolSubscription` (`tools_subscriptions/models.py:7`)
*   **Purpose**: Stores the details of an active tool subscription, allowing the system to re-execute specified tool calls automatically before generating new LLM queries.
*   **Inheritance**: Inherits from `common.models.ModelWithJsonData`.
*   **Fields**:
    *   `agent`, `agentInstance`: ForeignKeys linking to the agent and instance that owns this subscription.
    *   `creating_tool_call`: Optional ForeignKey linking to the `ToolCall` that created this subscription.
    *   `subscription_id`: `CharField` (max_length=128, unique per agent instance). This is the unique identifier given by the agent for managing the subscription.
    *   `tool_name`: `CharField` (max_length=64) storing the name of the tool (e.g., `'python'`, `'shell'`) that is subscribed to.
    *   `is_active`: `BooleanField` (default=True) to enable or disable the subscription.
    *   `arguments` property (`tools_subscriptions/models.py:25`): Stores the arguments for the subscribed tool call, backed by the `data` JSON field.
*   **Uniqueness**: `unique_together = ('agentInstance', 'subscription_id')` ensures that each agent instance has unique subscription IDs.
*   **`save()` Method (`tools_subscriptions/models.py:30`):** Overrides the default `save()`. Currently, it does not send real-time updates to the client (`send_object_to_clients(self)` is commented out), indicating that client-side rendering for subscriptions is not yet fully implemented or is handled indirectly.
*   **`__str__()` Method (`tools_subscriptions/models.py:40`):** Provides a human-readable string representation of the subscription.

---

## Subscriptions Tool (`tools_subscriptions/tool.py`)

### `tools_subscriptions.tool.SubscriptionsTool` (`tools_subscriptions/tool.py:7`)
*   **Purpose**: Implements the `unsubscribe` function, which is the primary way for agents to manage their active subscriptions. Inherits from `tools_common.models.BaseTool`.
*   **`functions` Dictionary (`tools_subscriptions/tool.py:8`)**: Defines the `unsubscribe` tool's function and its parameters, sourced from `tools_subscriptions.prompts.FUNCTIONS`.
*   **`get_header_parts()` (`tools_subscriptions/tool.py:11`)**:
    *   **Context Injection**: Injects the subscription tool's `Instructions` and `Functions` (definitions) into the LLM's context using `PromptString` templates.
*   **`unsubscribe(self, subscription_id: str, toolCall=None)` (`tools_subscriptions/tool.py:18`)**:
    *   **Action**: Deactivates an existing `ToolSubscription`.
    *   **Logic**: Retrieves the `ToolSubscription` matching the `agentInstance` and `subscription_id`, sets `is_active` to `False`, and saves the change.
    *   **Error Handling**: Returns an error if no active subscription with the given ID is found.

---

## Subscription Prompts (`tools_subscriptions/prompts.py`)

*   **`INSTRUCTIONS`**: Provides a detailed explanation of tool subscriptions, including how they work (auto-refreshing context), how to create them (using `mode='subscribe'` in `shell` or `python` tools), and how to `unsubscribe`. It also includes examples and best practices.
*   **`SUBSCRIPTION_RESULT_INJECTION`**: A Jinja2 template for formatting the output of a recurring command subscription when it's injected into the LLM's context. It includes `subscription_id`, `status`, `tool_name`, `arguments`, and the `output` itself.
*   **`FUNCTIONS`**: A dictionary defining the schema for the `unsubscribe` tool call, including `subscription_id`.

---

## Application Configuration

### `tools_subscriptions.apps.py` (`tools_subscriptions/apps.py:3`)
*   **Prompt Registration (`tools_subscriptions/apps.py:9`):** In its `ready()` method, it uses `common.models.PromptString.objects.get_or_create()` to seed the database with the tool's `Instructions`, `Functions` (generated as a Python stub), and `SubscriptionResultInjection` prompt templates.
