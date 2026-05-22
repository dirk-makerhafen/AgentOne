from __future__ import annotations

from typing import Any

from django.db import models

from server.models.skills.skill_version import SkillModelVersion


class SkillModel(models.Model):
    """A skill group that versions its configuration over time."""

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    name = models.CharField(default="", max_length=255, help_text="")
    latest_skill_version = models.ForeignKey(
        SkillModelVersion,
        default=None,
        null=True,
        on_delete=models.SET_NULL,
        related_name="related_newest_skill",
    )

    parent_agent = models.ForeignKey(
        "server.AgentModel",
        default=None,
        null=True,
        on_delete=models.CASCADE,
        related_name="related_skills",
    )
    parent_project = models.ForeignKey(
        "server.Project",
        default=None,
        null=True,
        on_delete=models.CASCADE,
        related_name="related_skills",
    )
    parent_skill = models.ForeignKey(
        "self",
        default=None,
        null=True,
        on_delete=models.CASCADE,
        related_name="related_skills",
    )
