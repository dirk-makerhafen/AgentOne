from django.db import models

from core.models.base_model import BaseModel

class ToolInstallationLog(BaseModel):
    class LogLevel(models.TextChoices):
        INFO = 'info', 'Info'
        ERROR = 'error', 'Error'

    tool_installation = models.ForeignKey("definitions.ToolInstallation", on_delete=models.CASCADE, related_name='logs')
    timestamp = models.DateTimeField(auto_now_add=True)
    level = models.CharField(max_length=10, choices=LogLevel.choices, default=LogLevel.INFO)
    message = models.TextField()

    class Meta:
        ordering = ['timestamp']

    def __str__(self):
        return f"[{self.timestamp}] [{self.level.upper()}] {self.message}"

    def save(self, send_to_client=True, *args, **kwargs):
        super().save(*args, **kwargs)
        if send_to_client:
            self.send_object_to_clients()

    def as_client_dict(self):
        return {
            'object': 'ToolInstallationLog',
            'id': self.pk,
            'tool_installation_id': self.tool_installation.pk,
            'timestamp': self.timestamp.isoformat(),
            'level': self.level,
            'message': self.message
        }
