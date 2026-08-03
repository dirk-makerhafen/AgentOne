from __future__ import annotations

from runtime.session.session import Session
from server.models.message import Message


def compact(_session: Session, message: Message | None = None) -> dict:
    if message is None:
        messages = _session.model.messages.order_by("-created_at")
        if not messages.exists():
            return {"status": "ok", "message": "No messages to compact."}
        message = messages.first()

    call = _session.get_task("compact_turn").delay(message=message)
    return {"status": "ok", "message": "Session compacted.", "result": call}
