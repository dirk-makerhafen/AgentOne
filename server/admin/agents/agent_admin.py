"""Admin for the AgentModel."""
from typing import Any

from django.contrib import admin
from django.http import HttpRequest

from server.models.agents.agent import AgentModel
from server.models.agents.agent_version import AgentVersionModel


class AgentVersionInline(admin.TabularInline):
    """Inline editor for agent versions."""

    model: type[AgentVersionModel] = AgentVersionModel
    extra: int = 0
    fields: tuple[str, ...] = ("version_number", "created_at")
    readonly_fields: tuple[str, ...] = ("version_number", "created_at")
    show_change_link: bool = True
    can_delete: bool = False


@admin.register(AgentModel)
class AgentAdmin(admin.ModelAdmin):
    """Admin for agent definitions."""

    list_display: tuple[str, ...] = (
        "id", "created_at", "name", "parent_project", "parent_agent", "parent_skill",
    )
