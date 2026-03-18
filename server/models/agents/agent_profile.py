from django.db import models
import random
from django.core.exceptions import ValidationError
from server.models.providers.ai_model import AiModel
from server.models.enums.task_enums import TaskExecutionMode
from server.models.base_model import BaseModel
from server.models.content import GenericContent


class AgentToolCallSyntax(models.TextChoices):
    DEFAULT = 'default', 'Default (OpenAI style)'
    CUSTOM = 'custom', 'Custom tagging'

class AgentProfile(BaseModel):
    """
    Immutable snapshot of settings for an Agent version.
    """
    name = models.CharField(default="",max_length=512)

    aimodel = models.ForeignKey("server.AiModel", on_delete=models.CASCADE, related_name="related_agent_profiles", blank=True, null=True)
    variants = models.ForeignKey("self", on_delete=models.CASCADE, related_name="related_agent_profiles", blank=True, null=True)
    parent = models.ForeignKey("self", on_delete=models.CASCADE, related_name="child_agent_profiles", blank=True, null=True)
    variant_defs = models.JSONField(default=list, blank=True)

    max_retries = models.IntegerField(default=0)
    max_task_steps = models.IntegerField(default=0)
    unattended_steps = models.IntegerField(default=0)
    max_history_messages = models.IntegerField(default=0)

    task_prompt   = models.ForeignKey(GenericContent, default=None, null=True, blank=True, on_delete=models.SET_DEFAULT, related_name="agent_profile_task_prompt")
    system_prompt = models.ForeignKey(GenericContent, default=None, null=True, blank=True, on_delete=models.SET_DEFAULT, related_name="agent_profile_system_prompt")

    execution_mode = models.CharField(max_length=20, default=TaskExecutionMode.QUEUE, choices=TaskExecutionMode)
    tool_call_syntax = models.CharField(max_length=20, choices=AgentToolCallSyntax.choices, default=AgentToolCallSyntax.DEFAULT)

    extra_settings = models.JSONField(default=dict, blank=True, null=True)
        
    def select(self, variant_names=None):
        if variant_names is None:
            variant_names = []
        if not self.variant_defs:
            return self

        # -------------------------
        # choose variant definition
        # -------------------------
        if variant_names:
            name = variant_names[0]
            selected = next((x for x in self.variant_defs if x.get("name") == name),None)
        else:
            selected = None

        if selected is None:
            selected = random.choice(self.variant_defs)

        variant_name = selected.get("name", "")

        # -------------------------
        # reuse existing profile
        # -------------------------

        existing = list(self.child_agent_profiles.filter(name=variant_name))
        if existing:
            profile = random.choice(existing)
        else:
            # -------------------------
            # create derived profile
            # -------------------------
            profile = AgentProfile()
            profile.parent = self
            profile.name = variant_name
            # copy base fields
            profile.aimodel = self.aimodel
            profile.max_retries = self.max_retries
            profile.max_task_steps = self.max_task_steps
            profile.unattended_steps = self.unattended_steps
            profile.max_history_messages = self.max_history_messages
            profile.task_prompt = self.task_prompt
            profile.system_prompt = self.system_prompt
            profile.execution_mode = self.execution_mode
            profile.tool_call_syntax = self.tool_call_syntax
            profile.extra_settings = dict(self.extra_settings or {})

            # -----------------------------
            # apply overrides from variant
            # -----------------------------

            if selected.get("model"):
                profile.aimodel = AiModel.objects.get(name=selected["model"])

            if "max_retries" in selected:
                profile.max_retries = selected["max_retries"]

            if "max_task_steps" in selected:
                profile.max_task_steps = selected["max_task_steps"]

            if "unattended_steps" in selected:
                profile.unattended_steps = selected["unattended_steps"]

            if "max_history_messages" in selected:
                profile.max_history_messages = selected["max_history_messages"]

            if "execution_mode" in selected:
                profile.execution_mode = selected["execution_mode"]

            if "tool_call_syntax" in selected:
                profile.tool_call_syntax = selected["tool_call_syntax"]

            if selected.get("extra_settings"):
                profile.extra_settings.update(selected["extra_settings"])

            # nested variants
            profile.variant_defs = selected.get("variants", [])
            profile.save()

        # recursive variant chain
        return profile.select(variant_names[1:])

    @property
    def use_in_agent_versions(self):
        return self.related_agent_versions # pyright: ignore[reportAttributeAccessIssue]

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError(f"You may not edit an existing {self._meta.model_name}")
        super().save(*args, **kwargs)
