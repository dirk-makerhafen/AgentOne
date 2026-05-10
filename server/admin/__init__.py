from django.contrib import admin

from server.models.content import GenericContent

@admin.register(GenericContent)
class GenericContentAdmin(admin.ModelAdmin):
    search_fields = ('id', "content", "content_type")
from .providers.ProvidersAdmin import *
from .agents.agent_admin import AgentAdmin
from .agents.agent_instance_version_admin import AgentInstanceVersionAdmin
from .agents.agent_instance_admin import AgentInstanceAdmin
from .agents.agent_settings_admin import AgentProfileAdmin
from .agents.agent_version_admin import AgentVersionAdmin

from .tasks.agent_task_call_admin import AgentTaskCallAdmin
from .tasks.agent_task_definition_admin import TaskDefinitionAdmin
from .tasks.agent_task_instance_admin import AgentTaskInstanceAdmin
from .tasks.agent_task_run_admin import AgentTaskRunAdmin

from .conversation_message_admin import ConversationMessageAdmin
from .conversation_message_part_admin import ConversationMessagePartAdmin

from .debug_log_entry_admin import DebugLogEntryAdmin
from .history_limit_admin import HistoryLimitAdmin
#from .prompt_admin import PromptAdmin
from .queries.query_admin import QueryAdmin
from .queries.query_message_admin import QueryMessageAdmin
from .queries.query_message_part_admin import QueryMessagePartAdmin
from .queries.response_admin import ResponseAdmin
from .system_admin import SystemAdmin

from .skill_admin import SkillAdmin
from .project_admin import ProjectAdmin

#from .tool_call_admin import ToolCallAdmin
#from .tool_definition_admin import ToolDefinitionAdmin
#from .tool_installation_admin import ToolInstallationAdmin
#from .tool_installation_log_admin import ToolInstallationLogAdmin
#from .tool_instance_admin import ToolInstanceAdmin
#from .tool_response_admin import ToolResponseAdmin
#from .agent_task_run_subtask_admin import AgentTaskRunSubtaskAdmin