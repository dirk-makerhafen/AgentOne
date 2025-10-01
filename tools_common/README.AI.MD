# AI Agent Documentation (`tools_common/README.AI.MD`) [Code-Verified]

This directory provides foundational models, utilities, and a base class for all other agent tools. It establishes the common infrastructure for tool definitions, execution, and parsing.

## Overview of Components

*   **`models.py`**: Defines abstract base classes for tools (`BaseTool`) and concrete models for `ToolCall` and `ToolResponse`.
*   **`admin.py`**: Registers `ToolCall` and `ToolResponse` with the Django administration interface.
*   **`prompts.py`**: Stores static prompt templates related to tool instructions and result formatting.
*   **`tool_parser.py`**: Contains utility functions for parsing tool calls from LLM responses and generating tool stubs.
*   **`management/commands/`**: Contains Django management commands related to tool call processing.
*   **`apps.py`**: Standard Django application configuration, handling prompt string registration.

---

## Core Models and Base Tool Classes

All concrete models in this directory inherit from `common.models.ModelWithJsonData`.

### `tools_common.models.BaseTool` (`tools_common/models.py:7`)
*   **Purpose**: An abstract base class that all specific agent tools (e.g., `FilesystemTool`, `A2ATool`) must inherit from. It provides a common interface for tool functionality.
*   **`__init__(self, agentInstance)` (`tools_common/models.py:8`)**: Initializes the tool with a reference to the `AgentInstance` it operates within.
*   **`get_functions()` (`tools_common/models.py:11`)**: Returns a dictionary mapping function names to their callable methods, descriptions, and argument schemas.
*   **`get_content_parts()` (`tools_common/models.py:17`)**: An optional method that tools can implement to inject additional content (e.g., loaded file contents, memory items) into the LLM's context.

### `tools_common.models.ToolCall` (`tools_common/models.py:20`)
*   **Purpose**: Represents a single tool function call proposed by the LLM. This model captures the intent to execute a tool.
*   **Fields**:
    *   `agent`, `agentInstance`: ForeignKeys linking to the agent and instance that initiated the call.
    *   `conversationMessage`: ForeignKey linking to the `ConversationMessage` that contained this tool call.
    *   `function_name`: `CharField` (max_length=64) storing the name of the tool function to be called.
    *   `status`: `CharField` (max_length=10, default='pending'), tracking the execution status (`pending`, `success`, `failed`).
    *   `arguments` property (`tools_common/models.py:29`): Stores the tool call arguments as a dictionary, backed by the `data` JSON field.
*   **Real-time Updates (`tools_common/models.py:34`):** The `save()` method calls `dashboard.tasks.send_object_to_clients()` to broadcast changes to connected frontend clients.
*   **Client Dictionary (`tools_common/models.py:39`):** `as_client_dict()` provides a serialized representation for frontend display, including the result from the last `ToolResponse`.
*   **`run()` Method (`tools_common/models.py:56`):**
    *   **Execution Logic**: This is the core method for executing the tool call.
    *   **Status Check**: Ensures the `ToolCall` is `pending` before execution.
    *   **Function Dispatch**: Retrieves the actual callable function using `agentInstance.get_tool_function()`.
    *   **Argument Validation**: Performs basic validation on arguments (checking for unknown or missing required arguments).
    *   **Execution**: Calls the tool's callable function, passing `toolCall=self` and the extracted arguments.
    *   **Error Handling**: Catches exceptions during execution and records them in the `ToolResponse`.
    *   **Result Storage**: Creates a `ToolResponse` object to store the outcome of the tool execution and updates the `ToolCall`'s `status`.

### `tools_common.models.ToolResponse` (`tools_common/models.py:97`)
*   **Purpose**: Stores the result of a `ToolCall`'s execution.
*   **Fields**:
    *   `agent`, `agentInstance`: ForeignKeys to the related agent and instance.
    *   `toolCall`: ForeignKey to the `ToolCall` that this response belongs to.
    *   `status`: `CharField` (max_length=32, default='unknown'), indicating the outcome of the tool execution.
*   **Note**: The `save()` method for `ToolResponse` does *not* send updates to the client directly, as the associated `ToolCall`'s update already includes the result data, preventing redundant WebSocket messages.

---

## Tool Parsing Utilities (`tools_common/tool_parser.py`)

*   **`extract_tool_call_parts(response_string)` (`tools_common/tool_parser.py:16`)**:
    *   **Purpose**: Parses an LLM's raw text response to identify and extract embedded tool calls.
    *   **Regex Pattern (`tools_common/tool_parser.py:22`):** Uses a complex regular expression to find `@@@function_name(arguments)@@@` patterns.
    *   **Argument Parsing (`tools_common/tool_parser.py:46`):** Employs `ast.literal_eval` to safely parse Python-like argument strings into actual Python data structures (dictionaries, strings, numbers, booleans). Handles triple-quoted strings and escapes.
    *   **Mixed Content**: Splits the `response_string` into alternating chat message segments and tool call segments.
    *   **Output Format**: Returns a list of dictionaries, where each dictionary represents either a chat message (`{'content': '...'}`) or a tool call (`{'tool': 'function_name', 'arguments': {...}, 'content': '...'}`).
*   **`generate_function_stub(func_name, func_def)` (`tools_common/tool_parser.py:101`)**:
    *   **Purpose**: Creates a Python function stub string (definition, parameters, docstring) from a dictionary describing a tool's function.
    *   **Dynamic Generation**: Used by `tools_common.apps.py` (and potentially other tool apps) to generate Python-like representations of tool functions for inclusion in the LLM's context.

---

## Administrative Interface

### `tools_common.admin.py` (`tools_common/admin.py:3`)
*   Registers `ToolCall` and `ToolResponse` models.
*   Configures `list_display`, `list_filter`, `search_fields`, and `autocomplete_fields` for comprehensive management and auditing of tool interactions.

---

## Django Management Commands (`tools_common/management/commands/`)

*   **`execute_pending_toolcalls.py`** (`tools_common/management/commands/execute_pending_toolcalls.py:6`):
    *   **Purpose**: A Django management command that can be run periodically (e.g., via Celery Beat or cron) to find and execute any `ToolCall` objects that are in a `pending` state.
    *   **Process**: Iterates through all `AgentInstance`s, finds `pending` tool calls, updates the instance status to `EXECUTING_TOOLS`, runs each call, and then calls `agent.tasks.decide_next_step()` to transition the agent's state.
*   **`fix_prex_next.py`** (`tools_common/management/commands/fix_prex_next.py:6`):
    *   **Purpose**: This command appears to be for development/debugging. The current implementation is commented out or returns immediately.
    *   **Previous/Next Version Logic**: The commented-out code suggests it was intended to re-establish or fix `next_version` pointers for `FsLogEntry` objects, which are used for file versioning/history.

---

## Application Configuration

### `tools_common.apps.py` (`tools_common/apps.py:3`)
*   **Prompt Registration (`tools_common/apps.py:9`):** In its `ready()` method, it uses `common.models.PromptString.objects.get_or_create()` to seed the database with the common tool `Instructions` and `ResultInjection` prompt templates.

---
