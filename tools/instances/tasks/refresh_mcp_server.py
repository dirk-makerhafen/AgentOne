from celery import shared_task
from executor.primitives import manage_tool_process
from tools.instances.models.tool_instance import ToolInstance


@shared_task
def refresh_mcp_server_tools_task(mcp_server_id):
    """
    Celery task to refresh tools from a running MCP server by calling the stateful primitive.
    """
    try:
        mcp_server = ToolInstance.objects.get(id=mcp_server_id)
        mcp_server.status = 'connecting'
        mcp_server.last_error = None
        mcp_server.save()

        if not mcp_server.tool_installation or not mcp_server.tool_installation.system:
            raise Exception(f"ToolInstance {mcp_server.id} is not linked to a system via a ToolInstallation.")

        system = mcp_server.tool_installation.system
        process_id = str(mcp_server.tool_installation.pk)

        result = manage_tool_process(
            system=system,
            action='list_tools',
            process_id=process_id
        )
        
        if result.get('status') == 'success':
            # The primitive returns the raw MCP tool list
            raw_tools = result.get('data', {}).get('tools', [])
            mcp_server.tools = raw_tools # Store the raw data
            mcp_server.status = 'connected'
            mcp_server.last_error = None
        else:
            mcp_server.status = 'error'
            mcp_server.last_error = result.get('message', 'Failed to list tools from executor.')
            
        mcp_server.save()

    except ToolInstance.DoesNotExist:
        print(f"MCP Server with ID {mcp_server_id} not found for tool refresh.")
    except Exception as e:
        print(f"Error refreshing MCP server {mcp_server_id}: {e}")
        try:
            mcp_server = ToolInstance.objects.get(id=mcp_server_id)
            mcp_server.status = 'error'
            mcp_server.last_error = str(e)
            mcp_server.save()
        except ToolInstance.DoesNotExist:
            pass # Server was deleted during the refresh.

