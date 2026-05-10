    
from __future__ import annotations
import json
import traceback
import re
from runtime.agents.base_agent import AgentRuntime, BoundTask
from runtime.context_manager import RuntimeContextTracker
from server.models.conversation_message import ConversationMessage
from server.models.conversation_message_part import ConversationMessagePart
from server.models.queries.query_message_part import QueryMessagePart
from server.models.enums.message_enums import MessageContentType
from registry.task_decorators import task, chain, group,command
from server.models.agents.profile import AgentToolCallSyntax
from server.models.tasks.agent_task_call import AgentTaskCall
from server.models.tasks.agent_task_run import  AgentTaskRun
from server.models.queries.query import Query, QueryAvailableTool, QueryStatus
from server.models.queries.response import Response

from server.models.content import GenericContent

from server.models.agents.agent_instance_version import InstanceVersionModel
from server.models.agents.agent_version import AgentVersionModel
from server.models.content import GenericContent

from typing import TYPE_CHECKING
from server.models.queries.query import Query
from server.models.queries.query_message import QueryMessage


# LLM QUERY HANDLING
@task()
def new_query(runtime: AgentRuntime):

    agent_profile = runtime.agent_instance_version.select_profile()
    query = Query.objects.create(
        aimodel = agent_profile.aimodel,
        agent_instance_version = runtime.agent_instance_version,
        agent_profile = agent_profile,
    )

    available_tools = runtime.agent_version.tools()
    if available_tools:
        for available_tool in available_tools.all():
            QueryAvailableTool.objects.create(
                query = query,
                tool_agent_version = available_tool.tool_agent_version,
                task_definition = available_tool.task_definition,
            )

    index = -1
    def get_index():
        nonlocal index
        index += 1
        return index
    
    # 1. System Prompt
    system_prompt = agent_profile.system_prompt
    if system_prompt:
        qmsg = QueryMessage.objects.create(role="system", query=query, index=get_index())
        QueryMessagePart.objects.create(
            content = GenericContent.from_data({}),
            content_type = MessageContentType.TEMPLATE,
            content_template = system_prompt,
            query_message = qmsg,
            index = get_index()
        )

    # Inject Tool Definitions if CUSTOM syntax is used
    if agent_profile.tool_call_syntax == AgentToolCallSyntax.CUSTOM:
        query_message = QueryMessage.objects.create(role="system", query=query, index=get_index())
        QueryMessagePart.objects.create(
            query_message = query_message,
            content = GenericContent.from_text('Available Tools (use syntax [call:tool_name(arg=val)]):\n'),
            index = get_index()
        )
        for tdef in available_tools:
            QueryMessagePart.objects.create(
                query_message = query_message,
                content = GenericContent.from_text(f"Tool: {tdef.name}\nDescription: {tdef.description}\nSchema: {json.dumps(tdef.function_schema)}\n"),
                index = get_index()
            )

    return query

@task(description="Send query to LLM provider")
def execute_query(runtime: AgentRuntime, query: Query):
    from server.models.queries.response import Response
    from openai import OpenAI
    from runtime.rate_limiter import RateLimitChecker, RateLimitError

    # --- Rate limit check + key selection ---
    # This is the only place rate limits are enforced.
    # RateLimitError is caught separately in AgentTaskRun.apply() and sets
    # status=RATE_LIMITED rather than FAILURE — no retry budget consumed.
    result = RateLimitChecker.check(query.aimodel)
    query.apikey = result.selected_key
    # --- End rate limit check ---

    query.status = "ACTIVE"
    query.save()
    try:
        messages = query.compile()
        tool_call_syntax = query.agent_instance_version.select_profile().tool_call_syntax
        api_tools = []

        if tool_call_syntax == AgentToolCallSyntax.DEFAULT:
            for tdef in query.available_tools.all():
                tdef: QueryAvailableTool
                tadef = tdef.task_definition
                api_tools.append({
                    "type": "function",
                    "function": {
                        "name": tadef.name,
                        "description": tadef.description,
                        "parameters": tadef.function_schema,
                    }
                })

        api_params = {
            "model": query.aimodel.name,
            "messages": messages,
            "extra_body": {}
        }
        if query.agent_profile.thinking is False:
            api_params["extra_body"]["reasoning_effort"] = "none"
            api_params["extra_body"]["thinking"] = False
            api_params["extra_body"]["think"] = False

        if api_tools:
            api_params["tools"] = api_tools
            api_params["tool_choice"] = "auto"

        client = OpenAI(api_key=query.apikey.key, base_url=query.aimodel.api_provider.url)

        from server.models.debug_log_entry import DebugLogEntry
        DebugLogEntry.objects.create(agent_instance=runtime.agent_instance, event='raw_query', data=api_params)

        api_response = client.chat.completions.create(**api_params)
        response_data = json.loads(api_response.model_dump_json())
        message_data = response_data['choices'][0].get('message', None)
        message_content = None
        message_reasoning = None
        if message_data:
            message_content = message_data.get("content", None)
            message_reasoning =  message_data.get("reasoning", None)
            if message_content is not None:
                message_content = GenericContent.from_text(message_content)
                del message_data["content"]
            if message_reasoning is not None:
                message_reasoning = GenericContent.from_text(message_reasoning)
                del message_data["reasoning"]

        response = Response.objects.create(
            query = query,
            aimodel = query.aimodel,
            agent_profile = query.agent_profile,
            agent_instance_version = query.agent_instance_version,
            data = response_data,
            message_content = message_content,
            message_reasoning = message_reasoning,
            status = "SUCCESS",
        )
        query.status = QueryStatus.SUCCESS
        query.save()
        return dict(response=response)

    except RateLimitError:
        query.status = QueryStatus.FAILURE
        query.save()
        # Don't touch query.status — the run will be re-dispatched by the
        # scheduler and _execute_query will be called again from scratch.
        raise  # re-raise so apply() can catch it by type

    except Exception:
        query.status = QueryStatus.FAILURE
        query.save()
        from server.models.debug_log_entry import DebugLogEntry
        DebugLogEntry.objects.create(
            agent_instance=runtime.agent_instance,
            event='exception',
            data={"exception": traceback.format_exc()},
        )
        raise

@task()
def handle_response(runtime: AgentRuntime, response:Response) -> dict[str,Response|AgentTaskRun]:
    try:
        print("handle_response", runtime, response)
        api_tool_calls = response.data.get('choices', [{},])[0].get('message', {}).get("tool_calls", None)

        custom_tool_calls = [] 
        if response.agent_profile.tool_call_syntax == AgentToolCallSyntax.CUSTOM and response.message_content:
            # Very basic regex parser for demonstration
            pattern = r"\[call:(\w+)\((.*?)\)\]"
            matches = re.finditer(pattern, response.message_content.get())
            for match in matches:
                func_name = match.group(1)
                raw_args = match.group(2)
                kwargs = {}
                if raw_args:
                    # Split by comma not inside quotes
                    parts = re.split(r",(?=(?:[^']*'[^']*')*[^']*$)", raw_args)
                    for p in parts:
                        if "=" in p:
                            k, v = p.split("=", 1)
                            kwargs[k.strip()] = v.strip().strip("'").strip('"')
                custom_tool_calls.append({"id": 23, "function": { "name": func_name, "arguments": kwargs}})

        all_tool_calls = (api_tool_calls or []) + custom_tool_calls
        tool_call_tasks = []
        if all_tool_calls :
            for tc_data in all_tool_calls:
                tc_id = tc_data['id']
                func_name = tc_data['function']['name']
                if isinstance(tc_data['function']['arguments'], str):
                    kwargs = json.loads(tc_data['function']['arguments'])
                else:
                    kwargs = tc_data['function']['arguments']
                available_tool_query = response.query.available_tools.filter(task_definition__name=func_name)
                for available_tool in available_tool_query:
                    available_tool: QueryAvailableTool
                    agent_version:AgentVersion = available_tool.tool_agent_version
                    tool_agent_instance_version:AgentInstanceVersion = agent_version.get_or_create_instance(
                        workingdir = runtime.agent_instance_version.workingdir,
                        parent_instance_version = runtime.agent_instance_version,
                    )
                    rt: AgentRuntime = tool_agent_instance_version.get_runtime_instance()
                    func: BoundTask = rt.__getattribute__(func_name)
                    task_call = AgentTaskCall.create(func.instance(), args=[], kwargs=kwargs)
                    tool_call_tasks.append(task_call)
                    # we just return them, they are linked to their parent by the calling AgentTaskRun.create_and_run function when this function is successfull,
                    # and are started started by AgentTaskCall.run when this AgentTaskRun.create_and_run returns successfull
        tool_runs = []
        for tool_call_task in tool_call_tasks:
            tool_runs.append(tool_call_task.apply_async())
        response.tool_calls.set(tool_call_tasks)
        # return tool_call_tasks to the framework can pick them up and wait for them to finish
        return dict(response=response, tool_runs=tool_runs)

    except Exception:
        from server.models.debug_log_entry import DebugLogEntry
        DebugLogEntry.objects.create(agent_instance=runtime.agent_instance, event='exception', data={"exception": traceback.format_exc()})
        raise

# USER COMMANDS

@task()
def handle_user_command(runtime: AgentRuntime, conversation_msg, command, cmdargs, cmdkwargs):
    taskdefinition = runtime.commands().filter(trigger=command).first()
    if not taskdefinition:
        taskdefinition = runtime.commands().filter(name=command).first()
    if not taskdefinition:
        taskdefinition = runtime.tools().filter(name=command).first()
    if not taskdefinition:
        taskdefinition = runtime.tasks().filter(name=command).first()

    if taskdefinition:
        
        # Schedule command Tool Call
        # add toolcall to user message
        command_tool_call = runtime.__getattribute__(command).delay(*cmdargs, **cmdkwargs)
        conversation_msg.tool_calls.add(command_tool_call)
    return runtime.handle_command_response.delay(command_response=command_tool_call)

@task()
def handle_command_response(runtime: AgentRuntime, command_response ):
    conv_msg = ConversationMessage.objects.create(role = "assistant", agent_instance_version = runtime.agent_instance_version)
    ConversationMessagePart.objects.create(
        message=conv_msg,
        #content=GenericContent.from_data(AgentTaskCall.callargs_to_json(command_response)[0]),
        content=GenericContent.from_data(command_response),
        content_type=MessageContentType.TEXT,
    )
    return conv_msg

@group(description="building group task")
def group(runtime, *tasks):
    return tasks

@chain(description="building chain task")
def chain(runtime, *tasks):
    return tasks

@command()
def ping(runtime, message: str|None = None):
    r = f"Pong from Agent {runtime.agent.name}, Version {runtime.agent_version.version_number}, Instance {runtime.agent_instance.name}"
    if message:
        r += f"\nMessage received:{message}"
    return r
