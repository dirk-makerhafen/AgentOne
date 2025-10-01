# AI Agent Documentation (`executor/README.AI.MD`) [Code-Verified]

This directory contains a standalone FastAPI application that functions as a remote execution environment. It allows the main Carna server to delegate Python and shell script execution to an external host, enhancing scalability and security.

## Overview of Components

*   **`main.py`**: The entry point for the FastAPI application, handling configuration, API key authentication, and exposing endpoints for Python and shell execution.
*   **`primitives.py`**: Contains the low-level functions for executing Python code, shell scripts, and fundamental filesystem operations. It includes a decorator to enable transparent local or remote dispatch.
*   **`installer.py`**: A command-line utility for comprehensive management of the executor: installation (including virtual environment setup and service registration), uninstallation, and status checks across Windows, Linux, and macOS. It also handles initial client registration with the Carna server.
*   **`requirements.txt`**: Lists the Python dependencies necessary for the executor to operate (e.g., `fastapi`, `uvicorn`).

---

## Core Execution Application (`executor/main.py`)

*   **Purpose**: The central component that exposes execution capabilities via a RESTful API.
*   **Configuration (`main.py:10`, `load_all_config()`):**
    *   Loads default settings from `CONFIG_DEFAULTS`.
    *   Overrides defaults with values from `client_config.json` (if present in the same directory). Key configurable items are `APIKEY`, `PORT`, `LISTEN` address, and `NAME`.
    *   **Critical Behavior**: If `APIKEY` is not set after configuration loading, the application terminates (`sys.exit(1)` at `main.py:30`).
*   **FastAPI Initialization (`main.py:44`):** Sets up the FastAPI application with metadata (`title`, `description`, `version`) derived from configuration.
*   **API Key Authentication (`get_api_key()` at `main.py:46`):**
    *   **Mechanism**: Implements API key security using `fastapi.security.api_key.APIKeyHeader`. It expects an `X-API-Key` header in incoming requests.
    *   **Validation**: Compares the received key against the `API_KEY` loaded from `client_config.json`.
    *   **Security Enforcement**: Raises `HTTPException(status.HTTP_403_FORBIDDEN)` for invalid credentials. All API endpoints require this authentication method.
*   **API Endpoints**:
    *   `GET /` (`main.py:53`): A health check endpoint. Returns JSON `{ "status": "ok", "name": ..., "port": ..., "listen": ... }`.
    *   `POST /shell` (`main.py:57`):
        *   **Request Body**: Accepts a `ShellExecution` Pydantic model (`main.py:40`), containing `command` (the script string), optional `env` (environment variables), and `timeout`.
        *   **Execution**: Calls `executor.primitives.run_shell_script()` to execute the command.
        *   **Response**: Returns a JSON response containing the script's `stdout`, `stderr`, and `return_code`.
    *   `POST /python` (`main.py:62`):
        *   **Request Body**: Accepts a `ScriptExecution` Pydantic model (`main.py:35`), containing `source` (the Python code string), optional `locals_dict` (initial local variables), and `locals_to_return` (list of local variable names to return).
        *   **Execution**: Calls `executor.primitives.run_python_code()` to execute the Python code.
        *   **Response**: Returns a JSON response including `stdout`, `stderr`, and a `vars` dictionary for any requested `locals_to_return`.
*   **Server Startup (`main.py:68`):** If `main.py` is executed directly, `uvicorn.run()` starts the ASGI server on the configured `LISTEN` address and `PORT`.

---

## Execution Primitives (`executor/primitives.py`)

*   **Purpose**: Provides core functionalities for code execution and filesystem interaction. It contains the actual implementations of the operations exposed via the FastAPI endpoints.
*   **`dispatched_primitive_operation` Decorator (`primitives.py:12`):**
    *   **Core Feature**: This decorator is the key mechanism for abstracting *where* an operation runs. It enables functions to be executed either locally within the Carna server's process or remotely on an attached executor instance.
    *   **Conditional Dispatch (`primitives.py:44`):**
        *   If an `agentInstance` is provided and its associated `system` object has `is_remote_executor=True`, `executor_url`, and `executor_api_key` defined, the decorated function call is converted into a `POST /python` request and sent to the remote executor (`_run_remote` function at `primitives.py:27`).
        *   Otherwise (no `agentInstance`, `system` not configured for remote, or missing remote details), the function executes locally within the current process (`_run_local` function at `primitives.py:19`).
    *   **Error Handling**: Both local and remote execution paths are wrapped in `try-except` blocks, returning a standardized dictionary with `status: 'error'` and a `message`.

*   **Python Code Execution (`run_python_code()` at `primitives.py:157`):**
    *   **Context Control**: Executes `python_code_string` in a controlled global namespace (`common_globals`) that includes a rich set of pre-imported standard Python modules (e.g., `os`, `sys`, `json`, `re`, `subprocess`, `pathlib`, `datetime`, `requests`) and all other functions from `executor.primitives` itself (`primitives.py:168-175`).
    *   **`VARS` Interaction**: Designed to interact with a `locals_dict` that may contain a `VARS` dictionary, allowing state to be maintained across `python` calls. Changes to specified `locals_to_return` keys are captured.
    *   **Output Capture**: Redirects `sys.stdout` and `sys.stderr` to `io.StringIO` buffers, capturing all printed output and errors.
    *   **Return Format**: Returns a dictionary with `status`, `stdout`, `stderr`, and a `vars` dictionary if `locals_to_return` were specified and found.

*   **Shell Script Execution (`run_shell_script()` at `primitives.py:207`):**
    *   **Interpreter Flexibility**: Supports `bash`, `powershell`, `cmd`, and includes `auto`-detection logic. On Windows, it heuristically detects PowerShell vs. CMD based on script syntax (`$` vs. `%` variables) (`primitives.py:214-220`).
    *   **Temporary File**: Writes the input `script` to a temporary file (`tempfile.NamedTemporaryFile`) and then executes this file using `subprocess.run()`. This handles multi-line scripts and ensures proper cleanup (`finally` block at `primitives.py:278`).
    *   **Environment and Timeout**: Allows custom `env` variables and specifies a `timeout` for command execution.
    *   **Return Format**: Returns a dictionary with `status`, `stdout`, `stderr`, `return_code`, and a `timed_out` boolean flag.

*   **Filesystem Primitives (All are decorated with `dispatched_primitive_operation`):**
    *   `stat_path(path)` (`primitives.py:53`): Returns metadata (`exists`, `is_dir`, `is_file`, `size`, `mtime`, `ctime`) for a given path.
    *   `list_directory(path, recursive=False, filter={})` (`primitives.py:92`): Lists contents of a directory. Includes options for recursion and filters out common VCS directories (`.git`, `__pycache__`, `.DS_Store`).
    *   `read_file(path)` (`primitives.py:139`): Reads file content. Attempts UTF-8 decoding, falls back to Latin-1 on `UnicodeDecodeError`.
    *   `write_file(path, content)` (`primitives.py:195`): Overwrites a file. Creates parent directories (`Path.parent.mkdir(parents=True, exist_ok=True)`) if they don't exist.
    *   `append_file(path, content)` (`primitives.py:228`): Appends content to a file. Creates the file and parents if they don't exist.
    *   `mkdir(path, parents=False, exist_ok=True)` (`primitives.py:302`): Creates a directory, supporting `parents` and `exist_ok` options (similar to `mkdir -p`).
    *   `rm(path, recursive=False)` (`primitives.py:326`): Deletes files or directories. For directories, `recursive=True` is required to delete contents (`shutil.rmtree`). Provides specific error messages for non-empty directories when `recursive=False`.

---

## Executor Installer and Service Manager (`executor/installer.py`)

*   **Purpose**: A standalone Python script (`installer.py`) for installing, managing, and uninstalling the `carna_executor` service across Linux (systemd), macOS (launchd), and Windows (Windows Service). It also handles the crucial client registration process with the main Carna server.
*   **Command-Line Interface (`main()` at `installer.py:465`):** Uses `argparse` to define `install`, `uninstall`, and `status` subcommands.
*   **Installation Logic (`handle_install_interactive()`, `handle_install_non_interactive()`):**
    *   **Admin Privileges**: Requires administrative privileges for service installation (`is_admin()` check at `installer.py:30`).
    *   **Directory Management**: Creates a default installation directory (`/opt/carna_executor` or `C:\Program Files\CarnaExecutor`) or uses a user-specified path. Copies `main.py`, `primitives.py`, and `requirements.txt` to this directory.
    *   **Python Virtual Environment (`setup_python_env_and_dependencies()` at `installer.py:408`):**
        *   Creates a Python `venv` within the installation directory.
        *   Installs all dependencies listed in `requirements.txt` into this `venv` using the `venv`'s Python executable.
    *   **Client Registration (`register_client_interactive()`, `register_client_non_interactive()` at `installer.py:306`):**
        *   **Server Interaction**: Prompts the user (or uses command-line arguments) for the Carna server's base URL and `AGENT_SERVER_SECRET_KEY`.
        *   **Registration API Call**: Makes an HTTP `POST` request to `{server_url}/systems/api/register_client/`.
        *   **API Key Retrieval**: The server responds with a unique `client_api_key` and a `resolved_client_url`.
        *   **Configuration Save**: This `client_api_key` (and other registration details) are saved to `client_config.json` inside the executor's installation directory. This file is then read by `executor/main.py` at startup to configure its API key.
    *   **System Service Integration**:
        *   **Linux (`install_service_linux()` at `installer.py:149`):** Creates a systemd service file (`/etc/systemd/system/carna_executor.service`), reloads the daemon, and enables/starts the service.
        *   **macOS (`install_service_macos()` at `installer.py:220`):** Creates a launchd `.plist` file (`/Library/LaunchDaemons/com.carna.carna_executor.plist`), sets permissions, loads, and starts the service using `launchctl`.
        *   **Windows (`install_service_windows()` at `installer.py:291`):** Uses `sc.exe` to create and start a Windows service named `carna_executor`.
*   **Uninstallation Logic (`handle_uninstall()` at `installer.py:59`):**
    *   Requires administrative privileges.
    *   Stops and deletes the system service using platform-specific commands.
    *   Optionally prompts the user to confirm deletion of the entire installation directory.
*   **Status Check (`handle_status()` at `installer.py:100`):**
    *   Queries the status of the `carna_executor` system service using platform-specific commands (`systemctl status`, `launchctl list`, `sc query`).

---

## Dependencies (`executor/requirements.txt`)

*   Lists the Python packages necessary for the FastAPI application:
    *   `fastapi`: Web framework.
    *   `uvicorn[standard]`: ASGI server for running FastAPI.
    *   `websockets`: For WebSocket client functionality, though not directly used in the FastAPI server itself, it's a common dependency for async operations.
