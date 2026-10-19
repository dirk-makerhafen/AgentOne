"""One-time session bootstrap — stable replacement for per-turn prefix injection.

Previously ``build_llm_context`` re-injected the guidance-file autoload, the
guidance index and the session-private-folder announcement as fresh
``QueryMessage`` rows on *every* turn, ahead of the conversation history.  Any
change to those bytes (guidance repin after a compaction or workspace switch,
a per-turn timestamp, ...) invalidated the whole prompt-cache (KV-cache)
prefix, forcing a full recompute.

Instead :func:`ensure_session_bootstrap` persists the same content **once**
as normal session-history ``Message`` rows (``pin_to_context=True``) at the
start of the current compaction segment:

* first turn — a USER guidance message (autoload + index) and a 
  environment message (start time, workspace path, private folder) are
  inserted ahead of the oldest message, so the normal history walk picks
  them up on every later turn;
* after compaction — the same content is embedded in the COMPACTION marker
  itself by ``ingest_compaction`` (see :func:`bootstrap_compaction_parts`),
  so the marker doubles as the new segment's bootstrap and no extra message
  is needed.

Later turns therefore see frozen, byte-stable prefix bytes and prompt caching
survives.  ``build_llm_context`` additionally re-includes pinned messages
that fell outside ``max_history_messages`` (honouring the documented
``pin_to_context`` "Always include" semantics), so guidance is never silently
dropped from the context the way a pure history walk would once the window
slides past it.
"""

from __future__ import annotations

import logging
import traceback
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)

# Sentinel first-lines identifying bootstrap messages.  Detection is by
# sentinel (not content matching) so rewording the body never breaks the
# idempotency check — only these headers are load-bearing.
USER_BOOTSTRAP_SENTINEL = "[Session bootstrap — auto-loaded workspace guidance."
ENV_BOOTSTRAP_SENTINEL = "[Session bootstrap — environment context."
COMPACTION_BOOTSTRAP_SENTINEL = "[Session bootstrap — repinned after compaction."

# Own workspace tracker (per session pk): the workspace path the current
# segment was bootstrapped for.  A mismatch means the workspace switched
# mid-segment and the frozen bootstrap is stale for the path.
_CACHE_BOOTSTRAP_WORKSPACE = "bootstrap:workspace:{pk}"


def _cache() -> Any:
    from django.core.cache import cache

    return cache


def build_bootstrap_contents(session: Any) -> tuple[str | None, str | None, str]:
    """Resolve the frozen bootstrap texts for *session*.

    Returns ``(autoload_text, index_text, env_text)``.  Guidance texts come
    from the pinned cache (resolved fresh on first call); the environment
    text carries a frozen start timestamp, the workspace path and the private
    folder announcement.  Never raises — guidance failures yield ``None``
    entries (logged to ``DebugLogEntry`` by the caller convention).
    """
    autoload_text: str | None = None
    index_text: str | None = None
    try:
        from runtime import guidance_files as _guidance

        autoload_text, index_text = _guidance.ensure_pinned(session)
    except Exception:  # pylint: disable=broad-exception-caught
        logger.warning("bootstrap: guidance resolve failed, skipping", exc_info=True)

    env_text = _build_env_text(session)
    return autoload_text, index_text, env_text


def _build_env_text(session: Any) -> str:
    """Build the environment text (time + workspace + private dir)."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    try:
        working_dir = session.workspace.path if session.workspace else "unknown"
    except Exception:  # pylint: disable=broad-exception-caught
        working_dir = "unknown"
    try:
        from runtime.session_folder import ensure_session_dir

        private_dir = ensure_session_dir(session).as_posix()
    except Exception:  # pylint: disable=broad-exception-caught
        logger.warning("bootstrap: private dir unavailable", exc_info=True)
        private_dir = "(unavailable)"
    return (
        f"<SYSTEM NOTICE>{ENV_BOOTSTRAP_SENTINEL} Session started at {now}; "
        "this header and the paths below are frozen for cache stability — "
        "ask for the current time if you need it.]"
        f"\nYour working directory is '{working_dir}'."
        f"\nYour private session folder is {private_dir}. "
        "Use the normal filesystem tools for scratch files, temporary "
        "memory, intermediate results, generated "
        "scripts and other session-specific artifacts. Reusable "
        "helpers belong in the database (adhoc_* tools, template_* "
        "tools), not as files here. It is private "
        "to this session — other sessions cannot access it.</SYSTEM NOTICE>"
    )


def _workspace_root_posix(session: Any) -> str | None:
    try:
        from runtime.guidance_files import workspace_root

        root = workspace_root(session)
        return root.as_posix() if root is not None else None
    except Exception:  # pylint: disable=broad-exception-caught
        return None


def bootstrap_compaction_parts(
    session: Any,
) -> tuple[str | None, str | None, str]:
    """Fresh bootstrap texts for embedding in a new COMPACTION marker.

    Clears the pinned guidance cache first so the marker embeds a live
    re-resolve (repin on compaction), then returns
    ``(autoload_text, index_text, env_text)``.  The caller
    (``ingest_compaction._build_compaction_message``) stores them as
    COMPACTION parts headed by ``COMPACTION_BOOTSTRAP_SENTINEL``, which
    :func:`ensure_session_bootstrap` recognises so it does not duplicate
    them with standalone messages.
    """
    try:
        from runtime import guidance_files as _guidance

        _guidance.clear_guidance_cache(session.model.pk)
    except Exception:  # pylint: disable=broad-exception-caught
        logger.warning("bootstrap: guidance cache clear failed", exc_info=True)
    autoload_text, index_text, env_text = build_bootstrap_contents(session)
    try:
        root_posix = _workspace_root_posix(session)
        if root_posix is not None:
            _cache().set(_CACHE_BOOTSTRAP_WORKSPACE.format(pk=session.model.pk), root_posix)
    except Exception:  # pylint: disable=broad-exception-caught
        logger.warning("bootstrap: workspace cache store failed", exc_info=True)
    return autoload_text, index_text, env_text


def _is_bootstrap_message(message: Any) -> bool:
    """True if *message* is a standalone bootstrap message (sentinel check)."""
    try:
        first = message.parts.order_by("pk").first()
        if first is None or first.content is None:
            return False
        text = str(first.content.get() or "")
        return text.startswith((USER_BOOTSTRAP_SENTINEL, ENV_BOOTSTRAP_SENTINEL, "<SYSTEM NOTICE>"+USER_BOOTSTRAP_SENTINEL,"<SYSTEM NOTICE>"+ENV_BOOTSTRAP_SENTINEL))
    except Exception:  # pylint: disable=broad-exception-caught
        return False


def _marker_has_bootstrap(marker: Any) -> bool:
    """True if a COMPACTION marker already embeds repinned bootstrap content."""
    try:
        from server.models.enums.message_enums import MessagePartType

        for part in marker.parts.filter(type=MessagePartType.COMPACTION).order_by("pk"):
            if part.content and COMPACTION_BOOTSTRAP_SENTINEL in str(part.content.get() or ""):
                return True
        return False
    except Exception:  # pylint: disable=broad-exception-caught
        return False


def ensure_session_bootstrap(session: Any, trigger: Any) -> list[Any]:
    """Idempotently persist the one-time bootstrap messages for *session*.

    Scans the current compaction segment (same-session ancestry of *trigger*,
    stopping at the first COMPACTION marker).  If neither a standalone
    bootstrap message nor a bootstrap-carrying marker is found, inserts the
    USER guidance message (when guidance texts exist) and the 
    environment message at the start of the segment and returns them.
    Returns the existing bootstrap messages when already bootstrapped, or
    ``[]`` when there is nothing to do.

    Also appends a short workspace-switch notice at the tail when the
    workspace changed since the segment was bootstrapped (suffix position, so
    the cached prefix is untouched).  Never raises.
    """
    try:
        return _ensure_session_bootstrap(session, trigger)
    except Exception:  # pylint: disable=broad-exception-caught
        logger.warning("bootstrap: ensure failed, skipping", exc_info=True)
        try:
            from server.models.debug_log_entry import DebugLogEntry

            DebugLogEntry.objects.create(
                session=session.model,
                event="bootstrap_skip",
                data={"exception": traceback.format_exc()},
            )
        except Exception:  # pylint: disable=broad-exception-caught
            pass
        return []


def _ensure_session_bootstrap(session: Any, trigger: Any) -> list[Any]:
    from server.models.enums.message_enums import MessageContentType, MessagePartType, MessageRole, MessageType
    from server.models.message import Message

    session_pk = session.model.pk
    if trigger is None:
        trigger = session.get_last_message()
    if trigger is None:
        return []

    # Walk the same-session ancestry newest-first, stopping at the first
    # COMPACTION marker (exclusive scan: the marker itself is examined
    # separately).  Cross-session links (fork anchors) end the segment.
    found: list[Any] = []
    marker: Any = None
    segment_oldest: Any = None
    current = trigger
    while current is not None:
        if getattr(current, "session_id", None) != session_pk:
            break
        if current.message_type == MessageType.COMPACTION:
            marker = current
            break
        segment_oldest = current
        if _is_bootstrap_message(current):
            found.append(current)
        current = current.prev_message

    if found:
        maybe_announce_workspace_switch(session)
        return found
    if marker is not None and _marker_has_bootstrap(marker):
        _remember_workspace(session)
        maybe_announce_workspace_switch(session)
        return []

    autoload_text, index_text, env_text = build_bootstrap_contents(session)

    sv = session.get_version_model()
    created: list[Any] = []

    if segment_oldest is None:
        # Trigger IS the marker (or an empty walk): anchor behind the marker.
        insert_before: Any = None
        anchor_prev: Any = marker
    else:
        insert_before = segment_oldest
        anchor_prev = segment_oldest.prev_message

    def _create(role: str, parts: list[str]) -> Any:
        message = Message.objects.create(
            session=sv.session,
            session_version=sv,
            role=role,
            message_type=MessageType.BOOTSTRAP,
            prev_message=anchor_prev if not created else created[-1],
        )
        for text in parts:
            message.add_part(
                type=MessagePartType.MESSAGE,
                content_type=MessageContentType.TEXT,
                content=text,
            )
        # Two-phase write (see Message.save): publish only now parts exist.
        message.publish("create")
        created.append(message)
        return message

    guidance_parts: list[str] = [
        USER_BOOTSTRAP_SENTINEL
        + " Frozen at session start for cache stability — re-read files "
        "directly if you suspect staleness.]"
    ]
    if autoload_text:
        guidance_parts.append(autoload_text)
    if index_text:
        guidance_parts.append(index_text)
    _create(MessageRole.USER, [env_text])
    if autoload_text or index_text:
        _create(MessageRole.USER, guidance_parts)

    # Splice the new head into the chain: the first created message takes
    # the anchor position, the last one feeds the previous successor.
    first, last = created[0], created[-1]
    if insert_before is not None:
        first.prev_message = anchor_prev
        first.save()
        insert_before.prev_message = last
        insert_before.save()

    _remember_workspace(session)
    return created


def _remember_workspace(session: Any) -> None:
    """Record the current workspace path for switch detection."""
    try:
        root_posix = _workspace_root_posix(session)
        if root_posix is not None:
            _cache().set(_CACHE_BOOTSTRAP_WORKSPACE.format(pk=session.model.pk), root_posix)
    except Exception:  # pylint: disable=broad-exception-caught
        logger.warning("bootstrap: workspace cache store failed", exc_info=True)


def maybe_announce_workspace_switch(session: Any) -> Any | None:
    """Append a short tail notice when the workspace switched mid-segment.

    The frozen bootstrap keeps the old path (prefix untouched, cache hot);
    the notice corrects it from the suffix position.  Returns the notice
    message, or ``None`` when nothing changed.  Never raises.
    """
    try:
        from server.models.enums.message_enums import (
            MessageContentType,
            MessagePartType,
            MessageRole,
            MessageType,
        )
        from server.models.message import Message

        root_posix = _workspace_root_posix(session)
        if root_posix is None:
            return None
        key = _CACHE_BOOTSTRAP_WORKSPACE.format(pk=session.model.pk)
        remembered = _cache().get(key)
        if remembered is None:
            _cache().set(key, root_posix)
            return None
        if remembered == root_posix:
            return None
        sv = session.get_version_model()
        notice = Message.objects.create(
            session=sv.session,
            session_version=sv,
            role=MessageRole.USER,
            message_type=MessageType.SYSTEM_NOTICE,
            prev_message=session.get_last_message(),
        )
        notice.add_part(
            type=MessagePartType.MESSAGE,
            content_type=MessageContentType.TEXT,
            content=(
                f"<SYSTEM NOTICE>Workspace switched mid-session: '{remembered}' → "
                f"'{root_posix}'. The bootstrap message above still shows "
                "the old path — use the new path going forward and re-read "
                "any workspace guidance files relevant to your task.</SYSTEM NOTICE>"
            ),
        )
        notice.publish("create")
        _cache().set(key, root_posix)
        return notice
    except Exception:  # pylint: disable=broad-exception-caught
        logger.warning("bootstrap: workspace-switch notice failed", exc_info=True)
        return None
