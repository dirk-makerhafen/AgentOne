from django.db import models
from core.models.base_model import BaseModel
from tools.calls.models.tool_call import ToolCall

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
            'parts': [],
            'role': self.role,
            'hide_from_context': self.hide_from_context,
            'pin_to_context': self.pin_to_context
        }
        parts = []
        for index, conversationMessagePart in enumerate(self.data.get("parts",[])):
            if conversationMessagePart.get("content","").strip() == '':
                continue
            if "tcId" not in conversationMessagePart and "toolCall__id" not in conversationMessagePart:
                content = conversationMessagePart.get("content","")
                parts.append({'content': content, "pnr": index, "tokens": len(content) // 3.8})
                continue

            try:
                tcid = conversationMessagePart.get('tcId',conversationMessagePart.get("toolCall__id")) 
                toolCall = ToolCall.objects.get(id=int(tcid))
                content = conversationMessagePart.get("content","")
                tool_call_part_data = {'content': content, "pnr": index, 'tool_call_id': toolCall.id, 'function_name': toolCall.function_name, 'arguments': toolCall.arguments, 'status': toolCall.status, "tokens": len(content) // 3.8, 'result': toolCall.toolResponses.last().data if toolCall.toolResponses.last() else None}
                parts.append(tool_call_part_data)
            except self.toolCalls.model.DoesNotExist:
                pass
        message['parts'] = parts
        return message
