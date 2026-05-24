"""Admin configuration for the AgentOne server.

Registers all Django models with their corresponding admin classes
and imports admin modules for side effects.
"""
from typing import Any

from django.contrib import admin
from django.http import HttpRequest

from server.models.content import GenericContent


@admin.register(GenericContent)
class GenericContentAdmin(admin.ModelAdmin):
    """Admin for polymorphic GenericContent storage."""

    search_fields: tuple[str, ...] = ("id", "content", "content_type")


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
from .history_limit_admin import HistoryLimitAdmin

# Query admins
from .queries.query_admin import QueryAdmin
from .queries.query_message_admin import QueryMessageAdmin
from .queries.query_message_part_admin import QueryMessagePartAdmin
from .queries.response_admin import ResponseAdmin

from .system_admin import SystemAdmin
from .pipe_admin import NamedPipeAdmin, NamedPipeSubscriptionAdmin
from .skill_admin import SkillAdmin
from .project_admin import ProjectAdmin
from .workspace import WorkspaceAdmin

# Legacy commented-out imports (kept for reference):
# from .tool_call_admin import ToolCallAdmin
# from .tool_definition_admin import ToolDefinitionAdmin
# from .tool_installation_admin import ToolInstallationAdmin
# from .tool_installation_log_admin import ToolInstallationLogAdmin
# from .tool_instance_admin import ToolInstanceAdmin
# from .tool_response_admin import ToolResponseAdmin
# from .agent_task_run_subtask_admin import AgentTaskRunSubtaskAdmin
