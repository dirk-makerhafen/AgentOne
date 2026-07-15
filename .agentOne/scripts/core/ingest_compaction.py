from __future__ import annotations

from typing import Any

from runtime.session.session import Session
from server.models.message import Message
from server.models.queries.response import Response


def ingest_compaction(
    session: Session, response: Response, parts: list[dict[str, Any]]
) -> dict[str, Any]:
    summary_text = ""
    for part in parts:
        if part["type"] == "message":
            content = part["content"]
            summary_text = str(content) if content else ""

    compaction_message = Message.objects.create(
        session_version=session.get_version_model(),
        response=response,
        role="system",
    )

    compaction_message.add_part(
        type="COMPACTION",
        content_type="text",
        content=summary_text,
    )

    return dict(
        response=response,
        parts=parts,
        message=compaction_message,
    )
