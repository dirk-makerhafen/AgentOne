"""Admin for the AgentVersionModel."""
from typing import Any

from django.contrib import admin
from django.http import HttpRequest

from server.models.agents.agent_version import AgentVersionModel
from server.models.settings import SettingsModel


class AgentProfileInline(admin.TabularInline):
    """Inline editor for settings attached to an agent version."""

    model: type[SettingsModel] = SettingsModel
    extra: int = 0
    fields: tuple[str, ...] = ("name", "created_at")
    readonly_fields: tuple[str, ...] = ("created_at",)
    show_change_link: bool = True


@admin.register(AgentVersionModel)
class AgentVersionAdmin(admin.ModelAdmin):
    """Admin for agent version instances."""

    list_display: tuple[str, ...] = ("version_number", "agent", "created_at")
    list_display_links: tuple[str, ...] = ("version_number",)
