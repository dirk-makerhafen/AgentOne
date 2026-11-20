"""Per-client SSE stream between the ORM event fan-out and htmx.

A tab registers the observable keys it currently renders (``POST /app/sse/watch``);
``publish_model_event`` fans out to exactly those tabs.  The stream itself
carries event *names* (the key) and a small JSON hint, never rendered HTML, so
a dropped event can only cost one refetch.

The production server is daphne (ASGI); ``manage.py runserver`` is WSGI.  Django
materialises the wrong iterator kind instead of streaming it, so the view picks
the generator that matches the request class.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re

import redis as redis_sync
import redis.asyncio as aioredis
from django.conf import settings
from django.http import HttpResponseBadRequest, JsonResponse, StreamingHttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from server.models.observables import (
    CLIENT_PREFIX,
    mark_seen,
    register_client,
    reset_client,
    touch_client,
)

log = logging.getLogger(__name__)

HEARTBEAT_SECONDS = 15.0
CLIENT_RE = re.compile(r"^[A-Za-z0-9_-]{8,64}$")
# A chat page can legitimately render hundreds of keys (80 sidebar session
# rows plus a 120-message thread already exceeds 500).  Reject only clearly
# abusive payloads; a rejection here leaves the tab subscribed to its *old*
# view, because heartbeats keep that registration's TTL alive.
MAX_WATCH_KEYS = 5000


def _frame(event: str, data: str) -> str:
    return f"event: {event}\ndata: {data}\n\n"


def _event_name(payload: str) -> tuple[str, str] | None:
    try:
        body = json.loads(payload)
    except ValueError:
        return None
    key = body.get("key")
    if not key or not isinstance(key, str):
        return None
    return key, payload


def _sync_event_stream(client_id: str):
    """WSGI variant: blocking redis reads, one thread per connection."""
    client = redis_sync.from_url(settings.REDIS_URL, decode_responses=True)
    pubsub = client.pubsub()
    channel = CLIENT_PREFIX + client_id
    pubsub.subscribe(channel)
    try:
        yield "retry: 3000\n\n"
        yield ": connected\n\n"
        if mark_seen(client_id):
            yield _frame("reset", "{}")
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
                touch_client(client_id)
                yield ": ping\n\n"
                continue
            parsed = _event_name(message.get("data") or "")
            if parsed is None:
                continue
            event, data = parsed
            yield _frame(event, data)
    finally:
        try:
            pubsub.unsubscribe(channel)
            pubsub.close()
        except Exception:  # pylint: disable=broad-exception-caught
            pass
        try:
            client.close()
        except Exception:  # pylint: disable=broad-exception-caught
            pass
        reset_client(client_id)


async def _async_event_stream(client_id: str):
    """ASGI variant: non-blocking redis reads on the event loop."""
    client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    pubsub = client.pubsub()
    channel = CLIENT_PREFIX + client_id
    await pubsub.subscribe(channel)
    try:
        yield "retry: 3000\n\n"
        yield ": connected\n\n"
        if mark_seen(client_id):
            yield _frame("reset", "{}")
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
                touch_client(client_id)
                yield ": ping\n\n"
                continue
            parsed = _event_name(message.get("data") or "")
            if parsed is None:
                continue
            event, data = parsed
            yield _frame(event, data)
    finally:
        try:
            await pubsub.unsubscribe(channel)
            await pubsub.aclose()
        except Exception:  # pylint: disable=broad-exception-caught
            pass
        try:
            await client.aclose()
        except Exception:  # pylint: disable=broad-exception-caught
            pass
        reset_client(client_id)


def _is_wsgi(request) -> bool:
    from django.core.handlers.wsgi import WSGIRequest

    return isinstance(request, WSGIRequest)


@csrf_exempt
async def sse_stream(request):
    """Stream the events one tab asked for (``?client=<id>``)."""
    client_id = request.GET.get("client", "")
    if not CLIENT_RE.match(client_id):
        return HttpResponseBadRequest("missing or invalid client id")

    if not request.user.is_authenticated:
        return StreamingHttpResponse(
            ["retry: 60000\n\n", ": unauthenticated\n\n"],
            content_type="text/event-stream",
        )

    stream = (
        _sync_event_stream(client_id)
        if _is_wsgi(request)
        else _async_event_stream(client_id)
    )
    response = StreamingHttpResponse(stream, content_type="text/event-stream")
    response["Cache-Control"] = "no-cache, no-transform"
    response["X-Accel-Buffering"] = "no"
    return response


@require_POST
def sse_watch(request):
    """Replace the set of keys this tab wants (idempotent, debounced client-side)."""
    if not request.user.is_authenticated:
        return JsonResponse({"error": "authentication required"}, status=403)

    try:
        payload = json.loads(request.body or b"{}")
    except ValueError:
        return JsonResponse({"error": "invalid json"}, status=400)

    client_id = payload.get("client") or ""
    if not isinstance(client_id, str) or not CLIENT_RE.match(client_id):
        return JsonResponse({"error": "invalid client id"}, status=400)

    keys = payload.get("keys") or []
    if not isinstance(keys, list) or len(keys) > MAX_WATCH_KEYS:
        return JsonResponse({"error": "invalid keys"}, status=400)
    keys = [key for key in keys if isinstance(key, str)]

    register_client(client_id, keys)
    return JsonResponse({"keys": keys})
