"""
MCP Wrapper for the UserInteractionTool.

This version correctly exposes its instructional text as a dynamic MCP Prompt.
"""
from typing import Any
import mcp.types as types
from mcp.server.lowlevel import Server, ElicitationContext
from pydantic import BaseModel, Field
from .prompts import FUNCTIONS
from .user_interaction_tool import UserInteractionTool

# --- Helper Function ---
def get_agent_instance_from_context(ctx: ElicitationContext):
    if "agent_instance" not in ctx.scope:
        raise ValueError("AgentInstance not found in context scope. The caller must provide it.")
    return ctx.scope["agent_instance"]

# --- Pydantic Schemas ---
class UserInputSchema(BaseModel):
    user_response: str = Field(..., description="The user's text response to the prompt.")

# --- MCP Server Factory ---
def get_mcp_server():
    """Factory to create and configure the MCP server instance for this tool."""
    from core.models.prompt_string import PromptString
    from tools.builtin_userinteraction.apps import ToolsBuiltinUserinteractionConfig

    server = Server("BuiltinUserInteractionMCPServer")

    @server.list_prompts()
    async def handle_list_prompts() -> list[types.Prompt]:
        """Advertises the availability of the main instructions prompt."""
        return [
            types.Prompt(
                name="Instructions",
                title="User Interaction Instructions",
                description="The main instructional text for how to use the User Interaction tool.",
                arguments=[] # This prompt takes no arguments
            )
        ]

    @server.get_prompt()
    async def handle_get_prompt(name: str, arguments: dict[str, Any]) -> types.PromptResult:
        """
        Handles requests for the prompt by dynamically fetching its content
        from the database and wrapping it in the correct message structure.
        """
        if name != "Instructions":
            raise ValueError(f"Unknown prompt: {name}")

        try:
            # Dynamically fetch the PromptString from the DB on every request.
            instruction_prompt_string = PromptString.objects.get(
                source=ToolsBuiltinUserinteractionConfig.name,
                key="Instructions"
            )
            return types.PromptResult(
                messages=[
                    types.PromptMessage(
                        role="user",
                        content=types.TextContent(type="text", text=instruction_prompt_string.value)
                    )
                ]
            )
        except PromptString.DoesNotExist:
            raise ValueError("Instructions prompt not found in the database.")

    @server.list_tools()
    async def handle_list_tools() -> list[types.Tool]:
        tool_definitions = []
        for func_name, func_def in FUNCTIONS.items():
            tool_definitions.append(
                types.Tool(
                    name=func_name,
                    title=func_name.replace("_", " ").title(),
                    description=func_def['description'],
                    inputSchema={"type": "object", "properties": func_def['parameters']},
                )
            )
        return tool_definitions

    @server.call_tool()
    async def handle_call_tool(
        name: str, arguments: dict[str, Any], ctx: ElicitationContext
    ) -> list[types.Content]:
        if name != "await_user_input":
            raise ValueError(f"Unknown tool: {name}")

        agent_instance = get_agent_instance_from_context(ctx)
        tool_instance = UserInteractionTool(agent_instance)

        prompt_message = arguments.get("reason", "Please provide your input.")
        await ctx.info(f"Requesting user input via {tool_instance.__class__.__name__} MCP wrapper.")
        result = await ctx.elicit(message=prompt_message, schema=UserInputSchema)

        if result.action == "accept" and result.data:
            return [types.TextContent(type="text", text=f"User responded: {result.data.user_response}")]
        elif result.action == "decline":
            return [types.TextContent(type="text", text="User declined the request.")]
        else:
            return [types.TextContent(type="text", text="User cancelled the input request.")]

    return server
