from django.db import models
from core.models.base_model import BaseModel

class ToolResponse(BaseModel):
    agent = models.ForeignKey("agents.Agent", on_delete=models.CASCADE, related_name='toolResponses')
    agentInstance = models.ForeignKey("agents.AgentInstance", on_delete=models.CASCADE, related_name='toolResponses')
    toolCall = models.ForeignKey("calls.ToolCall", null=True, default=None, on_delete=models.CASCADE, related_name='toolResponses')
    status = models.CharField(max_length=32, null=False, default='unknown')

    def save(self, send_to_client=True, *args, **kwargs):
        # The ToolCall object's update includes the result, so sending the response separately is redundant.
        super().save(send_to_client=False, *args, **kwargs)
