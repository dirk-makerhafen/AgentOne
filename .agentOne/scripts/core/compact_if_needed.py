from __future__ import annotations

from typing import Any

from runtime.session.session import Session
from server.models.message import Message
from server.history_limiter import (
    HistoryLimiter,
    find_compaction_boundary,
)


def compact_if_needed(session: Session, message: Message) -> Message | dict[str, Any]:
    boundary_pk = find_compaction_boundary(session, message.pk)
    messages = list(Message.objects.filter(
        session_version__session=session.model,
        pk__gte=boundary_pk,
        pk__lte=message.pk,
    ).order_by("-created_at"))

    if len(messages) < 3:
        return message

    total_tokens = HistoryLimiter.estimate_total_tokens(messages)
    auto_limit = session.auto_compact_limit
    if auto_limit > 0 and total_tokens < auto_limit:
        return message

    compact_call = session.get_task("compact_turn").delay(message=message)
    return {"message": message, "compact_call": compact_call}
