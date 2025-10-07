import json
from datetime import datetime
from django.db.models import Q
from agents.models.agent_instance import AgentInstance
from agents.models.conversation_message import ConversationMessage
from tools.buildin_a2a.models.a2a_message import AgentToAgentMessage
from ui.router import register_handler

@register_handler('conversationmessage_add')
def handle_conversationmessage_add(consumer, user_pk, payload):
    try:
        agent_instance = AgentInstance.objects.get(instance_pk=payload.get('instance_pk'))
    except AgentInstance.DoesNotExist:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'AgentInstance with pk {payload.get("instance_pk", None)} not found.'}))
        return
    content = payload.get('message')
    if content:
        agent_instance.add_to_conversation(role='user', content=content, user_pk=user_pk)
    agent_instance.start_or_continue(user_pk=user_pk)

@register_handler('conversationmessage_list')
def handle_conversationmessage_get(consumer, user_pk, payload):
    try:
        agent_instance = AgentInstance.objects.get(instance_pk=payload.get('instance_pk'))
    except AgentInstance.DoesNotExist:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'AgentInstance with pk {payload.get("instance_pk", None)} not found.'}))
        return
    max_id = payload.get('max_id')
    limit = payload.get('limit', 20)

    all_client_dicts = []
    conversation_query = agent_instance.conversationMessages.all()
    if max_id:
        conversation_query = conversation_query.filter(id__lt=max_id)
    conversation_messages = list(conversation_query.order_by('-created_at')[:limit])
    
    if not conversation_messages:
        consumer.send(text_data=json.dumps({'object': 'HistoryLoadResult', 'count': 0, 'agentInstance_id': agent_instance.instance_pk}))
        return
        
    oldest_msg_created_at = conversation_messages[-1].created_at
    next_message = agent_instance.conversationMessages.filter(created_at__gt=conversation_messages[0].created_at).order_by('created_at').first()
    datetime_limit = next_message.created_at if next_message else datetime.max
        
    for msg in conversation_messages:
        all_client_dicts.append(msg.as_client_dict())
        
    debug_log_entries = list(agent_instance.debugLogEntries.filter(Q(created_at__gte=oldest_msg_created_at, created_at__lt=datetime_limit)).order_by('-created_at'))
    all_client_dicts.extend([entry.as_client_dict() for entry in debug_log_entries])
        
    fs_file_entries = list(agent_instance.fsFileLogEntries.filter(Q(created_at__gte=oldest_msg_created_at, created_at__lte=datetime_limit)).order_by('-created_at'))
    all_client_dicts.extend([entry.as_client_dict() for entry in fs_file_entries])
        
    tool_calls = list(agent_instance.toolCalls.filter(Q(created_at__gte=oldest_msg_created_at, created_at__lt=datetime_limit)).order_by('-created_at'))
    all_client_dicts.extend([entry.as_client_dict() for entry in tool_calls])
        
    llm_queries = list(agent_instance.llmqueries.filter(Q(created_at__gte=oldest_msg_created_at, created_at__lt=datetime_limit)).order_by('-created-at'))
    all_client_dicts.extend([query_obj.as_client_dict() for query_obj in llm_queries])
        
    llm_responses = list(agent_instance.llmResponses.filter(Q(created_at__gte=oldest_msg_created_at, created_at__lt=datetime_limit)).order_by('-created_at'))
    all_client_dicts.extend([query_obj.as_client_dict() for query_obj in llm_responses])
        
    inter_agent_messages = list(AgentToAgentMessage.objects.filter(Q(sender_agentInstance=agent_instance) | Q(receiver_agentInstance=agent_instance), Q(created_at__gte=oldest_msg_created_at, created_at__lt=datetime_limit)).order_by('-created_at'))
    all_client_dicts.extend([entry.as_client_dict() for entry in inter_agent_messages])
        
    python_tool_vars = list(agent_instance.python_tool_vars.filter(Q(created_at__gte=oldest_msg_created_at, created_at__lt=datetime_limit)).order_by('-created_at'))
    all_client_dicts.extend([entry.as_client_dict() for entry in python_tool_vars])
        
    all_client_dicts.sort(key=lambda x: (x['created_at'], x.get('id', 0)), reverse=True)
    
    for msg in all_client_dicts:
        msg['prepend'] = True
        consumer.send(text_data=json.dumps(msg))
        
    consumer.send(text_data=json.dumps({'object': 'HistoryLoadResult', 'count': len(all_client_dicts), 'agentInstance_id': agent_instance.instance_pk}))

@register_handler('conversationmessage_update_flag')
def handle_conversationmessage_update_flags(consumer, user_pk, payload):
    message_id = payload.get('message_id')
    pin_to_context = payload.get('pin_to_context')
    hide_from_context = payload.get('hide_from_context')

    try:
        agent_instance = AgentInstance.objects.get(instance_pk=payload.get('instance_pk'))
    except AgentInstance.DoesNotExist:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'AgentInstance with pk {payload.get("instance_pk", None)} not found.'}))
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
        message.save()
    except Exception as e:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'Error saving ConversationMessage flags: {str(e)}'}))
