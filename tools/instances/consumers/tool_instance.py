import json
from django.core.exceptions import ValidationError
from tools.instances.models.tool_instance import ToolInstance
from ui.router import register_handler
from tools.instances.tasks.tool_fetch_details import fetch_mcp_tool_details
import traceback


@register_handler('toolinstance_create')
def handle_toolinstance_create(consumer, name, endpoint_url=None):
    try:
        server = ToolInstance.objects.create(name=name, endpoint_url=endpoint_url, transport_type='tcp')
    except (ValidationError, Exception) as e:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': str(e)}))

@register_handler('toolinstance_update')
def handle_toolinstance_update(consumer, id, name=None, endpoint_url=None, enabled=None):
    try:
        server = ToolInstance.objects.get(id=id)
        if name is not None:
            server.name = name
        if endpoint_url is not None:
            server.endpoint_url = endpoint_url
        if enabled is not None:
            server.enabled = enabled
        server.save()
    except (ToolInstance.DoesNotExist, ValidationError, Exception) as e:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': str(e)}))

@register_handler('toolinstance_delete')
def handle_toolinstance_delete(consumer, id):
    try:
        tool_instance = ToolInstance.objects.get(id=id)
        tool_instance.delete()
    except ToolInstance.DoesNotExist:
        pass
    except Exception as e:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f"Failed to delete tool instance: {str(e)} {traceback.format_exc()}"}))

@register_handler('toolinstance_list')
def handle_toolinstance_list(consumer, **kwargs):
    servers = ToolInstance.objects.all()
    consumer.send(text_data=json.dumps({
        'object': 'ToolInstanceList',
        'tool_instances': [server.as_client_dict() for server in servers]
    }))

@register_handler('toolinstance_tools_refresh')
def handle_toolinstance_tools_refresh(consumer, id):
    try:
        fetch_mcp_tool_details.delay(id)
    except Exception as e:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f"Failed to queue refresh task: {e} {traceback.format_exc()}"}))

from tools.instances.tasks.stop_tool import stop_tool

@register_handler('toolinstance_stop')
def handle_toolinstance_stop(consumer, tool_instance_pk):
    """Handles the request to stop a specific tool instance."""
    try:
        stop_tool.delay(tool_instance_pk)
    except Exception as e:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'Failed to queue tool stop task for instance {tool_instance_pk}: {e} {traceback.format_exc()}'}))
