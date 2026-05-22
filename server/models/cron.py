"""Cronjob model for scheduling periodic agent runs."""
from __future__ import annotations

from datetime import datetime

from django.db import models

from server.models.content import GenericContent


class Cronjob(models.Model):
    """A scheduled job that runs an agent on a recurring schedule."""

    created_at: datetime = models.DateTimeField(auto_now_add=True)
    updated_at: datetime = models.DateTimeField(auto_now=True)

    name: str = models.CharField(default="", max_length=255, help_text="")
    description: str = models.TextField(
        default="", max_length=10000, help_text=""
    )
    schedule: str = models.CharField(max_length=2048, help_text="")
    prompt: GenericContent | None = models.ForeignKey(
        GenericContent,
        default=None,
        null=True,
        blank=True,
        on_delete=models.SET_DEFAULT,
        related_name="related_cron_prompt",
    )
    agent: models.ForeignKey | None = models.ForeignKey(
        "server.AgentModel",
        on_delete=models.CASCADE,
        related_name="related_cron",
        blank=True,
        null=True,
    )
