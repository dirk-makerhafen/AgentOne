from django.db import models
from core.models.base_model import BaseModel

class AgentToAgentMessage(BaseModel):
    sender_agent = models.ForeignKey("agents.Agent", on_delete=models.CASCADE, related_name='sent_inter_agent_messages')
    sender_agentInstance = models.ForeignKey("agents.AgentInstance", on_delete=models.CASCADE, related_name='sent_inter_agent_messages')
    sender_conversationMessage = models.ForeignKey("agents.ConversationMessage", null=True, default=None, on_delete=models.CASCADE, related_name='sent_inter_agent_messages')
    sender_toolCall = models.ForeignKey("calls.ToolCall", on_delete=models.CASCADE, related_name='sent_inter_agent_messages', null=True, default=None)

    receiver_agent = models.ForeignKey("agents.Agent", on_delete=models.CASCADE, related_name='received_inter_agent_messages')
    receiver_agentInstance = models.ForeignKey("agents.AgentInstance", on_delete=models.CASCADE, related_name='received_inter_agent_messages')
    receiver_conversationMessage = models.ForeignKey("agents.ConversationMessage", null=True, default=None, on_delete=models.CASCADE, related_name='received_inter_agent_messages')

    @property
    def message(self):
        return self.data.get('content', {})

    @message.setter
    def message(self, data):
        self.data['content'] = data

    def as_client_dict(self):
        return {
            'object': 'AgentToAgentMessage',
            'id': self.id,
            'created_at': self.created_at.isoformat(),
            'sender_agentInstance_id': self.sender_agentInstance_id,
            'sender_agent_name': self.sender_agent.name,
            'receiver_agentInstance_id': self.receiver_agentInstance_id,
            'receiver_agent_name': self.receiver_agent.name,
            'message': self.message,
            'sender_toolCall_id': self.sender_toolCall_id,
        }

    def __str__(self):
        return f"Message from {self.sender_agentInstance_id} to {self.receiver_agentInstance_id} at {self.created_at}"

    class Meta:
        ordering = ['-created_at']
