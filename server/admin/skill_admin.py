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
    """Admin for skill version instances (immutable snapshots)."""

    list_display: tuple[str, ...] = (
        "id", "skill", "version_number", "path", "created_at",
    )
    list_filter: tuple[str, ...] = ("created_at",)
    search_fields: tuple[str, ...] = ("skill__name", "commit", "path")
    ordering: tuple[str, ...] = ("-created_at",)
    raw_id_fields: tuple[str, ...] = ("skill",)
    readonly_fields: tuple[str, ...] = (
        "skill", "description", "commit", "path", "version_number",
        "created_at", "updated_at",
    )
    fieldsets = (
        (None, {"fields": ("skill", "version_number", "description", "commit", "path")}),
        ("Timestamps", {"fields": ("created_at", "updated_at")}),
    )

    def has_add_permission(self, request: HttpRequest) -> bool:
        """Versions are created by the runtime, never by hand."""
        return False

    def has_change_permission(self, request: HttpRequest, obj=None) -> bool:
        """Versions are immutable — the model rejects edits on save."""
        return False
