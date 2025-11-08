from django.db import models
from core.models.base_model import BaseModel
from tools.calls.models.tool_call import ToolCall
import base64
import os

class ConversationMessage(BaseModel):
    agent = models.ForeignKey("agents.Agent", default=None, null=True, on_delete=models.CASCADE, related_name='conversationMessages')
    agentInstance = models.ForeignKey("agents.AgentInstance", on_delete=models.CASCADE, related_name='conversationMessages')
    llmResponse = models.ForeignKey("agents.LLMResponse", default=None, null=True, on_delete=models.SET_DEFAULT, related_name='conversationMessages')
    role = models.CharField(max_length=32)
    hide_from_context = models.BooleanField(default=False)
    pin_to_context = models.BooleanField(default=False)

    def save(self, send_to_client=True, *args, **kwargs):
        if self.hide_from_context is True and self.pin_to_context is True:
            self.pin_to_context = False
        super().save(send_to_client=send_to_client, *args, **kwargs)

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
    toolCall = models.ForeignKey(ToolCall, default=None, null=True, on_delete=models.SET_DEFAULT, related_name='conversationMessageParts')
    tokens =  models.IntegerField(default=0) #?
    index =  models.IntegerField(default=0)
    content = models.CharField(max_length=1000000)
    content_type = models.CharField(max_length=255, choices=ConversationMessagePartContentType.choices, default=ConversationMessagePartContentType.TEXT)

    @property
    def agentInstance(self):
        return self.conversationMessage.agentInstance

    def as_client_dict(self):
        if self.content_type.lower() == "image":
            if self.content.startswith("data:"):
                img = self.content
            elif self.content.startswith("path:"):
                p = self.content.split(":",1)[1]
                if os.path.exists(p):
                    with open(p, "rb") as f:
                        encoded = base64.b64encode(f.read()).decode("ascii")
                        img = f"data:image/jpeg;base64,{encoded}"
                else:
                    img = "Image file no longer exists"
            else:
                img = "No image, error"
        r = {
            'object': 'ConversationMessagePart',
            'id': self.id,
            'conversationMessage_id': self.conversationMessage_id,
            'tool_call_id': self.toolCall_id,
            'tokens': self.tokens,
            'index': self.index,
            'content': self.content if self.content_type.lower() == "text" else img,
            'content_type': self.content_type,
            'content_type_display': self.get_content_type_display(),
        }
        if self.toolCall:
            r.update({
                'function_name': self.toolCall.function_name, 
                'arguments': self.toolCall.arguments, 
                'status': self.toolCall.status, 
                'result': self.toolCall.toolResponses.last().data if self.toolCall.toolResponses.last() else None
            })
        return r
