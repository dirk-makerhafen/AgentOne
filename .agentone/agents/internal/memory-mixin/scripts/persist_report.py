"""Persist a reflection/compaction report into the memory tree immediately.

Runs as a detached ``after:`` hook on ``ingest_reflection_result`` and
``ingest_compaction``. The intercepted call's result is captured and written
to the session's canonical ``reflections.md`` / ``compaction.md`` file under
the memory tree, mirroring what ``memory_walk(refresh=True)`` does later.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from runtime.paths import agentone_home, ensure_private_dir
from runtime.session.session import Session
from runtime.session_folder import _agentone_dir, _project_of, _safe_segment, _workspace_of


def _resolve_message(result: Any, kwargs: dict[str, Any]) -> Any:
    """Extract the report message from a hook invocation."""
    msg = result
    if msg is None:
        msg = kwargs.get("result")
    if msg is None:
        msg = kwargs.get("message")
    if msg is None:
        msg = kwargs.get("compaction_result")
    # Unwrap dict refs / result dicts.
    if isinstance(msg, dict):
        if "_type" in msg and "pk" in msg:
            try:
                from django.apps import apps

                model = apps.get_model("server", msg["_type"])
                msg = model.objects.get(pk=msg["pk"])
            except Exception:  # pylint: disable=broad-exception-caught
                return None
        else:
            for key in ("message", "compaction_message", "marker", "reflection_message"):
                if msg.get(key) is not None:
                    msg = msg.get(key)
                    break
            if isinstance(msg, dict) and "_type" in msg and "pk" in msg:
                try:
                    from django.apps import apps

                    model = apps.get_model("server", msg["_type"])
                    msg = model.objects.get(pk=msg["pk"])
                except Exception:  # pylint: disable=broad-exception-caught
                    return None
    # Resolve pk-style ints via Message lookup.
    if isinstance(msg, int):
        try:
            from server.models.message import Message

            msg = Message.objects.filter(pk=msg).first()
        except Exception:  # pylint: disable=broad-exception-caught
            return None
    # Resolve task-call references (e.g. retry wrappers) to their result.
    try:
        from server.models.tasks.agent_task_call import AgentTaskCall

        if isinstance(msg, AgentTaskCall):
            try:
                resolved = msg.get_result(timeout=10, recursive=True, allow_partial_results=True)
            except Exception:  # pylint: disable=broad-exception-caught
                resolved = None
            if resolved is not None and resolved is not msg:
                msg = resolved
                if isinstance(msg, dict):
                    return _resolve_message(msg, {})
    except Exception:  # pylint: disable=broad-exception-caught
        pass
    return msg


def _extract_report_text(message: Any) -> str:
    """Mirror of memory_walk._extract_report_text (kept local for isolation)."""
    try:
        from server.models.enums.message_enums import MessageContentType
    except Exception:  # pylint: disable=broad-exception-caught
        return ""

    parts = getattr(message, "report_parts", None)
    if parts is None:
        manager = getattr(message, "parts", None)
        if manager is None:
            return ""
        try:
            parts = list(manager.order_by("pk"))
        except Exception:  # pylint: disable=broad-exception-caught
            return ""

    sentinel = ""
    try:
        from runtime.session_bootstrap import COMPACTION_BOOTSTRAP_SENTINEL

        sentinel = COMPACTION_BOOTSTRAP_SENTINEL
    except Exception:  # pylint: disable=broad-exception-caught
        pass

    texts: list[str] = []
    try:
        for part in parts:
            part_type = str(getattr(part, "type", "") or "").upper()
            if part_type not in ("MESSAGE", "COMPACTION"):
                continue
            if getattr(part, "content_type", None) != MessageContentType.TEXT:
                continue
            content = part.content.get() if getattr(part, "content", None) else None
            if not content:
                continue
            text = str(content)
            if sentinel and sentinel in text:
                break
            texts.append(text)
    except Exception:  # pylint: disable=broad-exception-caught
        pass
    return "\n".join(texts) if texts else ""


def _report_dir(session_model: Any, version: Any) -> Path | None:
    """Mirror of memory_walk._report_dir."""
    try:
        from runtime.paths import ensure_private_dir as _epd

        ws = getattr(version, "workspace", None)
        if callable(ws):
            try:
                ws = ws()
            except Exception:  # pylint: disable=broad-exception-caught
                ws = None
        proj = getattr(session_model, "parent_project", None)
        if ws is None and proj is None:
            base = agentone_home()
        else:
            base = _agentone_dir(ws, proj)
        root = base / "memory"
        agent_pk = getattr(version, "agent_id", None)
        if agent_pk is None:
            return None
        agent_dir = root / "agents" / f"{agent_pk}"
        group_key = (getattr(session_model, "group_key", "") or "").strip() or "default"
        task_dir = agent_dir / "tasks" / f"task_{_safe_segment(group_key)}"
        return task_dir
    except Exception:  # pylint: disable=broad-exception-caught
        return None


def _is_reflection(message: Any) -> bool:
    try:
        from server.models.enums.message_enums import MessageType

        return getattr(message, "message_type", None) == MessageType.REFLECTION
    except Exception:  # pylint: disable=broad-exception-caught
        return False


def persist_memory_report(
    _session: Session,
    result: Any = None,
    **kwargs: Any,
) -> Any:
    """Capture the report and write it to the correct memory folder."""
    try:
        from server.models.enums.message_enums import MessageType
    except Exception:  # pylint: disable=broad-exception-caught
        return None

    msg = _resolve_message(result, kwargs)
    if msg is None:
        return None

    text = _extract_report_text(msg)
    if not text.strip():
        return None

    try:
        db_session = getattr(_session, "model", None)
        if db_session is None:
            return None
        version = getattr(msg, "session_version", None)
        if version is None:
            try:
                version = _session.get_version_model()
            except Exception:  # pylint: disable=broad-exception-caught
                version = None
        if version is None:
            return None

        task_dir = _report_dir(db_session, version)
        if task_dir is None:
            return None

        session_pk = getattr(db_session, "pk", None)
        if session_pk is None:
            session_pk = getattr(_session, "pk", None)
        if session_pk is None:
            return None

        # session memory dir
        session_dir = task_dir / "sessions" / f"{session_pk}"
        ensure_private_dir(session_dir, 0o700)

        if _is_reflection(msg):
            filename = "reflections.md"
        else:
            filename = "compaction.md"

        target = session_dir / filename
        try:
            existing = target.read_text(encoding="utf-8") if target.exists() else ""
        except OSError:
            existing = ""
        if existing != text:
            target.write_text(text, encoding="utf-8")

        # Clean legacy timestamped reports (best-effort).
        import re as _re

        legacy_re = _re.compile(r"^(?:compaction|reflections)_\d{8}-\d{6}(?:_\d+)?\.md$")
        try:
            for legacy in session_dir.glob("*.md"):
                if legacy_re.fullmatch(legacy.name):
                    try:
                        legacy.unlink()
                    except OSError:
                        pass
        except OSError:
            pass

        return msg
    except Exception:  # pylint: disable=broad-exception-caught
        return None