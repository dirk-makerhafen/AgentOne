
import os
import sys
import tempfile
import shutil
import subprocess

# Embedded file contents
_EMBEDDED_PRIMITIVES_CONTENT = '''import os
from pathlib import Path
from copy import deepcopy
import os
import shutil
import sys
import io
import traceback
import functools
import traceback
import requests
import subprocess
import tempfile

def dispatched_primitive_operation(func):
    """
    A decorator that intercepts a filesystem function call and dispatches it
    for either local or remote execution based on the agentInstance's system configuration.
    The wrapper function created by this decorator will have the signature: wrapper(agentInstance, **kwargs)
    """

    def _run_local(func, **kwargs):
        try:
            return func(**kwargs)
        except Exception as e:
            return {'status': 'error', 'message': f"Local execution error in '{func.__name__}': {str(e)} {traceback.format_exc()}"}

    def _run_remote(system, func, **kwargs):
        try:
            response = requests.post(
                url = f"{system.executor_url.rstrip('/')}/python", 
                json= {
                    "source": f'FUNC_RESULT={func.__name__}(**kwargs)', 
                    "locals_dict": { "kwargs": kwargs }, 
                    "locals_to_return":["FUNC_RESULT", "VARS"]
                }, 
                headers={ 
                    'X-API-Key': system.executor_api_key, 
                    'Content-Type': 'application/json'
                }, 
                timeout=70
            )
            response.raise_for_status()
            return response.json().get("vars",{}).get("FUNC_RESULT", response.json())
        except Exception as e:
            return {'status': 'error', 'message': f"Remote dispatch error for '{func.__name__}': {str(e)} {traceback.format_exc()}"}

    @functools.wraps(func)
    def wrapper(agentInstance = None, **kwargs):
        is_remote = False
        if agentInstance:
            system = agentInstance.system
            is_remote = system and getattr(system, 'is_remote_executor', False) and system.executor_url and system.executor_api_key
        if is_remote:
            return _run_remote(system=system, func=func, **kwargs)
        return _run_local(func=func, **kwargs)
         
    return wrapper

@dispatched_primitive_operation
def stat_path(path):
    """
    Gets metadata for a file or directory.

    Args:
        'path': str

    Returns:
        dict: {
            'status': 'success' or 'error',
            'path': str,
            'exists': bool,
            'is_dir': bool,
            'is_file': bool,
            'size': int,
            'mtime': float,
            'ctime': float,
            'message': str (optional, on error)
        }
    """
    try:
        p = Path(path)
        if not p.exists():
            return {
                'status': 'success',
                'path': path,
                'exists': False,
                'is_dir': False,
                'is_file': False,
                'size': 0,
                'mtime': 0.0,
                'ctime': 0.0
            }

        stat = p.stat()
        return {
            'status': 'success',
            'path': path,
            'exists': True,
            'is_dir': p.is_dir(),
            'is_file': p.is_file(),
            'size': stat.st_size if p.is_file() else 0,
            'mtime': stat.st_mtime,
            'ctime': stat.st_ctime
        }
    except Exception as e:
        import traceback
        return {'status': 'error', 'message': f"Error getting stat for {path}: {str(e)} {traceback.format_exc()}"}


@dispatched_primitive_operation
def list_directory(path, recursive=False, filter={}):
    """
    Lists the content of a directory, returning a structured list of objects.

    Args:
        'path': str,
        'recursive': bool (default: False),
        'filter': dict (optional)

    Returns:
        dict: {
            'status': 'success' or 'error',
            'content': [
                {
                    "path":  str
                    "is_directory": bool,
                    "size": int
                },
            ],
            'message': str (optional, on error)
        }
    """
    try:
        if not path:
            return {'status': 'error', 'message': 'Path not provided'}

        base_path = Path(path)
        if not base_path.is_dir():
            return {'status': 'error', 'message': f"Directory not found: {path}"}

        items = []

        if recursive:
            for root, dirs, files in os.walk(base_path, topdown=True):
                # Sort for consistent output
                dirs.sort()
                files.sort()

                # Exclude common noise directories from traversal
                dirs[:] = [d for d in dirs if d not in ['.git', '__pycache__', '.DS_Store']]

                rel_root = Path(root).relative_to(base_path)

                for dir_name in dirs:
                    full_path = Path(root) / dir_name
                    rel_path = rel_root / dir_name if str(rel_root) != '.' else Path(dir_name)
                    try:
                        stat = full_path.stat()
                        items.append({
                            "path": str(rel_path),
                            "is_directory": True,
                            "size": stat.st_size,
                        })
                    except OSError:
                        # Could be a broken symlink, etc.
                        continue

                for file_name in [f for f in files if f not in ['.DS_Store']]:
                    full_path = Path(root) / file_name
                    rel_path = rel_root / file_name if str(rel_root) != '.' else Path(file_name)
                    try:
                        stat = full_path.stat()
                        items.append({
                            "path": str(rel_path),
                            "is_directory": False,
                            "size": stat.st_size,
                        })
                    except OSError:
                        continue
        else: # Non-recursive
            for entry in sorted(os.scandir(base_path), key=lambda e: e.name):
                if entry.name in ['.git', '__pycache__', '.DS_Store']:
                    continue
                try:
                    stat = entry.stat()
                    is_dir = entry.is_dir()
                    items.append({
                        "path": entry.name, # For non-recursive, path is just the name
                        "is_directory": is_dir,
                        "size": stat.st_size,
                    })
                except OSError:
                    continue

        return {'status': 'success', 'content': items}

    except Exception as e:
        return {'status': 'error', 'message': "Error listing directory {}: {}\n{}".format(path, str(e), traceback.format_exc())}


@dispatched_primitive_operation
def read_file(path):
    """
    Reads the content of a file.

    Args:
        'path': str

    Returns:
        dict: {
            'status': 'success' or 'error',
            'content': str (if successful),
            'message': str (optional, on error)
        }
    """
    try:
        if not path:
            return {'status': 'error', 'message': 'Path not provided'}

        p = Path(path)
        if not p.is_file():
            return {'status': 'error', 'message': f"File not found or not a regular file: {path}"}

        # Attempt to read as UTF-8, fall back to latin-1
        try:
            content = p.read_text(encoding='utf-8')
        except UnicodeDecodeError:
            content = p.read_text(encoding='latin-1')

        return {'status': 'success', 'content': content}
    except Exception as e:
        return {'status': 'error', 'message': f"Error reading file {path}: {str(e)} {traceback.format_exc()}"}


@dispatched_primitive_operation
def write_file(path, content):
    """
    Writes (overwrites) content to a file. Creates parent directories if they don't exist.

    Args:
        path: str, 
        content: str

    Returns:
        dict: {
            'status': 'success' or 'error',
            'message': str (optional)
        }
    """
    try:
        if not path:
            return {'status': 'error', 'message': 'Path not provided'}

        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding='utf-8')
        return {'status': 'success', 'message': f"File '{path}' written successfully."}
    except Exception as e:
        return {'status': 'error', 'message': f"Error writing to file {path}: {str(e)} {traceback.format_exc()}"}


@dispatched_primitive_operation
def append_file(path, content):
    """
    Appends content to a file. Creates the file and parent directories if they don't exist.

    Args:
        path: str, 
        content: str

    Returns:
        dict: {
            'status': 'success' or 'error',
            'message': str (optional)
        }
    """
    try:        
        if not path:
            return {'status': 'error', 'message': 'Path not provided'}

        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a", encoding='utf-8') as f:
            f.write(content)
        return {'status': 'success', 'message': f"Appended to file '{path}' successfully."}
    except Exception as e:
        return {'status': 'error', 'message': f"Error appending to file {path}: {str(e)}"}


@dispatched_primitive_operation
def run_python_code(python_code_string: str, locals_dict: dict, locals_to_return=[]):
    """
    Executes a Python code string within a controlled environment, providing common imports
    and initial variables. It specifically tracks changes made to a dictionary named 'VARS'
    if present in the locals_dict. This is the original local execution method.
    locals_to_return = list of keys for vars ins locals that we want to return if they have changed.
    
    return {
        "status": "success",
        "message": "some error in case of errors",
        "stdout": stdout,
        "stderr": stderr,
        "vars": {}
    }
    """

    common_globals = {}
    try:
        exec('import os, sys, json, re, subprocess, math, threading, copy, pathlib\n'
        'import datetime, random, itertools, time, io, traceback, requests, inspect, functools\n' \
        'from copy import deepcopy\n' \
        'from pathlib import Path\n' \
        'from executor.primitives import *\n' \
        'from executor import primitives\n', common_globals)
    except Exception as e:
        return {'status': 'error', 'message':  f'Error during common imports setup: {e}'}

    locals_dict_copy = deepcopy(locals_dict)
    
    old_stdout = sys.stdout
    old_stderr = sys.stderr
    sys.stdout = captured_stdout_buffer = io.StringIO()
    sys.stderr = captured_stderr_buffer = io.StringIO()

    caught_exception = None
    try:
        exec(python_code_string, common_globals, locals_dict_copy)
    except Exception as e:
        caught_exception = e
        traceback.print_exc(file=sys.stderr)
    finally:
        sys.stdout = old_stdout
        sys.stderr = old_stderr

    captured_stdout = captured_stdout_buffer.getvalue().strip()
    captured_stderr = captured_stderr_buffer.getvalue().strip()
    if caught_exception:
        u = {'status': 'error', 'message':  f'Exception: {caught_exception}'}
        if captured_stdout: 
            u["stdout"] = captured_stdout
        if captured_stderr: 
            u["stderr"] = captured_stderr
        return u

    vars = {local_to_return: locals_dict_copy[local_to_return] for local_to_return in locals_to_return if local_to_return in locals_dict_copy}
  
    u = {'status': 'success'}
    if captured_stdout: 
        u["stdout"] = captured_stdout
    if captured_stderr: 
        u["stderr"] = captured_stderr
    if vars: 
        u["vars"] = vars
    return u


@dispatched_primitive_operation
def run_shell_script(script: str, interpreter: str = "auto", env: dict = None, timeout: int = 60):
    """
    Executes a shell script using the specified interpreter, with auto-detection for Windows.

    Args:
        script (str): The multi-line script to execute.
        interpreter (str): 'auto', 'bash', 'powershell', or 'cmd'. Defaults to 'auto'.
        env (dict): Optional dictionary of environment variables.
        timeout (int): Maximum time in seconds to wait for the command to complete.

    Returns:
        dict: The result of the execution.
    """
    # Determine the interpreter
    is_windows = sys.platform == "win32"
    if interpreter == "auto":
        if is_windows:
            # Heuristic to detect if the script is PowerShell or CMD
            if "$" in script and not "%" in script:
                interpreter = "powershell"
            elif "%" in script and not "$" in script:
                interpreter = "cmd"
            else:
                # Default to PowerShell on Windows if ambiguous
                interpreter = "powershell"
        else:
            interpreter = "bash"

    # Prepare the script file and command
    file_extension = ".ps1" if interpreter == "powershell" else ".bat" if interpreter == "cmd" else ".sh"
    command_list = []

    # Create a temporary file to hold the script
    try:
        with tempfile.NamedTemporaryFile(mode='w+', suffix=file_extension, delete=False, encoding='utf-8') as tmp_script:
            tmp_script_path = tmp_script.name
            tmp_script.write(script)
            tmp_script.flush()

        if interpreter == "powershell":
            command_list = ["powershell.exe", "-ExecutionPolicy", "Bypass", "-File", tmp_script_path]
        elif interpreter == "cmd":
            command_list = ["cmd.exe", "/c", tmp_script_path]
        elif interpreter == "bash":
            command_list = ["bash", tmp_script_path]
        else:
            return {'status': 'error', 'message': f"Unsupported interpreter: {interpreter}"}

        # Execute the command
        full_env = os.environ.copy()
        if env:
            full_env.update(env)

        process = subprocess.run(command_list, env=full_env, capture_output=True, text=True, timeout=timeout)

        return {
            "status": "success",
            "stdout": process.stdout,
            "stderr": process.stderr,
            "return_code": process.returncode,
            "timed_out": False
        }

    except subprocess.TimeoutExpired as e:
        return {
            "status": "error",
            "stdout": e.stdout.decode(errors='ignore') if e.stdout else "",
            "stderr": e.stderr.decode(errors='ignore') if e.stderr else "",
            "return_code": -1,
            "timed_out": True,
            "message": f"Command timed out after {timeout} seconds."
        }
    except Exception as e:
        return {'status': 'error', 'message': f"Error executing shell script: {str(e)}{traceback.format_exc()}", "stdout": "", "stderr": "", "return_code": -1, "timed_out": False}
    finally:
        # Ensure the temporary file is always cleaned up
        if 'tmp_script_path' in locals() and os.path.exists(tmp_script_path):
            os.remove(tmp_script_path)

@dispatched_primitive_operation
def mkdir(path, parents=False, exist_ok=True):
    """
    Creates a directory, including any necessary parent directories.
    Behaves like `mkdir -p`.

    Args:
        path: str
        parents: bool 

    Returns:
        dict: {
            'status': 'success' or 'error',
            'message': str (optional)
        }
    """
    try:
        if not path:
            return {'status': 'error', 'message': 'Path not provided'}

        os.makedirs(path, parents=parents, exist_ok=exist_ok)
        return {'status': 'success', 'message': f"Directory '{path}' created successfully."}
    except Exception as e:
        return {'status': 'error', 'message': f"Error creating directory {path}: {str(e)} {traceback.format_exc()}"}
    
    
@dispatched_primitive_operation
def rm(path, recursive=False):
    """
    Deletes a file or directory.

    Args:
        path: str
        recursive: bool (default: False) - If True, deletes directories and their contents.

    Returns:
        dict: {
            'status': 'success' or 'error',
            'message': str (optional)
        }
    """
    try:
        if not path:
            return {'status': 'error', 'message': 'Path not provided'}

        p = Path(path)

        if not p.exists():
            return {'status': 'success', 'message': f"Path '{path}' does not exist, no action needed."}

        if p.is_file():
            os.remove(p)
            return {'status': 'success', 'message': f"File '{path}' deleted successfully."}
        elif p.is_dir():
            if recursive:
                shutil.rmtree(p)
                return {'status': 'success', 'message': f"Directory '{path}' and its contents deleted recursively."}
            else:
                # Try to remove empty directory
                try:
                    os.rmdir(p)
                    return {'status': 'success', 'message': f"Empty directory '{path}' deleted successfully."}
                except OSError as e:
                    if "Directory not empty" in str(e) or "The directory is not empty" in str(e):
                        return {'status': 'error', 'message': f"Directory '{path}' is not empty. Use recursive=True to delete its contents."}
                    else:
                        return {'status': 'error', 'message': f"Error deleting empty directory {path}: {str(e)} {traceback.format_exc()}"}
        else:
            return {'status': 'error', 'message': f"Path '{path}' is neither a file nor a directory (e.g., symlink to non-existent target). Cannot delete."}

    except Exception as e:
        return {'status': 'error', 'message': f"Error deleting path {path}: {str(e)} {traceback.format_exc()}"}
'''
_EMBEDDED_MAIN_CONTENT = '''import os
from pydantic import BaseModel
from fastapi.responses import JSONResponse
from fastapi.security.api_key import APIKeyHeader
from fastapi import FastAPI, Depends, HTTPException, status, Security
from executor.primitives import run_python_code, run_shell_script

import json
import sys

CONFIG_DEFAULTS = {
    "APIKEY": "my-api-key",
    "PORT": 8123,
    "LISTEN": "0.0.0.0",
    "NAME": "default-host"
}
CONFIG = {}

def load_all_config():
    """Loads default configuration and overrides with values from client_config.json."""
    global CONFIG
    CONFIG.update(CONFIG_DEFAULTS) 

    config_path = os.path.join(os.path.dirname(__file__), 'client_config.json')
    try:
        with open(config_path, 'r') as f:
            file_config = json.load(f)
            # Override defaults with values from client_config.json
            if 'client_api_key' in file_config:
                CONFIG["APIKEY"] = file_config['client_api_key']
            if 'client_port' in file_config:
                CONFIG["PORT"] = int(file_config['client_port'])
            if 'client_listen' in file_config:
                CONFIG["LISTEN"] = file_config['client_listen']
            if 'client_name' in file_config:
                CONFIG["NAME"] = file_config['client_name']
            
            print("Successfully loaded configuration from client_config.json.")
    except FileNotFoundError:
        print("Configuration file 'client_config.json' not found. Using default values.", file=sys.stderr)
    except (json.JSONDecodeError, KeyError) as e:
        print(f"Error reading config from client_config.json: {e}. Using default values where possible.", file=sys.stderr)

    if not CONFIG.get("APIKEY"):
        print("\nFATAL: Executor API key is not configured.", file=sys.stderr)
        print("Please ensure a valid 'client_config.json' with a 'client_api_key' exists.", file=sys.stderr)
        sys.exit(1)
    
    return CONFIG.get("APIKEY")

API_KEY = load_all_config()

class ScriptExecution(BaseModel):
    source: str
    locals_dict: dict = {}
    locals_to_return: list = []

class ShellExecution(BaseModel):
    command: str
    env: dict[str, str] = {}
    timeout: int = 60

app = FastAPI(title=CONFIG["NAME"], description="A lightweight agent for remote python and shell execution.", version="1.0.0")

async def get_api_key(api_key: str = Security( APIKeyHeader(name="X-API-Key", auto_error=True))):
    if api_key == API_KEY:
        return api_key
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Could not validate credentials")

@app.get("/", dependencies=[Depends(get_api_key)])
async def root():
    return {"status": "ok", "name": CONFIG["NAME"], "port": CONFIG["PORT"], "listen": CONFIG["LISTEN"]}

@app.post("/shell", dependencies=[Depends(get_api_key)])
async def execute_shell_command(item: ShellExecution):
    result = run_shell_script(command=item.command, env=item.env, timeout=item.timeout)
    return JSONResponse(content=result)

@app.post("/python", dependencies=[Depends(get_api_key)])
async def execute_python_code(item: ScriptExecution):
    result = run_python_code(agentInstance=None, python_code_string = item.source, locals_dict=item.locals_dict, locals_to_return=item.locals_to_return)
    return JSONResponse(content=result)


if __name__ == "__main__":
    import uvicorn
    print(f"Starting executor '{CONFIG['NAME']}' on {CONFIG['LISTEN']}:{CONFIG['PORT']}...")
    uvicorn.run(app, host=CONFIG["LISTEN"], port=CONFIG["PORT"])
'''
_EMBEDDED_INSTALLER_CONTENT = '''import argparse
import json
import os
import platform
import socket
import subprocess
import sys
import requests

# --- Configuration ---
CONFIG_FILE = 'client_config.json'
SERVICE_NAME = 'carna_executor'
SERVICE_DISPLAY_NAME = 'Carna Agent Executor'
EXECUTOR_MAIN_SCRIPT = 'main.py'

# --- Installation Configuration ---
DEFAULT_INSTALL_PATH_WINDOWS = os.path.join(os.environ.get('ProgramFiles', 'C:\\Program Files'), 'CarnaExecutor')
DEFAULT_INSTALL_PATH_LINUX_MAC = '/opt/carna_executor'
# Assumes the installer is in the 'executor' directory with the other source files.
SOURCE_DIR = os.path.dirname(os.path.abspath(__file__))
FILES_TO_COPY = ['main.py', 'primitives.py', 'requirements.txt']


# --- Platform-Specific Service Management ---

def is_admin():
    """Check if the script is running with administrative privileges."""
    try:
        is_admin = (os.getuid() == 0)
    except AttributeError:
        import ctypes
        is_admin = (ctypes.windll.shell32.IsUserAnAdmin() != 0)
    return is_admin

def handle_install_interactive(args):
    """Handles the interactive installation and service creation process."""
    print("--- Carna Agent Executor Installation ---")
    import shutil

    # Determine installation path
    system = platform.system()
    default_path = DEFAULT_INSTALL_PATH_WINDOWS if system == 'Windows' else DEFAULT_INSTALL_PATH_LINUX_MAC
    install_path_input = input(f"Enter installation directory (press Enter for default: '{default_path}'): ")
    install_path = os.path.abspath(install_path_input or default_path)
    print(f"Executor will be installed in: {install_path}")

    # --- Step 1: Create directory and copy files ---
    print(f"\n--- Preparing Installation Directory ---")
    if not os.path.exists(install_path):
        try:
            os.makedirs(install_path, exist_ok=True)
            print(f"Created directory: {install_path}")
        except OSError as e:
            print(f"ERROR: Could not create directory '{install_path}': {e}")
            return
    
    for filename in FILES_TO_COPY:
        source_file = os.path.join(SOURCE_DIR, filename)
        dest_file = os.path.join(install_path, filename)
        if os.path.exists(source_file):
            shutil.copy(source_file, dest_file)
            print(f"Copied '{filename}' to installation directory.")
        else:
            print(f"WARNING: Source file '{source_file}' not found. Skipping.")

    # --- Step 2: Set up Python environment ---
    venv_python = setup_python_env_and_dependencies(install_path)
    if not venv_python:
        print("Python environment setup failed. Aborting installation.")
        return

    # --- Step 3: Run the client registration process ---
    if not register_client_interactive(install_path):
        print("Client registration failed. Aborting installation.")
        return

    # --- Step 4: Ask to install the service ---
    install_service_prompt = input("\nDo you want to install the executor as a system service? (y/n): ").lower()
    if install_service_prompt != 'y':
        print(f"Service installation skipped. You can run the executor manually from '{install_path}'.")
        return

    if not is_admin():
        print("\nERROR: Service installation requires administrative privileges.")
        print("Please re-run this script with 'sudo' (Linux/macOS) or as an Administrator (Windows).")
        return

    if system == 'Linux':
        install_service_linux(venv_python, install_path)
    elif system == 'Darwin':
        install_service_macos(venv_python, install_path)
    elif system == 'Windows':
        install_service_windows(venv_python, install_path)
    else:
        print(f"Unsupported OS for service installation: {system}")

def handle_uninstall(args):
    """Handles the service uninstallation and directory removal process."""
    print(f"--- Uninstalling {SERVICE_DISPLAY_NAME} Service ---")

    system = platform.system()
    default_path = DEFAULT_INSTALL_PATH_WINDOWS if system == 'Windows' else DEFAULT_INSTALL_PATH_LINUX_MAC
    install_path = os.path.abspath(args.path or default_path)

    if not is_admin():
        print("\nERROR: Service uninstallation requires administrative privileges.")
        print("Please re-run this script with 'sudo' (Linux/macOS) or as an Administrator (Windows).")
        return

    # Step 1: Stop and remove the service
    if system == 'Linux':
        uninstall_service_linux()
    elif system == 'Darwin':
        uninstall_service_macos()
    elif system == 'Windows':
        uninstall_service_windows()
    else:
        print(f"Unsupported operating system for service removal: {system}")

    # Step 2: Remove the installation directory
    if os.path.exists(install_path):
        print(f"\nInstallation directory found at: {install_path}")
        confirm = input(f"--> Do you want to delete this directory and all its contents? (y/n): ").lower()
        if confirm == 'y':
            try:
                import shutil
                shutil.rmtree(install_path)
                print("Directory removed successfully.")
            except Exception as e:
                print(f"Error removing directory: {e}")
                print("You may need to remove it manually.")
        else:
            print("Directory removal skipped.")
    else:
        print(f"\nInstallation directory not found at '{install_path}', no files to remove.")

def handle_status():
    """Handles checking the status of the service."""
    print(f"--- Status for {SERVICE_DISPLAY_NAME} Service ---")
    system = platform.system()
    if system == 'Linux':
        get_service_status_linux()
    elif system == 'Darwin':
        get_service_status_macos()
    elif system == 'Windows':
        get_service_status_windows()
    else:
        print(f"Unsupported operating system: {system}")

# --- OS-Specific Implementations (Placeholders) ---

def install_service_linux(venv_python, install_path):
    """Installs the systemd service for Linux."""
    print("\n--- Installing systemd service for Linux ---")
    user = os.getenv("SUDO_USER") or os.getenv("USER")
    if not user:
        print("Could not determine the non-root user to run the service. Aborting.")
        return

    script_path = os.path.join(install_path, EXECUTOR_MAIN_SCRIPT)
    service_file_content = f"""[Unit]
Description={SERVICE_DISPLAY_NAME}
After=network.target

[Service]
User={user}
Group={user}
WorkingDirectory={install_path}
ExecStart={venv_python} {script_path}
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
"""
    service_path = f"/etc/systemd/system/{SERVICE_NAME}.service"
    try:
        print(f"Writing service file to {service_path}...")
        with open(service_path, 'w') as f:
            f.write(service_file_content)
        
        print("Reloading systemd daemon, enabling and starting service...")
        subprocess.run(['systemctl', 'daemon-reload'], check=True)
        subprocess.run(['systemctl', 'enable', f'{SERVICE_NAME}.service'], check=True)
        subprocess.run(['systemctl', 'start', f'{SERVICE_NAME}.service'], check=True)
        print("\nService installation completed successfully.")
        get_service_status_linux()
    except (subprocess.CalledProcessError, IOError) as e:
        print(f"\nError during service installation: {e}")

def uninstall_service_linux():
    service_path = f"/etc/systemd/system/{SERVICE_NAME}.service"
    print(f"Checking for service file at {service_path}...")

    if not os.path.exists(service_path):
        print("Service does not appear to be installed. Nothing to do.")
        return

    try:
        print(f"Stopping {SERVICE_NAME} service...")
        subprocess.run(['systemctl', 'stop', f'{SERVICE_NAME}.service'], check=False) # Don't fail if already stopped

        print(f"Disabling {SERVICE_NAME} service...")
        subprocess.run(['systemctl', 'disable', f'{SERVICE_NAME}.service'], check=False) # Don't fail if not enabled

        print(f"Removing service file: {service_path}")
        os.remove(service_path)

        print("Reloading systemd daemon...")
        subprocess.run(['systemctl', 'daemon-reload'], check=True)

        print("\nService uninstalled successfully.")
        if os.path.exists(CONFIG_FILE):
            print(f"NOTE: The client configuration file '{CONFIG_FILE}' was not removed.")

    except (subprocess.CalledProcessError, IOError) as e:
        print(f"\nAn error occurred during uninstallation: {e}")

def get_service_status_linux():
    try:
        print(f"Checking status of {SERVICE_NAME}.service...")
        subprocess.run(['systemctl', 'status', f'{SERVICE_NAME}.service', '--no-pager'], check=True)
    except FileNotFoundError:
        print("systemctl command not found. Is systemd your init system?")
    except subprocess.CalledProcessError:
        print(f"Service '{SERVICE_NAME}' does not appear to be installed or is in a failed state.")

def install_service_macos(venv_python, install_path):
    """Installs the launchd service for macOS."""
    print("\n--- Installing launchd service for macOS ---")
    script_path = os.path.join(install_path, EXECUTOR_MAIN_SCRIPT)
    service_label = f"com.carna.{SERVICE_NAME}"
    plist_path = f"/Library/LaunchDaemons/{service_label}.plist"

    plist_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>{service_label}</string>
    <key>ProgramArguments</key>
    <array>
        <string>{venv_python}</string>
        <string>{script_path}</string>
    </array>
    <key>WorkingDirectory</key>
    <string>{install_path}</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/tmp/{SERVICE_NAME}.out.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/{SERVICE_NAME}.err.log</string>
</dict>
</plist>
"""
    try:
        print(f"Writing launchd plist to {plist_path}...")
        with open(plist_path, 'w') as f:
            f.write(plist_content)
        
        subprocess.run(['chown', 'root:wheel', plist_path], check=True)
        subprocess.run(['chmod', '644', plist_path], check=True)
        print("Loading and starting service with launchctl...")
        subprocess.run(['launchctl', 'load', '-w', plist_path], check=True, capture_output=True)
        print("\nService installation completed successfully.")
        get_service_status_macos()
    except (subprocess.CalledProcessError, IOError) as e:
        print(f"\nError during service installation: {e}")

def uninstall_service_macos():
    service_label = f"com.carna.{SERVICE_NAME}"
    plist_path = f"/Library/LaunchDaemons/{service_label}.plist"

    print(f"Checking for service file at {plist_path}...")
    if not os.path.exists(plist_path):
        print("Service does not appear to be installed. Nothing to do.")
        return

    try:
        print(f"Unloading {service_label} service...")
        # Unload the service, which stops it as well.
        subprocess.run(['launchctl', 'unload', '-w', plist_path], check=False)

        print(f"Removing service file: {plist_path}")
        os.remove(plist_path)

        print("\nService uninstalled successfully.")
        if os.path.exists(CONFIG_FILE):
            print(f"NOTE: The client configuration file '{CONFIG_FILE}' was not removed.")

    except (subprocess.CalledProcessError, IOError) as e:
        print(f"\nAn error occurred during uninstallation: {e}")

def get_service_status_macos():
    service_label = f"com.carna.{SERVICE_NAME}"
    try:
        print(f"Checking status of {service_label}...")
        # Use launchctl list and grep to find the service
        result = subprocess.run(['launchctl', 'list'], capture_output=True, text=True, check=True)

        service_found = False
        for line in result.stdout.splitlines():
            if service_label in line:
                print("Service is loaded:")
                print(line)
                service_found = True
                break

        if not service_found:
            print("Service is not currently loaded.")

    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        print(f"Could not check service status: {e}")

def install_service_windows(venv_python, install_path):
    """Installs the service for Windows."""
    print("\n--- Installing service for Windows ---")
    script_path = os.path.join(install_path, EXECUTOR_MAIN_SCRIPT)
    # The entire binPath needs to be correctly quoted for sc.exe
    bin_path = f'"{venv_python}" "{script_path}"'
    
    try:
        print(f"Creating service '{SERVICE_NAME}'...")
        # The binPath and DisplayName arguments must be a single string like "binPath= <command>"
        # Note the required space after the '=' sign.
        subprocess.run([
            'sc', 'create', SERVICE_NAME,
            f'binPath= {bin_path}',
            f'DisplayName= "{SERVICE_DISPLAY_NAME}"',
            'start=', 'auto'
        ], check=True, capture_output=True, text=True)
        
        # Optional: Add a description to the service for better management.
        subprocess.run([
            'sc', 'description', SERVICE_NAME, 
            f'"{SERVICE_DISPLAY_NAME} - Runs remote code execution tasks."'
        ], check=False) # Don't fail if this doesn't work

        print("Starting service...")
        subprocess.run(['sc', 'start', SERVICE_NAME], check=True, capture_output=True, text=True)
        print("\nService installation completed successfully.")
        get_service_status_windows()
    except subprocess.CalledProcessError as e:
        print(f"\nError during service installation: {e}")
        # sc.exe often prints useful info to stderr, so we show it.
        print(f"Stderr: {e.stderr}")
    except FileNotFoundError:
        print("\nError: 'sc.exe' command not found. Is it in your system's PATH?")

def uninstall_service_windows():
    try:
        print(f"Stopping {SERVICE_NAME} service...")
        subprocess.run(['sc', 'stop', SERVICE_NAME], check=False, capture_output=True) # Don't fail if already stopped

        print(f"Deleting {SERVICE_NAME} service...")
        result = subprocess.run(['sc', 'delete', SERVICE_NAME], check=True, capture_output=True)

        if "service does not exist" in result.stderr.decode('utf-8').lower():
             print("Service does not appear to be installed. Nothing to do.")
             return

        print("\nService uninstalled successfully.")
        if os.path.exists(CONFIG_FILE):
            print(f"NOTE: The client configuration file '{CONFIG_FILE}' was not removed.")

    except subprocess.CalledProcessError as e:
        # Check if the error is because the service doesn't exist
        stderr_output = e.stderr.decode('utf-8').lower()
        if "does not exist" in stderr_output:
             print("Service does not appear to be installed. Nothing to do.")
        else:
            print(f"\nAn error occurred during uninstallation: {e}")
            print(f"Stderr: {stderr_output}")
    except FileNotFoundError:
        print("\nError: 'sc.exe' command not found.")

def get_venv_python_path(install_path):
    """Gets the path to the python executable in the virtual environment."""
    if platform.system() == 'Windows':
        return os.path.join(install_path, 'venv', 'Scripts', 'python.exe')
    else: # Linux/macOS
        return os.path.join(install_path, 'venv', 'bin', 'python')

def get_service_status_windows():
    try:
        print(f"Querying status of '{SERVICE_NAME}' service...")
        # We need to capture output to check it
        result = subprocess.run(['sc', 'query', SERVICE_NAME], check=True, capture_output=True, text=True)
        print(result.stdout)
    except subprocess.CalledProcessError as e:
        # sc query returns a non-zero exit code if the service doesn't exist
        print(f"Service '{SERVICE_NAME}' does not appear to be installed.")
    except FileNotFoundError:
        print("\nError: 'sc.exe' command not found.")

# --- Client Registration Logic ---

def register_client_interactive(install_path):
    """Guides the user through registering the client with the server."""
    print("\n--- Client Registration ---")
    config_path = os.path.join(install_path, CONFIG_FILE)

    if os.path.exists(config_path):
        overwrite = input(f"A configuration file already exists at '{config_path}'. Overwrite? (y/n): ").lower()
        if overwrite != 'y':
            print("Registration skipped.")
            return os.path.exists(config_path)

    server_url = input("Enter the full URL of the Carna server (e.g., http://127.0.0.1:8000): ")
    server_secret = input("Enter the server's AGENT_SERVER_SECRET_KEY: ")
    default_client_name = socket.gethostname()
    client_name = input(f"Enter a name for this client (default: '{default_client_name}'): ") or default_client_name
    client_port = input(f"Enter the port this client will listen on (default: '8123'): ") or '8123'
    client_listen = input(f"Enter the listen address for this client (default: '0.0.0.0' for all interfaces): ") or '0.0.0.0'

    registration_endpoint = f"{server_url.rstrip('/')}/systems/api/register_client/"
    payload = {'server_secret': server_secret, 'client_name': client_name, 'client_port': client_port}

    print(f"\nAttempting to register with {registration_endpoint}...")
    try:
        response = requests.post(registration_endpoint, json=payload)
        response.raise_for_status()
        response_data = response.json()
        client_api_key = response_data.get('client_api_key')
        resolved_url = response_data.get('resolved_client_url')

        if not client_api_key or not resolved_url:
            print(f"Error: Server response incomplete. Response: {response.text}")
            return False

        print("Registration successful!")
        print(f"Client registered with address: {resolved_url}")

        config_data = {
            'client_name': client_name,
            'client_api_key': client_api_key,
            'server_url': server_url.rstrip('/'),
            'client_port': client_port,
            'client_listen': client_listen
        }
        with open(config_path, 'w') as f:
            json.dump(config_data, f, indent=4)
        print(f"Client configuration saved to '{config_path}'.")
        return True

    except requests.exceptions.RequestException as e:
        print(f"\nError: Could not connect to the server. Details: {e}")
        return False
    except Exception as e:
        print(f"\nAn unexpected error occurred: {e}")
        if 'response' in locals():
            print(f"Server response: {response.status_code} - {response.text}")
        return False


def register_client_non_interactive(args, install_path):
    """Performs non-interactive client registration using provided arguments."""
    print("\n--- Client Registration (Non-Interactive) ---")
    config_path = os.path.join(install_path, CONFIG_FILE)

    if os.path.exists(config_path) and not args.force:
        print(f"ERROR: A configuration file exists at '{config_path}'. Use --force to overwrite.")
        return False

    server_url = args.server_url
    server_secret = args.server_secret
    client_name = args.client_name or socket.gethostname()
    client_port = args.client_port
    client_listen = args.client_listen

    registration_endpoint = f"{server_url.rstrip('/')}/systems/api/register_client/"
    payload = {'server_secret': server_secret, 'client_name': client_name, 'client_port': client_port}

    print(f"Attempting to register with {registration_endpoint}...")
    try:
        response = requests.post(registration_endpoint, json=payload)
        response.raise_for_status()
        response_data = response.json()

        client_api_key = response_data.get('client_api_key')
        resolved_url = response_data.get('resolved_client_url')

        if not client_api_key or not resolved_url:
            print(f"Error: Server response incomplete. Response: {response.text}")
            return False

        print("Registration successful!")
        print(f"Client registered with address: {resolved_url}")

        config_data = {
            'client_name': client_name,
            'client_api_key': client_api_key,
            'server_url': server_url.rstrip('/'),
            'client_port': client_port,
            'client_listen': client_listen
        }
        with open(config_path, 'w') as f:
            json.dump(config_data, f, indent=4)
        print(f"Client configuration saved to '{config_path}'.")
        return True

    except requests.exceptions.RequestException as e:
        print(f"\nError: Could not connect to the server. Details: {e}")
        return False
    except Exception as e:
        print(f"\nAn unexpected error occurred: {e}")
        if 'response' in locals():
            print(f"Server response: {response.status_code} - {response.text}")
        return False


def handle_install_non_interactive(args):
    """Handles the non-interactive installation process."""
    print("--- Carna Agent Executor Installation (Non-Interactive) ---")
    import shutil
    system = platform.system()
    default_path = DEFAULT_INSTALL_PATH_WINDOWS if system == 'Windows' else DEFAULT_INSTALL_PATH_LINUX_MAC
    install_path = os.path.abspath(args.path or default_path)
    print(f"Installation directory: {install_path}")

    # Step 1: Directory and File Copy
    print(f"\n--- Preparing Installation Directory ---")
    os.makedirs(install_path, exist_ok=True)
    for filename in FILES_TO_COPY:
        source_file = os.path.join(SOURCE_DIR, filename)
        dest_file = os.path.join(install_path, filename)
        if os.path.exists(source_file):
            shutil.copy(source_file, dest_file)
    print("Source files copied.")

    # Step 2: Python Environment
    venv_python = setup_python_env_and_dependencies(install_path)
    if not venv_python:
        print("Python environment setup failed. Aborting.")
        sys.exit(1)

    # Step 3: Client Registration
    if not register_client_non_interactive(args, install_path):
        print("Client registration failed. Aborting.")
        sys.exit(1)

    # Step 4: Service Installation
    if args.no_service:
        print("Service installation skipped as requested.")
        return
    if not is_admin():
        print("\nERROR: Service installation requires admin privileges.")
        sys.exit(1)
        
    if system == 'Linux':
        install_service_linux(venv_python, install_path)
    elif system == 'Darwin':
        install_service_macos(venv_python, install_path)
    elif system == 'Windows':
        install_service_windows(venv_python, install_path)
    else:
        print(f"Unsupported OS for service installation: {system}")
        sys.exit(1)


def setup_python_env_and_dependencies(install_path):
    """Creates a venv, gets python executable, and installs dependencies."""
    print("\n--- Setting up Python Virtual Environment ---")
    
    # 1. Create venv
    try:
        subprocess.run([sys.executable, '-m', 'venv', os.path.join(install_path, 'venv')], check=True, capture_output=True)
        print(f"Virtual environment created in '{os.path.join(install_path, 'venv')}'")
    except subprocess.CalledProcessError as e:
        print(f"ERROR: Failed to create virtual environment.")
        print(f"Stderr: {e.stderr.decode('utf-8')}")
        return None

    # 2. Get venv python path
    venv_python = get_venv_python_path(install_path)
    if not os.path.exists(venv_python):
        print(f"ERROR: Could not find python executable in venv at '{venv_python}'")
        return None
        
    print(f"Virtual environment python found at: {venv_python}")

    # 3. Install dependencies into venv
    requirements_path = os.path.join(install_path, 'requirements.txt')
    print(f"\n--- Installing Python Dependencies from '{requirements_path}' ---")
    try:
        subprocess.run(
            [venv_python, '-m', 'pip', 'install', '-r', requirements_path],
            check=True,
            capture_output=True,
            text=True
        )
        print("Dependencies installed successfully into virtual environment.")
        return venv_python
    except subprocess.CalledProcessError as e:
        print("\nERROR: Failed to install Python dependencies into venv.")
        print(f"pip stdout:\n{e.stdout}")
        print(f"pip stderr:\n{e.stderr}")
        return None
    except FileNotFoundError:
        print("\nERROR: 'pip' command not found inside the virtual environment.")
        return None


# --- Main Execution ---

def main():
    parser = argparse.ArgumentParser(
        description=f'{SERVICE_DISPLAY_NAME} Installer & Service Manager.',
        formatter_class=argparse.RawTextHelpFormatter
    )
    subparsers = parser.add_subparsers(dest='command', help='Available commands')

    # Install command
    p_install = subparsers.add_parser('install', help='Run the installer. Interactive by default, or non-interactive with arguments.')
    p_install.add_argument('--path', help='(Optional) The installation directory. Uses a system default if not provided.')
    p_install.add_argument('--server-url', help='(Non-interactive) Full URL of the Carna server')
    p_install.add_argument('--server-secret', help="(Non-interactive) Server's AGENT_SERVER_SECRET_KEY")
    p_install.add_argument('--client-name', help="(Non-interactive) Name for this client (defaults to hostname)")
    p_install.add_argument('--client-port', default='8123', help="(Non-interactive) Port for this client (default: 8123)")
    p_install.add_argument('--client-listen', default='0.0.0.0', help="(Non-interactive) Listen address for this client (default: 0.0.0.0)")
    p_install.add_argument('--no-service', action='store_true', help="(Non-interactive) Only register, do not install the system service.")
    p_install.add_argument('--force', action='store_true', help=f"(Non-interactive) Overwrite existing '{CONFIG_FILE}' in the installation directory.")
    
    # Uninstall command
    p_uninstall = subparsers.add_parser('uninstall', help='Uninstall the system service and delete files.')
    p_uninstall.add_argument('--path', help='(Optional) The installation directory to remove. Uses default if not provided.')
    
    # Status command
    subparsers.add_parser('status', help='Check the status of the system service.')

    args = parser.parse_args()

    # If no command is given, print help and exit.
    if args.command is None:
        parser.print_help()
        return

    if args.command == 'install':
        # Check if we are in non-interactive mode.
        is_non_interactive = args.server_url and args.server_secret
        if is_non_interactive:
            handle_install_non_interactive(args)
        else:
            # If 'install' is specified but without required args, run interactively.
            handle_install_interactive(args)
    elif args.command == 'uninstall':
        handle_uninstall(args)
    elif args.command == 'status':
        handle_status()

if __name__ == '__main__':
    main()
'''
_EMBEDDED_REQUIREMENTS_CONTENT = '''fastapi
uvicorn[standard]

websockets
'''

EMBEDDED_FILES_MAP = {
    'primitives.py': _EMBEDDED_PRIMITIVES_CONTENT,
    'main.py': _EMBEDDED_MAIN_CONTENT,
    'installer.py': _EMBEDDED_INSTALLER_CONTENT,
    'requirements.txt': _EMBEDDED_REQUIREMENTS_CONTENT,
}

def main():
    temp_dir = None
    original_cwd = os.getcwd()
    try:
        # Create a temporary directory
        temp_dir = tempfile.mkdtemp()
        
        print(f"Temporary directory created at: {temp_dir}")

        # Write embedded files to the temporary directory
        for filename, content in EMBEDDED_FILES_MAP.items():
            filepath = os.path.join(temp_dir, filename)
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"Wrote {filename} to {filepath}")

        # Change current working directory to the temporary directory
        os.chdir(temp_dir)

        # Execute the installer.py script from the temporary directory
        # Pass all arguments received by onefileinstaller.py to installer.py
        installer_script_path = os.path.join(temp_dir, 'installer.py')
        print(f"Executing installer from: {installer_script_path} with arguments: {sys.argv[1:]}")
        
        # We need to use the current python executable to run the embedded installer
        command = [sys.executable, installer_script_path] + sys.argv[1:]
        
        # Run the installer process
        process = subprocess.run(command, check=False)
        
        if process.returncode != 0:
            print(f"Installer exited with non-zero status: {process.returncode}", file=sys.stderr)
            sys.exit(process.returncode)

    except Exception as e:
        print(f"An error occurred during one-file installer execution: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        # Change back to original working directory
        os.chdir(original_cwd)
        # Clean up the temporary directory
        if temp_dir and os.path.exists(temp_dir):
            print(f"Cleaning up temporary directory: {temp_dir}")
            shutil.rmtree(temp_dir)
        else:
            print("No temporary directory to clean up or it was already removed.")

if __name__ == '__main__':
    main()

    