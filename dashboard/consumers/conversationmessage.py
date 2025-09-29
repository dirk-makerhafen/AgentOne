import json
from agent.models.conversation import ConversationMessage

def handle_conversationmessage_flags(consumer, payload):
    message_id = payload.get('message_id')
    pin_to_context = payload.get('pin_to_context')
    hide_from_context = payload.get('hide_from_context')

    from agent.models.agent import AgentInstance
    try:
        agent_instance = AgentInstance.objects.get(instance_pk=payload.get('instance_pk'))
    except AgentInstance.DoesNotExist:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'AgentInstance with pk {payload.get('instance_pk', None)} not found.'}))
        return

    if message_id is None:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': 'message_id is required.'}))
        return

    try:
        message = ConversationMessage.objects.get(pk=message_id, agentInstance=agent_instance)
    except ConversationMessage.DoesNotExist:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'ConversationMessage with id {message_id} not found.'}))
        return
    except Exception as e:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'Error fetching ConversationMessage: {str(e)}'}))
        return

    if pin_to_context is not None:
        message.pin_to_context = bool(pin_to_context)
    if hide_from_context is not None:
        message.hide_from_context = bool(hide_from_context)
    
    try:
        message.save(send_to_client=True)
    except Exception as e:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'Error saving ConversationMessage flags: {str(e)}'}))
