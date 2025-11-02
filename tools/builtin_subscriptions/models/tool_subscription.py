from django.db import models
from core.models.base_model import BaseModel

class ToolSubscription(BaseModel):
    agent = models.ForeignKey("agents.Agent", on_delete=models.CASCADE, related_name='tool_subscriptions')
    agentInstance = models.ForeignKey("agents.AgentInstance", on_delete=models.CASCADE, related_name='tool_subscriptions')
    creating_tool_call = models.ForeignKey("calls.ToolCall", null=True, default=None, on_delete=models.SET_NULL, related_name='created_subscriptions')
    
    subscription_id = models.CharField(max_length=128, help_text="A unique identifier for the subscription, provided by the agent.")
    tool_name = models.CharField(max_length=64, help_text="The name of the tool to execute (e.g., 'python', 'shell').")
    is_active = models.BooleanField(default=True)


    def as_client_dict(self):
        return {
            'object': 'ToolSubscription',
            'id': self.id,
            'created_at': self.created_at.isoformat(),
            'agent_id': self.agent_id,
            'agentInstance_id': self.agentInstance_id,
            'subscription_id': self.subscription_id,
            'tool_name': self.tool_name,
            'is_active': self.is_active,
        }

    class Meta:
        unique_together = ('agentInstance', 'subscription_id')

    @property
    def arguments(self):
        return self.data.get('arguments', {})

    @arguments.setter
    def arguments(self, data):
        self.data['arguments'] = data

    def __str__(self):
        return f"Subscription '{self.subscription_id}' for {self.agentInstance} (Tool: {self.tool_name}, Active: {self.is_active})"
