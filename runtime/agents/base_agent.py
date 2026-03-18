from __future__ import annotations
from functools import wraps
import inspect
import json
import random
import traceback
from typing import List, Any, Dict, Optional, Type, Set
from registry.agent_def import AgentDef
from attrs import define, field
import re
from runtime.tasks.bound_agent_function import BoundAgentFunction
from runtime.context_manager import RuntimeContextTracker
from server.models.tasks.agent_task_definition import AgentTaskDefinition
from server.models.queries.query_message_part import QueryMessagePart
from server.models.enums.message_enums import MessageContentType
from registry.task_decorators import task, chain, chord, map, group,command
from server.models.enums.task_enums import TaskExecutionMode
from server.models.agents.agent_profile import AgentToolCallSyntax
from server.models.tasks.agent_task_call import AgentTaskCall
from server.models.conversation_message_part import ConversationMessagePart
from server.models.queries.query import Query, QueryAvailableTool
from server.models.content import GenericContent

from server.models.conversation_message import ConversationMessage
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from server.models.agents.agent_instance_version import AgentInstanceVersion
    from server.models.agents.agent_instance import AgentInstance
    from server.models.agents.agent_version import AgentVersion

class BaseAgent(AgentDef):
    @task()
    def add_user_message(self,  message: str|None = None, parts: List[Dict]|None = None):
        # Command detection
        text = message.strip() if message else "".join([part["content"] for part in parts]).strip() if parts else ""
        conversation_msg = ConversationMessage.objects.create(role = "user", agent_instance_version = self.agent_instance_version)
        if text.startswith("!"):
            cmd = text[2:].split(" ",1)[0]
            agent_tool = self.agent_version.tools.filter(trigger=cmd).first()
            if agent_tool:
                agent_tool: QueryAvailableTool
                agent_version = agent_tool.tool_agent_version
                agent_version:AgentVersion
                tool_agent_instance_version = agent_version.get_or_create_instance(workingdir=self.agent_instance_version.workingdir, parent_instance=self.agent_instance
                )
                tool_agent_instance_version: AgentInstanceVersion
                runtime = tool_agent_instance_version.get_runtime_instance()
                task_function = getattr(runtime, agent_tool.task_definition.name) 
            elif agent_task := self.agent_version.agent_task_definitions.filter(name=cmd).first():
                agent_task: AgentTaskDefinition
                task_function = getattr(self, agent_task.name) 
            else:
                task_function = None

            if task_function:
                # parse args if task_function is available
                cmd_payload = text[1+len(cmd):].strip()
                namespace = {}
                exec(f"def to_args(*args, **kwargs):\n  return args, kwargs\nargs, kwargs = to_args({cmd_payload})", namespace)
                print("PARSED_ARGS", namespace['args'], namespace['kwargs'])
                tool_call = task_function.delay(*namespace['args'], **namespace['kwargs'])
                conversation_msg.tool_calls.add(tool_call)
                return self._command_result_to_message.delay(command_response=tool_call)

        if parts is None and message is not None:
            parts = [{"content": message, "type": "TEXT"}]
        if parts:
            for part in parts:
                conversation_msg.add_part(part["content"])
        return conversation_msg

    @task()
    def _command_result_to_message(self, command_response ):
        conv_msg = ConversationMessage.objects.create(role = "assistant", agent_instance_version = self.agent_instance_version)
        ConversationMessagePart.objects.create(
            message=conv_msg,
            content=GenericContent.from_data(AgentTaskCall.callargs_to_json(command_response)[0]),
            content_type=MessageContentType.TEMPLATE,
            content_template=self.agent_instance_version.select_profile().task_prompt,
        )

    @task()
    def _create_new_query(self):
        from server.models.queries.query import Query
        from server.models.queries.query_message import QueryMessage
        agent_profile = self.agent_instance_version.select_profile()
        query = Query.objects.create(
            aimodel =agent_profile.aimodel,
            agent_instance_version = self.agent_instance_version,
            agent_profile = agent_profile,
        )

        available_tools = self.agent_version.tools
        if available_tools:
            for available_tool in available_tools.all():
                QueryAvailableTool.objects.create(
                    query = query,
                    tool_agent_version = available_tool.tool_agent_version,
                    task_definition = available_tool.task_definition,
                )

        # 1. System Prompt
        system_prompt = agent_profile.system_prompt
        if system_prompt:
            qmsg = QueryMessage.objects.create(role="system", query=query, index=-1)
            QueryMessagePart.objects.create(
                content = GenericContent.from_data({"instance":self.agent_instance.pk, "agent":self.agent.pk}),
                content_type = MessageContentType.TEMPLATE,
                content_template = system_prompt,
                query_message = qmsg,
            )

        # Inject Tool Definitions if CUSTOM syntax is used
        if agent_profile.tool_call_syntax == AgentToolCallSyntax.CUSTOM:
            tool_defs = []
            for tdef in available_tools:
                tool_defs.append(f"Tool: {tdef.name}\nDescription: {tdef.description}\nSchema: {json.dumps(tdef.function_schema)}")

            tool_instructions = "\n\nAvailable Tools (use syntax [call:tool_name(arg=val)]):\n" + "\n---\n".join(tool_defs)
            system_prompt = (system_prompt or "") + tool_instructions

        return query

    @task(description="Send query to LLM provider")
    def _execute_query(self, query:Query):
        from server.models.queries.response import Response
        from openai import OpenAI
        query.apikey = random.choice(list(query.aimodel.api_provider.api_keys.all()))
        query.status = "ACTIVE"
        query.save()
        try:
            messages = query.compile()
            tool_call_syntax =query.agent_instance_version.select_profile().tool_call_syntax
            api_tools = []

            # Tools are only passed as API tools if syntax is DEFAULT
            if tool_call_syntax == AgentToolCallSyntax.DEFAULT:
                for tdef in query.available_tools.all():
                    tdef : QueryAvailableTool
                    tadef = tdef.task_definition
                    api_tools.append({
                        "type": "function",
                        "function": {
                            "name": tadef.name,
                            "description": tadef.description,
                            "parameters": tadef.function_schema
                        }
                    })

            api_params = {
                "model": query.aimodel.name,
                "messages": messages,
                #"extra_body": {
                #        "think": False,
                #        "thinking": False,
                #        "reasoning_effort": "none"
                #    }
            }
            if api_tools:
                api_params["tools"] = api_tools
                api_params["tool_choice"] = "auto"

            client = OpenAI(api_key=query.apikey.key, base_url=query.aimodel.api_provider.url)
            streaming = False
            #if streaming:
            #    llmResponse, conversationMessage = run_query_streaming(query, client, api_params)
            #else:
            #    llmResponse, conversationMessage = run_query_non_streaming(query, client, api_params)
            from server.models.debug_log_entry import DebugLogEntry
            DebugLogEntry.objects.create(agent_instance=self.agent_instance, event='raw_query', data=api_params)
           
            api_response = client.chat.completions.create(**api_params)
            response = Response.objects.create(
                query=query,
                aimodel=query.aimodel,
                agent_profile=query.agent_profile,
                agent_instance_version=query.agent_instance_version,
                data=json.loads(api_response.model_dump_json()),
                status="SUCCESS"
            )
            content, tool_call_tasks = self._parse_query_response(response=response)
            return dict(response=response, message=content, tool_calls=tool_call_tasks)

        except Exception:
            query.status = "FAILURE"
            query.save()
            from server.models.debug_log_entry import DebugLogEntry
            DebugLogEntry.objects.create(agent_instance=self.agent_instance, event='exception', data={"exception": traceback.format_exc()})
            raise

    def _parse_query_response(self, response):
        from server.models.conversation_message import ConversationMessage
        import re
        try:

            msg_data = response.data['choices'][0].get('message', {})
            content = msg_data.get("content", "")
            api_tool_calls = msg_data.get('tool_calls', [])
            custom_tool_calls = []
            if response.agent_profile.tool_call_syntax == AgentToolCallSyntax.CUSTOM and content:
                # Very basic regex parser for demonstration
                pattern = r"\[call:(\w+)\((.*?)\)\]"
                matches = re.finditer(pattern, content)
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
                print("all_tool_calls", all_tool_calls)
                for tc_data in all_tool_calls:
                    tc_id = tc_data['id']
                    func_name = tc_data['function']['name']
                    kwargs = json.loads(tc_data['function']['arguments'])
                    queryAvailableTools = response.query.available_tools.filter(task_definition__name=func_name)
                    print("queryAvailableTools", queryAvailableTools)
                    for queryAvailableTool in queryAvailableTools:
                        queryAvailableTool: QueryAvailableTool
                        agent_version = queryAvailableTool.tool_agent_version
                        agent_version:AgentVersion
                        tool_agent_instance_version = agent_version.get_or_create_instance(
                            workingdir=self.agent_instance_version.workingdir,
                            parent_instance=self.agent_instance
                        )
                        tool_agent_instance_version: AgentInstanceVersion
                        rt = tool_agent_instance_version.get_runtime_instance()
                        rt: AgentRuntime
                        func = getattr(rt, func_name)
                        func: BoundAgentFunction
                        tool_call_tasks.append(AgentTaskCall.create(func.instance(), args=[], kwargs=kwargs))
                        # we just return them, they are linked to their parent by the calling AgentTaskRun.create_and_run function when this function is successfull,
                        # and are started started by AgentTaskCall.run when this AgentTaskRun.create_and_run returns successfull
             
            if tool_call_tasks:
                print("set toolcals", tool_call_tasks)
                for tool_call_task in tool_call_tasks:
                    tool_call_task.apply_async()
            return content, tool_call_tasks

        except Exception:
            from server.models.debug_log_entry import DebugLogEntry
            DebugLogEntry.objects.create(agent_instance=self.agent_instance, event='exception', data={"exception": traceback.format_exc()})
            raise

    @group(description="building group task")
    def group(self, *tasks):
        return tasks

    @chain(description="building chain task")
    def chain(self, *tasks):
        return tasks



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
