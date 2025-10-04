from datetime import datetime
from celery import shared_task
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from django.contrib.auth.models import User


def send_object_to_clients(obj, instance_pk=None):
    from agent.models.agent import Agent, AgentInstance
    from common.models import PromptString
    from providers.models import ApiProvider
    from systems.models import System
    from tools_mcp.models import MCPServer
    from tools_common.models  import ToolDefinition, ToolInstallation # Added ToolInstallation

    message_data = obj if isinstance(obj, dict) else obj.as_client_dict()
    
    target_instance_pk = None
    target_user_pks = set()

    # Determine target(s) based on object type
    if instance_pk:
        target_instance_pk = instance_pk
    elif hasattr(obj, 'agentInstance') and obj.agentInstance:
        target_instance_pk = obj.agentInstance.pk
    elif isinstance(obj, Agent):
        target_user_pks.update(obj.owners.values_list('pk', flat=True))
    elif isinstance(obj, AgentInstance):
        target_user_pks.update(obj.agent.owners.values_list('pk', flat=True))
    elif isinstance(obj, PromptString):
        target_user_pks.add(obj.owner_id)
    elif isinstance(obj, (System, ApiProvider, MCPServer, ToolDefinition, ToolInstallation)): # Added ToolInstallation
        # Global objects are broadcast to all users
        target_user_pks.update(User.objects.values_list('pk', flat=True))
    else:
        # Fallback for dictionaries that might specify scope
        if isinstance(obj, dict) and 'agentInstance_id' in obj and obj['agentInstance_id']:
             target_instance_pk = obj['agentInstance_id']
        elif isinstance(obj, dict) and 'user_pk' in obj and obj['user_pk']:
             target_user_pks.add(obj['user_pk'])
        else:
            print(f'Warning: send_object_to_clients received unhandled object type: {type(obj)} with no clear target.')
            return

    # Dispatch messages via Celery
    if target_instance_pk:
        celery_send_websocket_update.delay(message_data, instance_pk=target_instance_pk)
    
    for user_pk in target_user_pks:
        celery_send_websocket_update.delay(message_data, user_pk=user_pk)

@shared_task
def celery_send_websocket_update(message_data, instance_pk=None, user_pk=None):
    channel_layer = get_channel_layer()
    if instance_pk is not None:
        group_name = f'agentInstance_{instance_pk}'
    elif user_pk is not None:
        group_name = f'user_{user_pk}'
    else:
        # This case should be prevented by the logic in send_object_to_clients
        print("Error: celery_send_websocket_update called without instance_pk or user_pk.")
        return

    if 'created_at' not in message_data:
        message_data['created_at'] = datetime.now().isoformat()
        
    async_to_sync(channel_layer.group_send)(
        group_name, 
        {
            'type': 'agent_message', 
            'payload': message_data
        }
    )
