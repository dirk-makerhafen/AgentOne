"""LiveSession — pyHtmlGui Observable bridging Redis channel layer to views."""

from __future__ import annotations
from ui.lib.pyHtmlGui.pyhtmlgui.lib.observable import Observable


class LiveSession(Observable):
    def __init__(self, session_id: int):
        super().__init__()
        self.session_id = session_id
