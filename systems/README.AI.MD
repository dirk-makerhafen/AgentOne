# AI Agent Documentation (`systems/README.AI.MD`) [Code-Verified]

This directory manages the definition, status, and configuration of remote execution systems or "hosts" where agent instances can run. It includes models for system details, background tasks for health checks, and API endpoints for client registration.

## Overview of Components

*   **`models.py`**: Defines the `System` Django model, which stores information about execution environments.
*   **`admin.py`**: Registers the `System` model with the Django administration interface.
*   **`tasks.py`**: Contains Celery background tasks for polling remote executors and updating their heartbeat status.
*   **`urls.py`**: Defines API routes, specifically for client registration.
*   **`views.py`**: Implements the logic for the client registration API endpoint.
*   **`management/commands/check_system_heartbeats.py`**: A Django management command to manually or periodically check system heartbeats.
*   **`service_templates/celery.service.template`**: A template for systemd service files, used to deploy Celery workers on remote systems.
*   **`apps.py`**: Standard Django application configuration.

---

## Core Models and Data Management

### `systems.models.System` (`systems/models.py:4`)
*   **Purpose**: Represents an external system (host) where agent processes or tool executions can occur.
*   **Inheritance**: Inherits from `common.models.ModelWithJsonData`.
*   **Fields**:
    *   `name`: `CharField` (max_length=255, unique=True).
    *   `description`: `TextField` (blank=True, default='').
    *   `status`: `CharField` with `STATUS_CHOICES` (`online`, `offline`, `maintenance`) (`systems/models.py:6`).
    *   `last_heartbeat`: `DateTimeField` (null=True, blank=True) recording the last time the system reported its status.
    *   `is_remote_executor`: `BooleanField` (default=False). If `True`, this system is a lightweight remote executor.
    *   `executor_url`: `URLField` (max_length=1024, blank=True) for the remote executor's API endpoint.
    *   `executor_api_key`: `CharField` (max_length=255, blank=True) for authenticating with the remote executor.
    *   `executor_mode`: `CharField` with `EXECUTOR_MODE_CHOICES` (`local`, `http`, `websocket`) (`systems/models.py:24`), determining how tool calls are dispatched for agent instances using this system.
*   **Real-time Updates (`systems/models.py:34`):** The `save()` method calls `dashboard.tasks.send_object_to_clients()` to broadcast changes to connected frontend clients, ensuring immediate UI synchronization.
*   **Client Dictionary (`systems/models.py:39`):** `as_client_dict()` provides a serialized representation of the system for frontend use, explicitly including executor configuration.

---

## Client Registration API

*   **`systems.urls.py` (`systems/urls.py:3`)**:
    *   Defines the URL `api/register_client/` which maps to `systems.views.register_client`. This endpoint is mounted under `/dashboard/systems/api/` as per `dashboard/urls.py`.
*   **`systems.views.py` (`systems/views.py:7`)**:
    *   **`register_client` View:**
        *   **Purpose**: Allows external executor instances to register themselves with the Carna server.
        *   **Authentication (`systems/views.py:22`):** Authenticates the request using a `server_secret` provided by the client against `settings.AGENT_SERVER_SECRET_KEY`. If the secret doesn't match, returns `HttpResponseForbidden`.
        *   **Client URL Resolution (`systems/views.py:26`):** If `client_url` is not provided in the payload, it infers the client's IP address from `HTTP_X_FORWARDED_FOR` or `REMOTE_ADDR` and constructs an `http://<ip>:<port>` URL.
        *   **System Creation/Update (`systems/views.py:39`):** Uses `System.objects.get_or_create()` to find or create a `System` entry based on `client_name`. It defaults `executor_mode` to `'http'`.
        *   **API Key Provisioning (`systems/views.py:48`):** If the system is newly created or an `executor_api_key` is missing, a new `secrets.token_urlsafe(32)` is generated and assigned as the `executor_api_key`.
        *   **Response (`systems/views.py:55`):** Returns a `JsonResponse` containing the `client_name`, the provisioned `client_api_key`, and the `resolved_client_url`.

---

## System Health Checks and Management

*   **`systems.tasks.py` (`systems/tasks.py:16`)**:
    *   **`poll_remote_executors_for_heartbeat` Celery Task:**
        *   **Purpose**: Periodically polls registered remote executors to check their health and update their `last_heartbeat`.
        *   **Polling Logic (`systems/tasks.py:30`):**
            *   Filters `System` objects for remote executors with configured `executor_url`.
            *   Uses `httpx.AsyncClient` and `asyncio.gather` with `async_to_sync` (`systems/tasks.py:65`) to concurrently send `GET /` requests to each executor's `executor_url`, including the `X-API-Key` header.
            *   Updates `system.last_heartbeat` if the poll is successful.
        *   **Status Update Logic (`systems/tasks.py:77`):**
            *   After polling, it defines a `stale_threshold` (2 minutes).
            *   Marks `online` systems with stale or missing heartbeats as `offline`.
            *   Marks `offline` systems with fresh heartbeats as `online`.
*   **`systems.management.commands.check_system_heartbeats.py` (`systems/management/commands/check_system_heartbeats.py:9`)**:
    *   **Purpose**: A Django management command (`python manage.py check_system_heartbeats`) that provides a CLI interface to the heartbeat check logic.
    *   **Functionality**: Contains logic almost identical to the `status` update portion of `systems.tasks.poll_remote_executors_for_heartbeat`, allowing for manual or scheduled execution of heartbeat status updates without necessarily performing the active polling.

---

## Administrative Interface

### `systems.admin.py` (`systems/admin.py:3`)
*   Registers the `System` model with the Django admin.
*   Customizes `list_display`, `list_filter`, `search_fields`, and `fieldsets` for structured management of system configurations, including executor details.
*   `readonly_fields` are set for automatic timestamps and `last_heartbeat`.

---

## Application Configuration

### `systems.apps.py` (`systems/apps.py:3`)
*   Standard `AppConfig` for the `systems` Django application. It does not contain any special initialization logic in its `ready()` method.
