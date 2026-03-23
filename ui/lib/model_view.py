from __future__ import annotations
import typing
import weakref
import random
import string
from ui.lib.pyHtmlGui.pyhtmlgui.view.pyhtml_view import ObservableMappings, PyHtmlView
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from ui.lib.pyHtmlGui.pyhtmlgui.pyhtmlgui_instance import PyHtmlGuiInstance

CHARACTERS = list(string.ascii_lowercase + string.digits)

class ModelView(PyHtmlView):
    def __init__(self, subject, parent: PyHtmlView | PyHtmlGuiInstance, **kwargs):
        super().__init__(subject, parent, **kwargs)
        self._subject_ref = subject
        self._parent_ref = parent

    @property
    def subject(self):
        return self._subject_ref
    
    @property
    def parent(self):
        return self._parent_ref

    def _on_subject_updated(self, source, **kwargs) -> None:
        self.update()

    def _on_subject_died(self, wr) -> None:
        print("subject dies", self.subject)
