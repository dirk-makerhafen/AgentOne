"""
Real-time event publishing for the UI reactive layer.

Celery workers and state machines publish events via Django's channel layer.
The WebSocket consumer subscribes and dispatches them to the in-process UiApp.

Event types
───────────
- ``model_event``      ORM model created/updated/deleted (primary mechanism)
- ``taskcall.status``  AgentTaskCall status_detail transition (legacy, phased out)
- ``taskrun.status``   AgentTaskRun status transition (legacy, phased out)
- ``message.created``  New Message in a session (legacy, phased out)

Usage (Celery worker)
--------------------
    from runtime.events import publish_model_event
    msg = Message.objects.create(...)
    publish_model_event(msg, "create")
"""

from __future__ import annotations

from typing import Any

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

CHANNEL_GROUP = "agentone_live"


def publish(session_id: int | None, event_type: str, payload: dict[str, Any]) -> None:
    """Publish an event to the live channel group."""
    channel_layer = get_channel_layer()
    if channel_layer is None:
        return
    async_to_sync(channel_layer.group_send)(
        CHANNEL_GROUP,
        {
            "type": "session_event",
            "session_id": session_id,
            "event_type": event_type,
            "payload": payload,
        },
    )


def _extract_filter_context(instance: Any) -> dict[str, Any]:
    """Extract FK fields + resolved session_id from a model instance."""
    from django.db.models import ForeignKey, OneToOneField

    ctx: dict[str, Any] = {}
    for field in instance._meta.fields:
        if isinstance(field, (ForeignKey, OneToOneField)):
            ctx[field.attname] = getattr(instance, field.attname)
    if "session_id" not in ctx and hasattr(instance, "session_version"):
        try:
            if instance.session_version_id:
                ctx["session_id"] = instance.session_version.session_id
        except Exception:
            pass
    return ctx


_LOG_FILE = "/tmp/agentone_events.log"
def _log(msg: str) -> None:
    import os, time
    try:
        with open(_LOG_FILE, "a") as f:
            f.write(f"[{time.strftime('%H:%M:%S')}] {msg}\n")
    except Exception:
        pass

def publish_model_event(instance: Any, action: str) -> None:
    """Publish an ORM model event.

    Args:
        instance: The Django model instance that was just written.
        action:   ``"create"``, ``"update"``, or ``"delete"``.
    """
    filter_context = _extract_filter_context(instance)
    session_id = filter_context.get("session_id")
    mn = instance._meta.model_name
    _log(f"PUBLISH_MODEL_EVENT: model={mn} action={action} pk={instance.pk} sid={session_id}")
    publish(
        session_id,
        "model_event",
        {
            "model_name": mn,
            "app_label": instance._meta.app_label,
            "pk": instance.pk,
            "action": action,
            "filter_context": filter_context,
        },
    )
