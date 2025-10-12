from django.db import models
from django.contrib.auth.models import User

from core.models.base_model import BaseModel
from tools.definitions.models.tool_definition import ToolDefinition

class Agent(BaseModel):
    agent_pk = models.AutoField(primary_key=True)
    owners = models.ManyToManyField(User, related_name='owned_agents', blank=True)
    name = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True, default='')
    aimodel = models.ForeignKey("providers.AiModel", default=None, on_delete=models.CASCADE, related_name='agents', null=True)
    available_tools = models.ManyToManyField(ToolDefinition, blank=True, related_name='agents')

    def __str__(self):
        return f'Agent: {self.name}'

    def as_client_dict(self):
        return {
            'object': 'Agent', 
            'id': self.agent_pk, 
            'created_at': self.created_at.isoformat(), 
            'updated_at': self.updated_at.isoformat(),
            'name': self.name, 
            'description': self.description,
            'available_tools':  [tool.pk for tool in self.available_tools.all()],
        }

    def get_delete_broadcast_payload(self):
        return {
            'object': 'AgentDeleted',
            'agent_pk': self.agent_pk
        }
