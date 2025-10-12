from django.db import models
from core.models.base_model import BaseModel

class System(BaseModel):
    class SystemStatusChoices(models.TextChoices):
        ONLINE = 'online', 'Online'
        OFFLINE = 'offline', 'Offline'
        MAINTENANCE = 'maintenance', 'Maintenance'
    
    OS_CHOICES = [
        ('linux', 'Linux'),
        ('windows', 'Windows'),
        ('osx', 'macOS'),
    ]
    EXECUTOR_MODE_CHOICES = [
        ('local', 'Local Execution (within agent_server3 process)'),
        ('http', 'HTTP Remote Executor (FastAPI client)'),
        ('websocket', 'WebSocket Remote Executor (NAT-traversing client)'),
    ]

    name = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True, default='')
    status = models.CharField(max_length=20, choices=SystemStatusChoices.choices, default=SystemStatusChoices.OFFLINE)
    last_heartbeat = models.DateTimeField(null=True, blank=True)

    os = models.CharField(max_length=10, choices=OS_CHOICES, default='linux', help_text="The operating system of the system.")
    executor_mode = models.CharField(max_length=20, choices=EXECUTOR_MODE_CHOICES, default='local', help_text="Determines how tool calls are executed for agent instances using this system.")
    executor_url = models.URLField(max_length=1024, blank=True, help_text="URL of the remote executor API (e.g., http://1.2.3.4:8000).")
    executor_api_key = models.CharField(max_length=255, blank=True, help_text="API key for the remote executor.")

    def __str__(self):
        return f'{self.name} ({self.status})'

    def as_client_dict(self):
        return {
            'object': 'System',
            'id': self.pk,
            'created_at': self.created_at.isoformat(),
            'name': self.name,
            'description': self.description,
            'status': self.status,
            'last_heartbeat': self.last_heartbeat.isoformat() if self.last_heartbeat else None,
            'executor_mode': self.executor_mode,
            'executor_url': self.executor_url,
            'executor_api_key': self.executor_api_key,
            'os': self.os,
        }
