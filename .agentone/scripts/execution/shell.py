from __future__ import annotations

import os
import subprocess
import sys
import tempfile


def shell(source: str, interpreter: str = "auto") -> tuple[bool, dict]:
    '''
    Execute a shell command or script.

    Use this tool when you need to:
    - Run system commands (git, curl, ls, grep, etc.)
    - Invoke command-line utilities or build tools
    - Inspect the filesystem or system state
    - Automate OS-level tasks

    Execution environment:
    - The script is written to a temporary file and executed.
    - Interpreter defaults to "auto" (bash on Unix, detects
      powershell/cmd on Windows).
    - Commands must be non-interactive and complete in finite time.

    Safety:
    - Commands are inspected by sh-guard before execution.
      Dangerous commands (score >= 90) are blocked.
    - pureshellcheck lint warnings are attached to the result
      metadata for the LLM to review and fix shell issues.

    Args:
        source: The shell script to execute.
        interpreter: The interpreter to use ("bash", "sh",
            "powershell", "cmd", or "auto"). Default: "auto".

    Returns:
        A tuple of (success, result).
        On success, result contains:
            - status: "success"
            - stdout: str
            - stderr: str
            - return_code: int (0 on success)
            - lint_warnings: list[dict] (pureshellcheck findings, optional)
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

    # --- Lint check (non-blocking) ---
    lint_warnings = _lint_check(source)

    cwd = os.getcwd()

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
            env={**os.environ},
        )

        result = {
            'status': 'success',
            'stdout': proc.stdout,
            'stderr': proc.stderr,
            'return_code': proc.returncode,
        }
        if lint_warnings:
            result['lint_warnings'] = lint_warnings
        return (proc.returncode == 0, result)

    except subprocess.TimeoutExpired:
        return (False, {
            'status': 'error',
            'stdout': '',
            'stderr': 'Command timed out after 300 seconds.',
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
    """Run sh-guard on the command.  Returns an error message or None."""
    try:
        from runtime.guardrails import check_shell_command

        verdict = check_shell_command(source, ask_threshold=90)
        if verdict.action == "ask":
            return (
                f"Command blocked by safety guardrail.\n"
                f"Reason: {verdict.reason}\n"
                f"Risk: {verdict.level} (score: {verdict.score})"
            )
    except Exception:
        pass
    return None


def _lint_check(source: str) -> list[dict]:
    """Run pureshellcheck on the command.  Returns a list of lint findings."""
    try:
        from runtime.guardrails import lint_shell_command

        return lint_shell_command(source)
    except Exception:
        return []

if __name__ == '__main__':
    import argparse
    import json

    parser = argparse.ArgumentParser(description='Execute a shell command or script.')
    parser.add_argument('--source', type=str, required=True, help='Shell script to execute')
    parser.add_argument('--interpreter', type=str, default='auto', choices=['auto', 'bash', 'sh', 'powershell', 'cmd'], help='Interpreter to use')
    args = parser.parse_args()

    success, result = shell(source=args.source, interpreter=args.interpreter)
    print(json.dumps(result, indent=2))
    exit(0 if success else 1)
