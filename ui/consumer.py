
from threading import Lock, Thread
from urllib.parse import parse_qs
from channels.generic.websocket import WebsocketConsumer
import json
import time
from ui.lib.pyHtmlGui.pyhtmlgui.pyhtmlgui_instance import PyHtmlGuiInstance
from ui.lib.pyHtmlGui.pyhtmlgui import PyHtmlGui
from ui.app import UiApp
from ui.app_view import UiAppView
from runtime import observables

# Global PyHtmlGui instance (single instance for the entire Django app)
_pyhtmlgui_lock = Lock()
_pyhtmlgui: PyHtmlGui|None = None
_pyhtmlgui_instance: PyHtmlGuiInstance|None = None
_view_app_instance = UiApp()
_loop_threads: dict[str, Thread] = {}


def process_queue_messages(instance: PyHtmlGuiInstance, messages: list[dict]) -> None:
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
            print("CONSUMER.loop dispatch ERROR\n" + traceback.format_exc())


def loop(instance: PyHtmlGuiInstance):
    """Drain one UI instance's redis queue and dispatch to its observers.

    One thread per instance (started on connect).  BLPOP uses a timeout so
    the thread can exit once the instance has no connections left instead
    of blocking forever.
    """
    queue_key = observables.QUEUE_PREFIX + instance.instance_key
    while True:
        try:
            r = observables.get_redis()
            result = r.blpop(queue_key, timeout=5)
            if result is None:
                if instance.connections_count() == 0:
                    return
                continue
            # Drain the entire list at once.
            remaining = r.lrange(queue_key, 0, -1)
            r.delete(queue_key)
            messages = [json.loads(result[1])]
            messages.extend(json.loads(m) for m in remaining)
        except Exception:
            if instance.connections_count() == 0:
                return
            time.sleep(0.5)
            continue
        process_queue_messages(instance, messages)


def _ensure_loop_thread(instance: PyHtmlGuiInstance) -> None:
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
        self._instance: PyHtmlGuiInstance | None = None

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
        global _pyhtmlgui
        global _pyhtmlgui_instance
        self.accept()
        with _pyhtmlgui_lock:
            if not _pyhtmlgui:
                _pyhtmlgui = PyHtmlGui(
                    app_instance=_view_app_instance,
                    view_class=UiAppView,
                    template_dir='ui/templates/',
                    base_template='pyhtmlgui_page.html',
                    single_instance=False,
                    enable_server=False,
                )
            # Every websocket gets its own instance (new uuid key), so each
            # tab has its own redis queue and subscriptions.
            self._instance = _pyhtmlgui.get_or_create_instance(
                url_params=self._url_params(),
            )
            _pyhtmlgui_instance = self._instance
            self._instance.connect_send_function(self.send)
        _ensure_loop_thread(self._instance)

    def disconnect(self, close_code):
        instance = getattr(self, "_instance", None) or _pyhtmlgui_instance
        if instance is not None:
            instance.disconnect_send_function(self.send)
            if instance.connections_count() == 0:
                observables.unsubscribe_all(instance.instance_key)
                if _pyhtmlgui is not None:
                    _pyhtmlgui.release_instance(instance)

    def receive(self, text_data: str | None = None, bytes_data=None):
        instance = getattr(self, "_instance", None) or _pyhtmlgui_instance
        if instance and text_data:
            instance.process_received_message(json.loads(text_data))

    def send(self, message):
        super().send(text_data=message)
