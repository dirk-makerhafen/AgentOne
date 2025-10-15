import json
from agents.models.agent_instance import AgentInstance
from tools.builtin_memory.models.memory_item import MemoryItem
from tools.builtin_memory.prompts import TRACKS
from ui.router import register_handler
import traceback

@register_handler('memoryitem_update')
def handle_memoryitem_update(consumer, track=None, layer=None, index=None, content=None, instance_pk=None):
    try:
        agent_instance = AgentInstance.objects.get(pk=instance_pk)
        # Directly update the memory item instead of going through the tool
        # This is more efficient and avoids circular dependencies
        item = MemoryItem.objects.get(
            agentInstance=agent_instance, 
            track=track, 
            layer=layer, 
            index=int(index),
            next_version=None
        )
        if item.content != content:
            item.content = content
            item.save()
    except Exception as e:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'Failed to update memory item: {str(e)} {traceback.format_exc()}'}))

@register_handler('memoryitem_list')
def handle_memoryitem_list(consumer, instance_pk):
    try:
        agent_instance = AgentInstance.objects.get(instance_pk=instance_pk)

        latest_memories = []
        for track, trackitem in TRACKS.items():
            for layer, _ in trackitem['layers'].items():
                items = MemoryItem.objects.filter(
                    track=track, 
                    layer=layer, 
                    next_version=None, 
                    agentInstance=agent_instance
                ).order_by('-index')[:agent_instance.effective_limit_max_memory_items]
                latest_memories.extend(items)

        memory_items = [item.as_client_dict() for item in latest_memories]
        consumer.send(text_data=json.dumps({'object': 'InitialMemoryState', 'items': memory_items, 'agentInstance_id': agent_instance.instance_pk}))

    except AgentInstance.DoesNotExist:
        pass # Fail silently
