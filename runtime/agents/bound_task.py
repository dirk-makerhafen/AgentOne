from __future__ import annotations
from contextlib import contextmanager
from pathlib import Path
import sys
from typing import TYPE_CHECKING
from server.models.enums.task_enums import TaskCallStatusDetail
from registry.task_decorators import TaskDescriptor
from server.models.tasks.agent_task_call import AgentTaskCall
from server.models.tasks.agent_task_instance import AgentTaskInstance
from server.models.tasks.task_definition import TaskDefinition
from server.models.tasks.task_definition_version import TaskDefinitionVersion

if TYPE_CHECKING:
    from server.models.sessions.session_version import SessionVersionModel

@contextmanager
def temp_sys_path(path):
    """Temporarily adds a directory to sys.path."""
    path = str(path)
    if path not in sys.path:
        sys.path.insert(0, path)
        try:
            yield
        finally:
            sys.path.remove(path)
    else:
        yield

class BoundTask:
    def __init__(self, session_version: SessionVersionModel, task_definition_version:TaskDefinitionVersion):
        self.session_version = session_version
        from runtime.agents.session import Session

        self.session = Session(session_model=self.session_version.session, pinned_session_version=self.session_version)
        self.task_definition_version = task_definition_version
        self.task_definition =  self.task_definition_version.task_definition
        print("BOUN TASK CREATED")

    def call(self, *args, **kwargs):
        '''
        synchronous call
        '''
        print("CALL", self)
        exec_globals = {"__builtins__": __builtins__}
        with temp_sys_path(Path( self.task_definition_version.path or "")):
            exec(Path(self.task_definition_version.path or "").read_text(), exec_globals) # Execute the source code
        func: TaskDescriptor|None = exec_globals.get(self.task_definition.name, None)
        if func:
            return func.call(self.session, *args, **kwargs)
        raise Exception(f"Task '{self.task_definition.name}' not found, call failed, {self.task_definition_version.path}")

    def get_calls(self):
        return AgentTaskCall.objects.filter(session=self.session_version.session, task_definition_version=self.task_definition_version)

    def lastest_result(self):
        query = self.get_calls().exclude(taskcall_result_run=None).filter(status_detail=TaskCallStatusDetail.ENDED_SUCCESS)
        task_call = query.last()
        return task_call.get_result(timeout=0) if task_call else None

    def delay(self, *args, **kwargs) -> AgentTaskCall:
        """Star argument version of :meth:`apply_async`.
        Does not support the extra options enabled by :meth:`apply_async`.

        Arguments:
            *args (Any): Positional arguments passed on to the task.
            **kwargs (Any): Keyword arguments passed on to the task.
        Returns:
            AgentTaskCall
        """
        return self.apply_async(args, kwargs)

    def apply_async(self, args=None, kwargs=None, countdown=0, eta=None, expires=None,retry=False,time_limit=0, soft_time_limit=0,priority=0) -> AgentTaskCall:
        """Apply tasks asynchronously by sending a message.

        Arguments:
            args (Tuple): The positional arguments to pass on to the task.
            kwargs (Dict): The keyword arguments to pass on to the task.
            link (Signature): A single, or a list of tasks signatures to apply if the task returns successfully.
            link_error (Signature): A single, or a list of task signatures to apply if an error occurs while executing the task.
            countdown (float): Number of seconds into the future that the task should execute.  Defaults to immediate execution.
            eta (~datetime.datetime): Absolute time and date of when the task should be executed.  May not be specified if `countdown` is also supplied.
            expires (float, ~datetime.datetime): Datetime or seconds in the future for the task should expire. The task won't be executed after the expiration time.
        Returns:
            celery.result.AsyncResult: Promise of future evaluation.

        Raises:
            TypeError: If not enough arguments are passed, or too many arguments are passed.  Note that signature checks may be disabled by specifying ``@task(typing=False)``.
            ValueError: If soft_time_limit and time_limit both are set but soft_time_limit is greater than time_limit
            kombu.exceptions.OperationalError: If a connection to the transport cannot be made, or if the connection is lost.
        """
        #print("BoundAgentTaskDefinition.apply_async", self.func.__name__, args, kwargs)
        agentTaskInstance = self.instance()
        #print("here",  args, kwargs )
        return agentTaskInstance.apply_async( args=args, kwargs = kwargs)

    def instance(self, args = None, kwargs=None, **options ) -> AgentTaskInstance:
        """get/Create AgentTaskInstance.

        Returns:
            :class:`AgentTaskInstance`:  object for this task, wrapping arguments and options for multiple task invocation.
        """
        args = args if args else []
        kwargs = kwargs if kwargs else {}
        print("HEREHRHEHR", )
        return AgentTaskInstance.get_or_create(
            task_definition = self.task_definition_version,
            session_version = self.session_version,
            args = args,
            kwargs=kwargs,
            **options
        )

    def i(self, *args, **kwargs) -> AgentTaskInstance: # fertig
        """Create AgentTaskInstance.  Shortcut for ``.i(*a, **k) -> .instance(a, k)``."""
        return self.instance(args=args, kwargs=kwargs)

    def hook_after_run(self, callback_task: "BoundTask"):
        """Register an interceptor that modifies the result of this task."""
        # callback_task is the task that will receive the result of 'self'
        target_instance = callback_task.instance() if hasattr(callback_task, 'instance') else callback_task
        self.instance().taskinstances_after_run_hooks.add(target_instance)
        return self

    def hook_before_run(self, callback_task: "BoundTask"):
        """Register an interceptor that modifies/validates the input of this task."""
        target_instance = callback_task.instance() if hasattr(callback_task, 'instance') else callback_task
        self.instance().taskinstances_before_run_hooks.add(target_instance)
        return self

    def on_error_callback(self, callback_task: "BoundTask"):
        target_instance = callback_task.instance() if hasattr(callback_task, 'instance') else callback_task
        self.instance().taskinstances_on_error_callbacks.add(target_instance)
        return self

    def on_success_callback(self, callback_task: "BoundTask"):
        target_instance = callback_task.instance() if hasattr(callback_task, 'instance') else callback_task
        self.instance().taskinstances_on_success_callbacks.add(target_instance)
        return self

    def __str__(self) -> str:
        return f"<BoundTask {self.task_definition.name} of {self.session_version}>"
