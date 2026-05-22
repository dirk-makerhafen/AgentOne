from contextvars import ContextVar
from contextlib import contextmanager
from typing import Any, Iterator


class _ContextTracker:
    """Tracks a context variable across nested scopes."""

    def __init__(self) -> None:
        self.ctxvar: ContextVar[Any] = ContextVar("parent")

    @property
    def current(self) -> Any:
        """Return the current context value, or *None* if none is set."""
        return self.ctxvar.get(None)

    @contextmanager
    def __call__(self, node: Any) -> Iterator[None]:
        """Set *node* as the current context within the enclosed block."""
        token = self.ctxvar.set(node)
        try:
            yield
        finally:
            self.ctxvar.reset(token)


ContextTracker = _ContextTracker()
RuntimeContextTracker = _ContextTracker()
