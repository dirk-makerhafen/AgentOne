# AI Agent Documentation (`providers/README.AI.MD`) [Code-Verified]

This directory manages the configuration of external Large Language Model (LLM) API providers, their specific models, and the API keys used for authentication. It establishes a hierarchical structure for these resources.

## Overview of Components

*   **`models.py`**: Defines the Django models (`ApiProvider`, `Model`, `ApiKey`) that structure the provider configuration.
*   **`admin.py`**: Registers these models with the Django administration interface for backend management.
*   **`apps.py`**: Standard Django application configuration.

---

## Core Models and Data Management

All models in this directory inherit from `common.models.ModelWithJsonData`, providing automatic `created_at`, `updated_at` timestamps, and `raw_data` JSON handling.

### `providers.models.ApiProvider` (`providers/models.py:7`)
*   **Purpose**: Represents an external LLM API service (e.g., OpenAI, Anthropic).
*   **Fields**: `name` (CharField) and `url` (CharField).
*   **Usage Metrics (`providers/models.py:13`):** Includes `@property` methods (`total_llm_queries`, `total_prompt_tokens`, `total_completion_tokens`) that aggregate data by querying related `LLMQuery` and `LLMResponse` models, providing a view of overall usage for the provider.
*   **Real-time Updates (`providers/models.py:28`):** The `save()` method calls `dashboard.tasks.send_object_to_clients()` to broadcast changes to connected frontend clients, ensuring immediate UI synchronization.
*   **Client Dictionary (`providers/models.py:34`):** `as_client_dict()` includes serialized lists of its related `Model` and `ApiKey` objects.

### `providers.models.Model` (`providers/models.py:50`)
*   **Purpose**: Represents a specific LLM available from an `ApiProvider` (e.g., "gpt-4", "claude-3-opus").
*   **Fields**: `apiProvider` (ForeignKey to `ApiProvider`), `name`, `enabled` (boolean), `max_tokens`, and `free_limit_per_day`.
*   **Usage Metrics (`providers/models.py:60`):** Similar `@property` methods as `ApiProvider` for `total_llm_queries`, `total_prompt_tokens`, `total_completion_tokens`, but scoped to this specific model.
*   **Real-time Updates (`providers/models.py:67`):** The `save()` method calls `dashboard.tasks.send_object_to_clients()` for UI updates.

### `providers.models.ApiKey` (`providers/models.py:82`)
*   **Purpose**: Stores authentication keys for accessing an `ApiProvider`.
*   **Fields**: `apiProvider` (ForeignKey to `ApiProvider`), `key` (the actual API key), and `comment` for descriptive notes.
*   **Usage Metrics (`providers/models.py:89`):** Similar `@property` methods as `ApiProvider` for usage statistics related to this specific key.
*   **Security (`providers/models.py:101`):** The `as_client_dict()` method explicitly **masks the actual `key` value as '***'** before sending it to the client, preventing exposure of sensitive credentials in the frontend.
*   **Real-time Updates (`providers/models.py:110`):** The `save()` method calls `dashboard.tasks.send_object_to_clients()` for UI updates.

---

## Administrative Interface

### `providers.admin.py` (`providers/admin.py:3`)
*   Registers `ApiProvider`, `ApiKey`, and `Model` with Django's admin interface.
*   Configures `list_display`, `list_display_links`, `search_fields`, `list_filter`, and `autocomplete_fields` to facilitate easy management of provider data. `readonly_fields` are set for automatic timestamps and `raw_data`.

---

## Application Configuration

### `providers.apps.py` (`providers/apps.py:3`)
*   Standard `AppConfig` for the `providers` Django application. It does not contain any special initialization logic in its `ready()` method.
