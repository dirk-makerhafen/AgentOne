from __future__ import annotations
from runtime.agents.base_agent import BaseAgent
from server.models.content import GenericContent
from server.models.queries.query_message import QueryMessage
from server.models.queries.query_message_part import QueryMessagePart
from server.models.enums.message_enums import MessageContentType
from registry.task_decorators import task, chain


class TaskAgent(BaseAgent):

    @chain()
    def run(self, **kwargs):
        return [
            self._create_query.i(),     # **kwargs -> query
            self._execute_query.i(),    # query -> response
            self._handle_response.i(),  # response -> response, tool_runs
            self._decide_next_step.i(), # response, tool_runs -> str
        ]

    @task()
    def _create_query(self, task_prompt=None, **kwargs):
        print("test")
        query = super()._create_query()
        query_message = QueryMessage.objects.create(role="user", query=query, index=-1)
        QueryMessagePart.objects.create(
            content = GenericContent.from_data(kwargs),
            content_type = MessageContentType.TEMPLATE,
            content_template = task_prompt if task_prompt else query.agent_settings.task_prompt,
            query_message = query_message,
        )
        print("test")
        return query

    @task()
    def _decide_next_step(self, response, tool_runs):
        print("here")
        print("___decide_next_step", response, tool_runs)
        return response.message_content.get()
