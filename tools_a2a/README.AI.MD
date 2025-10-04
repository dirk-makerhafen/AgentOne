# AI Agent Documentation (`tools_a2a/README.AI.MD`) [Code-Verified]

This directory contains the necessary components for enabling agent-to-agent communication and for agents to manage their public descriptions. It defines models for inter-agent messages, permissions, and tool implementations.

## Overview of Components

*   **`models.py`**: Defines Django models for `AgentInstanceDescriptionLog`, `InterAgentMessage`, and `InstancePermission`.
*   **`admin.py`**: Registers these models with the Django administration interface.
*   **`prompts.py`**: Stores the static prompt templates used by the A2A tool.
*   **`tool.py`**: Implements the `A2ATool` with methods for sending messages and setting agent descriptions.
*   **`apps.py`**: Standard Django application configuration, handling prompt string registration.

---

## Core Models and Data Management

All models here inherit from `common.models.ModelWithJsonData` or `django.db.models.Model` and include `created_at` and `updated_at` fields for auditing.

### `tools_a2a.models.AgentInstanceDescriptionLog` (`tools_a2a/models.py:4`)
*   **Purpose**: Logs changes to an agent instance's public description.
*   **Fields**: `toolCall` (ForeignKey to `tools_common.ToolCall` if triggered by a tool), `agent`, `agent_instance`, and `description` (TextField).
*   This provides a history of how an agent described itself over time.

### `tools_a2a.models.InterAgentMessage` (`tools_a2a/models.py:16`)
*   **Purpose**: Records messages exchanged between two `AgentInstance`s.
*   **Fields**:
    *   `sender_agent`, `sender_agentInstance`, `sender_conversationMessage`, `sender_toolCall`: References to the origin of the message.
    *   `receiver_agent`, `receiver_agentInstance`, `receiver_conversationMessage`: References to the destination of the message.
    *   `message` property (`tools_a2a/models.py:29`): Stores the actual message content, backed by the `data` JSON field.
*   **Real-time Updates (`tools_a2a/models.py:34`):** The `save()` method calls `dashboard.tasks.send_object_to_clients()` to broadcast changes to connected frontend clients, ensuring immediate UI synchronization.
*   **Client Dictionary (`tools_a2a/models.py:39`):** `as_client_dict()` provides a serialized representation for frontend display.

### `tools_a2a.models.InstancePermission` (`tools_a2a/models.py:58`)
*   **Purpose**: Defines explicit, one-way communication permissions between two `AgentInstance`s.
*   **Fields**: `source_instance`, `target_instance` (both ForeignKeys to `agent.AgentInstance`), `can_send` (BooleanField), and `can_receive` (BooleanField).
*   **Uniqueness**: `unique_together = ('source_instance', 'target_instance')` ensures only one permission entry exists for a given pair.

---

## Inter-Agent Tool (`tools_a2a/tool.py`)

### `tools_a2a.tool.A2ATool` (`tools_a2a/tool.py:7`)
*   **Purpose**: Implements the logic for agent-to-agent interactions. Inherits from `tools_common.models.BaseTool`.
*   **`functions` Dictionary (`tools_a2a/tool.py:8`):** Defines the available tool functions (`agent_send_message`, `set_agent_description`) and their parameters, sourced from `tools_a2a.prompts.FUNCTIONS`.
*   **`get_header_parts()` (`tools_a2a/tool.py:10`):**
    *   **Context Injection**: This method is called during LLM prompt compilation (`agent.tasks.py:61`) to inject relevant A2A tool documentation and a list of other available agent instances into the agent's context.
    *   **Permission-Aware List**: It queries `InstancePermission` to determine which agent instances the current `agentInstance` can communicate with, and constructs a list of these agents with their descriptions for the LLM.
    *   Uses `PromptString` templates from `tools_a2a.prompts` (`Description`, `Functions`, `AgentList`).
*   **`agent_send_message(toolCall, id, message)` (`tools_a2a/tool.py:33`):**
    *   **Permission Check (`tools_a2a/tool.py:48`):** Before sending, it verifies communication permissions. An agent can send if `(sender -> recipient: can_send=True)` OR `(recipient -> sender: can_receive=True)`.
    *   **Recipient Conversation Injection (`tools_a2a/tool.py:62`):** Adds the message to the recipient `AgentInstance`'s conversation history (as if the user sent it).
    *   **Transaction Logging (`tools_a2a/tool.py:66`):** Creates an `InterAgentMessage` record to log the full details of the message exchange.
    *   **Recipient Trigger**: (Commented out in provided code, but conceptually present: `recipient_instance.start_or_continue()`) Would trigger the recipient agent to process the new message.
*   **`set_agent_description(toolCall, description)` (`tools_a2a/tool.py:104`):**
    *   **Purpose**: Allows an agent to update its public `description`.
    *   **Validation**: Checks `description` type and length.
    *   **Description Logging (`tools_a2a/tool.py:114`):** Creates an `AgentInstanceDescriptionLog` entry to record the new description, but only if it differs from the most recent one.
*   **`get_history_limiting_rules()` (`tools_a2a/tool.py:77`):**
    *   Defines rules for the `HistoryLimiter` (`agent.history_limiter.py`) to manage the visibility of A2A tool call messages in the LLM's context.
    *   Includes rules for general A2A messages, messages per recipient, and description updates, each with specific `success`, `failed`, and `max` limits.

---

## Tool Prompts (`tools_a2a/prompts.py`)

*   **`INSTRUCTIONS`**: General introduction to the Inter-Agent Tool.
*   **`FUNCTIONS`**: A dictionary defining the schema for `agent_send_message` and `set_agent_description` tool calls, including descriptions and parameters.
*   **`AGENTLIST`**: A Jinja2 template for formatting a list of other available agent instances to be injected into the LLM's context.

---

## Administrative Interface

### `tools_a2a.admin.py` (`tools_a2a/admin.py:3`)
*   Registers `InterAgentMessage`, `AgentInstanceDescriptionLog`, and `InstancePermission` models.
*   Configures `list_display`, `list_filter`, `search_fields`, and `autocomplete_fields` for efficient management of inter-agent data.

---

## Application Configuration

### `tools_a2a.apps.py` (`tools_a2a/apps.py:3`)
*   **Prompt Registration (`tools_a2a/apps.py:10`):** In its `ready()` method, it uses `common.models.PromptString.objects.get_or_create()` to seed the database with the tool's `Description`, `AgentList`, and `Functions` (generated as a Python stub string via `tools_common.tool_parser.generate_function_stub`).
