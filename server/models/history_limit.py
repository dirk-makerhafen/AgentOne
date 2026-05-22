"""Per-agent rules for limiting history entries by tool group and rule name."""
from __future__ import annotations

from datetime import datetime

from django.db import models


class HistoryLimitingRule(models.Model):
    """Override default history limits for a specific tool group and rule on a
    per-agent basis."""

    created_at: datetime = models.DateTimeField(auto_now_add=True)
    updated_at: datetime = models.DateTimeField(auto_now=True)
    agent: models.ForeignKey | None = models.ForeignKey(
        "server.AgentModel",
        on_delete=models.CASCADE,
        related_name="history_limiting_rules",
    )

    group_name: str = models.CharField(
        default="default",
        max_length=255,
        help_text="Name of tool or other group this limit belongs to",
    )
    rule_name: str = models.CharField(
        max_length=255,
        help_text="The unique name of the rule template to override (e.g., 'fs_by_path').",
    )
    description: str = models.TextField(
        blank=True,
        default="",
        help_text="Optional description of why this override exists.",
    )

    limit_success: int | None = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Override for successful calls. Blank uses tool default.",
    )
    limit_failed: int | None = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Override for failed calls. Blank uses tool default.",
    )
    limit_pending: int | None = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Override for pending calls. Blank uses tool default.",
    )
    limit_max: int | None = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Override for total calls. Blank uses tool default.",
    )

    class Meta:
        unique_together = ("agent", "group_name", "rule_name")
        ordering = ["group_name", "rule_name"]

    def __str__(self) -> str:
        """Return a human-readable representation of the rule."""
        return f"{self.agent.name}: {self.group_name}.{self.rule_name}"
