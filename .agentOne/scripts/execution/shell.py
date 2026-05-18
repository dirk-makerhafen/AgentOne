import sys
import os
import subprocess
import tempfile

def shell(caller, source, interpreter="auto"):
    '''
    Execute a shell command or script.

    Use this tool when you need to:
    - Run system commands (git, curl, ls, grep, etc.)
    - Invoke command-line utilities or build tools
    - Inspect the filesystem or system state
    - Automate OS-level tasks

    Execution environment:
    - The script is written to a temporary file and executed.
    - Interpreter defaults to "auto" (bash on Unix, detects powershell/cmd on Windows).
    - Commands must be non-interactive and complete in finite time.
    - Never use for speculative or destructive actions.

    Args:
        source (str): The shell script to execute.
        interpreter (str): The interpreter to use (e.g., "bash", "sh", "powershell", "cmd", "auto"). Default: "auto".

    Returns:
        tuple: (success: bool, result: dict)
            On success, result contains:
                - 'status': 'success'
                - 'stdout': str
                - 'stderr': str
                - 'return_code': int (0 on success)
            On error, result contains:
                - 'status': 'error'
                - 'stdout': str
                - 'stderr': str
                - 'return_code': int
    '''
    cwd = caller.workingdir if hasattr(caller, 'workingdir') and caller.workingdir else os.getcwd()

    is_windows = sys.platform == "win32"
    if interpreter == "auto":
        if is_windows:
            if "$" in source and "%" not in source:
                interpreter = "powershell"
            elif "%" in source and "$" not in source:
                interpreter = "cmd"
            else:
                interpreter = "powershell"
        else:
            interpreter = "bash"

    file_extension = ".ps1" if interpreter == "powershell" else ".bat" if interpreter == "cmd" else ".sh"

    if interpreter == "powershell":
        cmd = ["powershell.exe", "-ExecutionPolicy", "Bypass", "-File"]
    elif interpreter == "cmd":
        cmd = ["cmd.exe", "/c"]
    elif interpreter == "bash":
        cmd = ["bash"]
    else:
        return (False, {
            'status': 'error',
            'stdout': '',
            'stderr': f'Unsupported interpreter: {interpreter}',
            'return_code': -1,
        })

    try:
        with tempfile.NamedTemporaryFile(mode='w', suffix=file_extension, delete=False, encoding='utf-8') as f:
            f.write(source)
            tmp_path = f.name

        cmd.append(tmp_path)

        proc = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=300,
            env={**os.environ}
        )

        result = {
            'status': 'success',
            'stdout': proc.stdout,
            'stderr': proc.stderr,
            'return_code': proc.returncode,
        }
        return (proc.returncode == 0, result)

    except subprocess.TimeoutExpired:
        return (False, {
            'status': 'error',
            'stdout': '',
            'stderr': f'Command timed out after 300 seconds.',
            'return_code': -1,
        })
    except Exception as e:
        import traceback
        return (False, {
            'status': 'error',
            'stdout': '',
            'stderr': f'{str(e)}\n{traceback.format_exc()}',
            'return_code': -1,
        })
    finally:
        if 'tmp_path' in locals() and os.path.exists(tmp_path):
            os.remove(tmp_path)
