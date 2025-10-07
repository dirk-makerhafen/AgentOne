from django.db import models
from django.contrib.auth.models import User

from core.models.base_model import BaseModel

class Agent(BaseModel):
    agent_pk = models.AutoField(primary_key=True)
    owners = models.ManyToManyField(User, related_name='owned_agents', blank=True)
    name = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True, default='')
    aimodel = models.ForeignKey("providers.AiModel", default=None, on_delete=models.CASCADE, related_name='agents', null=True)
    available_tools = models.ManyToManyField("definitions.ToolDefinition", related_name='agents_using_this_tool', blank=True)

    def __str__(self):
        return f'Agent: {self.name}'

    def save(self, send_to_client=True, *args, **kwargs):
        super().save(*args, **kwargs)
        if send_to_client:
            self.send_object_to_clients()

    def as_client_dict(self):
        return {
            'object': 'Agent', 
            'id': self.agent_pk, 
            'created_at': self.created_at.isoformat(), 
            'updated_at': self.updated_at.isoformat(),
            'name': self.name, 
            'description': self.description,
            'available_tools': list(self.available_tools.values_list('pk', flat=True)),
        }
