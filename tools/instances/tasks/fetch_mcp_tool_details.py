from celery import shared_task
import traceback
from tools.instances.models.tool_instance import ToolInstance

@shared_task
def fetch_mcp_tool_details(tool_instance_pk):
    """
    Celery task to fetch the manifest from a running MCP tool instance
    and cache it in the ToolInstance's raw_data field.
    """
    try:
        instance = ToolInstance.objects.get(pk=tool_instance_pk)    
        instance.mcp_tools = instance.mcp_client.list_tools()
        instance.mcp_prompts = instance.mcp_client.list_prompts()
        instance.mcp_templates = instance.mcp_client.list_resource_templates()
        instance.mcp_resources = instance.mcp_client.list_resources()
        instance.save()
        print(f"Successfully fetched and cached MCP details for instance {tool_instance_pk}.")
    except ToolInstance.DoesNotExist:
        print(f"ToolInstance with pk {tool_instance_pk} not found for fetching MCP details.")
    except Exception as e:
        print(f"An error occurred in fetch_mcp_tool_details for instance {tool_instance_pk}: {e}\n{traceback.format_exc()}")
