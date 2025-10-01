# AI Agent Onboarding & Guidelines (`README.AI.MD`)

This document provides essential context, architectural principles, and coding standards for any AI agent working on this project. Load and review this file at the beginning of each session to ensure alignment.

## Project Overview

- **Mission:** To build and maintain a robust, multi-agent AI development environment with a rich, interactive user interface.
- **Core Technologies:** Django (backend), Channels (WebSockets), JavaScript/Handlebars (frontend), Celery (background tasks).

## Architectural Principles

1.  **Modularity:** New tools and major features should be encapsulated in their own Django apps (e.g., `tools_shell`). This includes creating `prompts.py`, `tool.py`/`shelltool.py`, and an `apps.py` for registration.
2.  **Asynchronous Backend:** The core of the application is built on Django Channels for real-time WebSocket communication. Business logic triggered by user actions is handled in dedicated consumer functions.
3.  **Instance-Specific Frontend:** The UI supports multiple agent instances. All JavaScript and CSS must be carefully scoped to the specific `agentInstancePk` to prevent state leakage or incorrect element selection. Use of instance-specific data attributes and selectors is mandatory.
4.  **Templating:** Use Handlebars.js for dynamically rendering complex HTML components on the frontend. Avoid generating large blocks of HTML directly in JavaScript strings.

## Coding Style

- **Python:** Adhere strictly to PEP 8.
- **JavaScript:** Follow modern ES6+ standards. Use `const` and `let` appropriately. Maintain a consistent style for variable naming (e.g., camelCase).
- **DOM Manipulation:** Prefer `data-*` attributes for targeting elements in JavaScript over relying on class names that are used for styling.

## Key File Locations

- **Main WebSocket Consumer:** `dashboard/consumers/consumers.py` (This is the central router for incoming messages).
- **Frontend Rendering Logic:** `dashboard/static/js/` (Contains individual `.js` files for rendering different message types and UI components).
- **Tool Definitions:** Each tool resides in its own `tools_*` directory.
- **Core Agent Models:** `agent/models/`
