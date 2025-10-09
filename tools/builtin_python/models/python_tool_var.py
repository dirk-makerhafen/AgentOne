from django.db import models
from core.models.base_model import BaseModel

class PythonToolVar(BaseModel):
    agent = models.ForeignKey("agents.Agent", on_delete=models.CASCADE, related_name='python_tool_vars')
    agentInstance = models.ForeignKey("agents.AgentInstance", on_delete=models.CASCADE, related_name='python_tool_vars')
    toolCall = models.ForeignKey("calls.ToolCall", on_delete=models.CASCADE, related_name='python_tool_vars', null=True, default=None)
    action = models.CharField(max_length=512,default="add")

    key = models.CharField(max_length=512)
    next_version = models.OneToOneField("self", on_delete=models.CASCADE, related_name='prev_version', null=True, default=None)

    @property
    def value(self): return self.data.get("value", None)
    @value.setter
    def value(self, data): self.data["value"] = data  

    def __str__(self):
        return f"VARS:{self.key} ({self.agentInstance.name})"

    def as_client_dict(self):
        return {
            'object': 'PythonToolVar',
            'id': self.id,
            'created_at': self.created_at.isoformat(),
            'agentInstance_id': self.agentInstance_id,
            'key': self.key,
            'value': self.value,
            'toolCall_id': self.toolCall_id,
        }
