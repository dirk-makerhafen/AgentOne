from django.db import models
from common.models import ModelWithJsonData

class PythonToolVar(ModelWithJsonData):
    agent = models.ForeignKey("agent.Agent", on_delete=models.CASCADE, related_name='python_tool_vars')
    agentInstance = models.ForeignKey("agent.AgentInstance", on_delete=models.CASCADE, related_name='python_tool_vars')
    toolCall = models.ForeignKey("tools_common.ToolCall", on_delete=models.CASCADE, related_name='python_tool_vars', null=True, default=None)
    action = models.CharField(max_length=512,default="add") # add/update/delete

    key = models.CharField(max_length=512) # The variable name (e.g., 'my_string')
    next_version = models.OneToOneField("PythonToolVar", on_delete=models.CASCADE, related_name='prev_version', null=True, default=None)

    def save(self, send_to_client=True, *args, **kwargs):
        from dashboard.tasks import send_object_to_clients
        is_new = self.pk is None
        super().save(*args, **kwargs)
        if send_to_client:
            send_object_to_clients(self)

    @property
    def value(self): return self.data.get("value", None)
    @value.setter
    def value(self, data): self.data["value"] = data  

    def __str__(self):
        return f"VARS:{self.key} ({self.agentInstance.name})"

    def as_client_dict(self):
        # This will be for UI display if needed, similar to MemoryItem
        return {
            'object': 'PythonToolVar',
            'id': self.id,
            'created_at': self.created_at.isoformat(),
            'agentInstance_id': self.agentInstance_id,
            'key': self.key,
            'value': self.value,
            'toolCall_id': self.toolCall_id,
        }
