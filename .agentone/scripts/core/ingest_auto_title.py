"""Apply the title produced by an auto-title fork to the parent session.

Runs as a bound task in the parent session.  The ``title_result`` argument is
an auto-awaited child call, so by the time this executes the fork has finished
and its ``final_result`` can be extracted with the shared helper.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from django.conf import settings

from runtime.final_result import extract_final_result_text
from runtime.session.session import Session
from server.models.sessions.session import SessionModel
from server.models.sessions.session_version import SessionVersionModel

log = logging.getLogger(__name__)

NON_TOPIC = {
    "hi", "hello", "hey", "test", "thanks", "thank you", "ok", "okay",
    "yes", "no", "continue", "help", "ping", "start",
}


def sanitize_title(value: Any) -> str:
    """Turn raw model output into a single short, safe display title."""
    text = str(value or "")
    line = next((line.strip() for line in text.splitlines() if line.strip()), "")
    line = re.sub(r"^\s*(?:chat\s+)?title\s*:\s*", "", line, flags=re.IGNORECASE)
    line = re.sub(r"^[\s#>*_`\"'“”‘’]+", "", line)
    line = re.sub(r"[\s*_`\"'“”‘’]+$", "", line)
    line = re.sub(r"\s+", " ", line).strip().rstrip(".,;:!?-–—")
    max_chars = int(getattr(settings, "AGENTONE_AUTO_TITLE_MAX_CHARS", 60))
    return line[:max_chars].rstrip()


def _unique_title(title: str, session_pk: int) -> str:
    """Mirror new_chat's global name check; append a suffix on collision."""
    candidate = title
    index = 2
    max_chars = int(getattr(settings, "AGENTONE_AUTO_TITLE_MAX_CHARS", 60))
    while SessionModel.objects.filter(name=candidate).exclude(pk=session_pk).exists():
        suffix = f" {index}"
        candidate = f"{title[:max_chars - len(suffix)]}{suffix}"
        index += 1
    return candidate


def ingest_auto_title(
    _session: Session,
    anchor_message: Any = None,
    title_result: Any = None,
    expected_name: str = "",
    child_session_pk: Any = None,
    **kwargs: Any,
) -> SessionModel | None:
    """Write the generated title, unless the user renamed the session meanwhile."""
    if not getattr(settings, "AGENTONE_AUTO_TITLE_ENABLED", True):
        return None

    title = sanitize_title(extract_final_result_text(title_result))
    if len(title) < 2 or title.lower() in NON_TOPIC:
        return None

    session_pk = _session.model.pk
    current = SessionModel.objects.filter(pk=session_pk).first()
    if current is None or not current.name_is_auto:
        return None

    # Atomic guard: a manual rename between enqueue and ingest wins.
    expect: dict[str, Any] = {"name_is_auto": True}
    if expected_name:
        expect["name"] = expected_name
    updated = SessionModel.atomic_update_by_pk(
        session_pk,
        action="update",
        expect=expect,
        name=_unique_title(title, session_pk),
    )
    if not updated:
        return None

    # display_name is best-effort: SessionVersionModel.save() rejects updates
    # to existing rows, so use a queryset update instead.
    version_pk = current.latest_session_version_id
    if version_pk:
        SessionVersionModel.objects.filter(pk=version_pk).update(display_name=title)

    if child_session_pk:
        try:
            child_model = SessionModel.objects.filter(pk=child_session_pk).first()
            if child_model is not None:
                Session(session_model=child_model).request_end(reason="auto_title_done")
        except Exception:  # pylint: disable=broad-exception-caught
            log.exception("failed to close auto-title fork %s", child_session_pk)

    return SessionModel.objects.filter(pk=session_pk).first()
