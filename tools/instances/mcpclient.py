import json
from typing import Any, Dict, List
from systems.models.system import System
from tools.primitives.manage_tool_process import call_tool_session
from mcp import ClientSession

class MCPClient(ClientSession):
    """
    A thin proxy client that dispatches MCP calls to the stateful client
    living on the remote executor via the 'manage_tool_process' primitive.
    """
    def __init__(self, tool_instance, system: System):
        self.tool_instance = tool_instance
        self.system = system
        self.name = self.tool_instance.tool_installation.tool_definition.name
        if not tool_instance.tool_installation:
            raise ValueError("ToolInstance is not linked to a ToolInstallation.")
            
    def __getattribute__(self, name):
        print("getattr", name)
        return super().__getattribute__(name)
    
    def _remote_call(self, function_name, kwargs={}):
        return call_tool_session(system=self.system, function_name=function_name, process_id=self.tool_instance.pk, kwargs=kwargs)

    def list_tools(self) -> List[Dict[str, Any]]:
        return self._remote_call("list_tools")
    
    def list_prompts(self, cursor = None):
        return self._remote_call("list_prompts", kwargs={"cursor":cursor})
    
    def list_resources(self, cursor = None):
        return self._remote_call("list_resources", kwargs={"cursor":cursor})
    
    def list_resource_templates(self, cursor = None):
        return self._remote_call("list_resource_templates", kwargs={"cursor":cursor})

    def read_resource(self, uri):
        return self._remote_call("read_resource", kwargs={"uri":uri})

    def get_prompt(self, name, arguments = None):
        return self._remote_call('get_prompt', kwargs={"name":name, "arguments": arguments})

    def call_tool(self, name, arguments = None, read_timeout_seconds = None, progress_callback = None):  
        return self._remote_call('call_tool', kwargs={"name": name, "arguments": arguments, "read_timeout_seconds":read_timeout_seconds})

    def _format_tools_for_openai(self, mcp_tools: list) -> List[Dict[str, Any]]:
        """Converts a list of raw MCP tool definitions to the OpenAI function tool format."""
        openai_tools = []
        for tool in mcp_tools:
            input_schema = tool.get('inputSchema', {})
            properties = input_schema.get('properties', {})
            
            openai_parameters = {"type": "object", "properties": properties}
            required = input_schema.get("required", [])
            if required:
                openai_parameters["required"] = required
            
            openai_tools.append({
                "type": "function",
                "function": {
                    "name": f"{self.name}.{tool.get('name')}",
                    "description": tool.get('description', ''),
                    "parameters": openai_parameters
                }
            })
        return openai_tools
