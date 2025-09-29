from datetime import datetime
from celery import shared_task
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from agent.models.llm import LLMQuery, LLMResponse
from agent.models.conversation import ConversationMessage
from agent.models.agent import Agent, AgentInstance
from agent.models.debug import DebugLogEntry
from common.models import PromptString
from providers.models import ApiProvider
from tools_common.models import ToolCall, ToolResponse
from tools_filesystem.models import FsLogEntry
from systems.models import System
from django.contrib.auth.models import User # Imported here for global scope

@shared_task
def celery_send_websocket_update(message_data, instance_pk=None, user_pk=None):
    channel_layer = get_channel_layer()
    if instance_pk is not None and user_pk is None:
        group_name = f'agentInstance_{instance_pk}'
    elif user_pk is not None and instance_pk is None:
        group_name = f'user_{user_pk}'
    else:
        raise ValueError("Exactly one of 'instance_pk' or 'user_pk' must be provided for WebSocket update.")
    if 'created_at' not in message_data:
        message_data['created_at'] = datetime.now().isoformat()
    async_to_sync(channel_layer.group_send)(group_name, {'type': 'agent_message', 'payload': message_data})

def send_object_to_clients(obj, instance_pk=None):
    message_data = obj if isinstance(obj, dict) else obj.as_client_dict()
    
    target_instance_pk = None
    target_user_pks = set() # Use a set to avoid duplicate user_pks

    # Determine target(s) based on object type or explicit instance_pk
    if instance_pk: # Explicit instance_pk argument takes highest priority
        target_instance_pk = instance_pk
    elif 'agentInstance_id' in message_data and message_data['agentInstance_id']:
        # This covers dicts that already have an instance_pk, like raw log messages from the agent.
        target_instance_pk = message_data['agentInstance_id']
    elif hasattr(obj, 'agentInstance') and obj.agentInstance: # For log entry models
        target_instance_pk = obj.agentInstance.pk
    elif isinstance(obj, Agent):
        target_user_pks.update(obj.owners.values_list('pk', flat=True))
    elif isinstance(obj, AgentInstance):
        target_user_pks.update(obj.agent.owners.values_list('pk', flat=True))
    elif isinstance(obj, PromptString):
        target_user_pks.add(obj.owner_id)
    elif isinstance(obj, System) or isinstance(obj, ApiProvider):
        target_user_pks.update(User.objects.values_list('pk', flat=True))
    else:
        # Handle cases for other global objects like Provider, ProviderModel, etc.
        # These are usually sent via request_provider_list or similar, which construct specific message_data.
        # If 'object' field is present and it's a global type, broadcast to all users.
        if isinstance(obj, dict) and 'object' in obj:
            if obj['object'] in ['PromptString', 'ApiProviderList', 'ProviderDeleted', 'SystemList', 'ApiProviderList', 'ProviderDeleted', 'System', 'SystemList']:
                target_user_pks.update(User.objects.values_list('pk', flat=True))
        else:
            print(f'Warning: send_object_to_clients received unhandled object type: {type(obj)} or dict without instance/user scope.')
            return # Prevent sending if no target is identified

    # Dispatch messages
    if target_instance_pk:
        celery_send_websocket_update.delay(message_data, instance_pk=target_instance_pk)
    elif target_user_pks:
        for user_pk in target_user_pks:
            celery_send_websocket_update.delay(message_data, user_pk=user_pk)