from django.db import models
import random
from django.core.exceptions import ValidationError
from server.models.providers.ai_model import AiModel
from server.models.enums.task_enums import TaskSchedulerStrategy
from server.models.base_model import BaseModel
from server.models.content import GenericContent


class AgentToolCallSyntax(models.TextChoices):
    DEFAULT = 'default', 'Default (OpenAI style)'
    CUSTOM = 'custom', 'Custom tagging'

class ReasoningEffort(models.TextChoices):
    NONE = 'none', 'None, default'
    MINIMAL = 'minimal', "Minimal"
    LOW = 'low', 'Low'
    MEDIUM = 'medium', 'Medium'
    HIGH = 'high', "High"
    XHIGH = 'xhigh', "Extra High"


class SettingsModel(BaseModel):
    """
    Immutable snapshot of settings for an Agent version.
    """

    aimodel = models.ForeignKey("server.AiModel", on_delete=models.CASCADE, related_name="related_agent_settings", blank=True, null=True)
    thinking = models.BooleanField(default=None, null=True, blank=True)

    reasoning_effort = models.CharField(max_length=20, choices=ReasoningEffort, default=None, null=True, blank=True)

    max_retries = models.IntegerField(default=None, null=True, blank=True)
    max_turns = models.IntegerField(default=None, null=True, blank=True)
    max_unattended_turns = models.IntegerField(default=None, null=True, blank=True)
    max_history_messages = models.IntegerField(default=None, null=True, blank=True)
    priority = models.IntegerField(default=None, null=True, blank=True)   # 0 = highest, 1..999 less important

    task_prompt   = models.ForeignKey(GenericContent, default=None, null=True, blank=True, on_delete=models.SET_DEFAULT, related_name="agent_settings_task_prompt")
    system_prompt = models.ForeignKey(GenericContent, default=None, null=True, blank=True, on_delete=models.SET_DEFAULT, related_name="agent_settings_system_prompt")

    scheduler_strategy = models.CharField(max_length=20, choices=TaskSchedulerStrategy, default=None, null=True, blank=True)
    tool_call_syntax = models.CharField(max_length=20, choices=AgentToolCallSyntax.choices, default=None, null=True, blank=True)

    commandNames = models.JSONField(default=None, null=True, blank=True)
    disallowedCommandNames = models.JSONField(default=None, null=True, blank=True)

    taskNames = models.JSONField(default=None, null=True, blank=True)
    disallowedTaskNames = models.JSONField(default=None, null=True, blank=True)

    toolNames = models.JSONField(default=None, null=True, blank=True)
    disallowedToolNames = models.JSONField(default=None, null=True, blank=True)

    skillNames = models.JSONField(default=None, null=True, blank=True)
    disallowedSkillNames = models.JSONField(default=None, null=True, blank=True)

    subagentNames = models.JSONField(default=None, null=True, blank=True)
    disallowedSubagentNames = models.JSONField(default=None, null=True, blank=True)

    extra_settings = models.JSONField(default=None, null=True, blank=True)
    commit = models.TextField(max_length=1024, default="")

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError(f"You may not edit an existing {self._meta.model_name}")
        super().save(*args, **kwargs)
