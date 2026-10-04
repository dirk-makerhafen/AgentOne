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


def orm_subscribe(view: PyHtmlView, observable_key: str, target_function: typing.Callable) -> int | None:
    """Subscribe *view* to a Redis observable key (cross-process ORM→UI path).

    Works for any view (``ModelView`` or plain ``PyHtmlView``) — unlike
    :meth:`ModelView.add_observable` it takes an explicit key instead of
    resolving ``subject.observables.pk``, so views whose subject is a
    runtime wrapper can subscribe to e.g. ``"Message.session:5"``.

    Returns the registered function_id, or None when there is no UI
    instance (e.g. in unit tests).
    """
    instance = getattr(view, "_instance", None)
    if instance is None:
        return None
    if not hasattr(view, "_observed_function_ids") or view._observed_function_ids is None:
        view._observed_function_ids = []
    function_id = instance._function_references.add(target_function)
    observables.subscribe(instance.instance_key, observable_key, function_id)
    instance.observed_views.setdefault(observable_key, []).append(function_id)
    view._observed_function_ids.append((observable_key, function_id))
    return function_id


def orm_unsubscribe_view(view: PyHtmlView, observable_key: str | None = None) -> None:
    """Remove all (or one key's) Redis subscriptions registered via :func:`orm_subscribe`."""
    instance = getattr(view, "_instance", None)
    if instance is None:
        return
    for key, function_id in list(getattr(view, "_observed_function_ids", None) or []):
        if observable_key is not None and key != observable_key:
            continue
        try:
            observables.unsubscribe(instance.instance_key, key, function_id)
        except Exception:
            pass
        try:
            instance.observed_views[key].remove(function_id)
        except Exception:
            pass
        try:
            view._observed_function_ids.remove((key, function_id))
        except ValueError:
            pass


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
        if self._on_subject_updated is not None and hasattr(subject, "observables"):
            # by default we observe the subject — but only when it is an ORM
            # instance exposing ``.observables``.  Runtime wrappers (Session,
            # UiApp, …) have no observable keys; those views subscribe
            # explicitly via orm_subscribe()/add_observable(observable_key=…).
            try:
                self.add_observable(self.subject)
            except Exception:
                pass

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
        orm_subscribe(self, observable_key, target_function)

    def remove_observable(self, subject: Observable, target_function: typing.Callable = None,
                          observable_key: str = None) -> None:
        orm_unsubscribe_view(self, observable_key)
        if target_function is None:
            target_function = self._on_subject_updated
        try:
            self._observables.remove(subject, target_function)
        except Exception:
            pass
