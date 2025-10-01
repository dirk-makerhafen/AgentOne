# AI Agent Documentation (`dashboard/README.AI.MD`) [Code-Verified]

This directory contains all code for the user-facing dashboard, including backend WebSocket handlers and frontend rendering logic. This documentation is based on a full review of the source code.

## Core Architectural Principles

1.  **WebSocket-Centric Communication:** The entire application is real-time and event-driven via a WebSocket connection managed by Django Channels.

2.  **Backend: The Consumer as a Router:**
    *   **`consumers/consumers.py`**: The `AgentConsumer` class is the single entry point for all client communication.
    *   **Message Dispatching:** The `receive` method is a large `if/elif` block that routes incoming messages to specific handler functions based on the `message_type` string in the JSON payload.
    *   **Broadcasting via Channels Groups:** The backend uses two distinct group layers for pushing updates:
        *   `user_{user_pk}`: For user-wide notifications (e.g., the list of available agents).
        *   `agentInstance_{instance_pk}`: For all events specific to one agent instance. A client must send a `'subscribe'` message to join this group.

3.  **Frontend: A Consistent Rendering Pattern:**
    *   **`static/js/websocket.js`**: Manages the client connection. Its `onmessage` function contains a `switch` statement that acts as the primary client-side router, delegating payloads to the correct `render...()` function based on the `payload.object` field.
    *   **Handlebars Templates:** UI components are defined as Handlebars template strings at the top of their corresponding `render<Thing>.js` file.
    *   **Stateful Idempotent Rendering:** Rendering functions (`renderConversationMessage.js` is a prime example) follow a critical pattern to update the DOM without losing user state:
        1. Check if a DOM element with the new data's ID already exists.
        2. If it does, inspect the existing element for UI state (e.g., expanded views, toggles).
        3. Apply this state to the new HTML element *before* it's added to the DOM.
        4. Use `replaceChild()` to swap the old element with the new one. This ensures updates are seamless.
    *   **Global State Caching:** The frontend uses global variables like `window.allAvailableSystems` to cache lists of data from the server, which are then used to populate UI elements like dropdowns.

## Full-Stack Data Flow (Example: Pinning a Message)

1.  **User Action:** User clicks the pin icon on a message in the UI.
2.  **Frontend Event:** The `onclick` attribute calls `togglePinToContext(messageId, instancePk)` in `renderConversationMessage.js`.
3.  **Client to Server:** This function sends a WebSocket message with `type: 'update_conversation_message_flags'`.
4.  **Backend Routing:** `consumers.py` receives the message and its `if/elif` block routes it to the `handle_conversationmessage_flags` handler.
5.  **Business Logic:** The handler updates the `pin_to_context` field on the `ConversationMessage` model and saves it.
6.  **Server to Client (Broadcast):** The model's `save()` method triggers a task that serializes the updated `ConversationMessage` and broadcasts it to the `agentInstance_{instance_pk}` group.
7.  **Frontend Reception:** `websocket.js` receives the updated message payload. Its `switch` statement routes it to `renderConversationMessage()`.
8.  **DOM Update:** `renderConversationMessage()` executes its idempotent rendering logic, replacing the old message element with a new one that reflects the "pinned" state.

## Guidelines for Modification

*   **Adding a new User Action:**
    1.  Define a new `message_type` string.
    2.  Add a new handler function in `dashboard/consumers/`.
    3.  Add an `elif` block for your new `message_type` in `consumers.py`.
    4.  Add a corresponding JavaScript function to send the message from the client.
*   **Adding a new Display Component:**
    1.  Define a new `object` name (e.g., 'NewComponent').
    2.  Create a `renderNewComponent.js` file with a Handlebars template.
    3.  Add a `case 'NewComponent':` to the `switch` statement in `websocket.js` to call your new renderer.
    4.  Ensure the backend serializes and sends this object type after a relevant event.
