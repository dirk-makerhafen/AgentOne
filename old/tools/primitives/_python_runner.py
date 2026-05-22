import sys, io, traceback, json, os
import re, subprocess, math, threading, copy, pathlib
import datetime, random, itertools, time, requests, inspect, functools
from copy import deepcopy
from pathlib import Path

# Determine the project root and add it to sys.path
# This script is in <project_root>/tools/primitives/
script_dir = pathlib.Path(__file__).parent.resolve() # <project_root>/tools/primitives
tools_dir = script_dir.parent.resolve() # <project_root>/tools
project_root = tools_dir.parent.resolve() # <project_root>

if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Explicitly import primitive functions using their absolute paths from the project root
from old.tools.primitives.append_file import append_file
from old.tools.primitives.list_directory import list_directory
from old.tools.primitives.manage_tool_process import start_tool_process, stop_tool_process, call_tool_session
from old.tools.primitives.mkdir import mkdir
from old.tools.primitives.read_file import read_file
from old.tools.primitives.rm import rm
from old.tools.primitives.run_python_code import run_python_code
from old.tools.primitives.run_shell_script import run_shell_script
from old.tools.primitives.stat_path import stat_path
from old.tools.primitives.write_file import write_file

# Load data from stdin
data_transfered = json.loads(sys.stdin.readline())
locals = data_transfered["locals"]
locals_to_return = data_transfered["locals_to_return"]

old_stdout, old_stderr = sys.stdout, sys.stderr
sys.stdout, sys.stderr = io.StringIO(), io.StringIO()
caught_exception = None

try:
    # Read the actual user code from stdin after the JSON
    code = sys.stdin.read()
    exec(code, globals(), locals)
except Exception as e:
    caught_exception = str(e)
    traceback.print_exc(file=sys.stderr)

stdout_val = sys.stdout.getvalue().strip()
stderr_val = sys.stderr.getvalue().strip()
sys.stdout, sys.stderr = old_stdout, old_stderr

result = {
    "status": "success" if not caught_exception else "error",
}
if caught_exception:
    result["message"] = f"Exception: {caught_exception}"
if stdout_val:
    result["stdout"] = stdout_val
if stderr_val:
    result["stderr"] = stderr_val
result["vars"] = {k: locals[k] for k in locals_to_return if k in locals}

print(json.dumps(result))