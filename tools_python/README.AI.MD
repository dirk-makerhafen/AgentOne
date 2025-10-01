# AI Agent Documentation (`tools_python/README.AI.MD`) [Code-Verified]

This directory provides the agent with the capability to execute arbitrary Python code, manage persistent variables (`VARS` dictionary), and analyze conversation history. It integrates with an external or local executor for code execution.

## Overview of Components

*   **`models.py`**: Defines the `PythonToolVar` Django model for tracking shared Python variables.
*   **`pythontool.py`**: Implements the `PythonTool`, exposing the `python` function for LLM interaction.
*   **`prompts.py`**: Stores static prompt templates for the Python tool's description, function definitions, and the format for injecting shared `VARS` information.
*   **`admin.py`**: Registers `PythonToolVar` with the Django administration interface.
*   **`apps.py`**: Standard Django application configuration, handling prompt string registration.

---

## Core Models and Data Management

### `tools_python.models.PythonToolVar` (`tools_python/models.py:7`)
*   **Purpose**: Stores individual key-value pairs of the shared `VARS` dictionary used by Python tool calls. This provides persistence across multiple `python` tool invocations.
*   **Inheritance**: Inherits from `common.models.ModelWithJsonData`.
*   **Fields**:
    *   `agent`, `agentInstance`: ForeignKeys linking to the agent and instance that owns this variable.
    *   `toolCall`: Optional ForeignKey linking to the `ToolCall` that last modified this variable.
    *   `action`: `CharField` (`add`, `update`, `delete`) indicating the last action performed on the variable.
    *   `key`: `CharField` (max_length=512) storing the variable's name.
    *   `next_version`: `OneToOneField` to `PythonToolVar` itself, forming a linked list for versioning. `None` indicates the latest version.
    *   `value` property (`tools_python/models.py:27`): Stores the variable's content, backed by the `data` JSON field.
*   **Real-time Updates (`tools_python/models.py:21`):** The `save()` method calls `dashboard.tasks.send_object_to_clients()` to broadcast changes to connected frontend clients, ensuring immediate UI synchronization.
*   **Client Dictionary (`tools_python/models.py:34`):** `as_client_dict()` provides a serialized representation for frontend display.

---

## Python Tool (`tools_python/pythontool.py`)

### `tools_python.pythontool.PythonTool` (`tools_python/pythontool.py:7`)
*   **Purpose**: Implements the `python` tool function exposed to the LLM. Inherits from `tools_common.models.BaseTool`.
*   **`functions` Dictionary (`tools_python/pythontool.py:8`)**: Defines the `python` tool's function and its parameters, sourced from `tools_python.prompts.FUNCTIONS`.
*   **`get_header_parts()` (`tools_python/pythontool.py:11`)**:
    *   **Context Injection**: Injects the Python tool's `Description`, `Functions` (definitions), and a list of existing `VARS` keys (`SharedVarsInjection`) into the LLM's context.
    *   **`existing_vars`**: Fetches up to 20 latest `PythonToolVar` entries to inform the LLM about current shared variables.
*   **`python(self, source, mode="one-shot", subscription_id=None, toolCall=None)` (`tools_python/pythontool.py:21`)**:
    *   **Core Execution**: Executes Python `source` code.
    *   **Subscription Mode (`mode="subscribe"`)**:
        *   If `mode` is `subscribe`, it creates or updates a `ToolSubscription` (`tools_subscriptions.models.ToolSubscription`) to run this Python code before every subsequent LLM query. Requires a `subscription_id`.
    *   **`VARS` Management (`tools_python/pythontool.py:46`):**
        *   Loads the current state of `VARS` from `PythonToolVar` models into the execution environment.
        *   Calls `executor.primitives.run_python_code` to execute the `source` code.
        *   After execution, it analyzes the `returned_vars` (specifically changes to the `VARS` dictionary) via `handle_results_vars` to update `PythonToolVar` models.
    *   **Return Value**: Returns a tuple `(success, result_dict)`, where `result_dict` includes `stdout`, `stderr`, and `updated_vars` (list of changed variable names).
*   **`handle_results_vars(self, original_vars, current_vars, toolCall)` (`tools_python/pythontool.py:74`)**:
    *   **Purpose**: Compares the `original_vars` state before execution with `current_vars` after execution.
    *   **Change Detection**: Identifies `added`, `updated`, and `deleted` variables in `VARS`.
    *   **`PythonToolVar` Update**: Creates new `PythonToolVar` entries (linked via `next_version`) for each detected change, marking the `action` appropriately. Broadcasts these updates to the frontend.
*   **`_deep_equals(self, val1, val2)` (`tools_python/pythontool.py:122`)**: A helper method for recursively comparing two Python objects (dictionaries, lists, tuples, or scalars) for equality, used to detect if a `VARS` entry has truly changed.
*   **`get_history_limiting_rules()` (`tools_python/pythontool.py:108`)**:
    *   Defines rules for the `HistoryLimiter` to manage the visibility of `python` tool calls in the LLM's context.
    *   Includes specific limits for Python calls that produce no output, or only change `VARS`.

---

## Python Tool Prompts (`tools_python/prompts.py`)

*   **`DESCRIPTION`**: Detailed explanation of the Python tool, its purpose, the `VARS` dictionary (persistence, capacity, management, access methods), and how to interpret execution feedback. Includes an example code block.
*   **`FUNCTIONS`**: A dictionary defining the schema for the `python` tool call, including `source`, `subscription_id`, and `mode`.
*   **`LIST_OF_SHARED_VARS`**: A Jinja2 template for injecting the list of currently existing `VARS` keys into the LLM's context.

---

## Administrative Interface

### `tools_python.admin.py` (`tools_python/admin.py:3`)
*   Registers the `PythonToolVar` model.
*   Configures `list_display`, `list_filter`, `search_fields`, `autocomplete_fields`, and `readonly_fields` for managing shared Python variables.

---

## Application Configuration

### `tools_python.apps.py` (`tools_python/apps.py:3`)
*   **Prompt Registration (`tools_python/apps.py:9`):** In its `ready()` method, it uses `common.models.PromptString.objects.get_or_create()` to seed the database with the tool's `Description`, `Functions`, and `SharedVarsInjection` prompt templates.
