"""One-time session bootstrap, frozen per compaction segment.

Agent ``sessionBootstrap`` templates and workspace guidance are persisted once
as pinned history messages.  This keeps the prompt-cache prefix byte-stable
between compactions; after a compaction the marker carries a freshly rendered
copy.
"""
from __future__ import annotations

import logging
import time
import traceback
from datetime import datetime
from typing import Any

from jinja2 import BaseLoader, Environment, StrictUndefined

logger = logging.getLogger(__name__)

COMPACTION_BOOTSTRAP_SENTINEL = "[Session bootstrap — repinned after compaction."
_CACHE_BOOTSTRAP_WORKSPACE = "bootstrap:workspace:{pk}"

_JINJA = Environment(
    loader=BaseLoader(),
    undefined=StrictUndefined,
    finalize=lambda value: "null" if value is None else value,
)


def _cache() -> Any:
    from django.core.cache import cache

    return cache


def bootstrap_context(session: Any) -> dict[str, Any]:
    """Return the variables available to ``sessionBootstrap`` templates."""
    now = datetime.now()
    workspace = session.workspace
    project = session.get_project()
    workspace_dir = (getattr(workspace, "path", "") or None) if workspace else None
    project_dir = (getattr(project, "path", "") or None) if project else None

    workspace_agentone_dir = None
    if workspace is not None:
        try:
            workspace_agentone_dir = workspace.get_agentone_dir().as_posix()
        except Exception:  # pylint: disable=broad-exception-caught
            logger.warning("bootstrap: workspace dir unavailable", exc_info=True)

    project_agentone_dir = None
    if project is not None:
        try:
            project_agentone_dir = project.get_agentone_dir().as_posix()
        except Exception:  # pylint: disable=broad-exception-caught
            logger.warning("bootstrap: project dir unavailable", exc_info=True)

    try:
        from runtime.session_folder import ensure_session_dir

        session_dir = ensure_session_dir(session).as_posix()
    except Exception:  # pylint: disable=broad-exception-caught
        logger.warning("bootstrap: session dir unavailable", exc_info=True)
        session_dir = None

    return {
        "workspace_dir": workspace_dir,
        "workspace_agentone_dir": workspace_agentone_dir,
        "project_dir": project_dir,
        "project_agentone_dir": project_agentone_dir,
        "session_dir": session_dir,
        "unix_timestamp": int(time.time()),
        "date": now.strftime("%Y-%m-%d"),
        "datetime": now.strftime("%Y-%m-%d %H:%M:%S"),
    }


def build_bootstrap_messages(session: Any) -> list[tuple[str, str]]:
    """Return ``(role, text)`` bootstrap messages for this session.

    Agent templates come first, parent before child, followed by the workspace
    guidance message.  Empty or failed templates are skipped.
    """
    from server.models.enums.message_enums import MessageRole

    context = bootstrap_context(session)
    messages: list[tuple[str, str]] = []
    for template in session.session_bootstrap_chain:
        try:
            text = _JINJA.from_string(template).render(**context).strip()
        except Exception:  # pylint: disable=broad-exception-caught
            logger.warning("bootstrap: template render failed", exc_info=True)
            continue
        if text:
            messages.append((MessageRole.USER, text))

    try:
        from runtime import guidance_files

        autoload, index = guidance_files.ensure_pinned(session)
    except Exception:  # pylint: disable=broad-exception-caught
        logger.warning("bootstrap: guidance resolve failed, skipping", exc_info=True)
        autoload, index = None, None
    guidance = "\n\n".join(part for part in (autoload, index) if part)
    if guidance:
        messages.append((MessageRole.USER, guidance))
    return messages


def bootstrap_compaction_parts(session: Any) -> list[str]:
    """Return fresh bootstrap texts for embedding in a new COMPACTION marker."""
    try:
        from runtime import guidance_files

        guidance_files.clear_guidance_cache(session.model.pk)
    except Exception:  # pylint: disable=broad-exception-caught
        logger.warning("bootstrap: guidance cache clear failed", exc_info=True)
    messages = build_bootstrap_messages(session)
    _remember_workspace(session)
    return [text for _, text in messages]


def _marker_has_bootstrap(marker: Any) -> bool:
    """True if a COMPACTION marker already embeds bootstrap content."""
    try:
        from server.models.enums.message_enums import MessagePartType

        return any(
            part.content
            and COMPACTION_BOOTSTRAP_SENTINEL in str(part.content.get() or "")
            for part in marker.parts.filter(type=MessagePartType.COMPACTION)
        )
    except Exception:  # pylint: disable=broad-exception-caught
        return False


def ensure_session_bootstrap(session: Any, trigger: Any) -> list[Any]:
    from server.models.enums.message_enums import (
        MessageContentType,
        MessagePartType,
        MessageType,
    )
    from server.models.message import Message

    session_pk = session.model.pk
    trigger = trigger or session.get_last_message()
    if trigger is None:
        return []

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
        if current.message_type == MessageType.BOOTSTRAP:
            found.append(current)
        current = current.prev_message

    if found:
        maybe_announce_workspace_switch(session)
        return found
    if marker is not None and _marker_has_bootstrap(marker):
        _remember_workspace(session)
        maybe_announce_workspace_switch(session)
        return []

    contents = build_bootstrap_messages(session)
    if not contents:
        return []

    sv = session.get_version_model()
    created: list[Any] = []
    if segment_oldest is None:
        insert_before: Any = None
        anchor_prev: Any = marker
    else:
        insert_before = segment_oldest
        anchor_prev = segment_oldest.prev_message

    for role, text in contents:
        message = Message.objects.create(
            session=sv.session,
            session_version=sv,
            role=role,
            message_type=MessageType.BOOTSTRAP,
            pin_to_context=True,
            prev_message=anchor_prev if not created else created[-1],
        )
        message.add_part(
            type=MessagePartType.MESSAGE,
            content_type=MessageContentType.TEXT,
            content=text,
        )
        message.publish("create")
        created.append(message)

    first, last = created[0], created[-1]
    if insert_before is not None:
        first.prev_message = anchor_prev
        first.save()
        insert_before.prev_message = last
        insert_before.save()

    _remember_workspace(session)
    return created


def _workspace_root_posix(session: Any) -> str | None:
    try:
        from runtime.guidance_files import workspace_root

        root = workspace_root(session)
        return root.as_posix() if root is not None else None
    except Exception:  # pylint: disable=broad-exception-caught
        return None


def _remember_workspace(session: Any) -> None:
    """Record the current workspace path for switch detection."""
    try:
        root_posix = _workspace_root_posix(session)
        if root_posix is not None:
            _cache().set(
                _CACHE_BOOTSTRAP_WORKSPACE.format(pk=session.model.pk), root_posix
            )
    except Exception:  # pylint: disable=broad-exception-caught
        logger.warning("bootstrap: workspace cache store failed", exc_info=True)


def maybe_announce_workspace_switch(session: Any) -> Any | None:
    """Append a short tail notice when the workspace switched mid-segment."""
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
                "any workspace guidance files relevant to your task."
                "</SYSTEM NOTICE>"
            ),
        )
        notice.publish("create")
        _cache().set(key, root_posix)
        return notice
    except Exception:  # pylint: disable=broad-exception-caught
        logger.warning("bootstrap: workspace-switch notice failed", exc_info=True)
        return None
