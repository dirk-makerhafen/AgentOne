# AI Agent Documentation (`tools_filesystem/README.AI.MD`) [Code-Verified]

This directory provides a robust and version-controlled filesystem interaction layer for agent instances. It tracks all changes, allows for loading/unloading content, summarizes file structures, and includes capabilities for reverting changes.

## Overview of Components

*   **`models.py`**: Defines the `FsLogEntry` model for tracking all filesystem operations and content versions.
*   **`filesystem.py`**: Implements the `FilesystemTool`, which exposes `fs_*` functions for LLM interaction.
*   **`fsutils.py`**: Contains utility functions for path manipulation, content diffing/patching, fuzzy matching, and directory listing formatting.
*   **`permissions.py`**: Implements logic for fine-grained access control to the filesystem based on agent instance rules.
*   **`prompts.py`**: Stores static prompt templates describing the filesystem tools and their usage.
*   **`summarize.py`**: Provides language-specific content summarization functions for various file types (Python, JS, CSS, JSON, etc.).
*   **`tasks.py`**: Contains Celery background tasks for asynchronous filesystem undo/revert operations.
*   **`tests.py`**: Contains unit tests for the `FsLogEntry.undo` method and related Celery tasks.
*   **`admin.py`**: Registers `FsLogEntry` with the Django administration interface.
*   **`apps.py`**: Standard Django application configuration, handling prompt string registration.

---

## Core Models and Data Management

### `tools_filesystem.models.FsLogEntry` (`tools_filesystem/models.py:126`)
*   **Purpose**: The central model for maintaining a comprehensive, version-controlled log of all filesystem interactions (reads, writes, appends, deletions, refreshes) for an `AgentInstance`. Each change or observation creates a new `FsLogEntry`.
*   **Inheritance**: Inherits from `django.db.models.Model`.
*   **Fields**:
    *   `agent`, `agentInstance`, `toolCall`: ForeignKeys linking to the origin of the action.
    *   `prev_version`: ForeignKey to the previous `FsLogEntry` for the same path, forming a linked list history.
    *   `is_newest_version`: `BooleanField` (db_index=True) to quickly identify the current state of a path.
    *   `path`: `CharField` storing the absolute path.
    *   `load_mode`: `CharField` (`full`, `summary`, `None`) indicating how the content was loaded into context.
    *   `is_pinned`: `BooleanField` (default=False) to prevent `fs_unload` if set by the user.
    *   `is_directory`, `exists_on_fs`: Booleans reflecting the path's type and existence on the actual filesystem.
    *   `fs_created`, `fs_modified`, `fs_lastread`: Timestamps from the actual filesystem or the last read time.
    *   `action`: `CharField` (`init`, `load`, `unload`, `write`, `append`, `replace`, `refresh`).
    *   `content_diff`: `TextField` storing the content. The `stored_as` field dictates how this is interpreted.
    *   `stored_as`: `CharField` (`full`, `patch`, `append`, `prepend`, `""` for no change). Dictates the content storage strategy.
    *   `summary`: `CharField` for token-efficient file outlines in `summary` mode.
*   **`content` Property (`tools_filesystem/models.py:165`)**:
    *   **Purpose**: Reconstructs the full content of the file/directory at this log entry's version.
    *   **Patching Logic**: Uses `tools_filesystem.fsutils.apply_patch` to reconstruct content if `stored_as` is `patch`, efficiently managing large content changes. It also handles `append` and `prepend` storage methods.
    *   **LRU Cache**: `functools.lru_cache(maxsize=1000)` is used for performance, caching the reconstructed content.
*   **`write(content, toolCall=None)` (`tools_filesystem/models.py:204`)**: Overwrites the file on disk and creates a new `FsLogEntry` version.
*   **`append(content, toolCall=None)` (`tools_filesystem/models.py:231`)**: Appends content to the file on disk and creates a new `FsLogEntry` version.
*   **`refresh_from_disk(toolCall=None, ...)` (`tools_filesystem/models.py:259`)**:
    *   Compares the current `FsLogEntry` with the actual state on disk.
    *   Creates a new `FsLogEntry` version only if the file's content, metadata, or the requested load parameters (`recursive`, `filter`, `mode`) have changed. This prevents redundant log entries.
*   **`create_next_version(**kwargs)` (`tools_filesystem/models.py:341`)**: Helper to create a new `FsLogEntry` that links back to the current one via `prev_version`.
*   **`_get_storage_method(existing_content, new_content)` (`tools_filesystem/models.py:365`)**: Determines the most token-efficient way to store the `content_diff` (full content, patch, append, prepend).
*   **`undo(toolCall=None)` (`tools_filesystem/models.py:421`)**:
    *   **Purpose**: Reverts the actual filesystem on disk to the state *before* this specific `FsLogEntry` was created (i.e., to the state of `self.prev_version`).
    *   **Mechanism**: Performs necessary filesystem operations (delete, create directory, write file) to restore the target state.
    *   **Logging**: Creates a new `FsLogEntry` with `action="revert"` that reflects the restored state.

### `tools_filesystem.models.FsLogEntryManager` (`tools_filesystem/models.py:10`)
*   **Purpose**: Custom manager for `FsLogEntry` to simplify creation and refreshing of log entries.
*   **`get_or_create_latest(...)` (`tools_filesystem/models.py:11`)**: A dispatcher that either creates an initial `FsLogEntry` for a path not yet tracked or refreshes an existing one. Includes validation for existence and file/directory type.

---

## Filesystem Tool (`tools_filesystem/filesystem.py`)

### `tools_filesystem.filesystem.FilesystemTool` (`tools_filesystem/filesystem.py:10`)
*   **Purpose**: Implements the `fs_*` functions that are exposed to the LLM. Inherits from `tools_common.models.BaseTool`.
*   **`functions` Dictionary (`tools_filesystem/filesystem.py:11`)**: Defines the available tool functions and their parameters, sourced from `tools_filesystem.prompts.FUNCTIONS`.
*   **`get_header_parts()` (`tools_filesystem/filesystem.py:13`)**: Injects tool descriptions and function definitions into the LLM's context using `PromptString` templates.
*   **`get_loaded_items(refresh_from_disk=False)` (`tools_filesystem/filesystem.py:20`)**: Retrieves all `FsLogEntry` objects currently loaded into the agent's context (`is_newest_version=True`, `load_mode != None`), optionally refreshing them from disk.
*   **`fs_load(toolCall, path, filter="", recursive=False, mode="full")` (`tools_filesystem/filesystem.py:26`)**:
    *   **Action**: Loads file/directory content into the agent's context by creating or refreshing an `FsLogEntry`.
    *   **Permissions**: Calls `tools_filesystem.permissions.check_permission` for 'read' access.
    *   **Modes**: Supports `full` and `summary` modes. `summary` mode uses `tools_filesystem.summarize.summarize`.
*   **`fs_unload(toolCall, path)` (`tools_filesystem/filesystem.py:41`)**:
    *   **Action**: Marks an `FsLogEntry` as unloaded (`load_mode=None`).
    *   **Pinning**: Prevents unloading if the item `is_pinned` by the user.
*   **`fs_write(toolCall, path, content)` (`tools_filesystem/filesystem.py:53`)**:
    *   **Action**: Overwrites a file on disk with new `content`.
    *   **Permissions**: Calls `check_permission` for 'write' access.
    *   **Logging**: Records the operation as a new `FsLogEntry` version.
*   **`fs_append(toolCall, path, content)` (`tools_filesystem/filesystem.py:68`)**: Appends `content` to a file on disk, with permission checks and logging.
*   **`fs_replace(toolCall, path, search, replace)` (`tools_filesystem/filesystem.py:83`)**:
    *   **Action**: Searches for `search` string in a file's content and replaces it with `replace`.
    *   **Fuzzy Matching**: If `search` is not found, it attempts `tools_filesystem.fsutils.find_fuzzy_match` to suggest alternatives.
    *   **Logging**: Records the operation as a new `FsLogEntry` version.
*   **`fs_python_edit(toolCall, path, source, classname=None, functionname=None)` (`tools_filesystem/filesystem.py:102`)**:
    *   **Purpose**: Specialized tool for efficient editing of Python code (functions or classes).
    *   **AST Manipulation**: Uses Python's `ast` module to parse the file, find the target function/class (by `classname`/`functionname`), replace its definition with the provided `source`, and handle indentation.
    *   **Error Handling**: Catches `SyntaxError` for invalid Python code.
    *   **Logging**: Records the operation as a new `FsLogEntry` version.
*   **`get_history_limiting_rules()` (`tools_filesystem/filesystem.py:166`)**:
    *   Defines rules for the `HistoryLimiter` to manage visibility of `fs_*` tool calls in the LLM's context.
    *   Includes rules for unloaded paths, per-path/per-function limits, and general filesystem operation limits.

---

## Filesystem Utilities (`tools_filesystem/fsutils.py`)

*   **`find_fuzzy_match(text, search, ...)` (`tools_filesystem/fsutils.py:10`)**: Implements a fuzzy string matching algorithm (based on Levenshtein distance and splitting strategies) to help the agent find approximate matches for `fs_replace`.
*   **`make_patch(from_content, to_content)` (`tools_filesystem/fsutils.py:129`)**: Generates a diff patch string using `diff_match_patch` library.
*   **`apply_patch(original_content, patching)` (`tools_filesystem/fsutils.py:137`)**: Applies a diff patch to `original_content`.
*   **Path Helpers (`get_abs_path`, `get_relative_path`, `clean_path`):** Standardizes path handling, converting between absolute and relative paths based on the `agentInstance.workingdir`.
*   **`format_directory_listing(entries)` (`tools_filesystem/fsutils.py:165`)**: Formats a list of file/directory entries into a human-readable, LLM-friendly hierarchical string with `d` and `f` prefixes.

---

## Filesystem Permissions (`tools_filesystem/permissions.py`)

*   **`check_permission(agent_instance, absolute_path, action)` (`tools_filesystem/permissions.py:27`)**:
    *   **Purpose**: Enforces access control rules for filesystem operations.
    *   **Rule Parsing (`_parse_rules`)**: Parses `agent_instance.access_rules` (a multi-line string) into structured rules (deny `!`, read-only `<`, write-allowed `>`).
    *   **Rule Matching (`_matches`)**: Checks if a path matches a glob-style pattern, supporting directory patterns (ending with `/`).
    *   **Rule Evaluation**: Rules are evaluated in order. If a rule matches, its permission is applied.
    *   **Default Permissions**: If no specific rule matches, it falls back to:
        *   Read access: Implicitly granted within `workingdir`.
        *   Write access: Controlled by `agent_instance.workingdir_write_allowed` flag within `workingdir`.
        *   Outside `workingdir`: Default deny.

---

## Filesystem Prompts (`tools_filesystem/prompts.py`)

*   **`INSTRUCTIONS`**: Comprehensive text describing the filesystem tools, core principles, best practices, available tools (`fs_load`, `fs_unload`, etc.), and how to interpret `FS_TOOL_CONTENT` messages.
*   **`CONTENT_INJECTION`**: Jinja2 template for formatting `FsLogEntry` data when injected into the LLM's context.
*   **`FUNCTIONS`**: A dictionary defining the schema for all `fs_*` tool calls, including descriptions and parameters.

---

## Content Summarization (`tools_filesystem/summarize.py`)

*   **`summarize(file_path, content)` (`tools_filesystem/summarize.py:9`)**:
    *   **Purpose**: Provides token-efficient structural outlines of various source code and data files.
    *   **Dispatcher**: Selects the appropriate `summarize_*` function based on `file_path` extension.
    *   **Supported Types**: Python, JavaScript/JSX, CSS, C/C++/Arduino, Java, Go, C#, TypeScript/TSX, Ruby, JSON, YAML.
*   **Language-Specific Summarizers (`summarize_python`, `summarize_javascript`, etc.)**:
    *   **Python (`summarize_python`)**: Uses Python's `ast` module and a `PythonSummarizer` (`tools_filesystem/summarize.py:230` - `ast.NodeTransformer`) to replace function and method bodies with `pass` statements, preserving definitions and docstrings.
    *   **CSS (`summarize_css`)**: Uses regex to remove all rules within selectors.
    *   **JSON/YAML (`summarize_yaml_json`)**: Recursively replaces scalar values with `'...'` and array elements with placeholders, preserving structure.
    *   **Other Languages (C/C++, C#, Go, Java, JavaScript/JSX, Ruby, TypeScript/TSX)**: Employ regex and brace/keyword counting heuristics to empty function/method/block bodies, preserving declarations and comments.

---

## Asynchronous Tasks (`tools_filesystem/tasks.py`)

*   **`celery_undo_filesystem_changes(instance_pk, log_entry_pk, user_comment)` (`tools_filesystem/tasks.py:11`)**:
    *   **Purpose**: Celery task to asynchronously perform a single filesystem revert operation.
    *   **Logic**: Retrieves the target `FsLogEntry` and calls its `undo()` method. Logs success/failure to debug logs and adds a user-facing message to the agent's conversation.
*   **`celery_undo_all_filesystem_changes(instance_pk, log_entry_pk, comment='')` (`tools_filesystem/tasks.py:43`)**:
    *   **Purpose**: Celery task to asynchronously perform a bulk undo of multiple filesystem changes.
    *   **Logic**: Identifies all `FsLogEntry` items for a given `instance_pk` created at or after `target_log_entry.created_at`. It then iterates through these items, calling `undo()` on each *unique* path (only the oldest relevant entry for a path is undone in this batch).
    *   **Reporting**: Summarizes successful and failed undo actions in a user-facing conversation message and detailed debug logs.

---

## Tests (`tools_filesystem/tests.py`)

*   **`FsLogEntryUndoTests(TestCase)` (`tools_filesystem/tests.py:133`)**:
    *   Contains unit tests for the `FsLogEntry.undo()` method and the `celery_undo_filesystem_changes` and `celery_undo_all_filesystem_changes` tasks.
    *   **Mocking**: Employs an elaborate `MockFileSystem` (`tools_filesystem/tests.py:46`) and patches (`unittest.mock.patch`) to simulate filesystem interactions and `FsLogEntry._get_storage_method` without touching the actual disk.
    *   **Scenarios**: Tests various undo scenarios including file creation, modification, deletion, directory creation, and directory deletion, as well as handling of patch-stored content and simulated failures.
    *   **`celery_undo_all_filesystem_changes` Tests**: Includes scenarios for basic undo-all, multiple paths, and mixed success/failure to verify the batch undo logic and reporting.

---

## Administrative Interface

### `tools_filesystem.admin.py` (`tools_filesystem/admin.py:4`)
*   Registers the `FsLogEntry` model.
*   Configures `list_display`, `list_filter`, `search_fields`, `autocomplete_fields`, and `readonly_fields` for detailed management and auditing of filesystem log entries.

---

## Application Configuration

### `tools_filesystem.apps.py` (`tools_filesystem/apps.py:3`)
*   **Prompt Registration (`tools_filesystem/apps.py:9`):** In its `ready()` method, it uses `common.models.PromptString.objects.get_or_create()` to seed the database with the tool's `Description`, `ContentInjection`, and `Functions` prompt templates.
