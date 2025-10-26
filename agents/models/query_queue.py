from django.db import models
from core.models.base_model import BaseModel

class QueryQueue(BaseModel):
    class QueryQueueStatusChoices(models.TextChoices):
        QUEUED = 'QUEUED', 'Queued'
        PROCESSING = 'PROCESSING', 'Processing'
        DONE = 'DONE', 'Done'
        ERROR = 'ERROR', 'Error'

    agent_instance = models.OneToOneField(
        "agents.AgentInstance",
        on_delete=models.CASCADE,
        related_name='queue_entry',
        primary_key=True
    )
    status = models.CharField(
        max_length=20,
        choices=QueryQueueStatusChoices.choices,
        default=QueryQueueStatusChoices.QUEUED
    )

    class Meta:
        ordering = ['created_at'] # Ensures FIFO ordering

    def __str__(self):
        return f"Queue entry for Agent Instance {self.agent_instance.instance_pk} ({self.status})"
