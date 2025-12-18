from django.db import models
from core.models.base_model import BaseModel
import base64
import os


class ConversationMessage(BaseModel):
    agent = models.ForeignKey("agents.Agent", default=None, null=True, on_delete=models.CASCADE, related_name='conversationMessages')
    agentInstance = models.ForeignKey("agents.AgentInstance", on_delete=models.CASCADE, related_name='conversationMessages')
    llmResponse = models.ForeignKey("agents.LLMResponse", default=None, null=True, on_delete=models.SET_DEFAULT, related_name='conversationMessages')
    role = models.CharField(max_length=32)
    hide_from_context = models.BooleanField(default=False)
    pin_to_context = models.BooleanField(default=False)
    trigger_query = models.BooleanField(default=False)

    def save(self, send_to_client=True, *args, **kwargs):
        if self.hide_from_context is True and self.pin_to_context is True:
            self.pin_to_context = False
        super().save(send_to_client=send_to_client, *args, **kwargs)

    def add_part(self, content, content_type="TEXT"):
        ConversationMessagePart.objects.create(
            conversationMessage=self,
            content=content,
            content_type=content_type,
        )

    def as_client_dict(self):
        message = {
            'object': 'ConversationMessage', "id": self.id,  
            "agent_id": self.agent_id,  
            "agentInstance_id": self.agentInstance_id, 
            'created_at': self.created_at.isoformat(), 
            'role': self.role,
            'hide_from_context': self.hide_from_context,
            'pin_to_context': self.pin_to_context,
            'parts': [p.as_client_dict() for p in self.conversationMessageParts.all()]
        }
        return message


class ConversationMessagePart(BaseModel):
    class ConversationMessagePartContentType(models.TextChoices):
        TEXT = 'TEXT', 'Text'
        IMAGE = 'IMAGE', 'Image'

    conversationMessage = models.ForeignKey(ConversationMessage, default=None, null=True, on_delete=models.SET_DEFAULT, related_name='conversationMessageParts')
    tokens =  models.IntegerField(default=0) #?
    index =  models.IntegerField(default=0)
    content = models.CharField(max_length=1000000)
    content_type = models.CharField(max_length=255, choices=ConversationMessagePartContentType.choices, default=ConversationMessagePartContentType.TEXT)

    @property
    def agentInstance(self):
        return self.conversationMessage.agentInstance

    def as_client_dict(self):
        content = self.content
        if self.content_type == self.ConversationMessagePartContentType.IMAGE:
            if self.content.startswith("data:"):
                pass # Already a data URL
            elif self.content.startswith("path:"):
                path_str = self.content.split(":", 1)[1]
                if os.path.exists(path_str):
                    with open(path_str, "rb") as f:
                        encoded = base64.b64encode(f.read()).decode("ascii")
                        content = f"data:image/jpeg;base64,{encoded}"
                else:
                    content = "data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7" # 1x1 transparent gif
            else:
                content = "data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7"

        data = {
            'object': 'ConversationMessagePart',
            'id': self.id,
            'conversationMessage_id': self.conversationMessage_id,
            'tool_call_id': None, # Default to null
            'tokens': self.tokens,
            'index': self.index,
            'content': content,
            'content_type': self.content_type,
        }

        return data
