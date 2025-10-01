# AI Agent Documentation (`tools_memory/README.AI.MD`) [Code-Verified]

This directory implements the core memory system for the AI agent, allowing it to store and retrieve information across different time horizons (Short-Term, Medium-Term, Long-Term) and thematic tracks (SELF, REVIEW, INSIGHTS, GOALS, STATUS, SYSTEMS, PLANS, PREDICTIONS, MEMORY). It provides mechanisms for adding, correcting, and repositioning memory items.

## Overview of Components

*   **`models.py`**: Defines the `MemoryItem` Django model, which represents a single entry in the agent's memory.
*   **`memory.py`**: Implements the `SMLMemoryTool`, exposing `memory_*` functions for LLM interaction and managing memory content generation for the agent's context.
*   **`prompts.py`**: Stores static prompt templates for the memory tool's description, function definitions, and the structured format for injecting memory content into the LLM's context. It also defines the various memory `TRACKS` and `LAYERS`.
*   **`admin.py`**: Registers `MemoryItem` with the Django administration interface.
*   **`apps.py`**: Standard Django application configuration, handling prompt string and memory track/layer header registration.

---

## Core Models and Data Management

### `tools_memory.models.MemoryItem` (`tools_memory/models.py:7`)
*   **Purpose**: Represents an individual piece of information stored in the agent's memory.
*   **Inheritance**: Inherits from `common.models.ModelWithJsonData`.
*   **Fields**:
    *   `agent`, `agentInstance`: ForeignKeys linking to the agent and instance that owns this memory.
    *   `conversationMessage`, `toolCall`: Optional ForeignKeys linking to the origin of the memory (e.g., which conversation message or tool call led to this memory).
    *   `next_version`: `OneToOneField` to `MemoryItem` itself, forming a linked list for versioning/correction. `None` indicates the latest version.
    *   `track`, `layer`: `CharField` (e.g., 'REVIEW', 'ST') categorizing the memory.
    *   `index`: `IntegerField` indicating the position of the memory within its track/layer.
    *   `value` property (`tools_memory/models.py:38`): Stores the actual memory content, backed by the `data` JSON field.
*   **Version History (`first_version`, `latest_version` properties)**: Helper properties to navigate the linked list of memory item versions.
*   **Real-time Updates (`tools_memory/models.py:27`):** The `save()` method calls `dashboard.tasks.send_object_to_clients()` to broadcast changes (additions, updates) to connected frontend clients, ensuring immediate UI synchronization.
*   **Client Dictionary (`tools_memory/models.py:44`):** `as_client_dict()` provides a serialized representation for frontend display.

---

## Memory Tool (`tools_memory/memory.py`)

### `tools_memory.memory.SMLMemoryTool` (`tools_memory/memory.py:10`)
*   **Purpose**: Implements the `memory_*` functions exposed to the LLM. Inherits from `tools_common.models.BaseTool`.
*   **`functions` Dictionary (`tools_memory/memory.py:11`)**: Defines the available tool functions (`memory_add`, `memory_correct`, `memory_reposition`), sourced from `tools_memory.prompts.FUNCTIONS`.
*   **`tracks` Property (`tools_memory/memory.py:14`)**: Returns a list of all defined memory track names.
*   **`get_header_parts()` (`tools_memory/memory.py:18`)**: Injects the memory tool's `Description` and `Functions` (definitions) into the LLM's context using `PromptString` templates.
*   **`get_content_parts()` (`tools_memory/memory.py:26`)**:
    *   **Context Injection**: This crucial method dynamically generates the "Current Memory Content" section for the LLM's prompt.
    *   **Memory Retrieval**: Retrieves the latest versions of `MemoryItem`s for each defined `track` and `layer`, ordered by `index`, subject to `agentInstance.limit_max_memory_items`.
    *   **Stalled/Outdated Warnings (`tools_memory/memory.py:51`):** Includes logic to detect and flag memory tracks/layers that appear outdated or have not been updated for a long time, injecting `!ATTENTION:` warnings.
    *   **"To Be Forgotten" Flags (`tools_memory/memory.py:84`):** Flags older memory items within a layer with `[to be forgotten, review now!]` if the layer is approaching its limit, prompting the agent to summarize them to higher layers.
    *   **Formatted Output**: Uses `PromptString` templates (`ContentHeader`, `ContentHeader.<track>`, `ContentHeader.<track>.<layer>`, `Content`) to format the memory content clearly for the LLM, including track/layer descriptions.
*   **`get(track, layer, limit=20)` (`tools_memory/memory.py:126`)**: Retrieves a specified number of the latest memory items for a given `track` and `layer`, excluding empty content.
*   **`memory_add(toolCall, track, layer, content)` (`tools_memory/memory.py:138`)**:
    *   **Action**: Adds a new `MemoryItem` to the specified `track` and `layer` with the given `content`.
    *   **Indexing**: Assigns the new item the next available `index` for that track/layer.
    *   **Real-time Update**: Broadcasts the new item to the frontend.
*   **`memory_correct(toolCall, track, layer, index, content)` (`tools_memory/memory.py:147`)**:
    *   **Action**: Updates the `content` of an existing `MemoryItem` at a specific `index`.
    *   **Versioning**: Instead of overwriting, it creates a new `MemoryItem` linked to the old one via `next_version`, preserving history.
    *   **Duplicate Check**: Returns a warning if the `content` is identical to the existing one.
    *   **Real-time Update**: Broadcasts the updated item to the frontend.
*   **`memory_reposition(toolCall, track, layer, index, steps)` (`tools_memory/memory.py:165`)**:
    *   **Action**: Moves a `MemoryItem` to a new `index` within its `track` and `layer`, adjusting other items' indices as needed.
    *   **Versioning**: For each moved item, it creates a new `MemoryItem` (with the new index) linked to the old one.
    *   **Real-time Update**: Broadcasts the updated items to the frontend.
*   **`_memory_add(toolCall, track, layer, content)` (`tools_memory/memory.py:202`)**: Internal helper method for `memory_add`.
*   **`get_history_limiting_rules()` (`tools_memory/memory.py:214`)**:
    *   Defines rules for the `HistoryLimiter` to manage the visibility of `memory_*` tool calls in the LLM's context.
    *   Includes rules with varying limits based on function name, track, and layer specificity.

---

## Memory Prompts (`tools_memory/prompts.py`)

*   **`DESCRIPTION`**: Detailed explanation of the memory system, memory tracks and layers, rules for memorizing/not memorizing, and the expected output format for memory content.
*   **`FUNCTIONS`**: Dictionary defining the schema for `memory_add`, `memory_correct`, and `memory_reposition`.
*   **`TRACKS`**: A Python dictionary (also defined in `memory.py`) that serves as the canonical definition of all memory tracks (e.g., `REVIEW`, `SELF`) and their associated layers (e.g., `ST`, `MT`, `LT`), along with their descriptions.
*   **`STALLED_WARNING`**: Jinja2 template for the warning message when memory tracks/layers are detected as outdated.
*   **`CONTENT_HEADER`**: Jinja2 template for the overall memory content header.
*   **`CONTENT`**: Jinja2 template for formatting individual memory items within their track/layer sections, including "to be forgotten" flags.

---

## Administrative Interface

### `tools_memory.admin.py` (`tools_memory/admin.py:3`)
*   Registers the `MemoryItem` model.
*   Configures `list_display`, `list_filter`, `search_fields`, `autocomplete_fields`, and `readonly_fields` for comprehensive management and auditing of memory entries.

---

## Application Configuration

### `tools_memory.apps.py` (`tools_memory/apps.py:3`)
*   **Prompt Registration (`tools_memory/apps.py:9`):** In its `ready()` method, it uses `common.models.PromptString.objects.get_or_create()` to seed the database with the tool's `Description`, `Functions`, `StalledWarning`, and structured content templates. It dynamically creates prompt strings for each track and layer header defined in `TRACKS`.

---