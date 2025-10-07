from datetime import datetime
from celery import shared_task
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from django.contrib.auth.models import User


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
