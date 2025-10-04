# AI Engine Documentation: `tools_mcp` App

## Overview

The `tools_mcp` Django app provides the functionality to connect the agent system to external Model Context Protocol (MCP) servers. MCP is a standardized protocol that allows an AI or agent system to discover and invoke tools (functions, APIs) hosted on a remote server.

This app manages the configuration of these external servers, handles the process of connecting to them, retrieves the list of available tools, and stores this information for use by agent instances.

## Key Components

### 1. Models (`models.py`)

#### `MCPServer`
This is the core model of the app, representing a single configured MCP server endpoint.

-   **`name`**: A unique, human-readable name for the server (e.g., "Jira Tools," "Weather API Server").
-   **`endpoint_url`**: The full URL where the MCP server is listening. This must be a valid HTTP or HTTPS URL.
-   **`status`**: The current connection status of the server. It can be one of:
    -   `connected`: Successfully connected and retrieved the tool list.
    -   `disconnected`: The initial state before any connection attempt.
    -   `error`: A connection or tool-listing attempt failed.
    -   `connecting`: An active connection or tool-listing attempt is in progress.
-   **`last_error`**: Stores the text of the last exception if the status is `error`.
-   **`tools`**: A `JSONField` that stores the list of tool definitions retrieved from the server, formatted according to the OpenAI function tool specification.
-   **`enabled`**: A boolean flag to enable or disable the use of this server's tools by agents.
-   **`as_client_dict()`**: A method that serializes the model instance into a dictionary suitable for sending to the frontend client via WebSockets.
-   **`save()`**: The save method is overridden to call `send_object_to_clients`, a task that broadcasts the updated model data over WebSockets, ensuring the UI is always synchronized with the database state.

### 2. Admin (`admin.py`)

A standard Django admin interface is configured for the `MCPServer` model, allowing for easy management of MCP server configurations through the Django admin panel.

### 3. WebSocket Consumers (`dashboard/consumers/mcp.py`)

This file contains the backend logic for handling all real-time interactions with the MCP feature from the frontend.

-   **Handlers**: Asynchronous functions (`list_mcp_servers`, `create_mcp_server`, `update_mcp_server`, `delete_mcp_server`, `refresh_mcp_server_tools`) that process incoming WebSocket messages.
-   **Database Operations**: All Django ORM calls are wrapped with `@database_sync_to_async` to be safely executed in an asynchronous context.
-   **Celery Integration**:
    -   `refresh_mcp_server_tools_task`: This is a `@shared_task` that runs in a Celery worker. It is responsible for the potentially long-running process of connecting to the external MCP server, fetching the tool list, and updating the `MCPServer` model instance. Using Celery prevents the WebSocket consumer from blocking during this network-dependent operation.

### 4. Application Configuration (`apps.py`)

Defines the standard Django app configuration for `tools_mcp`.

## Data Flow & UI Integration

1.  **Initial Load**: When the dashboard loads, `websocket.js` calls `requestMcpList()`.
2.  **Tab Activation**: When the "MCP" tab is opened in the UI, `tabs.js` also calls `requestMcpList()`.
3.  **Backend Request Handling**: The `list_mcp_servers` message is received by the main consumer (`dashboard/consumers/consumers.py`), which routes it to the `list_mcp_servers` handler in `dashboard/consumers/mcp.py`.
4.  **Data Fetch & Broadcast**: The handler fetches all `MCPServer` objects from the database, serializes them using `as_client_dict`, and broadcasts the list to all connected clients.
5.  **Frontend Rendering**: `websocket.js` receives the `list_mcp_servers` message and passes the data to `renderMcpList()` in `renderMcpList.js`.
6.  **UI Display**: `renderMcpList.js` uses a Handlebars template (defined in `dashboard.html`) to render the list of MCP servers in the UI. It also attaches event listeners for all user actions (add, edit, delete, refresh).
7.  **CRUD Operations**: User actions trigger functions in `renderMcpList.js` which send WebSocket messages (`create_mcp_server`, `update_mcp_server`, `delete_mcp_server`) to the backend. The backend handlers process these requests, update the database, and the overridden `save()` method on the model automatically pushes the changes back to all clients for a real-time update.
8.  **Tool Refresh**: Clicking the "Refresh" button sends a `refresh_mcp_server_tools` message. The backend handler triggers the `refresh_mcp_server_tools_task.delay()` Celery task. The task immediately updates the server's status to "connecting" (which is pushed to the UI), performs the network request, and then updates the model with the result ("connected" or "error"), which is again automatically pushed to the UI.
