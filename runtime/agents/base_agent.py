from __future__ import annotations
from functools import wraps
import inspect
import json
from pathlib import Path
import random
import traceback
from typing import List, Any, Dict, Optional, Type, Set
from registry.profile import Profile
from registry.sub_agents import Subagents
import re
import shlex
import ast
from runtime.tasks.bound_agent_function import BoundAgentFunction
from runtime.context_manager import RuntimeContextTracker
from server.models.tasks.agent_task_definition import AgentTaskDefinition
from server.models.queries.query_message_part import QueryMessagePart
from server.models.enums.message_enums import MessageContentType
from registry.task_decorators import task, chain, chord, map, group,command
from server.models.agents.agent_profile import AgentToolCallSyntax
from server.models.tasks.agent_task_call import AgentTaskCall
from server.models.tasks.agent_task_run import  AgentTaskRun
from server.models.conversation_message_part import ConversationMessagePart
from server.models.queries.query import Query, QueryAvailableTool, QueryStatus
from server.models.queries.response import Response, ResponseStatus

from server.models.content import GenericContent

from registry.agent_registry import AgentRegistry
from server.models.agents.agent_instance_version import AgentInstanceVersion
from server.models.agents.agent import Agent
from server.models.agents.agent_version import AgentVersion, AgentVersionSubAgentRelation
from registry.profile import Profile
from server.models.content import GenericContent
from registry.utils import get_import_strings

from server.models.conversation_message import ConversationMessage
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from server.models.agents.agent_instance_version import AgentInstanceVersion
    from server.models.agents.agent_instance import AgentInstance
    from server.models.agents.agent_version import AgentVersion


class BaseAgent():
    """
    Base class for all agent definitions.
 
    Class-level attributes (agent, agent_version, etc.) are populated either by
    AgentRegistry.register() at startup, Instance-level attributes shadow them after __init__ runs.
    """

    parent: BaseAgent | None
    subagents: Subagents|None

    def __init__(self, name:Optional[str] = None, display_name:Optional[str]=None, workingdir:str|None|Path=None, profile:Profile|None=None, agent_instance_version: AgentInstanceVersion|None=None, parent:BaseAgent|None=None):
        # Inherit workingdir from parent agent if not explicitly provided.
        # self.parent set by __init_subclass__
        if not self.parent and parent:
            self.parent = parent
        if not workingdir and self.parent and self.parent.agent_instance_version:
            workingdir = self.parent.agent_instance_version.workingdir

        if agent_instance_version:
            # Instance version was injected directly (runtime loading path via
            # AgentInstanceVersion.get_runtime_instance). Trust it, skip DB check.
            self.agent = agent_instance_version.agent
            self.agent_version = agent_instance_version.agent_version
            self.agent_instance_version = agent_instance_version
            self.is_registered = True
        else:
            self.agent = getattr(self.__class__,"agent", None)  # injected by the backend loaded via in AgentVersion.get_runtime_class, otherwise get from db now
            if not self.agent:
                self.agent = Agent.objects.get(name=self.__class__.__name__)
            if not self.agent_version:
                self.agent_version = self.agent.agent_versions.order_by("-version_number").first()
        
            parent_instance_version = self.parent.agent_instance_version if self.parent else None

            self.is_registered = getattr(self.__class__, "is_registered", False)
            if not self.is_registered:
                source_path = inspect.getfile(self.__class__)
                source_code = inspect.getsource(self.__class__)
                python_dependencies = get_import_strings(source_path, self.__class__.__name__)
                source_changed = (not self.agent_version or self.agent_version.source_path != source_path or self.agent_version.source_code.content != source_code)
                python_dependencies_changed = (not self.agent_version or self.agent_version.python_dependencies != python_dependencies)
                self.is_registered = not (source_changed or python_dependencies_changed)
 
            if not self.is_registered:
                raise Exception("Only registerd classed can be inititalized")
            
            self.agent_instance_version = self.agent_version.get_or_create_instance(
                name = name,
                display_name = display_name,
                workingdir = workingdir,
                parent_instance_version = parent_instance_version,
            )

        self.agent_instance = self.agent_instance_version.agent_instance
        self.workingdir = self.agent_instance_version.workingdir
        self.is_registered = True
        if hasattr(self, "subagents") and self.subagents:
            self.subagents.runtime_init(self)


    def __init_subclass__(cls, **kwargs):
        """
        Wraps __init__ for every subclass of BaseAgent (ChatAgent, BaseAgent, etc.)
        to inject two behaviours before the real __init__ runs:
 
          1. Parent tracking: set self.parent to the BaseAgent instance currently
             active on the RuntimeContextTracker stack. This captures the agent that
             is constructing this one (e.g. a parent agent spinning up a sub-agent).
 
          2. Instance reset: clear all instance-level agent attributes so each new
             instance starts clean, regardless of what is cached on the class.
 
        Why the try/except for self.parent:
            __init_subclass__ fires once per class in the MRO, so for a hierarchy
            like ChatAgent -> BaseAgent -> BaseAgent, three wrappers are composed.
            The outermost wrapper (ChatAgent's) runs first and sets self.parent.
            The inner wrappers (BaseAgent's, BaseAgent's) must NOT overwrite it —
            self.parent is already correct by the time they execute. The
            AttributeError guard achieves this: only the first wrapper to run
            (which finds no self.parent yet) actually sets it from the tracker.
        """
        original_init = cls.__init__

        @wraps(original_init)
        def wrapped_init(self, *args, **kwargs):
            self.id = f"{cls.__name__}:{random.random():.5f}"

            # Only set parent if not already set by an outer (more-derived) wrapper.
            try:
                _ = self.parent  # will raise AttributeError on first (outermost) call
            except AttributeError:
                self.parent = RuntimeContextTracker.current

            # Reset instance state so class-level cached values don't bleed through.
            self.profile = None
            self.agent = None
            self.agent_version = None
            self.agent_instance = None
            #self.agent_instance_version = None
            self.is_registered = False

            # Push self onto the context stack so any agents constructed during
            # __init__ (sub-agents) will find this instance as their parent.
            with RuntimeContextTracker(self):
                original_init(self, *args, **kwargs)

        cls.__init__ = wrapped_init

    @classmethod
    def register(cls, recursive=False):
        ar = AgentRegistry()
        return ar.register(cls,recursive=recursive)

    def add_user_message(self,  message: str|None = None, parts: List[Dict]|None = None):
        if parts is None and message is not None:
            parts = [{"content": message, "type": "TEXT"}]
        if not parts:
            raise Exception("No message or message parts provided")
        
        conversation_msg = ConversationMessage.objects.create(role = "user", agent_instance_version = self.agent_instance_version)
        if parts[0] and parts[0].get("content", [None,])[0] == "!": # might be command
            cmd = parts[0].get("content", [None,]).split(None,1)[0][1:] # Get command without '!'
            task_function = None
            print("CMD", cmd)
            agent_tool = self.agent_version.tools.filter(task_definition__trigger=cmd).first()
            if agent_tool:
                tool_agent_instance_versio_runtime = agent_tool.tool_agent_version.get_or_create_instance().get_runtime_instance()
                task_function = getattr(tool_agent_instance_versio_runtime, agent_tool.task_definition.name, None)
                print("tool_agent_instance_versio_runtime", tool_agent_instance_versio_runtime, agent_tool.task_definition.name, task_function)
            else:
                agent_task = self.agent_version.task_definitions.filter(name=cmd).first()
                if agent_task:
                    task_function = getattr(self, agent_task.name, None)
                    print("task_function", task_function,  agent_task.name, task_function)
            if task_function:
                full_cmd_str = "".join([part["content"] for part in parts]).strip() if parts else ""
                cmd_payload = full_cmd_str[1+len(cmd):].strip()
                # Safely parse arguments and keyword arguments
                _payload_ast_tree = ast.parse(f"f({cmd_payload})")
                call = _payload_ast_tree.body[0].value if _payload_ast_tree.body else None
                args = [ast.literal_eval(arg) for arg in call.args] if call else []
                kwargs = {kw.arg: ast.literal_eval(kw.value) for kw in call.keywords} if call else {}

                # Schedule command Tool Call
                command_tool_call = task_function.delay(*args, **kwargs)
                
                conversation_msg.tool_calls.add(command_tool_call)
                return self._handle_command_response.delay(command_response=command_tool_call)
        
        for part in parts:
            conversation_msg.add_part(part["content"])
        return conversation_msg


    def _create_query(self):
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
                index=get_index()
            )

        # Inject Tool Definitions if CUSTOM syntax is used
        if agent_profile.tool_call_syntax == AgentToolCallSyntax.CUSTOM:
            query_message = QueryMessage.objects.create(role="system", query=query, index=get_index())
            QueryMessagePart.objects.create(
                query_message = query_message,
                content = GenericContent.from_text('Available Tools (use syntax [call:tool_name(arg=val)]):\n'),
                index=get_index()
            )
            for tdef in available_tools:
                QueryMessagePart.objects.create(
                    query_message = query_message,
                    content = GenericContent.from_text(f"Tool: {tdef.name}\nDescription: {tdef.description}\nSchema: {json.dumps(tdef.function_schema)}\n"),
                    index=get_index()
                )

        return query
    
    @task(description="Send query to LLM provider")
    def _execute_query(self, query: Query):
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
            DebugLogEntry.objects.create(agent_instance=self.agent_instance, event='raw_query', data=api_params)

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
                agent_instance=self.agent_instance,
                event='exception',
                data={"exception": traceback.format_exc()},
            )
            raise

    @task()
    def _handle_response(self, response:Response) -> dict[str,Response|AgentTaskRun]:
        try:
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
                            workingdir = self.agent_instance_version.workingdir,
                            parent_instance_version = self.agent_instance_version,
                        )
                        rt: BaseAgent = tool_agent_instance_version.get_runtime_instance()
                        func: BoundAgentFunction = getattr(rt, func_name)
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
            DebugLogEntry.objects.create(agent_instance=self.agent_instance, event='exception', data={"exception": traceback.format_exc()})
            raise

    @task()
    def _handle_command_response(self, command_response ):
        conv_msg = ConversationMessage.objects.create(role = "assistant", agent_instance_version = self.agent_instance_version)
        ConversationMessagePart.objects.create(
            message=conv_msg,
            #content=GenericContent.from_data(AgentTaskCall.callargs_to_json(command_response)[0]),
            content=GenericContent.from_data(command_response),
            content_type=MessageContentType.TEXT
            ,
        )
        return conv_msg

    @group(description="building group task")
    def group(self, *tasks):
        return tasks

    @chain(description="building chain task")
    def chain(self, *tasks):
        return tasks

    @task()
    def ping(self, message: str|None = None):
        r = f"Pong from Agent {self.agent.name}, Version {self.agent_version.version_number}, Instance {self.agent_instance.name}"
        if message:
            r += f"\nMessage received:{message}"
        return r













    '''
    def spawn_subagent_session(self, subagent_name: str, instance_name: Optional[str] = None, **kwargs) -> 'BaseAgent':
        """
        Spawns a new, isolated instance of a declared subagent type for delegation.
        The subagent must be declared with `create='agent'` or `create='both'`.

        Args:
            subagent_name: The name of the subagent as declared in `self.subagents`.
            instance_name: An optional name for this specific spawned instance.
            kwargs: Additional arguments to pass to the subagent's constructor.

        Returns:
            The new subagent instance.

        Raises:
            ValueError: If the subagent is not declared or cannot be spawned by an agent.
        """
        for subagent_relations in self.agent_version.subagent_relations.filter(create_option="auto"):

        declaration = self._get_subagent_declarations().get(subagent_name)
        if not declaration:
            raise ValueError(f"Subagent '{subagent_name}' not declared in '{self.name}'.")

        if declaration.create_option not in ["agent", "both"]:
            raise ValueError(f"Subagent '{subagent_name}' cannot be spawned by an agent (create='{declaration.create_option}').")

        # Instantiate the subagent
        new_subagent_instance = declaration.agent_class(
            name=instance_name or f"{declaration.agent_class.__name__}-{str(uuid.uuid4())[:4]}",
            workingdir=self.workingdir, # Inherit working directory
            parent_agent=self, # Set this agent as the parent
            _subagent_declaration=declaration, # Store declaration for runtime use
            **kwargs
        )
        # The new instance will register itself with the runtime during its own __init__
        print(f"Agent '{self.name}' spawned new session for '{declaration.agent_class.__name__}' (instance ID: {new_subagent_instance.instance_id}).")
        return new_subagent_instance

    def get_subagent_by_instance_name(self, instance_name: str) -> Optional['BaseAgent']:
        """
        Retrieves an 'auto' bound subagent instance by its assigned instance_name.
        This provides direct access to auto-created subagents.

        Args:
            instance_name: The name given in the Subagent declaration (or inferred).

        Returns:
            The auto-bound subagent instance, or None if not found or not auto-bound.
        """
        # This assumes _setup_subagents has already bound these attributes
        return getattr(self, instance_name, None)

    def get_active_subagent_sessions(self, subagent_name: Optional[str] = None, requester_is_user: bool = False) -> List['BaseAgent']:
        """
        Retrieves a list of active subagent sessions that are visible to the requester.

        Args:
            subagent_name: Optional. The name of the subagent type to filter by.
            requester_is_user: If True, filters for sessions visible to the user.
                               If False (requester is an agent), filters for sessions visible to agents,
                               including those specifically visible to the 'creator' if this agent is the creator.

        Returns:
            A list of active subagent instances.
        """
        target_declaration: Optional[Subagent] = None
        agent_class_to_filter: Optional[Type] = None

        if subagent_name:
            target_declaration = self._get_subagent_declarations().get(subagent_name)
            if not target_declaration:
                print(f"Warning: Subagent '{subagent_name}' not declared in '{self.name}'. Cannot filter accurately.")
                return []
            agent_class_to_filter = target_declaration.agent_class

        # Determine the visibility filter for the runtime
        visibility_filter: Literal["agent", "user", "creator", "both"]
        if requester_is_user:
            visibility_filter = "user"
        else:
            # An agent requesting wants to see what's broadly visible to agents
            # or what it specifically created. The runtime will handle the 'creator' check.
            visibility_filter = "agent"

        return _AGENTONE_RUNTIME.get_sessions(
            agent_class=agent_class_to_filter,
            requester_agent=self, # Pass self so runtime can check 'creator' visibility
            visible_to_filter=visibility_filter 
        )


        '''
    
    