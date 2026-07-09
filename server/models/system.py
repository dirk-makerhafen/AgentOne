"""System model representing a remote or local execution environment."""
from __future__ import annotations

from datetime import datetime

from django.db import models

from server.models.base_model import BaseModel


class SystemStatus(models.TextChoices):
    """Operational status of a system."""

    ONLINE = "online", "Online"
    OFFLINE = "offline", "Offline"
    MAINTENANCE = "maintenance", "Maintenance"


class SystemOS(models.TextChoices):
    """Supported operating system identifiers."""

    LINUX = "LINUX"
    WINDOWS = "WINDOWS"
    OSX = "OSX"


class SystemConnectionMode(models.TextChoices):
    """How tool calls are dispatched to the system."""

    LOCAL = "LOCAL", "Local Execution (within agent_server3 process)"
    HTTP = "HTTP", "HTTP Remote Executor (FastAPI client)"
    WEBSOCKET = "WEBSOCKET", "WebSocket Remote Executor (NAT-traversing client)"


class System(BaseModel):
    """A registered execution environment (local or remote) that agents can use
    for tool execution."""

    name: str = models.CharField(max_length=255, unique=True)
    description: str = models.TextField(blank=True, default="")

    os: str = models.CharField( max_length=10, choices=SystemOS, default=SystemOS.LINUX, help_text="The operating system of the system.")
    last_heartbeat: datetime | None = models.DateTimeField(null=True, blank=True)
    status: str = models.CharField( max_length=20, choices=SystemStatus.choices, default=SystemStatus.OFFLINE)

    executor_mode: str = models.CharField( max_length=20, choices=SystemConnectionMode, default=SystemConnectionMode.LOCAL, help_text="Determines how tool calls are executed for agent instances using this system.")
    executor_url: str = models.URLField( max_length=1024, blank=True, help_text="URL of the remote executor API (e.g., http://1.2.3.4:8000).")
    executor_api_key: str = models.CharField( max_length=255, blank=True, help_text="API key for the remote executor.")

    def __str__(self) -> str: 
        """Return a string identifying the system and its current status.""" 
        return f"{self.name} ({self.status})"
