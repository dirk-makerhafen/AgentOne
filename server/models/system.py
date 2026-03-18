from django.db import models
from server.models.base_model import BaseModel

class SystemStatus(models.TextChoices):
    ONLINE = 'online', 'Online'
    OFFLINE = 'offline', 'Offline'
    MAINTENANCE = 'maintenance', 'Maintenance'

class SystemOS(models.TextChoices):
    LINUX = 'LINUX'
    WINDOWS = 'WINDOWS'
    OSX = 'OSX'

class SystemConnectionMode(models.TextChoices):
    LOCAL = "LOCAL", 'Local Execution (within agent_server3 process)'
    HTTP = "HTTP", 'HTTP Remote Executor (FastAPI client)'
    WEBSOCKET = "WEBSOCKET", 'WebSocket Remote Executor (NAT-traversing client)'

class System(BaseModel):
    name           = models.CharField(max_length=255, unique=True)
    description    = models.TextField(blank=True, default='')

    os               = models.CharField(max_length=10, choices=SystemOS, default=SystemOS.LINUX, help_text="The operating system of the system.")
    last_heartbeat = models.DateTimeField(null=True, blank=True)
    status         = models.CharField(max_length=20, choices=SystemStatus.choices, default=SystemStatus.OFFLINE)

    executor_mode    = models.CharField(max_length=20, choices=SystemConnectionMode, default=SystemConnectionMode.LOCAL, help_text="Determines how tool calls are executed for agent instances using this system.")
    executor_url     = models.URLField(max_length=1024, blank=True, help_text="URL of the remote executor API (e.g., http://1.2.3.4:8000).")
    executor_api_key = models.CharField(max_length=255, blank=True, help_text="API key for the remote executor.")

    def __str__(self):
        return f'{self.name} ({self.status})'
