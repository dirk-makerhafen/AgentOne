import abc
from pathlib import Path

from launcher.runtime_env import current_python


class BaseService(abc.ABC):
    """Abstract base class for OS-specific service management."""

    def __init__(self, service_name, display_name, command, config_dir, current_user):
        self.service_name = service_name
        self.display_name = display_name
        self.command = command
        self.config_dir = config_dir
        self.current_user = current_user

    @property
    def python_executable(self) -> str:
        """Interpreter baked into the service; always the checkout's venv."""
        return current_python(Path(self.config_dir))

    def install(self, command_args=None):
        raise NotImplementedError("Each service manager must implement the 'install' method.")

    @abc.abstractmethod
    def uninstall(self, *args, **kwargs):
        """Uninstall the service."""
        pass

    @abc.abstractmethod
    def start(self, *args, **kwargs):
        """Start the service."""
        pass

    @abc.abstractmethod
    def stop(self, *args, **kwargs):
        """Stop the service."""
        pass

    @abc.abstractmethod
    def status(self, *args, **kwargs):
        """Get the status of the service."""
        pass
