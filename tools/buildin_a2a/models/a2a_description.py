from django.db import models
from core.models.base_model import BaseModel
class AgentToAgentDescription(BaseModel):
    toolCall = models.ForeignKey("calls.ToolCall", on_delete=models.CASCADE, related_name='description_logs', null=True, default=None)
    agent = models.ForeignKey('agents.Agent', on_delete=models.CASCADE, related_name='description_logs')
    agent_instance = models.ForeignKey('agents.AgentInstance', on_delete=models.CASCADE, related_name='description_logs')
    description = models.TextField()

    def __str__(self):
        return f'Description for {self.agent_instance} at {self.created_at}'
