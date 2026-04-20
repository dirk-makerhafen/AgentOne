from __future__ import annotations
import traceback
from typing import List, Any, Dict
from runtime.agents.base_agent import BaseAgent
from registry.task_decorators import task, chain, chord, map, group, command

from server.models.conversation_message import ConversationMessage
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from server.models.agents.agent_instance import AgentInstance


class ChatAgent(BaseAgent):
    @task()
    def add_user_message(self, message: str|None = None, parts: List[Dict]|None = None):
        message_or_call = super().add_user_message(message=message, parts=parts)
        if isinstance(message_or_call, ConversationMessage):
            return self._handle_chat_message.delay(conversation_message=message_or_call)
        return message_or_call
    
    @chain()
    def _handle_chat_message(self, conversation_message=None):
        return [
            self._create_query.i(),   # conversation_message -> query
            self._execute_query.i(),  # query -> response
            self._handle_response.i(), # response -> response, tool_runs
            self._decide_next_step.i(), # response, tool_runs  -> conversation_message
        ]

    @task()
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
  
        try:
            query = super()._create_query()

            print("FOOOOO)ooooo", conversation_message)
            # 2. Conversation History
            conversation_messages = self.agent_instance_version.agent_instance.conversation_messages.filter(pk__lte=conversation_message.pk, hide_from_context=False).order_by('-created_at')[:query.agent_profile.max_history_messages + 1]
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
    def _decide_next_step(self, response, tool_runs):
        print("here")
        conversation_message = ConversationMessage.objects.create(
            agent_instance_version = self.agent_instance_version,
            response=response,
            role='assistant',
        )
        if response.tool_calls.exists():
            conversation_message.tool_calls.set(response.tool_calls.all())
        if response.message_content:
            conversation_message.add_part(response.message_content.get())

        print("___decide_next_step", conversation_message, tool_runs)
        return conversation_message
        return
        agent_instance = conversation_message.agent_instance
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
