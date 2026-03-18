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
from server.models.tasks.agent_task_definition import AgentTaskDefinition
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


class ChatAgent(BaseAgent):
    @task()
    def add_user_message(self,  message: str|None = None, parts: List[Dict]|None = None):
        tmp = super().add_user_message.func(message=message, parts=parts)
        if isinstance(tmp, ConversationMessage):
            return self._process_conversation_message.delay(conversation_message=tmp)
        else: # command was parsed 
            return tmp
    
    @chain(description="Handle incoming chat message")
    def _process_conversation_message(self, conversation_message=None):
        return [
            self._create_query.i(),
            self._execute_query.i(),
            self.response_to_conversation.i(),
            self._decide_next_status.i(),
        ]

    @task(description="Prepare LLM query from context")
    def _create_query(self, conversation_message):
        from server.models.queries.query import Query
        from server.models.queries.query_message import QueryMessage
        from server.models.queries.query_message_part import QueryMessagePart
        from server.models.conversation_message import ConversationMessage
        from tools.builtin_filesystem.models.fs_log_entry import FsLogEntry
        from server.history_limiter import HistoryLimiter
        from server.models.content import GenericContent
        from server.models.agents.agent import Agent
        from jinja2 import Template
        import re
        import json
        try:
            query = self._create_new_query.func()

            print("FOOOOOooooo", conversation_message)
            # 2. Conversation History
            conversation_messages = self.agent_instance_version.related_conversation_messages.filter(pk__lte=conversation_message.pk, hide_from_context=False).order_by('-created_at')[:query.agent_profile.max_history_messages + 1]
            # Sort chronological
            print(conversation_messages)
            all_entries = list(conversation_messages) # sorted(conversation_messages, key=lambda x: -x.created_at if hasattr(x, "created_at") else -x.updated_at)
            print("all_entriesall_entriesall_entries", all_entries)
            # TODO: Track all loaded paths for HistoryLimiter or similar
            all_loaded_paths = set()
            limiter = HistoryLimiter(self.agent_instance_version, all_entries, all_loaded_paths)

            cmessages = []
            for entry in all_entries:
                if isinstance(entry, ConversationMessage):
                    msg_parts = []
                    for part in entry.parts.all():
                        msg_parts.append(QueryMessagePart(
                            conversation_message=entry,
                            conversation_message_part=part,
                            tags=["ChatMessage", f"{entry.role}"],
                            content_type=part.content_type,
                        ))

                    tool_calls = [tc for tc in entry.tool_calls.all() if not limiter.is_tool_call_limited(tc, entry)]
                    tool_responses = [x for x in [tc.taskcall_result_run for tc in tool_calls] if x]

                    if tool_responses:
                        for tool_response in tool_responses:
                            qmsg = QueryMessage.objects.create(role="tool", query=query, conversation_message=entry, tool_response=tool_response)
                            cmessages.append(qmsg)

                    if msg_parts or tool_calls:
                        print("query", query)
                        qmsg = QueryMessage.objects.create(role=entry.role, query=query, conversation_message=entry)
                        qmsg.tool_calls.set(tool_calls)
                        for i, msg_part in enumerate(msg_parts):
                            msg_part.query_message = qmsg
                            msg_part.index = i
                            msg_part.save()
                        cmessages.append(qmsg)
                        if limiter.is_general_message_limited('messages_dont_warn_forget', entry):
                            qmsg.content_prefix = GenericContent.from_text('@@@TO_BE_FORGOTTEN@@@')
                            qmsg.save()

                elif isinstance(entry, FsLogEntry):
                    qmsg = QueryMessage.objects.create(role="system", query=query)
                    QueryMessagePart.objects.create(
                        query_message=qmsg,
                        fsLogEntry=entry,
                        content_type="TEXT",
                        tags=["FilesystemLog"]
                    )
                    cmessages.append(qmsg)

            messages = reversed(cmessages)
            
            for index, message in enumerate(messages):
                message.index = index
                message.save()
                if hasattr(message, "_tool_calls"):
                    for tc in message.tool_calls.all():
                        message.tool_calls.add(tc)

            return query

        except Exception:
            from server.models.debug_log_entry import DebugLogEntry
            DebugLogEntry.objects.create(agent_instance=self.agent_instance, event='exception', data={"exception": traceback.format_exc()})
            raise

    @task()
    def response_to_conversation(self, response, message, tool_calls):
        conversation_message = ConversationMessage.objects.create(
            agent_instance_version = self.agent_instance_version,
            response=response,
            role='assistant',
        )
        if tool_calls:
            conversation_message.tool_calls.set(tool_calls)
        if message:
            conversation_message.add_part(message)
        return conversation_message

    @task()
    def _decide_next_status(self, message):
        return message
        return
        agent_instance = conversationMessage.agent_instance
        agent_instance.refresh_from_db()
        if agent_instance.require_user_interaction:
            agent_instance.set_status(AgentInstanceStatusChoices.AWAITING_USER_INPUT)
        elif agent_instance.effective_limit_max_automated_steps == 0: # automatic steps are  disabls, we need user input next
            agent_instance.set_status(AgentInstanceStatusChoices.AWAITING_USER_INPUT)
        elif agent_instance.automated_step_count >= agent_instance.effective_limit_max_automated_steps:  # automated step LIMIT REACHED, require user confirmation
            agent_instance.set_status(AgentInstance.AgentInstanceStatusChoices.AWAITING_USER_INPUT)
        else: # limit not reached, automation enabled
            agent_instance.set_status(AgentInstance.AgentInstanceStatusChoices.IDLE)
            if agent_instance.tasks.first(): # is task agent
                if not agent_instance.get_active_task(): # no active task
                    agent_instance.process_next_task()
            else: # chat agent, no tasks
                print("# chat agent, no tasks")
                #self._create_query()
                #celery_create_query.delay(agent_instance.instance_pk)



    '''
    #agent_instance: AgentInstance|None
    #agent_instance_version: AgentInstanceVersion|None
    #agent_version: AgentVersion|None
    parent: AgentRuntime|None
    children: list
    @classmethod
    def i(cls, agent_instance_version):
        print("AgentRuntime.agent_instance_version", agent_instance_version, cls)
        return cls(agent_instance_version=agent_instance_version)

    def __init__(self, workingdir = None, variant = None, name=None, agent_instance_version: AgentInstanceVersion|None=None):
        print("AgentRuntime.__init__", agent_instance_version)
        if agent_instance_version:
            print("here1")
            self.agent_instance_version = agent_instance_version
            self.agent_instance_version: AgentInstanceVersion
            self.agent_version = self.agent_instance_version.agent_version
            self.agent_version: AgentVersion
        else:
            print("here2",self.parent)
            # agent and agent_version are injected into the class by the agent registry or the class loader
            if not workingdir and self.parent and self.parent.agent_instance_version:
                workingdir = self.parent.agent_instance_version.workingdir
            parent_agent_instance = self.parent.agent_instance if self.parent else None
            self.agent_instance_version = self.agent_version.get_or_create_instance(parent_instance=parent_agent_instance, name=name, workingdir=workingdir , variant=variant)

        self.agent_instance = self.agent_instance_version.agent_instance
        self.workingdir =  self.agent_instance_version.workingdir
        self.agent = self.agent_instance.agent

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        original_init = cls.__init__
        print("__init_subclass__")
        @wraps(original_init)
        def wrapped_init(self, *args, **kwargs):
            print("wrapped_init")
            self.id = f"{cls.__name__}:{random.random():.5f}"
            self.parent = RuntimeContextTracker.current
            print("AgentRuntime.__init__1", self.parent, self)
            with RuntimeContextTracker(self):
                original_init(self, *args, **kwargs)

        cls.__init__ = wrapped_init
    '''
