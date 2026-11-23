from __future__ import annotations

from runtime.session.compaction_guard import current_root_id, end_compaction, set_compaction_call, stop_other_roots, try_begin_compaction
from runtime.session.session import Session
from server.models.message import Message


def compact(_session: Session, message: Message | None = None) -> dict:
    if message is None:
        messages = _session.model.messages.order_by("-created_at")
        if not messages.exists():
            return {"status": "ok", "message": "No messages to compact."}
        message = messages.first()

    root_id = current_root_id(_session)
    if not try_begin_compaction(_session, root_call_id=root_id):
        return {"status": "ok", "message": "Compaction already in progress."}
    stop_other_roots(_session, root_id)
    try:
        call = _session.get_task("compact_turn").delay(
            message=message, trigger="manual", idle_trigger=False
        )
    except Exception:
        end_compaction(_session.model.pk)
        raise
    set_compaction_call(_session, call)
    return {"status": "ok", "message": "Session compacted.", "result": call}
