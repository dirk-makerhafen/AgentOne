from django.db import models
from common.models import ModelWithJsonData

class AgentInstanceDescriptionLog(ModelWithJsonData):
    toolCall = models.ForeignKey("tools_common.ToolCall", on_delete=models.CASCADE, related_name='description_logs', null=True, default=None)
    agent = models.ForeignKey('agent.Agent', on_delete=models.CASCADE, related_name='description_logs')
    agent_instance = models.ForeignKey('agent.AgentInstance', on_delete=models.CASCADE, related_name='description_logs')
    description = models.TextField()

    def __str__(self):
        return f'Description for {self.agent_instance} at {self.created_at}'

class InterAgentMessage(ModelWithJsonData):
    """
    Represents a message sent from one agent instance to another.
    """
    sender_agent = models.ForeignKey("agent.Agent", on_delete=models.CASCADE, related_name='sent_inter_agent_messages')
    sender_agentInstance = models.ForeignKey("agent.AgentInstance", on_delete=models.CASCADE, related_name='sent_inter_agent_messages')
    sender_conversationMessage = models.ForeignKey("agent.ConversationMessage", null=True, default=None, on_delete=models.CASCADE, related_name='sent_inter_agent_messages')
    sender_toolCall = models.ForeignKey("tools_common.ToolCall", on_delete=models.CASCADE, related_name='sent_inter_agent_messages', null=True, default=None)

    receiver_agent = models.ForeignKey("agent.Agent", on_delete=models.CASCADE, related_name='received_inter_agent_messages')
    receiver_agentInstance = models.ForeignKey("agent.AgentInstance", on_delete=models.CASCADE, related_name='received_inter_agent_messages')
    receiver_conversationMessage = models.ForeignKey("agent.ConversationMessage", null=True, default=None, on_delete=models.CASCADE, related_name='received_inter_agent_messages')

    @property
    def message(self):
        return self.data.get('content', {})

    @message.setter
    def message(self, data):
        self.data['content'] = data

    def save(self, send_to_client=True, *args, **kwargs):
        from dashboard.tasks import send_object_to_clients
        super().save(*args, **kwargs)
        if send_to_client:
            send_object_to_clients(self)

    def as_client_dict(self):
        return {
            'object': 'InterAgentMessage',
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

class InstancePermission(models.Model):
    """
    Defines a one-way permission from a source agent instance to a target agent instance.
    """
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    source_instance = models.ForeignKey("agent.AgentInstance", on_delete=models.CASCADE, related_name='source_permissions')
    target_instance = models.ForeignKey("agent.AgentInstance", on_delete=models.CASCADE, related_name='target_permissions')
    can_send = models.BooleanField(default=False, help_text='Source can send messages to Target')
    can_receive = models.BooleanField(default=False, help_text='Source can receive messages from Target')

    class Meta:
        unique_together = 'source_instance', 'target_instance'

    def __str__(self):
        return f'{self.source_instance} -> {self.target_instance}'
