from datetime import datetime
import json
from django.db.models import Q
from tools_a2a.models import InterAgentMessage

def handle_conversation_add(consumer, payload):
    from agent.models.agent import AgentInstance
    try:
        agent_instance = AgentInstance.objects.get(instance_pk=payload.get('instance_pk'))
    except AgentInstance.DoesNotExist:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'AgentInstance with pk {payload.get('instance_pk', None)} not found.'}))
        return
    content = payload.get('message')
    if content:
        agent_instance.add_to_conversation(role='user', content=content)
    agent_instance.start_or_continue()

def handle_conversation_get(consumer, payload):
    from agent.models.agent import AgentInstance
    try:
        agent_instance = AgentInstance.objects.get(instance_pk=payload.get('instance_pk'))
    except AgentInstance.DoesNotExist:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'AgentInstance with pk {payload.get('instance_pk', None)} not found.'}))
        return
    max_id = payload.get('max_id')
    limit = payload.get('limit', 20)

    all_client_dicts = []
    conversation_query = agent_instance.conversationMessages.all()
    if max_id:
        conversation_query = conversation_query.filter(id__lt=max_id)
    conversation_messages = list(conversation_query.order_by(
        '-created_at')[:limit])
    if not conversation_messages:
        return []
    oldest_msg_created_at = conversation_messages[-1].created_at
    next_message = agent_instance.conversationMessages.filter(created_at__gt=
        conversation_messages[0].created_at).order_by('created_at').first()
    if next_message:
        datetime_limit = next_message.created_at
    else:
        datetime_limit = datetime.max
    for msg in conversation_messages:
        all_client_dicts.append(msg.as_client_dict())
    relevant_conversation_message_ids = {msg.id for msg in conversation_messages}
    debug_log_entries = list(agent_instance.debugLogEntries.filter(Q(created_at__gte=oldest_msg_created_at, created_at__lt=datetime_limit)).order_by('-created_at'))
    for entry in debug_log_entries:
        all_client_dicts.append(entry.as_client_dict())
    fs_file_entries = list(agent_instance.fsFileLogEntries.filter(Q(created_at__gte=oldest_msg_created_at, created_at__lte=datetime_limit)).order_by('-created_at'))
    for entry in fs_file_entries:
        all_client_dicts.append(entry.as_client_dict())
    tool_calls = list(agent_instance.toolCalls.filter(Q(created_at__gte=
        oldest_msg_created_at, created_at__lt=datetime_limit)).order_by
        ('-created_at'))
    for entry in tool_calls:
        all_client_dicts.append(entry.as_client_dict())
    llm_queries = list(agent_instance.llmqueries.filter(Q(created_at__gte=
        oldest_msg_created_at, created_at__lt=datetime_limit)).order_by
        ('-created_at'))
    for query_obj in llm_queries:
        all_client_dicts.append(query_obj.as_client_dict())
    llm_responses = list(agent_instance.llmResponses.filter(Q(created_at__gte=
        oldest_msg_created_at, created_at__lt=datetime_limit)).order_by
        ('-created_at'))
    for query_obj in llm_responses:
        all_client_dicts.append(query_obj.as_client_dict())
    inter_agent_messages = list(InterAgentMessage.objects.filter(Q(
        sender_agentInstance=agent_instance) | Q(receiver_agentInstance=agent_instance), Q(
        created_at__gte=oldest_msg_created_at, created_at__lt=
        datetime_limit)).order_by('-created_at'))
    for entry in inter_agent_messages:
        all_client_dicts.append(entry.as_client_dict())
    python_tool_vars = list(agent_instance.python_tool_vars.filter(Q(
        created_at__gte=oldest_msg_created_at, created_at__lt=
        datetime_limit)).order_by('-created_at'))
    for entry in python_tool_vars:
        all_client_dicts.append(entry.as_client_dict())
    all_client_dicts.sort(key=lambda x: (x['created_at'], x.get('id', 0
        )), reverse=True)
    for msg in all_client_dicts:
        msg['prepend'] = True
        consumer.send(text_data=json.dumps(msg))
    consumer.send(text_data=json.dumps({'object': 'HistoryLoadResult', 'count': len(all_client_dicts), 'agentInstance_id': agent_instance.instance_pk}))