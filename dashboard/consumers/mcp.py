import json
from channels.db import database_sync_to_async
from django.core.exceptions import ValidationError
from tools_mcp.models import MCPServer
from dashboard.tasks import send_object_to_clients
from celery import shared_task
from asgiref.sync import async_to_sync

from tools_mcp.tasks import refresh_mcp_server_tools_task


@database_sync_to_async
def _list_mcp_servers():
    return [server.as_client_dict() for server in MCPServer.objects.all()]

def list_mcp_servers(consumer, payload):
    """
    Handles request for the list of all MCP servers.
    Sends the list directly back to the requesting client.
    """
    servers = async_to_sync(_list_mcp_servers)()
    consumer.send(text_data=json.dumps({
        'object': 'list_mcp_servers', # Custom object type for frontend routing
        'data': servers
    }))

@database_sync_to_async
def _create_mcp_server(name, endpoint_url):
    try:
        server = MCPServer.objects.create(name=name, endpoint_url=endpoint_url)
        # The model's save() method will trigger send_object_to_clients to broadcast the new server.
        return server.id, None
    except (ValidationError, Exception) as e:
        return None, str(e)

def create_mcp_server(consumer, payload):
    """
    Handles request to create a new MCP server.
    Broadcasts the new server to all clients via the model's save method.
    """
    name = payload.get('name')
    endpoint_url = payload.get('endpoint_url')
    server_id, error = async_to_sync(_create_mcp_server)(name, endpoint_url)
    if error:
        consumer.send({'object': 'error', 'message': error})
    else:
        # Trigger an initial tool refresh for the new server
        refresh_mcp_server_tools_task.delay(server_id)

@database_sync_to_async
def _update_mcp_server(server_id, name, endpoint_url, enabled):
    try:
        server = MCPServer.objects.get(id=server_id)
        if name: server.name = name
        if endpoint_url: server.endpoint_url = endpoint_url
        if enabled is not None: server.enabled = enabled
        server.save()
        # The model's save() method will broadcast the changes.
        return None
    except (MCPServer.DoesNotExist, ValidationError, Exception) as e:
        return str(e)

def update_mcp_server(consumer, payload):
    """
    Handles request to update an existing MCP server.
    Broadcasts changes to all clients via the model's save method.
    """
    error = async_to_sync(_update_mcp_server)(
        server_id=payload.get('id'),
        name=payload.get('name'),
        endpoint_url=payload.get('endpoint_url'),
        enabled=payload.get('enabled')
    )
    if error:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': error}))

@database_sync_to_async
def _delete_mcp_server(server_id):
    try:
        MCPServer.objects.get(id=server_id).delete()
        return None
    except (MCPServer.DoesNotExist, Exception) as e:
        return str(e)

def delete_mcp_server(consumer, payload):
    """
    Handles request to delete an MCP server.
    Sends a confirmation message back to the deleting user.
    """
    server_id = payload.get('id')
    error = async_to_sync(_delete_mcp_server)(server_id)
    if error:
         consumer.send(text_data=json.dumps({'object': 'error', 'message': error}))
    else:
        # The frontend will remove the item based on the MCPServerDeleted message
        # broadcast by the model's post_delete signal (if dirtyfields is configured for it)
        # or we can send an explicit message.
        send_object_to_clients({
            'object': 'MCPServerDeleted',
            'mcp_server_pk': server_id
        }, user_pk=consumer.user_pk)


def refresh_mcp_server_tools(consumer, payload):
    """
    Handles request to trigger a tool refresh for an MCP server.
    """
    server_id = payload.get('id')
    try:
        # This will kick off the background task. The task itself is responsible
        # for broadcasting status updates ('connecting', 'connected', 'error').
        refresh_mcp_server_tools_task.delay(server_id)
    except Exception as e:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f"Failed to queue refresh task: {e}"}))
