import json
from agent.models.agent import AgentInstance
from tools_memory.models import MemoryItem
from tools_memory.prompts import TRACKS

def handle_memory_update(consumer, payload):
    track = payload.get('track')
    layer = payload.get('layer')
    index_str = payload.get('index') # Index is received as string from frontend
    content = payload.get('content')
    instance_pk = payload.get('instance_pk')
    if not all([track, layer, index_str, content, instance_pk]):
        consumer.send(text_data=json.dumps({'object': 'error', 'message': 'Missing track, layer, index, content, or instance_pk for memory update.'}))
        return

    try:
        instance_pk = int(instance_pk)
        agent_instance = AgentInstance.objects.get(pk=instance_pk)
        memory_correct_tool = agent_instance.get_tool_function('memory_correct')
        
        success, result = memory_correct_tool["callable"](toolCall=None, track=track, layer=layer, index=int(index_str), content=content)
        if not success:
            error_message = result.get('message', 'Unknown error during memory update.')
            consumer.send(text_data=json.dumps({'object': 'error', 'message': f'Failed to update memory item: {error_message}'}))

    except AgentInstance.DoesNotExist:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'AgentInstance with pk {instance_pk} not found.'}))
    except ValueError:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'Invalid instance_pk or index format.'}))
    except Exception as e:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'Failed to update memory item: {str(e)}'}))

def handle_memory_get(consumer, payload):
    try:
        agent_instance = AgentInstance.objects.get(instance_pk=payload.get('instance_pk'))
    except AgentInstance.DoesNotExist:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'AgentInstance with pk {payload.get('instance_pk')} not found.'}))
        return
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
