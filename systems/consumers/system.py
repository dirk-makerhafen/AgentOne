import json
from systems.models.system import System
from ui.router import register_handler

@register_handler('system_create')
def handle_system_create(consumer, name='New System'):
    try:
        system = System(name=name)
        system.save()
    except Exception as e:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'Failed to create system: {e}'}))

@register_handler('system_update')
def handle_system_update(consumer, system_pk, data=None):
    if data is None:
        data = {}
    try:
        system = System.objects.get(pk=system_pk)

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

@register_handler('system_list')
def handle_system_list(consumer, **kwargs):
    try:
        systems = System.objects.all().order_by('name')
        system_list = [s.as_client_dict() for s in systems]
        consumer.send(text_data=json.dumps({'object': 'SystemList', 'systems': system_list}))
    except Exception as e:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'Error fetching Systems: {str(e)}'}))
