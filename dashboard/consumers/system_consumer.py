import json
import asyncio
from channels.generic.websocket import WebsocketConsumer
from asgiref.sync import async_to_sync
from systems.models import System

class SystemConsumer(WebsocketConsumer):
    def connect(self):
        self.system_pk = self.scope['url_route']['kwargs'].get('system_pk')
        if not self.system_pk:
            self.close()
            return

        self.group_name = f'system_{self.system_pk}'
        
        try:
            # Check if the system exists
            if not System.objects.filter(pk=self.system_pk).exists():
                print(f"System with PK {self.system_pk} does not exist. Closing connection.")
                self.close()
                return

            async_to_sync(self.channel_layer.group_add)(self.group_name, self.channel_name)
            self.accept()
            print(f"WebSocket connection established for system {self.system_pk}")
        except asyncio.CancelledError:
            self.close()
            print(f"Connection for system {self.system_pk} was cancelled during connection setup.")

    def disconnect(self, close_code):
        if hasattr(self, 'group_name'):
            try:
                async_to_sync(self.channel_layer.group_discard)(self.group_name, self.channel_name)
                print(f"WebSocket disconnected for system {self.system_pk}")
            except asyncio.CancelledError:
                print(f"Group discard for system {self.system_pk} was cancelled during disconnection.")

    def receive(self, text_data):
        """
        Handles incoming messages for the system.
        This consumer is primarily for the system's executor to receive commands
        (e.g., install tool, start tool) from the main server.
        """
        print(f"Received message for system {self.system_pk}: {text_data}")
        data = json.loads(text_data)
        message_type = data.get('type')
        payload = data.get('payload', {})

        if message_type == 'executor_command':
            command = payload.get('command')
            print(f"System {self.system_pk}: Received executor command: {command} with payload: {payload}")

            if command == 'install_tool':
                # Here, the actual executor (e.g., a separate process on the remote system)
                # would perform the installation. For now, we'll log and assume success.
                # In a real scenario, this would trigger a Celery task on the executor itself.
                print(f"System {self.system_pk}: Initiating installation for tool '{payload.get('tool_definition_name')}' (ID: {payload.get('tool_definition_id')}) from {payload.get('repository_url')}")
                # After "installation", the executor would send a status_update back
                _update_tool_installation_status(
                    payload.get('installation_id'), 
                    'installed', # Or 'running' if it starts immediately after install
                    self.system_pk,
                    f"/opt/tools/{payload.get('tool_definition_name')}", # Placeholder path
                    None, None, # Placeholder PID and Port
                    None # No error
                )
            elif command == 'start_tool':
                print(f"System {self.system_pk}: Initiating startup for tool '{payload.get('tool_definition_name')}' (ID: {payload.get('tool_definition_id')})")
                # After "startup", the executor would send a status_update back
                _update_tool_installation_status(
                    payload.get('installation_id'), 
                    'running', 
                    self.system_pk,
                    f"/opt/tools/{payload.get('tool_definition_name')}", # Assumed path from install
                    12345, 8080, # Placeholder PID and Port
                    None # No error
                )
            elif command == 'status_update':
                _update_tool_installation_status(
                    payload.get('installation_id'),
                    payload.get('status'),
                    self.system_pk,
                    payload.get('local_path'),
                    payload.get('process_id'),
                    payload.get('assigned_port'),
                    payload.get('error_message')
                )
            else:
                print(f"System {self.system_pk}: Unknown executor command: {command}")
        else:
            print(f"System {self.system_pk}: Unknown message type: {message_type}")

def _update_tool_installation_status(installation_id, status, system_id, local_path=None, process_id=None, assigned_port=None, error_message=None):
    from tools_common.models  import ToolInstallation
    from tools_mcp.models import MCPServer
    from dashboard.tasks import send_object_to_clients # For updating frontend
    try:
        installation = ToolInstallation.objects.get(pk=installation_id, system_id=system_id)
        installation.status = status
        if local_path is not None:
            installation.local_path = local_path
        if process_id is not None:
            installation.process_id = process_id
        if assigned_port is not None:
            installation.assigned_port = assigned_port
        installation.save() # This should trigger send_object_to_clients for the installation

        # Also update or create MCPServer if the tool is running
        if status == 'running' and installation.assigned_port:
            mcp_server, created = MCPServer.objects.get_or_create(
                tool_installation=installation,
                defaults={
                    'name': f'MCP for {installation.tool_definition.display_name} on {installation.system.name}',
                    'endpoint_url': f'http://{installation.system.executor_url or 'localhost'}:{installation.assigned_port}', # Assuming local for now, need system IP
                    'enabled': True
                }
            )
            if not created:
                mcp_server.endpoint_url = f'http://{installation.system.executor_url or 'localhost'}:{installation.assigned_port}'
                mcp_server.name = f'MCP for {installation.tool_definition.display_name} on {installation.system.name}'
                mcp_server.enabled = True
                mcp_server.save() # This should also trigger send_object_to_clients for the MCPServer
            installation.mcp_server = mcp_server # Link the mcp_server back to the installation
            installation.save() # Save again to persist mcp_server link if it was just created
        elif installation.mcp_server and status != 'running':
            # Disable or delete MCPServer if tool stops or errors
            installation.mcp_server.enabled = False
            installation.mcp_server.last_error = error_message # Store error if any
            installation.mcp_server.save()
            
    except ToolInstallation.DoesNotExist:
        print(f"Error: ToolInstallation with ID {installation_id} on system {system_id} not found.")
    except Exception as e:
        print(f"Error updating ToolInstallation status for {installation_id}: {e}")
        import traceback
        traceback.print_exc()

    def object_message(self, event):
        """
        Receives messages from the channel layer and sends them over the WebSocket.
        This is how `send_object_to_clients` will deliver messages to this system.
        """
        self.send(text_data=json.dumps(event['payload']))
