"""Server-Sent Events bridge between the Redis observable registry and htmx.

The stream carries *event names*, not rendered HTML.  A channel suffix is
literally the observable key (``Message.session:7``), so a fragment can say
``hx-trigger="sse:Message.session:7"`` and refetch itself.  Because every
event is a hint rather than a payload, a dropped event can never leave the
page permanently stale -- the next event (or a reload) self-heals.

The production server is daphne (ASGI), which streams an *async* iterator
natively.  ``manage.py runserver`` is WSGI, which streams a *sync* iterator
natively.  Django 6 materialises the wrong kind instead of streaming it, so
the view picks the matching generator from the request class.
"""

from __future__ import annotations

import asyncio
import logging

import redis as redis_sync
import redis.asyncio as aioredis
from django.conf import settings
from django.http import HttpResponseBadRequest, StreamingHttpResponse

from server.models.observables import PUBSUB_PREFIX

log = logging.getLogger(__name__)

#: Keep idle proxies/load balancers from closing the connection.
HEARTBEAT_SECONDS = 15.0


def _session_keys(pk: int) -> list[str]:
    """Observable keys a chat page cares about.

    ``SessionModel`` (the bare any-key) is included so the sidebar can refresh
    when *any* session changes; the rest are scoped to this conversation.
    """
    return [
        f"Message.session:{pk}",
        f"Query.session:{pk}",
        f"Response.session:{pk}",
        f"AgentTaskCall.session:{pk}",
        f"SessionModel.pk:{pk}",
        "SessionModel",
    ]


async def _resolve_scope(scope: str) -> list[str] | None:
    """Translate ``scope=session:<pk>`` / ``scope=global`` into observable keys."""
    kind, _, raw = scope.partition(":")
    if kind == "global":
        return [
            "SessionModel",
            "AgentModel",
            "Project",
            "WorkspaceModel",
            "SkillModel",
            "Cronjob",
            "DataCollection",
            "WorkItem",
        ]
    if kind != "session" or not raw.isdigit():
        return None
    pk = int(raw)

    # Async ORM keeps the event loop free while validating the session.
    from server.models.sessions.session import SessionModel

    if not await SessionModel.objects.filter(pk=pk).aexists():
        return None
    return _session_keys(pk)


def _event_name(channel: str) -> str | None:
    if not channel.startswith(PUBSUB_PREFIX):
        return None
    return channel[len(PUBSUB_PREFIX):]


def _frame(event: str, data: str) -> str:
    return f"event: {event}\ndata: {data}\n\n"


def _sync_event_stream(keys: list[str]):
    """WSGI variant: blocking redis reads, one thread per connection."""
    client = redis_sync.from_url(settings.REDIS_URL, decode_responses=True)
    pubsub = client.pubsub()
    channels = [PUBSUB_PREFIX + key for key in keys]
    pubsub.subscribe(*channels)
    try:
        yield "retry: 3000\n\n"
        yield ": connected\n\n"
        while True:
            try:
                message = pubsub.get_message(
                    ignore_subscribe_messages=True,
                    timeout=HEARTBEAT_SECONDS,
                )
            except Exception:  # pylint: disable=broad-exception-caught
                log.exception("SSE redis read failed")
                break
            if message is None:
                yield ": ping\n\n"
                continue
            event = _event_name(message.get("channel") or "")
            if event is None:
                continue
            data = message.get("data") or "{}"
            if isinstance(data, bytes):
                data = data.decode("utf-8", "replace")
            yield _frame(event, data)
    finally:
        try:
            pubsub.unsubscribe(*channels)
            pubsub.close()
        except Exception:  # pylint: disable=broad-exception-caught
            pass
        try:
            client.close()
        except Exception:  # pylint: disable=broad-exception-caught
            pass


async def _async_event_stream(keys: list[str]):
    """ASGI variant: non-blocking redis reads on the event loop."""
    client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    pubsub = client.pubsub()
    channels = [PUBSUB_PREFIX + key for key in keys]
    await pubsub.subscribe(*channels)
    try:
        yield "retry: 3000\n\n"
        yield ": connected\n\n"
        while True:
            try:
                message = await pubsub.get_message(
                    ignore_subscribe_messages=True,
                    timeout=HEARTBEAT_SECONDS,
                )
            except asyncio.CancelledError:
                raise
            except Exception:  # pylint: disable=broad-exception-caught
                log.exception("SSE redis read failed")
                break
            if message is None:
                yield ": ping\n\n"
                continue
            event = _event_name(message.get("channel") or "")
            if event is None:
                continue
            data = message.get("data") or "{}"
            if isinstance(data, bytes):
                data = data.decode("utf-8", "replace")
            yield _frame(event, data)
    finally:
        try:
            await pubsub.unsubscribe(*channels)
            await pubsub.aclose()
        except Exception:  # pylint: disable=broad-exception-caught
            pass
        try:
            await client.aclose()
        except Exception:  # pylint: disable=broad-exception-caught
            pass


def _is_wsgi(request) -> bool:
    """True when served by ``runserver``/wsgiref rather than daphne."""
    from django.core.handlers.wsgi import WSGIRequest

    return isinstance(request, WSGIRequest)


async def sse_stream(request):
    """Stream observable-key events for one scope (currently ``session:<pk>``)."""
    keys = await _resolve_scope(request.GET.get("scope", ""))
    if keys is None:
        return HttpResponseBadRequest("unknown or missing scope")

    stream = _sync_event_stream(keys) if _is_wsgi(request) else _async_event_stream(keys)
    response = StreamingHttpResponse(stream, content_type="text/event-stream")
    response["Cache-Control"] = "no-cache, no-transform"
    response["X-Accel-Buffering"] = "no"
    return response
