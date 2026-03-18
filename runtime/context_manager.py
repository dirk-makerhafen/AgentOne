from contextvars import ContextVar
from contextlib import contextmanager
from typing import Any

class _ContextTracker:
    def __init__(self):
        self.ctxvar: ContextVar[Any] = ContextVar("parent")

    @property
    def current(self):
        return self.ctxvar.get(None)

    @contextmanager
    def __call__(self, node):
        token = self.ctxvar.set(node)
        try:
            yield
        finally:
            self.ctxvar.reset(token)

ContextTracker = _ContextTracker()
RuntimeContextTracker = _ContextTracker()
