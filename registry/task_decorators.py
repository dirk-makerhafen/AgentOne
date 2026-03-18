from __future__ import annotations
from typing import Any, Callable, List, Optional, Dict
from functools import wraps
from runtime.tasks.bound_agent_function import BoundAgentFunction
from server.models.enums.task_enums import TaskType

class TaskDecorator:
    """
    Base decorator for all Agent tasks. Stores metadata on the function object.
    Persistence is handled later by UnregisteredAgent.register().
    """

    def __init__(self, task_type: TaskType, name: Optional[str] = None, description: str = "", bound: bool = True, trigger:   Optional[str] = None, requires_approval:  Optional[bool] = False, max_retries: Optional[int]=None, retry_delay: Optional[int]=None, retry_requires_approval: Optional[bool]=None):
        self.task_type = task_type
        self.name = name
        self.description = description
        self.bound = bound
        self.trigger = trigger
        self.requires_approval = requires_approval
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.retry_requires_approval = retry_requires_approval

    def __call__(self, func: Callable) ->BoundAgentFunction:
        # Attach metadata to the function for later registration
        func._task_definition = {
            "name": self.name or func.__name__,
            "description": self.description,
            "task_type": self.task_type,
            "bound": self.bound,
            "trigger": self.trigger,
            "requires_approval": self.requires_approval,
            "max_retries": self.max_retries, # how many retries to we make in case of error
            "retry_delay": self.retry_delay, # time between retries in seconds
            "retry_requires_approval": self.retry_requires_approval, # required user approval before run
        }
        return TaskDescriptor(func)


class TaskDescriptor:
    """Acts as the bridge between the class method and the agent instance."""
    def __init__(self, func: Callable):
        self.func = func
        wraps(func)(self)

    def __get__(self, instance, owner):
        if instance is None:
            return self  # Access via class (e.g., MyAgent.add)
        return BoundAgentFunction(instance, self.func)

    def __call__(self, *args: Any, **kwds: Any):
        print("TaskDescriptor.__call__")
        #raise Exception()
        def wrapper(*args, **kwds):
            return self.func(*args, **kwds)
        return wrapper # self.func(*args, **kwds)



# User-facing / invocation roots
def command(trigger: str|None = None, name: str|None = None, description: str = "", requires_approval = False):
    """Decorator for user-invokable commands. Trigger is the string (after '!') that matches."""
    return TaskDecorator(task_type=TaskType.COMMAND, name=name, description=description, trigger=trigger, requires_approval=requires_approval)

# Executable units inside flows
def task(name: str|None = None, description: str = "", requires_approval = False):
    return TaskDecorator(task_type=TaskType.TASK, name=name, description=description, requires_approval=requires_approval )
def tool(name: str|None = None, description: str = "", requires_approval = False):
    return TaskDecorator(task_type=TaskType.TOOL, name=name, description=description, requires_approval=requires_approval)

# Flow controllers (Celery-equivalents)
def chain(name: str|None = None, description: str = "", requires_approval = False):
    return TaskDecorator(task_type=TaskType.CHAIN, name=name, description=description, requires_approval=requires_approval)
def group(name: str|None = None, description: str = "", requires_approval = False):
    return TaskDecorator(task_type=TaskType.GROUP, name=name, description=description, requires_approval=requires_approval)
def chord(name: str|None = None, description: str = "", requires_approval = False):
    return TaskDecorator(task_type=TaskType.CHORD, name=name, description=description, requires_approval=requires_approval)
def map(name: str|None = None, description: str = "", requires_approval = False):
    return TaskDecorator(task_type=TaskType.MAP, name=name, description=description, requires_approval=requires_approval)

# System hooks and callbacks
def setup(name: str|None = None, description: str = "", requires_approval = False):  # called on registration/version change
    return TaskDecorator(task_type=TaskType.SETUP, name=name, description=description, requires_approval=requires_approval)
def instance(name: str|None = None, description: str = "", requires_approval = False):  # called on agent instanciation
    return TaskDecorator(task_type=TaskType.INSTANCE, name=name, description=description, requires_approval=requires_approval)
def hook(name: str, description: str = "", requires_approval = False):
    """Decorator to tag a method as a lifecycle hook. name should be from TaskHook enum values."""
    return TaskDecorator(task_type=TaskType.HOOK, name=name, description=description, requires_approval=requires_approval)
