from threading import Lock
from channels.generic.websocket import WebsocketConsumer
import json
from ui.pyHtmlGui.pyhtmlgui import PyHtmlGui
from ui.main_app import UiApp
from ui.main_view import UiAppView

# Global PyHtmlGui instance (single instance for the entire Django app)
# This will be initialized only once when the consumer is first loaded
_pyhtmlgui_lock = Lock()
_pyhtmlgui = None
_pyhtmlgui_instance = None
_view_app_instance = UiApp() # Use the main UiApp as the app_instance

class PyHtmlGuiConsumer(WebsocketConsumer):
    def connect(self):
        global _pyhtmlgui
        global _pyhtmlgui_instance
        self.accept()
        with _pyhtmlgui_lock:
            if not _pyhtmlgui:
                _pyhtmlgui = PyHtmlGui(
                    app_instance=_view_app_instance, # Pass the UiApp instance
                    view_class=UiAppView,           # Pass the main UiAppView class
                    template_dir='ui/templates/',  
                    base_template='pyhtmlgui_page.html', # Use your custom base template
                    single_instance=True, 
                    enable_server=False
                )
            if not _pyhtmlgui_instance:
                _pyhtmlgui_instance = _pyhtmlgui.get_or_create_instance()
            _pyhtmlgui_instance.connect_send_function(self.send)

    def disconnect(self, close_code):
        _pyhtmlgui_instance.disconnect_send_function(self.send)

    def receive(self, text_data=None, bytes_data=None):
        _pyhtmlgui_instance.process_received_message(json.loads(text_data))
  
    def send(self, message):
        super().send(text_data=message)
