import json
import re
import traceback
from registry.task_decorators import task

from runtime.agents.bound_task import BoundTask
from runtime.agents.session import Session
from server.models.queries.response import Response
from server.models.settings import AgentToolCallSyntax
from server.models.tasks.agent_task_call import AgentTaskCall


@task()
def parse_response(session: Session, response: Response) -> dict[str,list[str]]:
    print("parse_responseparse_response", session, response)

    toolcalls = response.tool_calls
    content   = response.content
    reasoning = response.reasoning

    try:
        
        if session.tool_call_syntax == AgentToolCallSyntax.CUSTOM and content:
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
                toolcalls.append({"id": 23, "function": { "name": func_name, "arguments": kwargs}})

        tool_call_tasks = []
        for toolcall in toolcalls:
            tc_id = toolcall['id']
            func_name = toolcall['function']['name']
            if isinstance(toolcall['function']['arguments'], str):
                kwargs = json.loads(toolcall['function']['arguments'])
            else:
                kwargs = toolcall['function']['arguments']
            if func_name in session.allowedToolNames:
                task_definiton_version = session.agent.get_allowed_tool(func_name)
                bound_task = BoundTask(session_version = session.get_version_model(), task_definition_version = task_definiton_version)
                task_call = bound_task.apply_async( kwargs=kwargs)
                tool_call_tasks.append(task_call)
                # we just return them, they are linked to their parent by the calling AgentTaskRun.create_and_run function when this function is successfull,
                # and are started started by AgentTaskCall.run when this AgentTaskRun.create_and_run returns successfull
        
        for tool_call_task in tool_call_tasks:
            tool_call_task.apply_async()
       
        # return tool_call_tasks to the framework can pick them up and wait for them to finish
        
        return dict(content=content, tool_calls=tool_call_tasks)

    except Exception:
        from server.models.debug_log_entry import DebugLogEntry
        DebugLogEntry.objects.create(session=session.model, event='exception', data={"exception": traceback.format_exc()})
        raise