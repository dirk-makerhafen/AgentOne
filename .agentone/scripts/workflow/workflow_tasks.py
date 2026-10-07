"""Workflow engine continuations (internal tasks, never called by the LLM).

Each function runs one link of a workflow's non-blocking chain: it does a
small synchronous unit of work (render args, dispatch the next tool
call(s), or collect finished results) and returns either the next
continuation call or the final result envelope.  The scheduler parks a
continuation in ``WAITING_DEPENDENCY`` until the call(s) it takes as
arguments end, so no worker ever blocks waiting for tool results.

All real logic lives in ``runtime/session_workflows.py``; these functions
only forward the bound session.
"""

from __future__ import annotations

from typing import Any

from runtime.session.session import Session


def workflow_step(_session: Session, run_ctx: dict, index: int) -> Any:
    """Execute step ``index``: dispatch its tool call(s) + continuation."""
    from runtime import session_workflows as _wf

    return _wf.step_workflow(_session, run_ctx, index)


def workflow_advance(_session: Session, run_ctx: dict, index: int,
                     prior: Any) -> Any:
    """Continue after step ``index``'s tool call ended; run the next step."""
    from runtime import session_workflows as _wf

    return _wf.advance_workflow(_session, run_ctx, index, prior)


def workflow_join(_session: Session, run_ctx: dict, index: int,
                  branches: list) -> Any:
    """Continue after step ``index``'s group branches all ended."""
    from runtime import session_workflows as _wf

    return _wf.join_workflow(_session, run_ctx, index, branches)


def workflow_fanout(_session: Session, run_ctx: dict, index: int,
                    producer: Any) -> Any:
    """Continue after step ``index``'s map producer ended; fan out wave 1."""
    from runtime import session_workflows as _wf

    return _wf.fanout_workflow(_session, run_ctx, index, producer)


def workflow_mapjoin(_session: Session, run_ctx: dict, index: int,
                     collected: list, wave: list, remaining: list) -> Any:
    """Continue after a map wave ended; next wave, or the next step."""
    from runtime import session_workflows as _wf

    return _wf.mapjoin_workflow(_session, run_ctx, index, collected, wave,
                                remaining)


def workflow_inline(_session: Session, source: str, params: Any = None) -> Any:
    """Execute one inline ``function`` step body (internal; never called
    by the LLM — the engine dispatches it like a tool leaf so the step
    gets a recorded call).

    ``source`` is the raw body (bare ``return`` allowed); ``params`` keys
    become its parameter names. Runs isolated in a subprocess, same as
    ad-hoc tools; returns the namespaced ``(ok, payload)`` tuple.
    """
    from runtime import adhoc_tools as _adhoc

    return _adhoc.run_inline_function(_session, source, params)
