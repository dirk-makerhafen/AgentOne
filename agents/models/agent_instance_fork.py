from django.db import models
from core.models.base_model import BaseModel

class AgentInstanceFork(BaseModel):
    parent_instance = models.ForeignKey(
        'agents.AgentInstance',
        on_delete=models.CASCADE,
        null=True,
        related_name='forks_created'
    )
    child_instance = models.OneToOneField(
        'agents.AgentInstance',
        on_delete=models.CASCADE,
        null=True,
        related_name='fork_origin'
    )
    
    # The 'forked_at' timestamp is the 'created_at' field inherited from BaseModel.
    class Meta:
        ordering = ['-created_at']

    def as_client_dict(self):
        """
        Provides a dictionary representation of the object for client-side rendering.
        """
        return {
            'object': 'AgentInstanceFork',
            'id': self.pk,
            'created_at': self.created_at.isoformat(),
            'parent_instance_id': self.parent_instance.pk,
            'parent_instance_name': self.parent_instance.name, # Added for clarity in child view
            'child_instance_id': self.child_instance.pk,
            'child_instance_name': self.child_instance.name,
        }


    def __str__(self):
        return f"Fork: Instance {self.parent_instance.pk} -> {self.child_instance.pk}"
