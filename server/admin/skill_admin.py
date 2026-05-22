"""Admin for SkillModel and SkillModelVersion."""
from django.contrib import admin
from django.http import HttpRequest

from server.models.skills.skill import SkillModel
from server.models.skills.skill_version import SkillModelVersion


@admin.register(SkillModel)
class SkillAdmin(admin.ModelAdmin):
    """Admin for skill definitions."""

    list_display: tuple[str, ...] = (
        "id", "created_at", "name", "parent_project", "parent_agent", "parent_skill",
    )


@admin.register(SkillModelVersion)
class SkillVersionAdmin(admin.ModelAdmin):
    """Admin for skill version instances."""
