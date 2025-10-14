from typing import Any, Dict, List
from tools.primitives.manage_tool_process import call_tool_session
from mcp import ClientSession

class MCPClient(ClientSession):
    """
    A thin proxy client that dispatches MCP calls to the stateful client
    living on the remote executor via the 'manage_tool_process' primitive.
    """
    def __init__(self, system, process_id = None):
        self.system = system
        self.process_id = process_id

    def __getattribute__(self, name):
        print("getattr", name)
        return super().__getattribute__(name)
    
    def _call(self, function_name, kwargs={}):
        return call_tool_session(system=self.system, function_name=function_name, process_id=self.process_id, kwargs=kwargs)

    def list_tools(self) -> List[Dict[str, Any]]:
        return self._call("list_tools")
    
    def list_prompts(self, cursor = None):
        return self._call("list_prompts", kwargs={"cursor":cursor})
    
    def list_resources(self, cursor = None):
        return self._call("list_resources", kwargs={"cursor":cursor})
    
    def list_resource_templates(self, cursor = None):
        return self._call("list_resource_templates", kwargs={"cursor":cursor})

    def read_resource(self, uri):
        return self._call("read_resource", kwargs={"uri":uri})

    def get_prompt(self, name, arguments = None):
        return self._call('get_prompt', kwargs={"name":name, "arguments": arguments})

    def call_tool(self, name, arguments = None, read_timeout_seconds = None, progress_callback = None):  
        return self._call('call_tool', kwargs={"name": name, "arguments": arguments, "read_timeout_seconds":read_timeout_seconds})
