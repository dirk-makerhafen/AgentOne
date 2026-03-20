from __future__ import annotations
import typing
import weakref
import random
import string
from ui.lib.pyHtmlGui.pyhtmlgui.view.pyhtml_view import PyHtmlView
from ui.lib.pyHtmlGui.pyhtmlgui.pyhtmlgui_instance import PyHtmlGuiInstance

CHARACTERS = list(string.ascii_lowercase + string.digits)

class ModelView(PyHtmlView):
    def __init__(self, subject, parent:  typing.Union[PyHtmlView, PyHtmlGuiInstance], **kwargs):
        self.uid = "pv%s" % ("".join(random.choices(CHARACTERS, k=16)))
        self.is_visible = False
        parent._add_child(self)
        self._parent_wref = weakref.ref(parent, None)
        self._instance = parent if type(parent).__name__ == "PyHtmlGuiInstance" else parent._instance
        self._was_rendered = False
        self._last_rendered = 0
        #self._observables = ObservableMappings()
        self.children = set()
        self._subject = subject

    @property
    def subject(self):
        return self._subject
    
    @property
    def parent(self):
        return self._parent_wref()

    def _on_subject_updated(self, source, **kwargs) -> None:
        self.update()

    def _on_subject_died(self, wr) -> None:
        print("subject dies", self.subject)
