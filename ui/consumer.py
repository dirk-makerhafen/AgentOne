
from threading import Lock
from channels.generic.websocket import WebsocketConsumer
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
import json
from ui.lib.pyHtmlGui.pyhtmlgui.pyhtmlgui_instance import PyHtmlGuiInstance
from ui.lib.pyHtmlGui.pyhtmlgui import PyHtmlGui
from ui.app import UiApp
from ui.app_view import UiAppView
from runtime.events import CHANNEL_GROUP

# Global PyHtmlGui instance (single instance for the entire Django app)
_pyhtmlgui_lock = Lock()
_pyhtmlgui: PyHtmlGui|None = None
_pyhtmlgui_instance: PyHtmlGuiInstance|None = None
_view_app_instance = UiApp()


class PyHtmlGuiConsumer(WebsocketConsumer):
    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        
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
                    single_instance=True,
                    enable_server=False,
                )
            if not _pyhtmlgui_instance:
                _pyhtmlgui_instance = _pyhtmlgui.get_or_create_instance()
            _pyhtmlgui_instance.connect_send_function(self.send)

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
