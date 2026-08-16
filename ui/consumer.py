
from threading import Lock, Thread
from urllib.parse import parse_qs
from channels.generic.websocket import WebsocketConsumer
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
import json
import time
from ui.lib.pyHtmlGui.pyhtmlgui.pyhtmlgui_instance import PyHtmlGuiInstance
from ui.lib.pyHtmlGui.pyhtmlgui import PyHtmlGui
from ui.app import UiApp
from ui.app_view import UiAppView
from runtime.events import CHANNEL_GROUP
from runtime import observables

# Global PyHtmlGui instance (single instance for the entire Django app)
_pyhtmlgui_lock = Lock()
_pyhtmlgui: PyHtmlGui|None = None
_pyhtmlgui_instance: PyHtmlGuiInstance|None = None
_view_app_instance = UiApp()
_loop_thread_started = False

def loop():
    """Read the instance's redis queue (blocking) and dispatch to observers.

    BLPOP blocks until a message arrives, then the whole list is drained at
    once so N updates for the same key/function coalesce into a single call.
    """
    while True:
        try:
            instance = _pyhtmlgui_instance
            if instance is None:
                time.sleep(0.5)
                continue
            r = observables.get_redis()
            queue_key = observables.QUEUE_PREFIX + instance.instance_key
            result = r.blpop(queue_key, timeout=0)
            if result is None:
                continue
            # Drain the entire list at once.
            remaining = r.lrange(queue_key, 0, -1)
            r.delete(queue_key)
            messages = [json.loads(result[1])]
            messages.extend(json.loads(m) for m in remaining)
        except Exception:
            time.sleep(0.5)
            continue

        # Coalesce: one call per (function_id) with the latest message.
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

class PyHtmlGuiConsumer(WebsocketConsumer):
    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)

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
        global _loop_thread_started
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
            #if not _pyhtmlgui_instance:
            _pyhtmlgui_instance = _pyhtmlgui.get_or_create_instance(
                url_params=self._url_params(),
            )
            _pyhtmlgui_instance.connect_send_function(self.send)
            #if not _loop_thread_started:
            _loop_thread_started = True
            Thread(target=loop, daemon=True).start()

        try:
            async_to_sync(get_channel_layer().group_add)(CHANNEL_GROUP, self.channel_name)
        except Exception:
            pass

    def disconnect(self, close_code):
        try:
            async_to_sync(get_channel_layer().group_discard)(CHANNEL_GROUP, self.channel_name)
        except Exception:
            pass

        if _pyhtmlgui_instance:
            _pyhtmlgui_instance.disconnect_send_function(self.send)
            if _pyhtmlgui_instance.connections_count() == 0:
                observables.unsubscribe_all(_pyhtmlgui_instance.instance_key)

    def receive(self, text_data: str | None = None, bytes_data=None):
        if _pyhtmlgui_instance and text_data:
            _pyhtmlgui_instance.process_received_message(json.loads(text_data))

    def send(self, message):
        super().send(text_data=message)

    def session_event(self, event: dict) -> None:
        #print(f"CONSUMER.session_event: type={event.get('event_type')} "
        #     f"sid={event.get('session_id')} "
        #     f"payload_keys={list(event.get('payload', {}).keys())}")
        try:
            _view_app_instance.dispatch_session_event(
                event.get("session_id"),
                event.get("event_type"),
                event.get("payload", {}),
            )
        except Exception as e:
            import traceback
            print(f"CONSUMER.session_event ERROR: {e}\n{traceback.format_exc()}")
