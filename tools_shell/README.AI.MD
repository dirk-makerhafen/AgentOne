# AI Agent Documentation (`tools_shell/README.AI.MD`) [Code-Verified]

This directory provides the agent with the capability to execute arbitrary shell commands and scripts on the underlying operating system. It integrates with an external or local executor for command execution and supports a subscription mode for continuous monitoring.

## Overview of Components

*   **`shelltool.py`**: Implements the `ShellTool`, which exposes the `shell` function for LLM interaction.
*   **`prompts.py`**: Stores static prompt templates for the Shell tool's description and function definitions.
*   **`apps.py`**: Standard Django application configuration, handling prompt string registration.

---

## Shell Tool (`tools_shell/shelltool.py`)

### `tools_shell.shelltool.ShellTool` (`tools_shell/shelltool.py:7`)
*   **Purpose**: Implements the `shell` tool function exposed to the LLM. Inherits from `tools_common.models.BaseTool`.
*   **`functions` Dictionary (`tools_shell/shelltool.py:8`)**: Defines the `shell` tool's function and its parameters, sourced from `tools_shell.prompts.FUNCTIONS`.
*   **`get_header_parts()` (`tools_shell/shelltool.py:11`)**:
    *   **Context Injection**: Injects the Shell tool's `INSTRUCTIONS` and `Functions` (definitions) into the LLM's context using `PromptString` templates.
*   **`shell(self, source, interpreter="auto", subscription_id=None, mode="one-shot", toolCall=None)` (`tools_shell/shelltool.py:21`)**:
    *   **Core Execution**: Executes the shell `source` code.
    *   **Subscription Mode (`mode="subscribe"`)**:
        *   If `mode` is `subscribe`, it creates or updates a `ToolSubscription` (`tools_subscriptions.models.ToolSubscription`) to run this shell command before every subsequent LLM query. Requires a `subscription_id`.
    *   **Execution Dispatch**: Calls `executor.primitives.run_shell_script` to execute the shell command. This primitive handles interpreter detection (`auto`, `bash`, `powershell`, `cmd`) and execution environment.
    *   **Success Determination**: A tool call is considered `success` if the underlying `run_shell_script` also reports `status: "success"` and the `return_code` is `0`. This explicitly separates tool execution success from the shell command's exit status.
    *   **Return Value**: Returns a tuple `(success, result_dict)`, where `result_dict` includes `stdout`, `stderr`, and `return_code`.
*   **`get_history_limiting_rules()` (`tools_shell/shelltool.py:53`)**:
    *   Defines rules for the `HistoryLimiter` to manage the visibility of `shell` tool calls in the LLM's context.
    *   Currently includes a general limit for all shell tool calls.

---

## Shell Tool Prompts (`tools_shell/prompts.py`)

*   **`INSTRUCTIONS`**: Detailed explanation of the Shell tool, its purpose, execution environment (temporary file, interpreter options), and how to interpret its output (`stdout`, `stderr`, `return_code`).
*   **`FUNCTIONS`**: A dictionary defining the schema for the `shell` tool call, including `source`, `interpreter`, `subscription_id`, and `mode`.

---

## Application Configuration

### `tools_shell.apps.py` (`tools_shell/apps.py:3`)
*   **Prompt Registration (`tools_shell/apps.py:9`):** In its `ready()` method, it uses `common.models.PromptString.objects.get_or_create()` to seed the database with the tool's `INSTRUCTIONS` and `Functions` prompt templates. It specifically extracts the single function definition for the `shell` tool.
*   **Hidden Marker (`tools_shell/apps.py:7`):** Contains a commented-out line `##THIS_IS_A_MARKER` that was used as a target for a previous `grep` search.
