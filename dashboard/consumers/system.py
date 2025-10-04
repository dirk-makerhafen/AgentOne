import json
from systems.models import System

def handle_system_create(consumer, user_pk,payload):
    group_name = f'user_{consumer.user_pk}' if hasattr(consumer, 'user_pk') else None
    
    if not group_name:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': 'User PK not available for system creation.'}))
        return
    
    try:
        system_name = payload.get('name', 'New System')
        system = System(name=system_name)
        system.save()
    except Exception as e:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'Failed to create system: {e}'}))

def handle_system_list(consumer):
    try:
        systems = System.objects.all().order_by('name')
        system_list = []
        for system in systems:
            system_list.append(system.as_client_dict())
        consumer.send(text_data=json.dumps({'object': 'SystemList', 'systems': system_list}))
    except Exception as e:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'Error fetching Systems: {str(e)}'}))


def handle_system_update(consumer, user_pk, payload):
    try:
        system_pk = payload.get('system_pk')
        data = payload.get('data', {})
        system = System.objects.get(pk=system_pk)

        # Update fields from the payload if they exist
        system.name = data.get('name', system.name)
        system.description = data.get('description', system.description)
        system.is_remote_executor = data.get('is_remote_executor', system.is_remote_executor)
        system.executor_url = data.get('executor_url', system.executor_url)
        system.executor_api_key = data.get('executor_api_key', system.executor_api_key)
        system.executor_mode = data.get('executor_mode', system.executor_mode)
        system.os = data.get('os', system.os)

        system.save()

    except System.DoesNotExist:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'System with pk {system_pk} not found.'}))
    except Exception as e:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'Failed to update system: {e}'}))
