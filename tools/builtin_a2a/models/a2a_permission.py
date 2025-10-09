from django.db import models

class AgentToAgentPermission(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    source_instance = models.ForeignKey("agents.AgentInstance", on_delete=models.CASCADE, related_name='source_permissions')
    target_instance = models.ForeignKey("agents.AgentInstance", on_delete=models.CASCADE, related_name='target_permissions')
    can_send = models.BooleanField(default=False, help_text='Source can send messages to Target')
    can_receive = models.BooleanField(default=False, help_text='Source can receive messages from Target')

    class Meta:
        unique_together = ('source_instance', 'target_instance')

    def __str__(self):
        return f'{self.source_instance} -> {self.target_instance}'
