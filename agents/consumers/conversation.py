import json
from datetime import datetime
from django.db.models import Q
from agents.models.agent_instance import AgentInstance
from agents.models.conversation_message import ConversationMessage
from tools.builtin_a2a.models.a2a_message import AgentToAgentMessage
from ui.router import register_handler
from django.utils import timezone
import traceback

@register_handler('conversationmessage_add')
def handle_conversationmessage_add(consumer, instance_pk, message):
    try:
        agent_instance = AgentInstance.objects.get(instance_pk=instance_pk)
    except AgentInstance.DoesNotExist:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'AgentInstance with pk {instance_pk} not found.'}))
        return

    if message:
        agent_instance.add_to_conversation(role='user', content=message)
    agent_instance.start_or_continue()

@register_handler('conversationmessage_list')
def handle_conversationmessage_get(consumer, instance_pk, max_id=None, limit=20):
    try:
        agent_instance = AgentInstance.objects.get(instance_pk=instance_pk)
    except AgentInstance.DoesNotExist:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'AgentInstance with pk {instance_pk} not found.'}))
        return
    print("conversationmessage_list")
    conversation_messages = agent_instance.get_conversation_messages(max_id=max_id, limit=limit)
    if conversation_messages:
        # find next message after the current highest, so we can receive stuff related to the last conversation message 
        next_message = agent_instance.conversationMessages.filter(created_at__gt=conversation_messages[0].created_at).order_by('created_at').first()
        datetime_limit = next_message.created_at if next_message else datetime.max
        oldest_msg_created_at = conversation_messages[-1].created_at
    else:
        datetime_limit =  timezone.datetime.max
        oldest_msg_created_at = timezone.datetime.min

    all_client_dicts = []

    for msg in conversation_messages:
        all_client_dicts.append(msg.as_client_dict())

    debug_log_entries = list(agent_instance.debugLogEntries.filter(Q(created_at__gte=oldest_msg_created_at, created_at__lt=datetime_limit)).order_by('-created_at'))
    all_client_dicts.extend([entry.as_client_dict() for entry in debug_log_entries])

    fs_file_entries = list(agent_instance.fsLogEntries.filter(Q(created_at__gte=oldest_msg_created_at, created_at__lte=datetime_limit)).order_by('-created_at'))
    all_client_dicts.extend([entry.as_client_dict() for entry in fs_file_entries])

    tool_calls = list(agent_instance.toolCalls.filter(Q(created_at__gte=oldest_msg_created_at, created_at__lt=datetime_limit)).order_by('-created_at'))
    all_client_dicts.extend([entry.as_client_dict() for entry in tool_calls])

    llm_queries = list(agent_instance.llmQueries.filter(Q(created_at__gte=oldest_msg_created_at, created_at__lt=datetime_limit)).order_by('-created_at'))
    all_client_dicts.extend([query_obj.as_client_dict() for query_obj in llm_queries])

    llm_responses = list(agent_instance.llmResponses.filter(Q(created_at__gte=oldest_msg_created_at, created_at__lt=datetime_limit)).order_by('-created_at'))
    all_client_dicts.extend([query_obj.as_client_dict() for query_obj in llm_responses])

    if hasattr(agent_instance, "fork_origin"):
        fork_origin = agent_instance.fork_origin.as_client_dict()
        fork_origin.update({"target_instance_id": instance_pk})
        all_client_dicts.append(fork_origin)

    if hasattr(agent_instance, "forks_created"):
        forks_created = list(agent_instance.forks_created.filter(Q(created_at__gte=oldest_msg_created_at, created_at__lt=datetime_limit)).order_by('-created_at'))
        forks_created = [query_obj.as_client_dict() for query_obj in forks_created]
        [fork_created.update({"target_instance_id": instance_pk}) for fork_created in forks_created]
        all_client_dicts.extend(forks_created)

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
def handle_conversationmessage_update_flags(consumer, instance_pk, message_id, pin_to_context=None, hide_from_context=None):
    try:
        agent_instance = AgentInstance.objects.get(instance_pk=instance_pk)
    except AgentInstance.DoesNotExist:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'AgentInstance with pk {instance_pk} not found.'}))
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
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'Error fetching ConversationMessage: {str(e)} {traceback.format_exc()}'}))
        return

    if pin_to_context is not None:
        message.pin_to_context = bool(pin_to_context)
    if hide_from_context is not None:
        message.hide_from_context = bool(hide_from_context)

    try:
        message.save()
    except Exception as e:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'Error saving ConversationMessage flags: {str(e)} {traceback.format_exc()}'}))
