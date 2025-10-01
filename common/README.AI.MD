# AI Agent Documentation (`common/README.AI.MD`) [Code-Verified]

This directory contains reusable base Django models and a custom manager shared across other applications, providing foundational utilities and enforcing consistency.

## Overview of Components

*   **`models.py`**: Defines abstract base models (`ModelWithJsonData`) and a custom manager (`PromptStringManager`) for versioning prompts.
*   **`admin.py`**: Registers `PromptString` with the Django administration interface.
*   **`apps.py`**: Standard Django application configuration.

---

## Core Models and Managers

### `common.models.ModelWithJsonData` (`common/models.py:72`)
*   **Purpose**: An `abstract = True` base model providing common fields and JSON data handling for other models to inherit.
*   **Fields**:
    *   `created_at`: `DateTimeField` (auto_now_add).
    *   `updated_at`: `DateTimeField` (auto_now).
    *   `raw_data`: `TextField` (max_length=100MB, default=b'') stores JSON data as a string.
*   **`data` Property (`common/models.py:80`)**:
    *   Acts as a Pythonic interface to `raw_data`.
    *   **Getter**: Deserializes `raw_data` from JSON string to a Python dictionary (`self._data`) on access. Handles `json.loads` errors gracefully.
    *   **Setter**: Sets `self._data` to a new dictionary.
*   **`save()` Method (`common/models.py:94`)**:
    *   Automatically updates `created_at` (on creation) and `updated_at` timestamps.
    *   Serializes `self.data` (the `_data` dictionary) back into the `raw_data` field before saving.
    *   Uses `dirtyfields.DirtyFieldsMixin` to track field changes, allowing Django to perform efficient partial updates (only changed fields are written to the database) if `update_fields` is not explicitly provided in `kwargs`.

### `common.models.PromptString` (`common/models.py:36`)
*   **Purpose**: Stores LLM prompt templates, designed for version control.
*   **Fields**:
    *   `owner`: `ForeignKey` to `User` (null=True, default=None). `None` indicates a system-owned prompt.
    *   `source`: `CharField` (e.g., "Agent", "Tools.Common") categorizes the prompt.
    *   `key`: `CharField` (e.g., "System", "OutputFormat") identifies the specific prompt.
    *   `value`: `TextField` (max_length=1MB) contains the actual prompt content.
    *   `next_version`: `OneToOneField` to `self` (null=True, blank=True). Points to the next version in the prompt's history. `next_version__isnull=True` signifies the latest version.
*   **`as_client_dict()` Method (`common/models.py:53`)**: Prepares prompt data for frontend consumption, including `id`, `owner_id`, `owner_username`, `source`, `key`, `value`, and flags like `is_deleteable`, `is_editable`, and `is_newest_version`.
*   **`get_template()` Static Method (`common/models.py:70`)**: Retrieves the latest version (`next_version__isnull=True`) of a system-owned (`owner=None`) prompt by its `source` and `key`.

### `common.models.PromptStringManager` (`common/models.py:8`)
*   **Purpose**: Custom manager for `PromptString` that overrides the default `objects` manager to implement versioning logic for `get_or_create`.
*   **`get_or_create()` Method (`common/models.py:9`)**:
    *   Attempts to find the latest version of a prompt matching `owner`, `source`, and `key`.
    *   If no prompt exists, or if the provided `value` differs from the latest existing prompt's `value`, a new `PromptString` is created. If an older version exists, its `next_version` field is updated to point to this new prompt.
    *   If an identical latest prompt already exists (same `owner`, `source`, `key`, and `value`), it returns the existing prompt without creating a new version.

---

## Administrative Interface

### `common.admin.py` (`common/admin.py:3`)
*   Registers `PromptString` with the Django admin.
*   `list_display` includes `pk`, `created_at`, `owner`, `source`, `key`, `value`.
*   `readonly_fields` are `created_at` and `updated_at`.

---

## Application Configuration

### `common.apps.py` (`common/apps.py:3`)
*   Standard `AppConfig` for the `common` Django application. It does not contain any special initialization logic in its `ready()` method.
