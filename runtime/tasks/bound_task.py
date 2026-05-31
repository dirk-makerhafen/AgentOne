from __future__ import annotations
import importlib.util
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

from runtime.runtime_folder import RuntimeFolder
from server.models.enums.task_enums import TaskCallStatusDetail
from server.models.tasks.task_instance import TaskInstance

if TYPE_CHECKING:
    from runtime.session.session import Session
    from server.models.tasks.task_definition_version import TaskDefinitionVersion
    from server.models.tasks.agent_task_call import AgentTaskCall


class BoundTask:
    """
    A task definition bound to a specific session.

    Provides ``.call()`` for synchronous execution, ``.delay()`` /
    ``.apply_async()`` for asynchronous dispatch, and hook registration
    methods (``hook_after_run``, ``hook_before_run``, ``on_success_callback``,
    ``on_error_callback``).

    Runtime files are resolved through versioned runtime folders
    (``~/.agentone/runtime/<version_pk>/``) extracted from the install repo,
    not from the source tree.
    """

    def __init__(self, session: Session, task_definition_version: TaskDefinitionVersion) -> None:
        self.session = session
        self.task_definition_version = task_definition_version
        self.task_definition = task_definition_version.task_definition

    def call(self, *args: Any, **kwargs: Any) -> Any:
        """
        Execute the task synchronously.

        Raises ``TypeError`` for CHAIN/GROUP tasks, ``FileNotFoundError`` if
        the script file is missing, and ``AttributeError`` if the target
        function is not found.

        The script file is loaded from the versioned runtime folder
        (``~/.agentone/runtime/<pk>/``), ensuring the exact versioned copy
        is used.

        If the task definition is *bound* the session is passed as the first
        argument.
        """
        # Chain/group tasks have no Python file — they execute via AgentTaskRun.apply()
        if self.task_definition_version.task_execution_mode in ("CHAIN", "GROUP", "MAP"):
            raise TypeError(
                f"Task '{self.task_definition.name}' has execution_mode="
                f"{self.task_definition_version.task_execution_mode} "
                f"and has no callable Python function. "
                f"Use apply_async() or instance().apply_async() instead."
            )

        file_name = self._runtime_file_name()
        runtime = RuntimeFolder(self.task_definition_version)
        folder = runtime.ensure_folder()
        file_path = folder / file_name

        if not file_path.exists():
            raise FileNotFoundError(
                f"Script file not found in runtime folder: {file_path}"
            )

        # Ensure the runtime folder is on sys.path so sibling imports work
        if str(folder) not in sys.path:
            sys.path.insert(0, str(folder))

        if not self.task_definition_version.function_name:
            raise ValueError(
                f"TaskDefinitionVersion '{self.task_definition_version}' has no function_name set"
            )

        spec = importlib.util.spec_from_file_location(f"_bound_{self.task_definition.name}", file_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        func = getattr(module, self.task_definition_version.function_name, None)
        if func is None:
            raise AttributeError(
                f"Function '{self.task_definition_version.function_name}' not found in {file_path}"
            )

        if self.task_definition_version.bound:
            return func(self.session, *args, **kwargs)
        return func(*args, **kwargs)

    def _runtime_file_name(self) -> str:
        """Return the file name (not full path) for this task's runtime file.

        The ``path`` field on ``TaskDefinitionVersion`` may store an absolute
        source path; we only need the basename since the install repo's tree
        SHA points at the manifest folder containing that file.
        """
        raw = (self.task_definition_version.path or "")
        return Path(raw).name

    def get_calls(self) -> Any:
        """Return all AgentTaskCall instances for this task in this session."""
        from server.models.tasks.agent_task_call import AgentTaskCall

        return AgentTaskCall.objects.filter(
            session=self.session.model,
            task_definition=self.task_definition,
        )

    def lastest_result(self) -> Any:
        """Return the result of the most recent successful call, or *None*."""
        from server.models.tasks.agent_task_call import AgentTaskCall

        query = self.get_calls().exclude(taskcall_result_run=None).filter(
            status_detail=TaskCallStatusDetail.ENDED_SUCCESS
        )
        task_call = query.last()
        return task_call.get_result(timeout=0) if task_call else None

    def delay(self, *args: Any, **kwargs: Any) -> Any:
        """Star-argument shorthand for :meth:`apply_async`."""
        return self.apply_async(args, kwargs)

    def apply_async(
        self,
        args: tuple | None = None,
        kwargs: dict | None = None,
        countdown: int = 0,
        eta: Any = None,
        expires: Any = None,
        retry: bool = False,
        time_limit: int = 0,
        soft_time_limit: int = 0,
        priority: int = 0,
         **options: Any
    ) -> Any:
        """
        Dispatch the task asynchronously via a TaskInstance.

        Parameters
        ----------
        args : tuple | None
            Positional arguments for the task.
        kwargs : dict | None
            Keyword arguments for the task.
        countdown : int
            Seconds to wait before execution.
        eta : Any
            Absolute datetime for execution.
        expires : Any
            Absolute datetime or seconds after which the task expires.
        retry : bool
            Whether to retry on failure.
        time_limit : int
            Hard time limit in seconds.
        soft_time_limit : int
            Soft time limit in seconds.
        priority : int
            Task priority.
        """
        task_instance = self.instance()
        return task_instance.apply_async(args=args, kwargs=kwargs, **options)

    def instance(self, args: Any = None, kwargs: Any = None, **options: Any) -> TaskInstance:
        """
        Get or create a TaskInstance for this task bound to the current session
        version.

        Returns
        -------
        TaskInstance
        """
        args = args if args else []
        kwargs = kwargs if kwargs else {}
        return TaskInstance.get_or_create(
            task_definition=self.task_definition_version,
            session_version=self.session.get_version_model(),
            args=args,
            kwargs=kwargs,
            **options,
        )

    def i(self, *args: Any, **kwargs: Any) -> TaskInstance:
        """Shortcut for ``.instance(args=args, kwargs=kwargs)``."""
        return self.instance(args=args, kwargs=kwargs)

    def hook_after_run(self, callback_task: BoundTask) -> BoundTask:
        """Register a task whose result receives the output of *self*."""
        target_instance = callback_task.instance() if hasattr(callback_task, 'instance') else callback_task
        self.instance().taskinstances_after_run_hooks.add(target_instance)
        return self

    def hook_before_run(self, callback_task: BoundTask) -> BoundTask:
        """Register a task that modifies/validates the input of *self*."""
        target_instance = callback_task.instance() if hasattr(callback_task, 'instance') else callback_task
        self.instance().taskinstances_before_run_hooks.add(target_instance)
        return self

    def on_error_callback(self, callback_task: BoundTask) -> BoundTask:
        """Register a task to run when *self* fails."""
        target_instance = callback_task.instance() if hasattr(callback_task, 'instance') else callback_task
        self.instance().taskinstances_on_error_callbacks.add(target_instance)
        return self

    def on_success_callback(self, callback_task: BoundTask) -> BoundTask:
        """Register a task to run when *self* succeeds."""
        target_instance = callback_task.instance() if hasattr(callback_task, 'instance') else callback_task
        self.instance().taskinstances_on_success_callbacks.add(target_instance)
        return self

    def __str__(self) -> str:
        return f"<BoundTask {self.task_definition.name} of {self.session}>"
