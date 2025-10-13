from django.db import models
from django.contrib.auth.models import User

from core.models.base_model import BaseModel
from tools.calls.models.tool_call import ToolCall

class MemoryItem(BaseModel):
    agent = models.ForeignKey("agents.Agent", on_delete=models.CASCADE, related_name='memoryItems', null=True, blank=True)
    agentInstance = models.ForeignKey("agents.AgentInstance", on_delete=models.CASCADE, related_name='memoryItems', null=True, blank=True)
    conversationMessage = models.ForeignKey("agents.ConversationMessage", null=True, default=None, on_delete=models.CASCADE, related_name='memoryItems')

    toolCall = models.OneToOneField(ToolCall, on_delete=models.CASCADE, related_name='memoryItem', null=True, blank=True)    
    next_version = models.OneToOneField("self", on_delete=models.SET_DEFAULT, related_name='prev_version', null=True, default=None)
    
    track = models.CharField(max_length=128, null=True, blank=True) # New field
    layer = models.CharField(max_length=128, null=True, blank=True) # New field
    
    index = models.IntegerField()
    
    class Meta:
        indexes = [
            models.Index(fields=['track', 'layer']),
        ]

    def __str__(self):
        return f'{self.track}/{self.layer}[{self.index}]'
    
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


    @property
    def content(self): return self.data.get("value", None)
    @content.setter
    def content(self, data): self.data["value"] = data  


    def as_client_dict(self):
        return {
            'object': 'MemoryItem',
            'id': self.pk,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'track': self.track,
            'layer': self.layer,
            'content': self.value,
            'tokens': len(self.value) // 3.8,
            'index': self.index,
            'agentInstance_id': self.agentInstance_id,
            'conversationMessage_id': self.conversationMessage_id,
            'toolCall_id': self.toolCall_id,
            'prev_version_id': self.prev_version.pk if hasattr(self, "prev_version") and self.prev_version else None
        }
