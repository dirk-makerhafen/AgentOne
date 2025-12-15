from django.db import models
from core.models.base_model import BaseModel
import json

class KVItem(BaseModel):
    key = models.CharField(max_length=255, unique=True, db_index=True)
    value = models.JSONField()
    agentInstance = models.ForeignKey(
        "agents.AgentInstance",
        on_delete = models.CASCADE,
        related_name = 'kv_items',
        help_text = "The agent instance that owns this key-value item."
    )

    class Meta:
        verbose_name = "Key-Value Item"
        verbose_name_plural = "Key-Value Items"
        ordering = ['key']

    def __str__(self):
        return f"{self.key}: {json.dumps(self.value, indent=2)[:100]}..." # Show first 100 chars of JSON

    def as_client_dict(self):
        return {
            'object': 'KVItem',
            'id': self.id,
            'key': self.key,
            'value': self.value,
            'agent_instance_id': self.agentInstance_id,
        }