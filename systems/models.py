from django.db import models
from common.models import ModelWithJsonData

class System(ModelWithJsonData):
    STATUS_CHOICES = [
        ('online', 'Online'),
        ('offline', 'Offline'),
        ('maintenance', 'Maintenance'),
    ]
    OS_CHOICES = [
        ('linux', 'Linux'),
        ('windows', 'Windows'),
        ('osx', 'macOS'),
    ]

    name = models.CharField(max_length=255, unique=True)

    description = models.TextField(blank=True, default='')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='offline')
    last_heartbeat = models.DateTimeField(null=True, blank=True)

    # Remote Executor Configuration
    is_remote_executor = models.BooleanField(default=False, help_text="If True, this system is a lightweight remote executor, not a full deployment target.")
    executor_url = models.URLField(max_length=1024, blank=True, help_text="URL of the remote executor API (e.g., http://1.2.3.4:8000).")
    executor_api_key = models.CharField(max_length=255, blank=True, help_text="API key for the remote executor.")
    
    EXECUTOR_MODE_CHOICES = [
        ('local', 'Local Execution (within agent_server3 process)'),
        ('http', 'HTTP Remote Executor (FastAPI client)'),
        ('websocket', 'WebSocket Remote Executor (NAT-traversing client)'),
    ]
    executor_mode = models.CharField(max_length=20, choices=EXECUTOR_MODE_CHOICES, default='local', help_text="Determines how tool calls are executed for agent instances using this system.")

    def __str__(self):
        return f'{self.name} ({self.status})'

    def save(self, send_to_clients=True, *args, **kwargs):
        from dashboard.tasks import send_object_to_clients
        super().save(*args, **kwargs)
        if send_to_clients:
            send_object_to_clients(self)

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
        }