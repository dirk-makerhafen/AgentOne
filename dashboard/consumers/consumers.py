import json
import asyncio
from channels.generic.websocket import WebsocketConsumer
from asgiref.sync import async_to_sync
from dashboard.consumers.agent import handle_agent_create, handle_agent_delete, handle_agent_list, handle_agent_update
from dashboard.consumers.agentinstance import handle_agentinstance_create, handle_agentinstance_delete, handle_agentinstance_detail, handle_agentinstance_update, handle_agentinstance_getvars
from dashboard.consumers.tool_definition import handle_create_tool_definition, handle_update_tool_definition, handle_delete_tool_definition, handle_tool_definition_list, toggle_tool_definition_active, handle_refresh_tool_definition_manifest, handle_assign_system_to_tool, handle_unassign_system_from_tool
from dashboard.consumers.conversation import handle_conversation_add, handle_conversation_get
from dashboard.consumers.conversationmessage import handle_conversationmessage_flags
from dashboard.consumers.direct_tool_call import handle_direct_tool_call
from dashboard.consumers.filesystem import handle_filesystem_get, handle_filesystem_getcontent, handle_filesystem_revert, handle_filesystem_revert_all, handle_filesystem_togglepinned
from dashboard.consumers.limits import handle_limit_reset, handle_limit_update
from dashboard.consumers.memory import handle_memory_update, handle_memory_get
from dashboard.consumers.permissions import handle_permission_get, handle_permission_set
from dashboard.consumers.prompt import handle_prompt_create, handle_prompt_delete, handle_prompt_list, handle_prompt_update
from dashboard.consumers.provider_apikey import handle_provider_apikey_create, handle_provider_apikey_delete
from dashboard.consumers.provider_model import handle_provider_model_create, handle_provider_model_delete
from dashboard.consumers.provider import handle_provider_create, handle_provider_delete, handle_provider_list, handle_provider_update
from dashboard.consumers.system import handle_system_create, handle_system_update, handle_system_list 
from dashboard.consumers.mcp import list_mcp_servers, create_mcp_server, update_mcp_server, delete_mcp_server, refresh_mcp_server_tools
from dashboard.consumers.tool_installation import (
    handle_tool_installation_list, 
    handle_tool_installation_create, 
    handle_tool_installation_start, 
    handle_tool_installation_stop, 
    handle_tool_installation_update, 
    handle_tool_installation_delete,
    handle_tool_installation_logs_request,
    handle_request_tool_installation_logs
)

class AgentConsumer(WebsocketConsumer):
    def connect(self):
        self.user_pk = self.scope['url_route']['kwargs'].get('user_pk')
        if self.user_pk:
            self.group_name = f'user_{self.user_pk}'
        else:
            self.close()
            return
        try:
            async_to_sync(self.channel_layer.group_add)(self.group_name, self.channel_name)
            self.accept()
        except asyncio.CancelledError:
            self.close()
            print(f"Connection for user {self.user_pk} was cancelled during connection setup.")

    def disconnect(self, close_code):
        if hasattr(self, 'group_name'):
            try:
                async_to_sync(self.channel_layer.group_discard)(self.group_name, self.channel_name)
            except asyncio.CancelledError:
                print(f"Group discard for user {self.user_pk} was cancelled during disconnection.")

    def receive(self, text_data):
        print("received", text_data)
        data = json.loads(text_data)
        message_type = data.get('type')
        payload = data.get('payload', {})

        if self.user_pk and message_type == 'request_agent_list':
            handle_agent_list(self, self.user_pk)
        elif message_type == 'create_agent':
            handle_agent_create(self, self.user_pk, payload)
        elif message_type == 'update_agent':
            handle_agent_update(self, self.user_pk, payload)
        elif message_type == 'delete_agent':
            handle_agent_delete(self, self.user_pk, payload)


        elif message_type == 'create_agent_instance':
            handle_agentinstance_create(self, payload)
        elif message_type == 'update_instance_data':
            handle_agentinstance_update(self, payload)
        elif message_type == 'delete_agent_instance':
            handle_agentinstance_delete(self, payload)
        elif message_type == 'request_instance_details':
            handle_agentinstance_detail(self, payload)
        elif message_type == 'request_vars_state':
            handle_agentinstance_getvars(self, payload)


        elif message_type == 'load_history':
            handle_conversation_get(self, payload)
        elif message_type == 'user_input':
            handle_conversation_add(self, payload)


        elif message_type == 'update_conversation_message_flags':
            handle_conversationmessage_flags(self, payload)


        elif message_type == 'direct_tool_call':
            handle_direct_tool_call(self, payload)


        elif message_type == "request_fs_state":
            handle_filesystem_get(self, payload)
        elif message_type == 'revert_filesystem_changes':
            handle_filesystem_revert(self, payload)
        elif message_type == 'revert_all_filesystem_changes':
            handle_filesystem_revert_all(self, payload)
        elif message_type == 'request_fs_content':
            handle_filesystem_getcontent(self, payload)
        elif message_type == 'toggle_fs_pin':
            handle_filesystem_togglepinned(self, payload)

        
        elif message_type == 'update_history_limit':
            handle_limit_update(self, payload)
        elif message_type == 'reset_history_limit':
            handle_limit_reset(self, payload)


        elif message_type == 'update_memory_item':
            handle_memory_update(self, payload)
        elif message_type == 'request_memory_state':
            handle_memory_get(self, payload)



        elif message_type == 'get_instance_permissions':
            handle_permission_get(self, payload)
        elif message_type == 'set_instance_permission':
            handle_permission_set(self, payload)


        elif message_type == 'request_prompt_list':
            handle_prompt_list(self, self.user_pk)
        elif message_type == 'create_custom_prompt_version':
            handle_prompt_create(self, self.user_pk, payload)
        elif message_type == 'update_prompt':
            handle_prompt_update(self, self.user_pk, payload)
        elif message_type == 'delete_prompt':
            handle_prompt_delete(self, self.user_pk, payload)


        elif message_type == 'create_provider_apikey':
            handle_provider_apikey_create(self, payload)
        elif message_type == 'delete_provider_apikey':
            handle_provider_apikey_delete(self, payload)


        elif message_type == 'create_provider_model':
            handle_provider_model_create(self, payload)
        elif message_type == 'delete_provider_model':
            handle_provider_model_delete(self, payload)


        elif message_type == 'request_provider_list':
            handle_provider_list(self)
        elif message_type == 'create_provider':
            handle_provider_create(self, payload)
        elif message_type == 'delete_provider':
            handle_provider_delete(self, payload)
        elif message_type == 'update_provider':
            handle_provider_update(self, payload)
       

        elif message_type == 'system_create':
            handle_system_create(self, self.user_pk, payload)
        elif message_type == 'request_system_list':
            handle_system_list(self)
        elif message_type == 'update_system_details':
            handle_system_update(self, self.user_pk, payload)

        elif message_type == 'list_mcp_servers':
            list_mcp_servers(self, payload)
        elif message_type == 'create_mcp_server':
            create_mcp_server(self, payload)
        elif message_type == 'update_mcp_server':
            update_mcp_server(self, payload)
        elif message_type == 'delete_mcp_server':
            delete_mcp_server(self, payload)
        elif message_type == 'refresh_mcp_server_tools':
            refresh_mcp_server_tools(self, payload)

        elif message_type == 'create_tool_definition':
            handle_create_tool_definition(self, payload)
        elif message_type == 'update_tool_definition':
            handle_update_tool_definition(self, payload)
        elif message_type == 'delete_tool_definition':
            handle_delete_tool_definition(self, payload)
        elif message_type == 'request_tool_definition_list':
            handle_tool_definition_list(self, payload)
        elif message_type == 'toggle_tool_definition_active':
            toggle_tool_definition_active(self, payload.get('tool_definition_id'))
        elif message_type == 'request_refresh_tool_definition_manifest':
            handle_refresh_tool_definition_manifest(self, payload)
        elif message_type == 'assign_system_to_tool':
            handle_assign_system_to_tool(self, payload)
        elif message_type == 'unassign_system_from_tool':
            handle_unassign_system_from_tool(self, payload)

        elif message_type == 'request_tool_installation_list':
            handle_tool_installation_list(self, payload)
        elif message_type == 'create_tool_installation':
            handle_tool_installation_create(self, self.user_pk, payload)
        elif message_type == 'tool_installation_start':
            handle_tool_installation_start(self, self.user_pk, payload)
        elif message_type == 'tool_installation_stop':
            handle_tool_installation_stop(self, self.user_pk, payload)
        elif message_type == 'request_tool_installation_logs':
            handle_request_tool_installation_logs(self, payload)
        elif message_type == 'update_tool_installation':
            handle_tool_installation_update(self, self.user_pk, payload)
        elif message_type == 'delete_tool_installation':
            handle_tool_installation_delete(self, self.user_pk, payload)

        elif message_type == 'subscribe':
            try:
                async_to_sync(self.channel_layer.group_add)(f'agentInstance_{payload.get("instance_pk")}', self.channel_name)
            except asyncio.CancelledError:
                print(f"Subscription for agent instance {payload.get("instance_pk")} was cancelled for user {self.user_pk}.")

        elif message_type == 'unsubscribe':
            try:
                async_to_sync(self.channel_layer.group_discard)(f'agentInstance_{payload.get("instance_pk")}', self.channel_name)
            except asyncio.CancelledError:
                print(f"Unsubscription for agent instance {payload.get("instance_pk")} was cancelled for user {self.user_pk}.")

        else:
            self.send(text_data=json.dumps({'object': 'error', 'message': f'Unknown message type {message_type}, {data}'}))

        
    def agent_message(self, event):
        self.send(text_data=json.dumps(event['payload']))
