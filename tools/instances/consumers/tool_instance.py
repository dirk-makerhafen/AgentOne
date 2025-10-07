import json
from django.core.exceptions import ValidationError
from tools.instances.models.tool_instance import ToolInstance
from ui.router import register_handler
from tools.instances.tasks import refresh_mcp_server


@register_handler('mcpserver_create')
def handle_mcpserver_create(consumer, user_pk, payload):
    name = payload.get('name')
    endpoint_url = payload.get('endpoint_url')
    try:
        server = ToolInstance.objects.create(name=name, endpoint_url=endpoint_url, transport_type='tcp')
        refresh_mcp_server.delay(server.id, user_pk)
    except (ValidationError, Exception) as e:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': str(e)}))

@register_handler('mcpserver_update')
def handle_mcpserver_update(consumer, user_pk, payload):
    try:
        server = ToolInstance.objects.get(id=payload.get('id'))
        server.name = payload.get('name', server.name)
        server.endpoint_url = payload.get('endpoint_url', server.endpoint_url)
        server.enabled = payload.get('enabled', server.enabled)
        server.save()
    except (ToolInstance.DoesNotExist, ValidationError, Exception) as e:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': str(e)}))

@register_handler('mcpserver_delete')
def handle_mcpserver_delete(consumer, user_pk, payload):
    try:
        server = ToolInstance.objects.get(id=payload.get('id'))
        server.delete()
    except (ToolInstance.DoesNotExist, Exception) as e:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': str(e)}))

@register_handler('mcpserver_list')
def handle_mcpserver_list(consumer, user_pk, payload):
    servers = ToolInstance.objects.all()
    consumer.send(text_data=json.dumps({
        'object': 'ToolInstanceList',
        'tool_instances': [server.as_client_dict() for server in servers]
    }))

@register_handler('mcpserver_tools_refresh')
def handle_mcpserver_tools_refresh(consumer, user_pk, payload):
    server_id = payload.get('id')
    try:
        refresh_mcp_server.delay(server_id, user_pk)
    except Exception as e:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f"Failed to queue refresh task: {e}"}))
