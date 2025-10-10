import sys, io, traceback, json, os
import re, subprocess, math, threading, copy, pathlib
import datetime, random, itertools, time, requests, inspect, functools
from copy import deepcopy
from pathlib import Path

script_dir = pathlib.Path(__file__).parent.resolve()
if script_dir not in sys.path:
    sys.path.insert(0, script_dir)

from . import *  # import primitives

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