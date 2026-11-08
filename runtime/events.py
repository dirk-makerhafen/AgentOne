"""
Real-time event publishing for the UI reactive layer.

Producers call :func:`publish_model_event` after an ORM write; delivery to
subscribed browser views goes through the Redis observable registry
(``runtime/observables.py``), drained per UI instance by the consumer loop
in ``ui/consumer.py``.

Usage (preferred — models auto-publish, no import needed)
----------------------------------------------------------
    msg = Message.objects.create(...)   # "create" published from save()
    msg.atomic_update(status="...")     # atomic UPDATE + "update" on success
    msg.publish("update")               # manual publish (bulk ops, FSMs)
    msg.delete()                        # "delete" published from delete()

Direct calls (bulk paths that bypass the model — ``QuerySet.update()``,
``bulk_create()``, cascade helpers) still use this function:

    from runtime.events import publish_model_event
    msg = Message.objects.create(...)   # already auto-published; do NOT repeat
    publish_model_event(msg, "create")  # only when save()/delete() was bypassed
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
import logging
from typing import Any

log = logging.getLogger(__name__)


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


def publish_model_event(instance: Any, action: str, data: dict[str, Any] | None = None) -> None:
    """Publish an ORM model event.

    Args:
        instance: The Django model instance that was just written.
        action:   ``"create"``, ``"update"``, or ``"delete"``.
        data:     Optional payload forwarded to observers.

    Delivers to subscribed UI instances through the Redis observable
    registry (see ``runtime/observables.py``).  The old channel-layer
    broadcast is gone: all views subscribe to observable keys, so a
    fan-out to every connected consumer would only waste Redis round
    trips.  Instances without ``notify_observers`` (non-BaseModel
    mixins) are silently skipped.
    """
    event_instance = instance
    event_data = {**_extract_filter_context(event_instance), **(data or {})}
    serialize: Callable[[], dict[str, Any]] | None = getattr(
        event_instance, "serialize_observable", None
    )
    observable_keys: Callable[[], Sequence[str]] | None = getattr(
        event_instance, "observable_keys", None
    )
    if callable(serialize) and callable(observable_keys):
        def serialize_event() -> dict[str, Any]:
            current_instance = event_instance
            if action != "delete" and getattr(current_instance, "pk", None) is not None:
                refreshed = type(current_instance)._default_manager.filter(
                    pk=current_instance.pk
                ).first()
                if refreshed is not None:
                    current_instance = refreshed
            return {
                **_extract_filter_context(current_instance),
                **(data or {}),
                "object": current_instance.serialize_observable(),
            }

    notify = getattr(event_instance, "notify_observers", None)
    if callable(notify):
        try:
            if callable(serialize) and callable(observable_keys):
                notify(action, event_data, data_factory=serialize_event)
            else:
                notify(action, event_data)
        except Exception:
            log.exception(
                "Failed to publish observable event for %s pk=%s",
                type(event_instance).__name__,
                getattr(event_instance, "pk", None),
            )
