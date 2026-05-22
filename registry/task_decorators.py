from __future__ import annotations
from typing import Any, Callable, Optional
from functools import wraps

from server.models.enums.task_enums import TaskExecutionMode, TaskType


class TaskDescriptor:
    """Acts as the bridge between the class method and the agent session."""

    def __init__(self, func: Callable[..., Any]) -> None:
        """Wrap *func* so it is only invokable via .delay() / .apply_async().

        Direct __call__ raises ``TypeError``.
        """
        self.func = func
        wraps(func)(self)

    def call(self, session: Any, *args: Any, **kwargs: Any) -> Any:
        """Invoke the wrapped function with a session object."""
        print("TaskDescriptor.call", self, session, args, kwargs)
        return self.func(session, *args, **kwargs)

    def __call__(self, *args: Any, **kwds: Any) -> Any:
        raise TypeError(
            f"Task '{self.func.__name__}' must be invoked using .delay(), .apply_async()"
            "for asynchronous execution or session creation."
        )


class TaskDecorator:
    """Base decorator for all Agent tasks. Stores metadata on the function object."""

    def __init__(
        self,
        task_type: TaskType,
        task_execution_mode: TaskExecutionMode = TaskExecutionMode.FUNCTION,
        name: Optional[str] = None,
        description: str = "",
        bound: bool = True,
        requires_approval: bool = False,
        max_retries: Optional[int] = None,
        retry_delay: Optional[int] = None,
        retry_requires_approval: Optional[bool] = None,
        priority: Optional[int] = None,
    ) -> None:
        self.task_type = task_type
        self.task_execution_mode = task_execution_mode
        self.name = name
        self.description = description
        self.bound = bound
        self.requires_approval = requires_approval
        self.max_retries = max_retries
        self.priority = priority
        self.retry_delay = retry_delay
        self.retry_requires_approval = retry_requires_approval

    def __call__(self, func: Callable[..., Any]) -> TaskDescriptor:
        """Attach task metadata to *func* and return a ``TaskDescriptor``."""
        func._task_definition = {  # type: ignore[attr-defined]
            "name": self.name or func.__name__,
            "description": self.description,
            "task_type": self.task_type,
            "task_execution_mode": self.task_execution_mode,
            "bound": self.bound,
            "requires_approval": self.requires_approval,
            "priority": self.priority,
            "max_retries": self.max_retries,
            "retry_delay": self.retry_delay,
            "retry_requires_approval": self.retry_requires_approval,
        }
        return TaskDescriptor(func)


# ---------------------------------------------------------------------------
# User-facing / invocation roots
# ---------------------------------------------------------------------------

def command(
    name: Optional[str] = None,
    description: str = "",
    requires_approval: bool = False,
) -> TaskDecorator:
    """Decorator for user-invokable commands.

    The trigger is the string (after '!') that matches.
    """
    return TaskDecorator(
        task_type=TaskType.COMMAND,
        name=name,
        description=description,
        requires_approval=requires_approval,
    )


def task(
    name: Optional[str] = None,
    description: str = "",
    requires_approval: bool = False,
) -> TaskDecorator:
    """Decorator for executable units inside flows."""
    return TaskDecorator(
        task_type=TaskType.TASK,
        name=name,
        description=description,
        requires_approval=requires_approval,
    )


def tool(
    name: Optional[str] = None,
    description: str = "",
    requires_approval: bool = False,
) -> TaskDecorator:
    """Decorator for tool-callable functions."""
    return TaskDecorator(
        task_type=TaskType.TOOL,
        name=name,
        description=description,
        requires_approval=requires_approval,
    )


def webapi(
    name: Optional[str] = None,
    description: str = "",
    requires_approval: bool = False,
) -> TaskDecorator:
    """Decorator for Web API endpoints."""
    return TaskDecorator(
        task_type=TaskType.WEBAPI,
        name=name,
        description=description,
        requires_approval=requires_approval,
    )


def webview(
    name: Optional[str] = None,
    description: str = "",
    requires_approval: bool = False,
) -> TaskDecorator:
    """Decorator for Web view handlers."""
    return TaskDecorator(
        task_type=TaskType.WEBVIEW,
        name=name,
        description=description,
        requires_approval=requires_approval,
    )


# ---------------------------------------------------------------------------
# Flow controllers (Celery-equivalents)
# ---------------------------------------------------------------------------

def chain(
    name: Optional[str] = None,
    description: str = "",
    requires_approval: bool = False,
) -> TaskDecorator:
    """Decorator for a task that chains multiple steps sequentially."""
    return TaskDecorator(
        task_type=TaskType.TASK,
        task_execution_mode=TaskExecutionMode.CHAIN,
        name=name,
        description=description,
        requires_approval=requires_approval,
    )


def group(
    name: Optional[str] = None,
    description: str = "",
    requires_approval: bool = False,
) -> TaskDecorator:
    """Decorator for a task that runs steps concurrently as a group."""
    return TaskDecorator(
        task_type=TaskType.TASK,
        task_execution_mode=TaskExecutionMode.GROUP,
        name=name,
        description=description,
        requires_approval=requires_approval,
    )


def chord(
    name: Optional[str] = None,
    description: str = "",
    requires_approval: bool = False,
) -> TaskDecorator:
    """Decorator for a task that runs a group then a callback."""
    return TaskDecorator(
        task_type=TaskType.TASK,
        task_execution_mode=TaskExecutionMode.CHORD,
        name=name,
        description=description,
        requires_approval=requires_approval,
    )


def map(
    name: Optional[str] = None,
    description: str = "",
    requires_approval: bool = False,
) -> TaskDecorator:
    """Decorator for a task that maps an input list over a function."""
    return TaskDecorator(
        task_type=TaskType.TASK,
        task_execution_mode=TaskExecutionMode.MAP,
        name=name,
        description=description,
        requires_approval=requires_approval,
    )


"""
# Keep for later, not implemented yet
# System hooks and callbacks
def setup(name: str|None = None, description: str = "", requires_approval = False):
    return TaskDecorator(task_type=TaskType.SETUP, name=name, description=description, requires_approval=requires_approval)

def session(name: str|None = None, description: str = "", requires_approval = False):
    return TaskDecorator(task_type=TaskType.INSTANCE, name=name, description=description, requires_approval=requires_approval)

def hook(name: str, description: str = "", requires_approval = False):
    \"\"\"Decorator to tag a method as a lifecycle hook. name should be from TaskHook enum values.\"\"\"
    return TaskDecorator(task_type=TaskType.HOOK, name=name, description=description, requires_approval=requires_approval)
"""
