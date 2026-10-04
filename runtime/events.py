"""
Real-time event publishing for the UI reactive layer.

Producers call :func:`publish_model_event` after an ORM write; delivery to
subscribed browser views goes through the Redis observable registry
(``runtime/observables.py``), drained per UI instance by the consumer loop
in ``ui/consumer.py``.

Usage (Celery worker)
--------------------
    from runtime.events import publish_model_event
    msg = Message.objects.create(...)
    publish_model_event(msg, "create")
"""

from __future__ import annotations

from typing import Any


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

    Delivers to subscribed UI instances through the Redis observable
    registry (see ``runtime/observables.py``).  The old channel-layer
    broadcast is gone: all views subscribe to observable keys, so a
    fan-out to every connected consumer would only waste Redis round
    trips.  Instances without ``notify_observers`` (non-BaseModel
    mixins) are silently skipped.
    """
    filter_context = _extract_filter_context(instance)
    session_id = filter_context.get("session_id")
    mn = instance._meta.model_name
    _log(f"PUBLISH_MODEL_EVENT: model={mn} action={action} pk={instance.pk} sid={session_id}")
    notify = getattr(instance, "notify_observers", None)
    if callable(notify):
        try:
            notify(action)
        except Exception:
            pass
