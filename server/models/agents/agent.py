from django.db import models
from server.models.base_model import BaseModel
from django.core.exceptions import ValidationError

class Agent(BaseModel):
    """
    Uniquely identifies an Agent across all versions and variants.
    """
    name = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True, null=True, max_length=65535)

    @property
    def agent_instances(self):
        return self.related_agent_instances # pyright: ignore[reportAttributeAccessIssue]

    @property
    def agent_versions(self):
        return self.related_agent_versions # pyright: ignore[reportAttributeAccessIssue]

    @property
    def latest_agent_version(self):
        return self.related_agent_versions.last() # pyright: ignore[reportAttributeAccessIssue]

    @property
    def conversation_messages(self):
        return self.related_conversation_messages # pyright: ignore[reportAttributeAccessIssue]

    @property
    def queries(self):
        return self.related_queries # pyright: ignore[reportAttributeAccessIssue]

    @property
    def responses(self):
        return self.related_responses # pyright: ignore[reportAttributeAccessIssue]

    @property
    def tool_calls(self):
        return self.related_tool_calls # pyright: ignore[reportAttributeAccessIssue]

    @property
    def tool_responses(self):
        return self.related_tool_responses # pyright: ignore[reportAttributeAccessIssue]

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError(f"You may not edit an existing {self._meta.model_name}")
        super().save(*args, **kwargs) 

    def __str__(self):
        return self.name
    
