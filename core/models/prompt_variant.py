from django.db import models
from django.contrib.auth.models import User
from agents.models.agent import Agent
from core.models.base_model import BaseModel

class PromptVariant(BaseModel):
    """
    Represents a specific implementation or version of a Prompt.
    A variant can be global (system or user-owned) or agent-specific.
    It holds the actual prompt content and versioning information.
    """
    prompt = models.ForeignKey("core.Prompt", on_delete=models.CASCADE, related_name='variants')
    owner = models.ForeignKey(User, related_name='owned_prompt_variants', default=None, null=True, on_delete=models.SET_NULL)
    agent = models.ForeignKey(Agent, on_delete=models.CASCADE, null=True, blank=True, related_name='prompt_variants')
    is_enabled = models.BooleanField(default=True)
    value = models.TextField(max_length=1 * 1024 * 1024, default='')
    version_nr = models.IntegerField(default=1)

    next_version = models.OneToOneField('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='prev_version')
    # created_at and updated_at are inherited from BaseModel

    class Meta:
        ordering = ['-created_at']

    def as_client_dict(self):
        return {
            'object': 'PromptVariant',
            'id': self.pk,
            'prompt_id': self.prompt_id,
            'source': self.prompt.source, # Denormalized for convenience
            'key': self.prompt.key,       # Denormalized for convenience
            'owner_id': self.owner_id,
            'owner_username': self.owner.username if self.owner else "System",
            'agent_id': self.agent_id,
            'is_enabled': self.is_enabled,
            'created_at': self.created_at.isoformat(),
            'value': self.value,
            'version_nr': self.version_nr,
            'is_deleteable': self.owner is not None,
            'is_editable': self.owner is not None,
            'is_newest_version': self.next_version is None,
            'prev_version_id': self.prev_version.pk if hasattr(self, "prev_version") else None,
        }
    def update_value(self, new_value):
        """
        Updates the value of the prompt variant. If the value has changed,
        it creates a new version and links it, preserving history.
        """
        if self.value == new_value:
            return self

        # Create a new version
        new_version = PromptVariant.objects.create(
            prompt=self.prompt,
            owner=self.owner,
            agent=self.agent,
            is_enabled=self.is_enabled,
            value=new_value,
            version_nr=self.version_nr + 1
        )

        # Link the old version to the new one
        self.next_version = new_version
        self.save()

        return new_version

