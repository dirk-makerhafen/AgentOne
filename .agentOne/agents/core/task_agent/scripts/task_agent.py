from __future__ import annotations
from runtime.agents.base_agent import AgentRuntime
from server.models.content import GenericContent
from server.models.queries.query_message import QueryMessage
from server.models.queries.query_message_part import QueryMessagePart
from server.models.enums.message_enums import MessageContentType
from registry.task_decorators import task


@task()
def run(runtime: AgentRuntime, **kwargs):
    query = runtime.create_query.delay(**kwargs)
    response = runtime.execute_query.delay(query)
    response_handled = runtime.handle_response.delay(response)
    response_content = runtime.decide_next_step.delay(response_handled)
    return response_content

@task()
def create_query(runtime: AgentRuntime, task_prompt=None, **kwargs):
    print("test")
    query = runtime.new_query.call()
    query_message = QueryMessage.objects.create(role="user", query=query, index=-1)
    QueryMessagePart.objects.create(
        content = GenericContent.from_data(kwargs),
        content_type = MessageContentType.TEMPLATE,
        content_template = task_prompt if task_prompt else query.agent_profile.task_prompt,
        query_message = query_message,
    )
    print("test")
    return query

@task()
def decide_next_step(runtime: AgentRuntime, response, tool_runs):
    print("here")
    print("___decide_next_step", response, tool_runs)
    if len(tool_runs) > 0:
        pass
    else:
        pass
    return response.message_content.get()
