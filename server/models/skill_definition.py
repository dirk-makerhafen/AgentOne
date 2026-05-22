"""Declarative skill definition model parsed from SKILL.md files."""
from __future__ import annotations

from datetime import datetime

from django.db import models
from django_enum import EnumField

from .content import GenericContent


class SkillDefinition(models.Model):
    """Metadata for a declaratively defined agent skill, typically parsed from a
    ``SKILL.md`` manifest."""

    skill_slug: str = models.CharField(
        max_length=100,
        unique=True,
        help_text="A unique identifier for the skill (e.g., 'obsidian-search').",
    )

    name: str = models.CharField(
        max_length=200, help_text="The name used in the UI / system output."
    )

    description: str = models.TextField(
        help_text="A detailed explanation of the skill's capabilities."
    )

    tool_description: str | None = models.TextField(null=True, blank=True)

    target_source: str | None = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        help_text="The module/class to instantiate for core logic.",
    )

    requires_auth: bool = models.BooleanField(
        default=False,
        help_text="Does this skill require external authentication (e.g., API key)?",
    )

    created_at: datetime = models.DateTimeField(auto_now_add=True)
    updated_at: datetime = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Skill Definition"
        verbose_name_plural = "Skill Definitions"

    def __str__(self) -> str:
        """Return the unique slug as the string representation."""
        return self.skill_slug
