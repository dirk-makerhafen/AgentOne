"""Immutable settings snapshots for agent versions."""
from __future__ import annotations

from enum import Enum
from typing import Any

from django.db import models
from django.core.exceptions import ValidationError

from server.models.base_model import BaseModel
from server.models.content import GenericContent
from server.models.enums.task_enums import TaskSchedulerStrategy


class AgentToolCallSyntax(models.TextChoices):
    """Available tool-call syntax styles."""

    DEFAULT = "default", "Default (OpenAI style)"
    CUSTOM = "custom", "Custom tagging"


class SubagentResultDelivery(models.TextChoices):
    PASSIVE = "passive", "Passive — results added to conversation, processed on next turn"
    IMMEDIATE = "immediate", "Immediate — inject result and trigger process_turn"

class ReasoningEffort(models.TextChoices):
    """Reasoning effort levels for LLM inference."""

    NONE = "none", "None, default"
    MINIMAL = "minimal", "Minimal"
    LOW = "low", "Low"
    MEDIUM = "medium", "Medium"
    HIGH = "high", "High"
    XHIGH = "xhigh", "Extra High"

class ResponseTemperature(Enum):
    """ResponseTemperature levels with float values."""
    PRECISE = 0.05
    FOCUSED = 0.2
    BALANCED = 0.4
    CREATIVE = 0.6
    EXPLORATORY = 0.8
    EXPERIMENTAL = 1.0

    @classmethod
    def choices(cls):
        return [
            (cls.PRECISE.value, "Precise"),
            (cls.FOCUSED.value, "Focused"),
            (cls.BALANCED.value, "Balanced"),
            (cls.CREATIVE.value, "Creative"),
            (cls.EXPLORATORY.value, "Exploratory"),
            (cls.EXPERIMENTAL.value, "Experimental"),
        ]



class SettingsModel(BaseModel):
    """Immutable snapshot of settings for an agent version.

    Once saved, existing instances cannot be edited (the ``save`` method raises
    :class:`ValidationError` if ``self.pk`` is already set).
    """

    aimodel: models.ForeignKey | None = models.ForeignKey("server.AiModel",on_delete=models.CASCADE,related_name="related_agent_settings",blank=True,null=True)
    thinking: bool | None = models.BooleanField(default=None, null=True, blank=True)
    inherit_system_prompt: bool | None = models.BooleanField(default=None, null=True, blank=True)

    reasoning_effort: str | None = models.CharField(max_length=20,choices=ReasoningEffort,default=None,null=True,blank=True)
    precision:float | None = models.FloatField(choices=ResponseTemperature.choices, default=None, null=True, blank=True)

    max_retries: int | None = models.IntegerField(default=None, null=True, blank=True)
    max_turns: int | None = models.IntegerField(default=None, null=True, blank=True)
    max_unattended_turns: int | None = models.IntegerField(default=None, null=True, blank=True)
    max_history_messages: int | None = models.IntegerField(default=None, null=True, blank=True)
    auto_compact_limit: int | None = models.IntegerField(default=None, null=True, blank=True)
    compact_size_limit: int | None = models.IntegerField(default=None, null=True, blank=True)
    priority: int | None = models.IntegerField(default=None, null=True, blank=True)  # 0 = highest, 1..999 less important

    task_prompt: GenericContent | None = models.ForeignKey(GenericContent,default=None,null=True,blank=True,on_delete=models.SET_DEFAULT,related_name="agent_settings_task_prompt")
    system_prompt: GenericContent | None = models.ForeignKey(GenericContent,default=None,null=True,blank=True,on_delete=models.SET_DEFAULT,related_name="agent_settings_system_prompt")

    scheduler_strategy: str | None = models.CharField(max_length=20,choices=TaskSchedulerStrategy,default=None,null=True,blank=True)
    tool_call_syntax: str | None = models.CharField(max_length=20,choices=AgentToolCallSyntax.choices,default=None,null=True,blank=True)

    commandNames: Any = models.JSONField(default=None, null=True, blank=True)
    disallowedCommandNames: Any = models.JSONField(default=None, null=True, blank=True)

    taskNames: Any = models.JSONField(default=None, null=True, blank=True)
    disallowedTaskNames: Any = models.JSONField(default=None, null=True, blank=True)

    toolNames: Any = models.JSONField(default=None, null=True, blank=True)
    disallowedToolNames: Any = models.JSONField(default=None, null=True, blank=True)

    skillNames: Any = models.JSONField(default=None, null=True, blank=True)
    disallowedSkillNames: Any = models.JSONField(default=None, null=True, blank=True )

    subagentNames: Any = models.JSONField(default=None, null=True, blank=True)
    disallowedSubagentNames: Any = models.JSONField(default=None, null=True, blank=True)

    subagentResultDelivery: str | None = models.CharField(  max_length=20,  choices=SubagentResultDelivery,  default=None,  null=True,  blank=True)

    # Rate-limit card policy (per session):
    #   preferred_api_key        — the key this session sticks to for its current
    #                              provider (set by "Switch key" / auto-failover).
    #   auto_failover_keys       — when True, a cooling key is bypassed by rotating
    #                              to the next ready key of the same provider.
    #   max_rate_limit_wait_seconds — if the key cooldown would exceed this, fail
    #                              over automatically (0 = no max → always wait).
    preferred_api_key = models.ForeignKey(
        "server.ApiKey",
        default=None,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="related_session_settings",
    )
    auto_failover_keys = models.BooleanField(default=None, null=True, blank=True)
    max_rate_limit_wait_seconds = models.IntegerField(default=None, null=True, blank=True)

    access: Any = models.JSONField(default=None, null=True, blank=True)

    extra_settings: Any = models.JSONField(default=None, null=True, blank=True)
    commit: str = models.TextField(max_length=1024, default="")


    def save(self, *args: Any, **kwargs: Any) -> Any:
        """Raise :class:`ValidationError` on update; delegate to super on create."""
        if self.pk:
            raise ValidationError(
                f"You may not edit an existing {self._meta.model_name}"
            )
        return super().save(*args, **kwargs)
