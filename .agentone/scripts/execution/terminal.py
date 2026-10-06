from __future__ import annotations

"""Persistent named terminals for agent sessions (libtmux backend).

Unlike ``shell`` (one-shot ``subprocess.run``), these tools share a
long-lived shell per ``(session, terminal)`` pair, so environment,
working directory, background jobs, and interactive CLIs survive
individual tool calls. Agent-only: there is no browser input path.
"""


def _guardrail_block(session, source: str) -> str | None:
    """Mirror ``shell.py``: sh-guard (ask→block) + workspace path deny."""
    if not isinstance(source, str) or not source.strip():
        return None
    try:
        from runtime.guardrails import check_shell_command, check_shell_paths
        from runtime.workspace_access import resolve_policy

        verdict = check_shell_command(source, ask_threshold=90)
        if verdict.action == "ask":
            return (
                "Command blocked by safety guardrail.\n"
                f"Reason: {verdict.reason}\n"
                f"Risk: {verdict.level} (score: {verdict.score})"
            )
        try:
            policy = resolve_policy(session)
        except Exception:
            return None
        path_verdict = check_shell_paths(source, policy)
        if path_verdict.action == "deny":
            return (
                "Blocked by workspace access policy.\n"
                f"Reason: {path_verdict.reason}"
            )
    except Exception:
        pass
    return None


def _unavailable(exc: Exception) -> tuple[bool, dict]:
    return (False, {
        'status': 'error',
        'stdout': '',
        'stderr': str(exc),
        'return_code': -1,
    })


def terminal_exec(session, command: str, terminal: str = "default", timeout: int = 60) -> tuple[bool, dict]:
    '''Run a command in a named persistent terminal and wait for exit.

    The terminal persists across calls: cwd, env, and background jobs
    survive. First use creates ``terminal`` (tmux session
    ``agentone-s<sid>-<terminal>``) in the session workspace.

    Args:
        command: Shell command to execute.
        terminal: Named terminal (default: "default"). Use separate names
            (e.g. "dev", "agent") to isolate workflows.
        timeout: Seconds to wait for the sentinel marker (max 600).

    Returns:
        (success, result) with stdout/stderr/return_code/terminal.
    '''
    block = _guardrail_block(session, command)
    if block:
        return (False, {'status': 'error', 'stdout': '', 'stderr': block, 'return_code': -1})
    try:
        from runtime.terminal.manager import exec_command

        result = exec_command(session.model, command, name=terminal or "default", timeout=timeout or 60)
    except Exception as e:
        import traceback
        return (False, {'status': 'error', 'stdout': '', 'stderr': f'{e}\n{traceback.format_exc()}', 'return_code': -1})
    ok = result.get("status") == "success" and result.get("return_code", -1) == 0
    return (ok, result)


def terminal_send(session, text: str, terminal: str = "default", submit: bool = True) -> tuple[bool, dict]:
    '''Send keystrokes to a named terminal (interactive CLIs, prompts).

    Use after ``terminal_exec`` starts something interactive, or to drive
    an external agent CLI (answer its prompts). Pair with
    ``terminal_poll`` to read the response.

    Args:
        text: Keystrokes to send (e.g. "y", "exit", "/quit").
        terminal: Named terminal (default: "default").
        submit: Press Enter after the text (default True).

    Returns:
        (success, result) with terminal/submitted.
    '''
    block = _guardrail_block(session, text)
    if block:
        return (False, {'status': 'error', 'message': block})
    try:
        from runtime.terminal.manager import send_input

        result = send_input(session.model, text or "", name=terminal or "default", submit=submit)
    except Exception as e:
        import traceback
        return (False, {'status': 'error', 'message': f'{e}\n{traceback.format_exc()}'})
    return (True, result)


def terminal_poll(session, terminal: str = "default", lines: int = 200) -> tuple[bool, dict]:
    '''Read a terminal's visible buffer without executing anything.

    Poll after ``terminal_exec`` (long jobs) or ``terminal_send``
    (interactive prompts) to see current output.

    Args:
        terminal: Named terminal (default: "default").
        lines: Max trailing lines to return (default 200, max 2000).

    Returns:
        (success, result) with output/terminal.
    '''
    try:
        from runtime.terminal.manager import poll_output

        result = poll_output(session.model, name=terminal or "default", lines=lines or 200)
    except Exception as e:
        import traceback
        return (False, {'status': 'error', 'message': f'{e}\n{traceback.format_exc()}'})
    return (True, result)


def terminal_list(session) -> tuple[bool, dict]:
    '''List this session's named terminals with liveness info.

    Returns:
        (success, result) with terminals: [{name, status, alive, cwd}].
    '''
    try:
        from runtime.terminal.manager import list_terminals

        return (True, {'status': 'success', 'terminals': list_terminals(session.model)})
    except Exception as e:
        import traceback
        return (False, {'status': 'error', 'message': f'{e}\n{traceback.format_exc()}'})


def terminal_kill(session, terminal: str = "default") -> tuple[bool, dict]:
    '''Kill a named terminal (tmux session + bookkeeping row).

    Args:
        terminal: Named terminal to destroy.

    Returns:
        (success, result).
    '''
    try:
        from runtime.terminal.manager import kill_terminal

        result = kill_terminal(session.model, name=terminal or "default")
    except Exception as e:
        import traceback
        return (False, {'status': 'error', 'message': f'{e}\n{traceback.format_exc()}'})
    return (result.get("status") == "success", result)
