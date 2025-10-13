import os
import sys
import traceback
import subprocess
import tempfile
import sys, subprocess, tempfile, os
from ._dispatch_decorator import dispatched_detached



@dispatched_detached
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
        full_env = {"PATH": os.environ["PATH"]} 
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


    