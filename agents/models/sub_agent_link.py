from django.db import models
from core.models.base_model import BaseModel

class SubAgentLink(BaseModel):
    supervisor_instance = models.ForeignKey(
        'agents.AgentInstance',
        on_delete=models.CASCADE,
        related_name='subordinates'
    )
    subordinate_instance = models.OneToOneField(
        'agents.AgentInstance',
        on_delete=models.CASCADE,
        related_name='supervisor_link'
    )
    # created_at is inherited from BaseModel.

    class Meta:
        ordering = ['-created_at']

    def as_client_dict(self):
        """
        Provides a dictionary representation for the client.
        """
        return {
            'object': 'SubAgentLink',
            'id': self.pk,
            'created_at': self.created_at.isoformat(),
            'supervisor_instance_id': self.supervisor_instance.pk,
            'subordinate_instance_id': self.subordinate_instance.pk,
            'subordinate_instance_name': self.subordinate_instance.name,
            'subordinate_instance_status': self.subordinate_instance.status,
        }

    def __str__(self):
        return f"Link: {self.supervisor_instance.pk} -> {self.subordinate_instance.pk}"
