import os
import ast
import textwrap
from pathlib import Path
from copy import deepcopy
import os
import ast
import textwrap
import shutil
import sys
import io
import traceback
import functools
import traceback
import types
from pydantic import AnyUrl
import requests
import subprocess
import tempfile
import threading


# Global state for managing long-running tool processes launched by this executor.
# Key: process_id (string), Value: dict containing the live async session and context managers.
managed_processes = {}

# Global state for the asyncio event loop running in a background thread
_async_loop = None
_loop_thread = None

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
    def wrapper(agentInstance=None, system=None, **kwargs): # Added 'system' argument
        is_remote = False
        target_system = None

        if system: # Prioritize system if explicitly passed
            target_system = system
        elif agentInstance: # Fallback to agentInstance.system
            target_system = agentInstance.system

        if target_system:
            is_remote = target_system.is_remote_executor and target_system.executor_url and target_system.executor_api_key

        if is_remote:
            return _run_remote(system=target_system, func=func, **kwargs)
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
def run_python_code(python_code_string: str, locals_dict={}, locals_to_return=[]):
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
def run_shell_script(script: str, interpreter: str = "auto", env: dict = None, timeout: int = 60, cwd: str= None):
    """
    Executes a shell script using the specified interpreter, with auto-detection for Windows.

    Args:
        script (str): The multi-line script to execute.
        interpreter (str): 'auto', 'bash', 'powershell', or 'cmd'. Defaults to 'auto'.
        env (dict): Optional dictionary of environment variables.
        timeout (int): Maximum time in seconds to wait for the command to complete.
        cwd (str): Change working dir to str
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

        process = subprocess.run(command_list, env=full_env, capture_output=True, text=True, timeout=timeout, cwd=cwd)

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
        if parents:
            os.makedirs(path, exist_ok=exist_ok)
        elif not (os.path.exists(path) and exist_ok == True):
            os.mkdir(path)
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

@dispatched_primitive_operation
def manage_tool_process(
    action: str, 
    process_id: str, 
    command: str = None, 
    args: list = None,
    cwd: str = None, 
    env: dict = None,
    mcp_server_config: dict = None, # For starting the client
    tool_name: str = None, # For invoking a tool
    tool_kwargs: dict = None # For invoking a tool
):
    """
    Manages the lifecycle and interaction with stateful MCP clients on the executor
    by submitting async tasks to a persistent, thread-safe event loop.
    """
    import asyncio
    import traceback
    return
    try:
        loop = _get_async_loop()
        coro = _manage_tool_process_async(
            action, process_id, command, args, cwd, env, mcp_server_config, tool_name, tool_kwargs
        )
        future = asyncio.run_coroutine_threadsafe(coro, loop)
        result = future.result(timeout=60)  # Add a timeout for safety
        return result
    except Exception as e:
        return {'status': 'error', 'message': f"An error occurred in manage_tool_process (action: {action}): {type(e).__name__}: {e}\n{traceback.format_exc()}"}



def _get_async_loop():
    """Starts and returns the global asyncio event loop running in a background thread."""
    global _async_loop, _loop_thread
    return
    if _loop_thread is None:
        import asyncio
        import threading
        _async_loop = asyncio.new_event_loop()
        _loop_thread = threading.Thread(target=_async_loop.run_forever, daemon=True)
        _loop_thread.start()
    return _async_loop



async def _manage_tool_process_async(
    action: str, 
    process_id: str, 
    command: str = None, 
    args: list = None,
    cwd: str = None, 
    env: dict = None,
    mcp_server_config: dict = None,
    tool_name: str = None,
    tool_kwargs: dict = None
):
    """
    The core async logic for managing tool processes. This function manually handles async context 
    managers to create a persistent, stateful connection that can be used across multiple calls.
    """
    global managed_processes
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    import traceback

    if action == 'start':
        # Clean up any previous, orphaned instance for this process_id before starting a new one.
        if process_id in managed_processes:
            old_client_info = managed_processes.pop(process_id)
            try:
                await old_client_info['session_cm'].__aexit__(None, None, None)
                await old_client_info['stdio_cm'].__aexit__(None, None, None)
            except Exception:
                pass # Ignore errors during cleanup of potentially broken clients

        if not all([command, cwd, mcp_server_config]):
            return {'status': 'error', 'message': "'command', 'cwd', and 'mcp_server_config' are required for start."}

        try:
            server_params = StdioServerParameters(command=command, args=args or [], cwd=cwd, env=env)
            
            # Manually enter the async context managers to keep them alive beyond this single 'start' call.
            # This is the core of creating a persistent connection.
            stdio_cm = stdio_client(server_params)
            read, write = await stdio_cm.__aenter__()
            
            session_cm = ClientSession(read, write)
            session = await session_cm.__aenter__()
            
            # Perform the handshake to ensure the tool is ready.
            await session.initialize()
            
            # Store the active session and the context managers in our global state dictionary.
            # This allows subsequent actions ('list_tools', 'invoke_tool') to find and use this connection.
            managed_processes[process_id] = {
                'session': session,
                'session_cm': session_cm,
                'stdio_cm': stdio_cm,
            }
            return {'status': 'success', 'message': f'Client {process_id} started and initialized successfully.'}
        except Exception as e:
            # If starting fails, ensure we clean up any partially created contexts.
            if 'session_cm' in locals() and hasattr(session_cm, '__aexit__'):
                await session_cm.__aexit__(None, None, None)
            if 'stdio_cm' in locals() and hasattr(stdio_cm, '__aexit__'):
                await stdio_cm.__aexit__(None, None, None)
            return {'status': 'error', 'message': f"Failed to start client {process_id}: {e}\n{traceback.format_exc()}"}

    elif action == 'stop':
        client_info = managed_processes.pop(process_id, None)
        if client_info:
            try:
                # Explicitly exit the contexts in reverse order of creation to gracefully shut down.
                await client_info['session_cm'].__aexit__(None, None, None)
                await client_info['stdio_cm'].__aexit__(None, None, None)
                return {'status': 'success', 'message': f'Client {process_id} stopped.'}
            except Exception as e:
                return {'status': 'warning', 'message': f'Error during client stop for {process_id}: {e}'}
        return {'status': 'success', 'message': f'Client {process_id} was not running.'}

    elif action == 'list_tools':
        if process_id not in managed_processes: return {'status': 'error', 'message': f'Client {process_id} not found or not running.'}
        session = managed_processes[process_id]['session']
        result = await session.list_tools()
        return {'status': 'success', 'data': result.model_dump() if result else {}}

    elif action == 'invoke_tool':
        if process_id not in managed_processes: return {'status': 'error', 'message': f'Client {process_id} not found or not running.'}
        if not tool_name: return {'status': 'error', 'message': "'tool_name' is required."}
        session = managed_processes[process_id]['session']
        result = await session.call_tool(tool_name, arguments=tool_kwargs or {})
        if result and result.content:
            return {'status': 'success', 'data': [item.model_dump() for item in result.content]}
        return {'status': 'success', 'data': None}

    else:
        return {'status': 'error', 'message': f'Unknown action: {action}'}
