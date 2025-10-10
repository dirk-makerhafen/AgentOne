
from copy import deepcopy
import sys
import io
import traceback
import pathlib
import traceback
import subprocess
import sys, subprocess, json, os
from ._dispatch_decorator import dispatched_primitive_operation


@dispatched_primitive_operation
def run_python_code(python_code_string: str, locals_dict={}, locals_to_return=[], workingdir=None):
    """
    Executes Python code in an isolated subprocess, with its own working directory.
    Adds the original working directory to sys.path so local modules can still be imported.
    Returns the same structured result dict as the original function.
    """
    script_dir = pathlib.Path(__file__).parent.resolve()
    script_file = os.path.join(script_dir, "_python_runner.py")
    try:
        # First line: locals_dict as JSON, then the user code itself
        stdin_data = json.dumps({
            "locals": locals_dict,
            "locals_to_return": locals_to_return,
        }) + "\n" + python_code_string
        proc = subprocess.run([sys.executable, script_file],
            cwd = workingdir or os.getcwd(),
            input = stdin_data,
            capture_output = True,
            text = True
        )
        if proc.returncode != 0:
            return {
                "status": "error",
                "message": f"Subprocess failed with code {proc.returncode}",
                "stdout": proc.stdout.strip(),
                "stderr": proc.stderr.strip(),
            }
        return json.loads(proc.stdout.strip())
    finally:
        pass






def run_python_code_old(python_code_string: str, locals_dict={}, locals_to_return=[]):
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
        'from tools.primitives import *\n' \
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

