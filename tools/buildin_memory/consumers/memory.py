import json
from agents.models.agent_instance import AgentInstance
from tools.buildin_memory.models.memory_item import MemoryItem
from tools.buildin_memory.prompts import TRACKS
from ui.router import register_handler

@register_handler('memoryitem_update')
def handle_memoryitem_update(consumer, user_pk, payload):
    track = payload.get('track')
    layer = payload.get('layer')
    index_str = payload.get('index')
    content = payload.get('content')
    instance_pk = payload.get('instance_pk')
    
    if not all([track, layer, index_str, content, instance_pk]):
        return # Fail silently

    try:
        agent_instance = AgentInstance.objects.get(pk=instance_pk)
        # Directly update the memory item instead of going through the tool
        # This is more efficient and avoids circular dependencies
        item = MemoryItem.objects.get(
            agentInstance=agent_instance, 
            track=track, 
            layer=layer, 
            index=int(index_str),
            next_version=None
        )
        if item.content != content:
            item.content = content
            item.save()

    except (AgentInstance.DoesNotExist, MemoryItem.DoesNotExist, ValueError):
        pass # Fail silently
    except Exception as e:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'Failed to update memory item: {str(e)}'}))

@register_handler('memoryitem_list')
def handle_memoryitem_list(consumer, user_pk, payload):
    try:
        agent_instance = AgentInstance.objects.get(instance_pk=payload.get('instance_pk'))
        
        latest_memories = []
        for track, trackitem in TRACKS.items():
            for layer, _ in trackitem['layers'].items():
                items = MemoryItem.objects.filter(
                    track=track, 
                    layer=layer, 
                    next_version=None, 
                    agentInstance=agent_instance
                ).order_by('-index')[:agent_instance.limit_max_memory_items]
                latest_memories.extend(items)
                
        memory_items = [item.as_client_dict(is_initial_state=True) for item in latest_memories]
        consumer.send(text_data=json.dumps({'object': 'InitialMemoryState', 'items': memory_items, 'agentInstance_id': agent_instance.instance_pk}))

    except AgentInstance.DoesNotExist:
        pass # Fail silently
