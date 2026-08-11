from __future__ import annotations
import typing
import weakref
import random
import string
from server.models.agents.agent import AgentModel
from ui.lib.pyHtmlGui.pyhtmlgui.lib.observable import Observable
from ui.lib.pyHtmlGui.pyhtmlgui.view.pyhtml_view import ObservableMappings, PyHtmlView
from runtime import observables
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from ui.lib.pyHtmlGui.pyhtmlgui.pyhtmlgui_instance import PyHtmlGuiInstance

CHARACTERS = list(string.ascii_lowercase + string.digits)

class ModelView(PyHtmlView):
    def __init__(self, subject, parent: PyHtmlView | PyHtmlGuiInstance, **kwargs):
        self.uid = "pv%s" % ("".join(random.choices(CHARACTERS, k=16)))
        self.is_visible = False
        parent._add_child(self)
       
        self._subject_wref = weakref.ref(subject, self._on_subject_died)
        self._parent_wref = weakref.ref(parent, None)
        self._instance = parent if type(parent).__name__ == "PyHtmlGuiInstance" else parent._instance
        self._was_rendered = False
        self._last_rendered = 0
        self._observables = ObservableMappings()
        self._children = weakref.WeakSet()
        self._subject = None  # this is replace for a short time on render by the actual resolved object
        self._observed_function_ids = []  # function_ids registered in redis (tracked here for cleanup)
        if self.CSS_STR:
            self._instance.add_css_string(self.__class__.__name__, self.CSS_STR )        
        if self._on_subject_updated is not None: # by default we observe the subject
            try:
                self.add_observable(self.subject)
            except Exception as e:
                pass#ogging.warning("object type '%s' can not be observed, %s" % (type(subject),e))

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

    def on_orm_updated(self, **kwargs) -> None:
        """Called by the redis loop when a subscribed ORM observable fires.

        kwargs carries ``key``, ``model``, ``pk``, ``action``, ``data``.
        """
        self.update()

    def _on_subject_died(self, wr) -> None:
        print("subject dies", self.subject)
        self.remove_observable(self.subject)

    def add_observable(self, subject: AgentModel, target_function: typing.Callable = None,
                       observable_key: str = None) -> None:
        if observable_key is None:
            observable_key = subject.observables.pk
        if target_function is None:
            target_function = self.on_orm_updated
        function_id = self._instance._function_references.add(target_function)
        observables.subscribe(self._instance.instance_key, observable_key, function_id)
        self._instance.observed_views.setdefault(observable_key, []).append(function_id)
        self._observed_function_ids.append((observable_key, function_id))

    def remove_observable(self, subject: Observable, target_function: typing.Callable = None,
                          observable_key: str = None) -> None:
        for key, function_id in list(self._observed_function_ids):
            if observable_key is not None and key != observable_key:
                continue
            observables.unsubscribe(self._instance.instance_key, key, function_id)
            try:
                self._instance.observed_views[key].remove(function_id)
            except Exception:
                pass
            self._observed_function_ids.remove((key, function_id))
        if target_function is None:
            target_function = self._on_subject_updated
        self._observables.remove(subject, target_function)
