from django.db import models
from common.models import ModelWithJsonData

class ToolSubscription(ModelWithJsonData):
    """
    Represents a subscription to a tool call that should be re-executed
    before generating a new LLM query to provide up-to-date context.
    """
    agent = models.ForeignKey("agent.Agent", on_delete=models.CASCADE, related_name='tool_subscriptions')
    agentInstance = models.ForeignKey("agent.AgentInstance", on_delete=models.CASCADE, related_name='tool_subscriptions')
    creating_tool_call = models.ForeignKey("tools_common.ToolCall", null=True, default=None, on_delete=models.SET_NULL, related_name='created_subscriptions')
    
    subscription_id = models.CharField(max_length=128, help_text="A unique identifier for the subscription, provided by the agent.")
    tool_name = models.CharField(max_length=64, help_text="The name of the tool to execute (e.g., 'python', 'shell').")
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ('agentInstance', 'subscription_id')

    @property
    def arguments(self):
        return self.data.get('arguments', {})

    @arguments.setter
    def arguments(self, data):
        self.data['arguments'] = data

    def save(self, send_to_client=True, *args, **kwargs):
        from dashboard.tasks import send_object_to_clients
        super().save(*args, **kwargs)
        if send_to_client:
            # We will need a new client-side object renderer for this later.
            # send_object_to_clients(self)
            pass

    def __str__(self):
        return f"Subscription '{self.subscription_id}' for {self.agentInstance} (Tool: {self.tool_name}, Active: {self.is_active})"
