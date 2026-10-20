
from __future__ import annotations

from datetime import datetime
from time import time
from typing import Any

from runtime.session.session import Session
from server.models.enums.session_enums import SessionType


def delegate_task(_session: Session, agentname: str|None=None, prompt: str = "", blocking: bool = True) -> dict[str, Any]:
    """Send a one-off task to another agent.

    Creates a fresh session for the target agent, sends *prompt* as its
    first message.  Unlike ``start_subsession``, every call creates a new
    uniquely-named session — use ``start_subsession`` if you need a named,
    reusable background session that you can message repeatedly.

    When *blocking* is ``True``: your turn pauses until the agent finishes.
    The ``result`` field will contain the agent's final reply (a message
    dict with ``content``, ``role``, etc.).

    When *blocking* is ``False``: returns immediately. The agent's reply
    will be injected into your conversation once it completes.

    See also: ``spawn_subtask`` (same idea but forks your current session),
    ``start_subsession`` (named persistent background sessions).

    Args:
        prompt: The task description to execute. This must be a plain-language
            task description in your own words — not a tool-call string, and
            never a final_result(...) call. The subagent will call final_result
            itself when done.
        agentname: Optional name of the agent to perform the task. Run
            ``get_available_agents`` to see valid names. Defaults to the same agent as you.
        blocking: ``True`` to wait for the result, ``False`` to submit and
            receive the result later asynchronously. Defaults to ``True``.

    Returns:
        Blocking mode (blocking=True):
            ``{"result": {message dict}, "session_pk": int}``
        Non-blocking mode (blocking=False):
            ``{"result": "delegated", "session_pk": int}``
        On error:
            ``{"error": "Agent '<name>' not found"}``
    """

    if not prompt:
        return {"error": f"You must provide a prompt to delegate a task"}
    if not agentname:
        agentname = _session.agent.name

    name = f"p{_session.model.pk}:{agentname}:{datetime.now().strftime('%Y.%m.%d-%H:%M:%S')}"
    description = prompt[:100] + "..." if len(prompt) > 100 else ""

    if agentname == _session.agent.name:
        # Delegating to ourselves is a settings-only fork: inherit our session
        # config, but start a fresh message chain (no history link).
        child_session = _session.fork(
            name=name,
            description=description,
            session_type=SessionType.SUBTASK_DELEGATE,
        )
    else:
        child_session = _session.spawn_subagent(
            agentname,
            name=name,
            description=description,
            session_type=SessionType.SUBTASK_DELEGATE,
        )
        if child_session is None:
            return {"error": f"Agent '{agentname}' not found"}


    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    working_dir = child_session.workspace.path if child_session.workspace else "unknown"
    parts = [
        f"It is now {now}, your working dir is '{working_dir}'.\n",
        "You are running as a subtask for another agent. "
        "When your work is complete, finish by invoking the final_result tool directly "
        "with your result as its content argument. "
        "Do not return your result as plain text only. Your task:\n",
        prompt,
    ]
    taskcall = child_session.add_user_message(parts)

    if blocking:
        return taskcall

    _session.get_task("ingest_subagent_result").delay(
        child_session_pk=child_session.model.pk,
        summary=prompt,
        result=taskcall,
    )
    return {"result": "delegated", "session_pk": child_session.model.pk}
