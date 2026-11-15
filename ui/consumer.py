
from threading import Lock, Thread, current_thread
from urllib.parse import parse_qs
from channels.generic.websocket import WebsocketConsumer
import json
import logging
import time
from server.models import observables

log = logging.getLogger("ui.consumer")


# Global instance tracker (pyhtmlgui disabled - using simple WebSocket only)
_pyhtmlgui_lock = Lock()
_loop_threads: dict[str, Thread] = {}


# Use a simple namespace-like class for type hints (pyhtmlgui disabled)
class _PyHtmlGuiInstancePlaceholder:
    """Placeholder class for type hints when pyhtmlgui is disabled."""
    instance_key: str
    connections_count: lambda self: int
    connect_send_function: any
    disconnect_send_function: any
    render: any


_PyHtmlGuiInstance = _PyHtmlGuiInstancePlaceholder


def process_queue_messages(instance: _PyHtmlGuiInstance, messages: list[dict]) -> None:
    """Coalesce drained queue messages and invoke the subscribed callbacks.

    One call per function_id with the latest message wins.  Extracted from
    :func:`loop` so it can be unit-tested without Redis or threads.
    """
    dispatch = {}
    for message in messages:
        for function_id in message.get("function_ids", []):
            dispatch[function_id] = message
    for function_id, message in dispatch.items():
        try:
            function = instance._function_references.get(function_id)
        except Exception:
            continue
        if function is None:
            continue
        try:
            function(
                key=message.get("key"),
                model=message.get("model"),
                pk=message.get("pk"),
                action=message.get("action"),
                data=message.get("data", {}),
            )
        except Exception:
            import traceback
            log.debug("CONSUMER.loop dispatch ERROR\n%s", traceback.format_exc())


def loop(instance: _PyHtmlGuiInstance):
    """Drain one UI instance's redis queue and dispatch to its observers.

    One thread per instance (started on connect).  BLPOP uses a timeout so
    the thread can exit once the instance has no connections left instead
    of blocking forever.
    """
    queue_key = observables.QUEUE_PREFIX + instance.instance_key
    try:
        while True:
            try:
                r = observables.get_redis()
                result = r.blpop(queue_key, timeout=5)
                if result is None:
                    if instance.connections_count() == 0:
                        return
                    continue
                # Drain the entire list at once.  Use LTRIM (not DELETE) so
                # anything pushed between LRANGE and the trim survives.
                remaining = r.lrange(queue_key, 0, -1)
                r.ltrim(queue_key, len(remaining), -1)
                messages = [json.loads(result[1])]
                messages.extend(json.loads(m) for m in remaining)
            except Exception:
                if instance.connections_count() == 0:
                    return
                time.sleep(0.5)
                continue
            process_queue_messages(instance, messages)
    finally:
        # Don't leak dead entries; only remove our own registration so a
        # reconnect that already started a new thread is left alone.
        with _pyhtmlgui_lock:
            if _loop_threads.get(instance.instance_key) is current_thread():
                _loop_threads.pop(instance.instance_key, None)
        

def _ensure_loop_thread(instance: _PyHtmlGuiInstance) -> None:
    """Start the drain thread for *instance* unless one is already alive."""
    with _pyhtmlgui_lock:
        thread = _loop_threads.get(instance.instance_key)
        if thread is not None and thread.is_alive():
            return
        thread = Thread(target=loop, args=(instance,), daemon=True)
        _loop_threads[instance.instance_key] = thread
        thread.start()

class PyHtmlGuiConsumer(WebsocketConsumer):
    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        self._instance = None  # pyhtmlgui disabled - use basic WebSocket
        # Serializes concurrent send() calls
        self._send_lock = Lock()
        self._closed = False
        self._connect_time = time.monotonic()
        self._last_rx = self._connect_time

    def _url_params(self) -> dict[str, object]:
        """URL query parameters from the page, passed on the websocket URL.

        The browser appends ``?token=...`` plus every query parameter of the
        page URL (from ``window.location.search``) when opening the socket.
        """
        qs = (self.scope.get("query_string") or b"").decode("utf-8", "replace")
        return {
            key: values[0] if len(values) == 1 else values
            for key, values in parse_qs(qs, keep_blank_values=True).items()
        }

    def connect(self):
        """Simplified connect: just accept the WebSocket, no pyhtmlgui setup."""
        self._closed = False
        self._connect_time = time.monotonic()
        self._last_rx = self._connect_time
        self.accept()
        log.info("ws connect client=%s", self.scope.get("client"))

    def disconnect(self, close_code):
        # Mark closed first so in-flight sends are dropped instead of writing
        # onto a closing TLS connection (which surfaces as BIO failures /
        # tlsv1 alerts on the peer).
        self._closed = True
        log.info(
            "ws disconnect close_code=%s up_s=%.0f rx_idle_s=%.1f",
            close_code,
            time.monotonic() - self._connect_time,
            time.monotonic() - self._last_rx,
        )

    def receive(self, text_data: str | None = None, bytes_data=None):
        self._last_rx = time.monotonic()
        # pyhtmlgui disabled - basic text handling only
        if text_data:
            # Echo or handle basic messages here
            pass

    def send(self, message):
        super().send(text_data=message)
