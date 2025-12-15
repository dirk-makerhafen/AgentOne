# Agent Server

Welcome to Agent Server, a powerful and extensible platform for creating, managing, and interacting with autonomous AI agents. This project provides a complete Django-based backend and a real-time, feature-rich web interface for observing, directing, and debugging agent behavior at a granular level.

It's designed for developers, researchers, and hobbyists who want to move beyond simple prompt-and-response chatbots and build sophisticated agents that can perform complex, multi-step tasks.

_[(Screenshot of the main dashboard UI)]_

---

## Key Features

-   **Multi-Agent Architecture**: Define multiple types of agents and run numerous, distinct instances of each. Clone any instance at any point in its history to branch off and explore different task approaches.
-   **Rich, Real-time UI**: A dynamic web dashboard built with Django and Channels provides a live, color-coded stream of agent thoughts, tool calls, filesystem changes, and debug logs.
-   **Interactive Filesystem Management**: The UI includes a sidebar that shows the agent's current working directory and all loaded files. You can view, pin, and even edit file contents directly in the browser, with changes seamlessly synced.
-   **Comprehensive History Revert**:
    -   **Single File Revert**: Instantly revert any file to a previous state from its change history in the log.
    -   **Full Filesystem Rollback**: Revert the *entire* agent-managed filesystem to the exact state it was in at any point in the conversation history, providing a powerful undo capability.
-   **Extensible Tool System**: Equip agents with a variety of powerful tools out-of-the-box:
    -   **Filesystem**: Read, write, and list files and directories.
    -   **Persistent Memory**: A structured memory system with Short-Term, Medium-Term, and Long-Term tracks.
    -   **Python**: Execute Python code and maintain state in a persistent `VARS` dictionary.
    -   **Inter-Agent Communication**: Allow agents to send messages and delegate tasks to each other.
-   **Granular Context Window Control**: Fine-tune an agent's context window using a rules-based history limiter. Set precise limits on how many successful, failed, or pending tool calls are included in the LLM prompt on a per-tool or even per-file basis.
-   **Remote System Management & Deployment**:
    -   Define "Systems" (e.g., local, staging, production) that can run on remote machines.
    -   Assign agent instances to specific systems to distribute workloads.
    -   Deploy the latest version of the Agent Server code to all defined systems with a single click from the UI.
-   **In-depth Debugging**: The UI provides expandable, detailed views of LLM prompts, tool call arguments/results, and state changes, making it easy to trace an agent's execution flow.

---

## Architecture Overview

The Agent Server is comprised of several key components:

1.  **Django Web Application**: The central hub that serves the web UI, provides the Django Admin for configuration, and handles WebSocket connections for real-time updates.
2.  **Redis**: Acts as the message broker for Celery and the channel layer for Django Channels, enabling asynchronous task processing and real-time communication.
3.  **Celery Worker (Main)**: A primary worker process that handles core application tasks, including LLM queries, UI updates, and deployments.
4.  **Celery Beat**: A scheduler that handles periodic tasks, such as checking system heartbeats to ensure remote workers are online.

---

## Getting Started

### Prerequisites

-   Python 3.10+
-   Git
-   Redis Server

### 1. Clone the Repository

```bash
git clone <repository-url>
cd agent_server3
```

### 2. Create a `.gitignore` File

It's recommended to create a `.gitignore` file to exclude common Python and temporary files.

```bash
# Example .gitignore content
__pycache__/
*.pyc
db.sqlite3
venv/
```

### 3. Create and Activate a Python Virtual Environment

```bash
python3 -m venv venv
source venv/bin/activate
```

### 4. Install Dependencies

```bash
pip install -r requirements.txt
```

### 5. Configure Settings

Edit `agent/settings.py` to configure your database and Redis connection.

-   **For simple local development (recommended):**
    Set `LOCAL_DEV = True`. This will use a `db.sqlite3` file and connect to Redis on `localhost:6739`.

-   **For a custom/production setup:**
    Set `LOCAL_DEV = False` and configure the `DATABASES`, `CELERY_BROKER_URL`, and `CHANNEL_LAYERS` settings to point to your MySQL/PostgreSQL and Redis instances.

### 6. Apply Database Migrations

This will create the necessary tables in your configured database.

```bash
python3 manage.py migrate
```

### 7. Create a Superuser

You will need a superuser account to access the Django Admin interface for initial setup.

```bash
python3 manage.py createsuperuser
```

---

## Running the Application

To run the full application locally, you will need to start three separate processes in three different terminals (ensure your `venv` is active in each).

**Terminal 1: Start the Django Web Server**
```bash
 daphne -b 0.0.0.0 -p 8000 dashboard.asgi:app
```

**Terminal 2: Start the Main Celery Worker**
```bash
 celery -A agent worker --concurrency=10  --loglevel=info

```

**Terminal 3: Start the Celery Beat Scheduler**
```bash
celery -A agent beat -l info   --loglevel=info
```

You can now access the Agent Server dashboard at `http://127.0.0.1:8000/`.

---

## Core Concepts & Initial Setup

### Admin Panel First Steps

Before you can create an agent, you must configure a few core components in the Django Admin at `http://127.0.0.1:8000/admin/`:

1.  **Add an API Key**: Go to `Providers > Api Keys` and add an API key for your preferred LLM provider (e.g., OpenAI).
2.  **Add a Model**: Go to `Providers > Models` and add a model definition, linking it to the API key you just created (e.g., `gpt-4-turbo`).
3.  **Create a System**: Go to `Systems > Systems`. A "System" represents an environment where agent workers can run. For local development, create one named `local-dev`.
4.  **Create an Agent**: Go to `Agent > Agents`. An "Agent" is a *template* or *definition*. You can assign a default model and provide a master prompt or description here.

### Agent vs. Agent Instance

-   **Agent**: The template. It defines the core identity and purpose.
-   **Agent Instance**: A running, stateful copy of an Agent. All conversation history, memory, and filesystem changes are tied to an instance.

From the main dashboard, you can now create an "instance" of the Agent you defined. Once created, you can select it from the sidebar to begin interacting with it.

---

## License

This project is licensed under the MIT License.

