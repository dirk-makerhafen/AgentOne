"""Admin configuration for the AgentOne server.

Registers all Django models with their corresponding admin classes
and imports admin modules for side effects.
"""
from django.contrib import admin
from django.db.models import QuerySet
from django.db.models.functions import Length
from django.http import HttpRequest

from server.models.content import GenericContent


@admin.register(GenericContent)
class GenericContentAdmin(admin.ModelAdmin):
    """Admin for deduplicated, content-addressed GenericContent storage.

    ``content`` is deliberately kept out of the list view — it can hold
    megabytes of base64 image data or JSON — so the size column is computed
    DB-side via ``Length()`` rather than materializing the column.
    """

    list_display: tuple[str, ...] = (
        "sha256_short", "content_type", "content_size", "expires_at",
    )
    list_filter: tuple[str, ...] = ("content_type",)
    search_fields: tuple[str, ...] = ("sha256",)
    readonly_fields: tuple[str, ...] = (
        "sha256", "content_type", "content", "content_size",
    )
    fieldsets = (
        (None, {"fields": ("sha256", "content_type", "content_size", "expires_at")}),
        ("Content", {"fields": ("content",)}),
    )
    show_full_result_count: bool = False

    def get_queryset(self, request: HttpRequest) -> QuerySet:
        return (
            super().get_queryset(request)
            .defer("content")
            .annotate(_content_size=Length("content"))
        )

    @admin.display(description="SHA-256", ordering="sha256")
    def sha256_short(self, obj: GenericContent) -> str:
        return obj.sha256[:12]

    @admin.display(description="Size", ordering="_content_size")
    def content_size(self, obj: GenericContent) -> int:
        return getattr(obj, "_content_size", 0) or 0

    def has_add_permission(self, request: HttpRequest) -> bool:
        """Rows are content-addressed and created by the runtime."""
        return False


# Provider admins (wildcard re-export)
from .providers.ProvidersAdmin import *

# Agent / session admins
from .agents.agent_admin import AgentAdmin
from .agents.agent_instance_version_admin import SessionVersionModelAdmin
from .agents.agent_instance_admin import SessionModelAdmin
from .agents.agent_settings_admin import SettingsModelAdmin
from .agents.agent_version_admin import AgentVersionAdmin

# Task admins
from .tasks.agent_task_call_admin import AgentTaskCallAdmin
from .tasks.task_definition_version_admin import TaskDefinitionVersionAdmin
from .tasks.task_definition_admin import TaskDefinitionAdmin
from .tasks.agent_task_instance_admin import AgentTaskInstanceAdmin
from .tasks.agent_task_run_admin import AgentTaskRunAdmin

# Message admins
from .message_admin import MessageAdmin
from .message_part_admin import MessagePartAdmin

# Misc admins
from .debug_log_entry_admin import DebugLogEntryAdmin


# Query admins
from .queries.query_admin import QueryAdmin
from .queries.query_message_admin import QueryMessageAdmin
from .queries.query_message_part_admin import QueryMessagePartAdmin
from .queries.response_admin import ResponseAdmin

from .system_admin import SystemAdmin
from .skill_admin import SkillAdmin
from .project_admin import ProjectAdmin
from .workspace import WorkspaceAdmin
from .cron_admin import CronjobAdmin
from .collection_admin import DataCollectionAdmin, CollectionItemAdmin
from .terminal_admin import TerminalSessionAdmin

# Legacy commented-out imports (kept for reference):
# from .tool_call_admin import ToolCallAdmin
# from .tool_definition_admin import ToolDefinitionAdmin
# from .tool_installation_admin import ToolInstallationAdmin
# from .tool_installation_log_admin import ToolInstallationLogAdmin
# from .tool_instance_admin import ToolInstanceAdmin
# from .tool_response_admin import ToolResponseAdmin
# from .agent_task_run_subtask_admin import AgentTaskRunSubtaskAdmin
