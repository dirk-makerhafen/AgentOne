"""Per-tab event stream between the ORM fan-out and htmx.

A tab registers the observable keys it currently renders (``POST /app/sse/watch``);
``publish_model_event`` fans out to exactly those tabs.  The stream carries
event *names* (the key) and a small JSON hint, never rendered HTML, so a dropped
event can only cost one refetch.

The transport is a WebSocket (``/app/ws/events/``).  Chrome caps HTTP/1.1 at six
connections per origin and counts long-lived ``EventSource`` streams against
that pool, so five or six open tabs leave no socket for a new tab's document
and component requests.  WebSockets have a separate, much higher per-host limit
(255 in Chromium, 200 in Firefox), so one socket per tab is safe.  The browser
side keeps htmx's ``sse:`` triggers unchanged via a small EventSource-shaped
WebSocket polyfill (``webui/static/webui/ws-events.js``).

The old HTTP ``/app/sse/`` view below is kept as a fallback for WSGI/dev use,
but the UI no longer connects to it.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from urllib.parse import parse_qs

import redis as redis_sync
import redis.asyncio as aioredis
from channels.generic.websocket import AsyncWebsocketConsumer
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


def _ws_message(event: str, data: str) -> str:
    """One WebSocket frame, shaped like the SSE event the polyfill expects."""
    return json.dumps({"event": event, "data": data})


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


class EventsConsumer(AsyncWebsocketConsumer):
    """Forward Redis fan-out frames to one authenticated tab.

    Authentication is handled by ``AuthMiddlewareStack`` in ``config/asgi.py``;
    the client id only identifies which per-tab pubsub channel to follow.  The
    watch set is still registered by ``POST /app/sse/watch`` (a short request),
    so reconnect cleanup behaves exactly as it does for the HTTP stream.
    """

    async def connect(self) -> None:
        query = parse_qs((self.scope.get("query_string") or b"").decode())
        client_id = (query.get("client") or [""])[0]
        user = self.scope.get("user")
        # Accept before rejecting: a pre-accept close() is reported by ASGI
        # servers as an HTTP 403 handshake failure, so the browser would see
        # close code 1006 and the client shim could not tell it apart from a
        # network error (and would keep retrying).
        if not CLIENT_RE.match(client_id):
            await self.accept()
            await self.close(code=4400)
            return
        if not user or not user.is_authenticated:
            await self.accept()
            await self.close(code=4401)
            return

        self.client_id = client_id
        self.channel = CLIENT_PREFIX + client_id
        self.redis = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        self.pubsub = self.redis.pubsub()
        try:
            await self.pubsub.subscribe(self.channel)
        except Exception:  # pylint: disable=broad-exception-caught
            log.exception("SSE websocket subscribe failed")
            await self.close(code=1011)
            return

        await self.accept()
        # A reconnect within SEEN_TTL means the tab already has DOM rendered;
        # tell it to refetch everything before it goes stale.  Send this before
        # starting the reader so a live event can't overtake the reset frame.
        if await asyncio.to_thread(mark_seen, client_id):
            await self.send(text_data=_ws_message("reset", "{}"))
        self._reader = asyncio.create_task(self._read_pubsub())

    async def _read_pubsub(self) -> None:
        try:
            while True:
                message = await self.pubsub.get_message(
                    ignore_subscribe_messages=True,
                    timeout=HEARTBEAT_SECONDS,
                )
                if message is None:
                    # observables' redis client is synchronous; keep it off the
                    # ASGI event loop (same cadence as the HTTP stream).
                    await asyncio.to_thread(touch_client, self.client_id)
                    continue
                parsed = _event_name(message.get("data") or "")
                if parsed is None:
                    continue
                event, data = parsed
                await self.send(text_data=_ws_message(event, data))
        except asyncio.CancelledError:
            raise
        except Exception:  # pylint: disable=broad-exception-caught
            log.exception("SSE websocket redis read failed")

    async def disconnect(self, code: int) -> None:  # pylint: disable=unused-argument
        reader = getattr(self, "_reader", None)
        if reader is not None:
            reader.cancel()
            try:
                await reader
            except asyncio.CancelledError:
                pass
        pubsub = getattr(self, "pubsub", None)
        if pubsub is not None:
            try:
                await pubsub.unsubscribe(self.channel)
                await pubsub.aclose()
            except Exception:  # pylint: disable=broad-exception-caught
                log.exception("SSE websocket unsubscribe failed")
        redis = getattr(self, "redis", None)
        if redis is not None:
            try:
                await redis.aclose()
            except Exception:  # pylint: disable=broad-exception-caught
                log.exception("SSE websocket redis close failed")
        if getattr(self, "client_id", None):
            await asyncio.to_thread(reset_client, self.client_id)


def events_ws_url(request):
    """Name-only HTTP route so templates can reverse the WebSocket path."""
    return HttpResponseBadRequest("Use a WebSocket connection for this endpoint.")


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
