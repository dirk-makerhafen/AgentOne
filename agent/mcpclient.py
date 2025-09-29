"""

COPY OF:

MCP SSE Client - A Python client for interacting with Model Context Protocol (MCP) endpoints.

This module provides a client for connecting to MCP endpoints using Server-Sent Events (SSE),
listing available tools, and invoking tools with parameters.
"""

from typing import Any, Dict, List, Optional
from urllib.parse import urlparse
from dataclasses import dataclass
from mcp import ClientSession
from mcp.client.sse import sse_client
from pydantic import BaseModel
import asyncio

@dataclass
class ToolParameter:
    """Represents a parameter for a tool.
    
    Attributes:
        name: Parameter name
        parameter_type: Parameter type (e.g., "string", "number")
        description: Parameter description
        required: Whether the parameter is required
        default: Default value for the parameter
    """
    name: str
    parameter_type: str
    description: str
    required: bool = False
    default: Any = None


@dataclass
class ToolDef:
    """Represents a tool definition.
    
    Attributes:
        name: Tool name
        description: Tool description
        input_schema: The full JSON schema for the tool's input parameters.
        metadata: Optional dictionary of additional metadata
        identifier: Tool identifier (defaults to name)
    """
    name: str
    description: str
    input_schema: Dict[str, Any]
    metadata: Optional[Dict[str, Any]] = None
    identifier: str = ""

class MCPClient:
    """Client for interacting with Model Context Protocol (MCP) endpoints"""
    
    def __init__(self, name, endpoint: str):
        """Initialize MCP client with endpoint URL
        
        Args:
            endpoint: The MCP endpoint URL (must be http or https)
        """
        if urlparse(endpoint).scheme not in ("http", "https"):
            raise ValueError(f"Endpoint {endpoint} is not a valid HTTP(S) URL")
        self.endpoint = endpoint
        self.name = name

    def list_tools(self):
        return asyncio.run(self._list_tools_async())

    def invoke_tool(self, tool_name: str, kwargs: Dict[str, Any]):
        return asyncio.run(self._invoke_tool_async(tool_name, kwargs))

    async def _list_tools_async(self):
        """List available tools from the MCP endpoint
        
        Returns:
            List of ToolDef objects describing available tools
        """
        tools = []
        async with sse_client(self.endpoint) as streams:
            async with ClientSession(*streams) as session:
                await session.initialize()
                tools_result = await session.list_tools()
                for tool in tools_result.tools:
                    # Convert ToolDef to OpenAI function tool format
                    openai_parameters = {"type": "object", "properties": tool.inputSchema["properties"]}
                    required_params = tool.inputSchema.get("required", []) # Get required params from schema
                    if required_params:
                        openai_parameters["required"] = required_params
                    openai_tool_format = {
                        "type": "function",
                        "function": {
                            "name": f"{self.name}.{tool.name}",
                            "description": tool.description if tool.description is not None else "",
                            "parameters": openai_parameters
                        }
                    }
                    tools.append(openai_tool_format)
        return tools

    async def _invoke_tool_async(self, tool_name: str, kwargs: Dict[str, Any]):
        async with sse_client(self.endpoint) as streams:
            async with ClientSession(*streams) as session:
                await session.initialize()
                result = await session.call_tool(tool_name, kwargs) 
                content = "\n".join([result.model_dump_json() for result in result.content])
                success = False if result.isError else True,
                return success, content