from django.db import models
from core.models.base_model import BaseModel

class MemoryItem(BaseModel):
    agent = models.ForeignKey("agents.Agent", on_delete=models.CASCADE, related_name='memoryItems')
    agentInstance = models.ForeignKey("agents.AgentInstance", on_delete=models.CASCADE, related_name='memoryItems')
    conversationMessage = models.ForeignKey("agents.ConversationMessage", null=True, default=None, on_delete=models.CASCADE, related_name='memoryItems')
    toolCall = models.ForeignKey("calls.ToolCall", on_delete=models.SET_DEFAULT, related_name='memoryItems', default=None, null=True)
    next_version = models.OneToOneField("self", on_delete=models.SET_DEFAULT, related_name='prev_version', null=True, default=None)
 
    track = models.CharField(max_length=128, null=True, blank=True) # New field
    layer = models.CharField(max_length=128, null=True, blank=True) # New field
    index = models.IntegerField(default=0)

    @property
    def first_version(self):
        first_version = self
        while first_version.prev_version is not None:
            first_version = first_version.prev_version
        return first_version

    @property
    def latest_version(self):
        latest_version = self
        while latest_version.next_version is not None:
            latest_version = latest_version.next_version
        return latest_version

    @property
    def value(self): return self.data.get("value", None)
    @value.setter
    def value(self, data): self.data["value"] = data  

    def as_client_dict(self):
        return {
            'object': 'MemoryItem',
            'id': self.id,
            'created_at': self.created_at.isoformat(),
            'track': self.track,
            'layer': self.layer,
            'content': self.value,
            'tokens': len(self.value) // 3.8,
            'index': self.index,
            'agentInstance_id': self.agentInstance_id,
        }
