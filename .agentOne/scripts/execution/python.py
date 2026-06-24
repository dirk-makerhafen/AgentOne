from __future__ import annotations

import os
import subprocess
import sys
import tempfile


def python(source: str) -> tuple[bool, dict]:
    '''
    Execute a Python script.

    Use this tool when you need to run Python code for:
    - Performing calculations or data processing
    - Reading, writing, or transforming files
    - Running small scripts to verify behavior
    - Installing packages via subprocess

    Args:
        source: The Python source code to execute.

    Returns:
        A tuple of (success, result).
        On success, result contains:
            - status: "success"
            - stdout: str
            - stderr: str
            - return_code: int
        On error, result contains the same keys with status "error".
    '''

    # --- Guardrail check ---
    guardrail_block = _guardrail_check(source)
    if guardrail_block:
        return (False, {
            'status': 'error',
            'stdout': '',
            'stderr': guardrail_block,
            'return_code': -1,
        })

    cwd = os.getcwd()

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
            env={**os.environ},
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


def _guardrail_check(source: str) -> str | None:
    """Run Python guardrail on the source code.  Returns an error message or None."""
    try:
        from runtime.guardrails import check_python_command

        verdict = check_python_command(source, ask_threshold=90)
        if verdict.action == "ask":
            return (
                f"Python code blocked by safety guardrail.\n"
                f"Reason: {verdict.reason}\n"
                f"Risk: {verdict.level} (score: {verdict.score})"
            )
    except Exception:
        pass
    return None

if __name__ == '__main__':
    import argparse
    import json

    parser = argparse.ArgumentParser(description='Execute a Python script.')
    parser.add_argument('--source', type=str, required=True, help='Python source code to execute')
    parser.add_argument('--file', type=str, help='Python file to execute (alternative to --source)')
    args = parser.parse_args()

    source = args.source
    if args.file:
        with open(args.file, 'r') as f:
            source = f.read()

    success, result = python(source=source)
    print(json.dumps(result, indent=2))
    exit(0 if success else 1)
