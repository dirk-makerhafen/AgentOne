from __future__ import annotations
from typing import List, Any, Dict
import ast
from runtime.agents.bound_task import BoundTask
from server.models.agents.agent import AgentModel
from server.models.sessions.session import SessionModel
from server.models.agents.agent_version import AgentVersionModel
from server.models.sessions.session_version import SessionVersionModel
from server.models.message import Message
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from server.models.sessions.session_version import SessionVersionModel


class AgentRuntime():
    def __init__(self, session_version: SessionVersionModel ):
        self.agent:AgentModel = session_version.agent
        self.agent_instance:SessionModel = session_version.session
        self.session_version:SessionVersionModel = session_version
        self.agent_version: AgentVersionModel = session_version.agent_version

    def __getattribute__(self, name: str) -> Any:
        try:
            return object.__getattribute__(self, name)
        except Exception as e:
            task = object.__getattribute__(self, "all_tasks")(filter=dict(name=name)).first()
            if task:
                return BoundTask(self, task)
            raise Exception(f"Task '{name}' not found in {self}")

    def all_tasks(self, filter:Dict={}):
        return self.tasks().filter(**filter).union(self.tools().filter(**filter)).union(self.commands().filter(**filter)).union(self.skills().filter(**filter))

    def tasks(self):
        return self.agent.latest_agent_version.tasks()

    def tools(self):
        return  self.agent.latest_agent_version.tools()

    def commands(self):
        return  self.agent.latest_agent_version.commands()

    def skills(self):
        return  self.agent.latest_agent_version.skills()

    def add_user_message(self,  message: str|None = None, parts: List[Dict]|None = None):
        if parts is None and message is not None:
            parts = [{"content": message, "type": "TEXT"}]
        if not parts:
            raise Exception("No message or message parts provided")
        
        conversation_msg = Message.objects.create(role = "user", session_version = self.session_version)
        if parts[0] and parts[0].get("content", [None,])[0] == "!": # might be command
            cmd = parts[0].get("content", [None,]).split(None,1)[0][1:].strip()  # Get command without '!'
            task_function = None
            print("CMD", cmd)
            taskdefinition = self.commands().filter(trigger=cmd).first()
            if not taskdefinition:
                taskdefinition = self.commands().filter(name=cmd).first()
            if not taskdefinition:
                taskdefinition = self.tools().filter(name=cmd).first()
            if not taskdefinition:
                taskdefinition = self.tasks().filter(name=cmd).first()

            if taskdefinition:
                task_function = self.__getattribute__(taskdefinition.name)
                print("task_function", task_function,  taskdefinition.name, task_function, taskdefinition.path)
            if task_function:

                full_cmd_str = "".join([part["content"] for part in parts]).strip() if parts else ""
                cmd_payload = full_cmd_str[1+len(cmd):].strip()
                # Safely parse arguments and keyword arguments
                _payload_ast_tree = ast.parse(f"f({cmd_payload})")
                call = _payload_ast_tree.body[0].value if _payload_ast_tree.body else None
                args = [ast.literal_eval(arg) for arg in call.args] if call else []
                kwargs = {kw.arg: ast.literal_eval(kw.value) for kw in call.keywords} if call else {}
                return self.handle_user_command.delay(conversation_msg, cmd, cmdargs = args, cmdkwargs = kwargs)

            print("NOT TASK!")
        for part in parts:
            conversation_msg.add_part(part["content"])
        return self.handle_chat_message.delay(message=conversation_msg)


'''
class BaseAgent():
    """
    Base class for all agent definitions.
 
    Class-level attributes (agent, agent_version, etc.) are populated either by
    AgentRegistry.register() at startup, Session-level attributes shadow them after __init__ runs.
    """

    parent: BaseAgent | None
    subagents: Subagents|None

    def __init__(self, name:Optional[str] = None, display_name:Optional[str]=None, workingdir:str|None|Path=None, profile:Profile|None=None, session_version: AgentInstanceVersion|None=None, parent:BaseAgent|None=None):
        # Inherit workingdir from parent agent if not explicitly provided.
        # self.parent set by __init_subclass__
        if not self.parent and parent:
            self.parent = parent
        if not workingdir and self.parent and self.parent.session_version:
            workingdir = self.parent.session_version.workingdir

        if session_version:
            # Session version was injected directly (runtime loading path via
            # AgentInstanceVersion.get_runtime). Trust it, skip DB check.
            self.agent = session_version.agent
            self.agent_version = session_version.agent_version
            self.session_version = session_version
            self.is_registered = True
        else:
            self.agent = getattr(self.__class__,"agent", None)  # injected by the backend loaded via in AgentVersion.get_runtime_class, otherwise get from db now
            if not self.agent:
                self.agent = Agent.objects.get(name=self.__class__.__name__)
            if not self.agent_version:
                self.agent_version = self.agent.agent_versions.order_by("-version_number").first()

            parent_instance_version = self.parent.session_version if self.parent else None

            self.is_registered = getattr(self.__class__, "is_registered", False)
            if not self.is_registered:
                source_path = inspect.getfile(self.__class__)
                source_code = inspect.getsource(self.__class__)
                python_dependencies = get_import_strings(source_path, self.__class__.__name__)
                source_changed = (not self.agent_version or self.agent_version.source_path != source_path or self.agent_version.source_code.content != source_code)
                python_dependencies_changed = (not self.agent_version or self.agent_version.python_dependencies != python_dependencies)
                self.is_registered = not (source_changed or python_dependencies_changed)
 
            if not self.is_registered:
                raise Exception(f"Only registered classed can be inititalized, failed {self}")
            
            self.session_version = self.agent_version.get_or_create_instance(
                name = name,
                display_name = display_name,
                workingdir = workingdir,
                parent_instance_version = parent_instance_version,
            )

        self.agent_instance = self.session_version.agent_instance
        self.workingdir = self.session_version.workingdir
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
 
          2. Session reset: clear all instance-level agent attributes so each new
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
            #self.session_version = None
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
        
        conversation_msg = Message.objects.create(role = "user", session_version = self.session_version)
        if parts[0] and parts[0].get("content", [None,])[0] == "!": # might be command
            cmd = parts[0].get("content", [None,]).split(None,1)[0][1:] # Get command without '!'
            task_function = None
            print("CMD", cmd)
            agent_tool = self.agent_version.tools.filter(task_definition__trigger=cmd).first()
            if agent_tool:
                tool_agent_instance_versio_runtime = agent_tool.tool_agent_version.get_or_create_instance().get_runtime()
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
                return self.handle_command_response.delay(command_response=command_tool_call)
        
        for part in parts:
            conversation_msg.add_part(part["content"])
        return conversation_msg

    @task()
    def _create_query(self):
        from server.models.queries.query import Query
        from server.models.queries.query_message import QueryMessage
        agent_settings = self.session_version.select_profile()
        query = Query.objects.create(
            aimodel =agent_settings.aimodel,
            session_version = self.session_version,
            agent_settings = agent_settings,
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
        system_prompt = agent_settings.system_prompt
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
        if agent_settings.tool_call_syntax == AgentToolCallSyntax.CUSTOM:
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
            tool_call_syntax = query.session_version.select_profile().tool_call_syntax
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
            if query.agent_settings.thinking is False:
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
                agent_settings = query.agent_settings,
                session_version = query.session_version,
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
            if response.agent_settings.tool_call_syntax == AgentToolCallSyntax.CUSTOM and response.message_content:
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
                        tool_session_version:AgentInstanceVersion = agent_version.get_or_create_instance(
                            workingdir = self.session_version.workingdir,
                            parent_instance_version = self.session_version,
                        )
                        rt: BaseAgent = tool_session_version.get_runtime()
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
    def handle_command_response(self, command_response ):
        conv_msg = Message.objects.create(role = "assistant", session_version = self.session_version)
        MessagePart.objects.create(
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
        r = f"Pong from Agent {self.agent.name}, Version {self.agent_version.version_number}, Session {self.agent_instance.name}"
        if message:
            r += f"\nMessage received:{message}"
        return r

        
        '''
