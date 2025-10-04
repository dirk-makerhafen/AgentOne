import json
from typing import Any, Dict, List, Optional, TYPE_CHECKING
from executor.primitives import manage_tool_process
from tools_mcp.models import MCPServer

if TYPE_CHECKING:
    from agent.models.agent import AgentInstance

class MCPClient:
    """
    A thin proxy client that dispatches MCP calls to the stateful client
    living on the remote executor via the 'manage_tool_process' primitive.
    """
    def __init__(self, name: str, mcp_server: MCPServer, agent_instance: 'AgentInstance'):
        self.name = name
        self.mcp_server = mcp_server
        self.agent_instance = agent_instance
        self.system = agent_instance.system
        
        if not self.system:
            raise ValueError("MCPClient requires an agent_instance with an assigned system.")
        if not mcp_server.tool_installation:
            raise ValueError("MCPServer is not linked to a ToolInstallation.")
            
        self.process_id = str(mcp_server.tool_installation.pk)

    def list_tools(self) -> List[Dict[str, Any]]:
        """Dispatches a 'list_tools' call to the remote executor."""
        result = manage_tool_process(
            system=self.system,
            action='list_tools',
            process_id=self.process_id
        )

        if result.get('status') == 'success' and result.get('data'):
            mcp_tools_raw = result['data'].get('tools', [])
            # Store the raw tools in the MCPServer model for caching/display
            self.mcp_server.tools = mcp_tools_raw
            self.mcp_server.save(send_to_client=True)
            return self._format_tools_for_openai(mcp_tools_raw)
        else:
            print(f"Error listing tools for {self.name}: {result.get('message')}")
            return []

    def invoke_tool(self, tool_name: str, kwargs: Dict[str, Any]) -> (bool, str):
        """Dispatches an 'invoke_tool' call to the remote executor."""
        method_name = tool_name.split('.', 1)[-1]

        result = manage_tool_process(
            system=self.system,
            action='invoke_tool',
            process_id=self.process_id,
            tool_name=method_name,
            tool_kwargs=kwargs
        )

        if result.get('status') == 'success':
            return True, json.dumps(result.get('data', ''))
        else:
            return False, f"Error invoking tool {tool_name}: {result.get('message')}"

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
