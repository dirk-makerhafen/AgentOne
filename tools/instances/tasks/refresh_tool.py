from celery import shared_task
from executor.primitives import manage_tool_process
from tools.instances.models.tool_instance import ToolInstance


@shared_task
def refresh_tool_instance(tool_instance_id):
    """
    Celery task to refresh tools from a running ToolInstallation by calling the stateful primitive.
    """
    try:
        tool_instance = ToolInstance.objects.get(id=tool_instance_id)
        tool_instance.status = 'connecting'
        tool_instance.last_error = None
        tool_instance.save()

        if not tool_instance.tool_installation or not tool_instance.tool_installation.system:
            raise Exception(f"ToolInstance {tool_instance.id} is not linked to a system via a ToolInstallation.")

        system = tool_instance.tool_installation.system
        process_id = str(tool_instance.tool_installation.pk)

        result = manage_tool_process(
            system=system,
            action='list_tools',
            process_id=process_id
        )
        
        if result.get('status') == 'success':
            # The primitive returns the raw tool list
            raw_tools = result.get('data', {}).get('tools', [])
            tool_instance.tools = raw_tools # Store the raw data
            tool_instance.status = 'connected'
            tool_instance.last_error = None
        else:
            tool_instance.status = 'error'
            tool_instance.last_error = result.get('message', 'Failed to list tools from executor.')
            
        tool_instance.save()

    except ToolInstance.DoesNotExist:
        print(f"ToolInstance with ID {tool_instance_id} not found for tool refresh.")
    except Exception as e:
        print(f"Error refreshing ToolInstance {tool_instance_id}: {e}")
        try:
            tool_instance = ToolInstance.objects.get(id=tool_instance_id)
            tool_instance.status = 'error'
            tool_instance.last_error = str(e)
            tool_instance.save()
        except ToolInstance.DoesNotExist:
            pass # Server was deleted during the refresh.

