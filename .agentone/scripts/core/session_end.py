"""End a session — the single deactivation path.

Every session deactivation is dispatched through this task (via
``session.get_task("session_end").delay(reason=...)``), which makes it the
anchor for ``after:`` intercept hooks on ``session_end`` — the replacement
for the old bespoke ``session_end`` lifecycle event (see
``docs/session-hooks.md``). The task itself is a tiny bookkeeping write; any
hook task runs detached in the intercepted call's own after-chain and reads
the returned dict.
"""
from __future__ import annotations

from typing import Any

from runtime.session.session import Session


def session_end(
    _session: Session,
    reason: str = "deactivated",
    **kwargs: Any,
) -> dict[str, Any]:
    """Deactivate the session and return an after-hook context.

    Flips ``is_active`` to ``False`` (idempotent) and returns the frame a
    post-hook needs: ``reason``, ``session_type`` and ``last_message_pk``
    (the message a detached hook should fork from), plus ``transitioned``
    (whether this call actually deactivated) and any extra kwargs.
    """
    tail = _session.get_last_message()
    was_active = bool(_session.model.is_active)
    _session.set_is_active(False)
    return {
        "reason": reason,
        "session_type": _session.session_type,
        "last_message_pk": tail.pk if tail is not None else None,
        "transitioned": was_active,
        **kwargs,
    }
