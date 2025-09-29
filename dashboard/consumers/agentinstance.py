import json
from agent.models.agent import Agent, AgentInstance
from dashboard.tasks import send_object_to_clients
from tools_filesystem.models import FsLogEntry
from tools_python.models import PythonToolVar
from tools_memory.models import MemoryItem
from tools_memory.memory import TRACKS
from providers.models import Model
from systems.models import System
from asgiref.sync import async_to_sync

def handle_agentinstance_create(consumer, payload):
    try:
        agent = Agent.objects.get(pk=payload.get('agent_pk'))
        new_agent = AgentInstance()
        new_agent.agent = agent
        new_agent.name = f'New Instance for {agent.name}'
        new_agent.save()
    except Agent.DoesNotExist:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'Agent with pk {payload.get('agent_pk')} not found.'}))

def handle_agentinstance_delete(consumer, payload):
    instance_pk = payload.get('instance_pk')

    if not instance_pk:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': "Agent instance PK not provided for deletion." }))
        return

    try:
        instance = AgentInstance.objects.get(instance_pk=instance_pk)
        deleted_agentInstance_pk = instance.instance_pk
        instance_name = instance.name # Get name before deletion for logging
        instance.delete()
        async_to_sync(consumer.channel_layer.group_send)(
            consumer.group_name,
            {
                'type': 'agent_message',
                'payload': {
                    'object': 'AgentInstanceDeleted',
                    'agent_pk': deleted_agentInstance_pk
                }
            }
        )
    except AgentInstance.DoesNotExist:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f"Agent instance with PK {instance_pk} not found."}))
    except Exception as e:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f"Error deleting agent instance {instance_pk}: {str(e)}"}))



def handle_agentinstance_detail(consumer, payload):
    try:
        agent_instance = AgentInstance.objects.get(instance_pk=payload.get('instance_pk'))
    except AgentInstance.DoesNotExist:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'AgentInstance with pk {payload.get('instance_pk')} not found.'}))
        return
    send_object_to_clients(agent_instance)
    '''
    latest_files = list(FsLogEntry.objects.filter(agentInstance=agent_instance, is_newest_version=True))
    sorted_items = sorted(latest_files , key=lambda x:x.path)
    fs_items = []
    for item in sorted_items:
        client_dict = item.as_client_dict()
        client_dict['is_initial_state'] = True
        fs_items.append(client_dict)
    consumer.send(text_data=json.dumps({'object': 'InitialFilesystemState', 'items': fs_items, 'agentInstance_id': agent_instance.instance_pk}))
    latest_memories = []
    for track, trackitem in TRACKS.items():                   
        for layer, layer_description in trackitem['layers'].items():# dont use distinct, not supported by db.
            latest_memories.extend([x for x in MemoryItem.objects.filter(track=track, layer=layer, next_version=None, agentInstance=agent_instance).order_by('-index')[:agent_instance.limit_max_memory_items]])
            
    memory_items = []
    for item in latest_memories:
        client_dict = item.as_client_dict()
        client_dict['is_initial_state'] = True
        memory_items.append(client_dict)
    consumer.send(text_data=json.dumps({'object': 'InitialMemoryState', 'items': memory_items, 'agentInstance_id': agent_instance.instance_pk}))
    
    latest_vars = PythonToolVar.objects.filter(agentInstance=agent_instance, next_version=None).order_by('key')
    vars_items = [item.as_client_dict() for item in latest_vars]
    consumer.send(text_data=json.dumps({'object': 'InitialVarsState', 'items': vars_items, 'agentInstance_id': agent_instance.instance_pk}))
    '''

def handle_agentinstance_getvars(consumer, payload):
    try:
        agent_instance = AgentInstance.objects.get(instance_pk=payload.get('instance_pk'))
    except AgentInstance.DoesNotExist:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'AgentInstance with pk {payload.get('instance_pk')} not found.'}))
        return
    latest_vars = PythonToolVar.objects.filter(agentInstance=agent_instance, next_version=None).order_by('key')
    vars_items = [item.as_client_dict() for item in latest_vars]
    consumer.send(text_data=json.dumps({'object': 'InitialVarsState', 'items': vars_items, 'agentInstance_id': agent_instance.instance_pk}))



def handle_agentinstance_update(consumer, payload):
    try:
        agent_instance = AgentInstance.objects.get(instance_pk=payload.get('instance_pk'))
    except AgentInstance.DoesNotExist:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'AgentInstance with pk {payload.get('instance_pk')} not found.'}))
        return
    data_to_update = payload.get('data', {})
    if 'name' in data_to_update:
        agent_instance.name = data_to_update['name']
    if 'workingdir' in data_to_update:
        agent_instance.workingdir = data_to_update['workingdir']
    if 'description' in data_to_update:
        agent_instance.description = data_to_update['description']
    if 'limit_max_conversation_messages' in data_to_update:
        agent_instance.limit_max_conversation_messages = int(data_to_update['limit_max_conversation_messages'])
    if 'limit_max_memory_items' in data_to_update:
        agent_instance.limit_max_memory_items = int(data_to_update['limit_max_memory_items'])
    if 'limit_max_automated_steps' in data_to_update:
        agent_instance.limit_max_automated_steps = int(data_to_update['limit_max_automated_steps'])
    if 'workingdir_write_allowed' in data_to_update:
        agent_instance.workingdir_write_allowed = bool(data_to_update['workingdir_write_allowed'])
    if 'access_rules' in data_to_update:
        agent_instance.access_rules = data_to_update['access_rules']
    if 'model_id' in data_to_update :
        try:
            model_id = int(data_to_update['model_id'])
            new_model = Model.objects.get(pk=model_id)
            agent_instance.model = new_model
        except Exception as e:
            consumer.send(text_data=json.dumps({'object': 'error', 'message': f'Model with pk {data_to_update['model_id']} not found.'}))
            return
    if 'system_id' in data_to_update:
        try:
            system_id = int(data_to_update['system_id'])
            if system_id:
                agent_instance.system = System.objects.get(pk=system_id)
            else:
                agent_instance.system = None
        except Exception as e:
            consumer.send(text_data=json.dumps({'object': 'error', 'message': f'System with pk {data_to_update['system_id']} not found.'}))
            return
    agent_instance.save()