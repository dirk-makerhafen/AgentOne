


from __future__ import annotations
from functools import wraps
import inspect
import json
import random
import traceback
from typing import List, Any, Dict, Optional, Type, Set
from runtime.agents.base_agent import BaseAgent
from registry.agent_def import AgentDef
from attrs import define, field
import re
from runtime.tasks.bound_agent_function import BoundAgentFunction
from runtime.context_manager import RuntimeContextTracker
from server.models.queries.query_message import QueryMessage
from server.models.queries.query_message_part import QueryMessagePart
from server.models.enums.message_enums import MessageContentType
from registry.task_decorators import task, chain, chord, map, group,command
from server.models.enums.task_enums import TaskExecutionMode
from server.models.agents.agent_profile import AgentToolCallSyntax
from server.models.tasks.agent_task_call import AgentTaskCall
from server.models.conversation_message_part import ConversationMessagePart
from server.models.queries.query import QueryAvailableTool
from server.models.content import GenericContent
from server.models.providers.ai_model import AiModel
import shlex

from server.models.conversation_message import ConversationMessage
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from server.models.agents.agent_instance_version import AgentInstanceVersion
    from server.models.agents.agent_instance import AgentInstance
    from server.models.agents.agent_version import AgentVersion

class SimpleTaskAgent(BaseAgent):
    @chain()
    def run(self, **kwargs):
        return [
            self._create_task_query.i(),
            self._execute_query.i(),
            self._get_response_message.i(),
        ]

    @task()
    def _create_task_query(self, payload):
        query = self._create_new_query()
        query_message = QueryMessage.objects.create(role="system", query=query, index=-1)
        QueryMessagePart.objects.create(
            content = GenericContent.from_data(payload),
            content_type = MessageContentType.TEMPLATE,
            content_template = query.agent_profile.task_prompt,
            query_message = query_message,
        )
        return query

    @task()
    def _get_response_message(self, content:str, **kwargs):
        return content
