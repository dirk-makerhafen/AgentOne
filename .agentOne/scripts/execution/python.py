import sys
import os
import subprocess
import tempfile
import json

def python(caller, source):
    '''
    Execute a Python script.

    Use this tool when you need to run Python code for:
    - Performing calculations or data processing
    - Reading, writing, or transforming files
    - Running small scripts to verify behavior
    - Installing packages via subprocess

    Args:
        source (str): The Python source code to execute.

    Returns:
        tuple: (success: bool, result: dict)
            On success, result contains:
                - 'status': 'success'
                - 'stdout': str
                - 'stderr': str
                - 'return_code': int
            On error, result contains:
                - 'status': 'error'
                - 'stdout': str
                - 'stderr': str
                - 'return_code': int
    '''
    cwd = caller.workingdir if hasattr(caller, 'workingdir') and caller.workingdir else os.getcwd()

    try:
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8') as f:
            f.write(source)
            tmp_path = f.name

        proc = subprocess.run(
            [sys.executable, tmp_path],
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
            'stderr': 'Python script timed out after 300 seconds.',
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
