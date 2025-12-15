import json
from agents.models.agent import Agent
from events.models.event_handler import EventHandler
from events.models.event_subscription import EventSubscription
from ui.router import register_handler

# --- EventHandler Handlers ---

@register_handler('agentevents_receiver_list')
def handle_receiver_list(consumer, agent_pk):
    receivers = EventHandler.objects.filter(agent_id=agent_pk)
    receivers_data = [receiver.as_client_dict() for receiver in receivers]
    consumer.send(text_data=json.dumps({
        'object': 'AgentEventReceiverList',
        'agent_pk': agent_pk,
        'receivers': receivers_data
    }))

@register_handler('agentevents_receiver_get')
def handle_receiver_get(consumer, receiver_id):
    try:
        receiver = EventHandler.objects.get(pk=receiver_id)
        consumer.send(text_data=json.dumps({
            'object': 'AgentEventReceiver',
            'receiver': receiver.as_client_dict()
        }))
    except EventHandler.DoesNotExist:
        # Handle error
        pass

@register_handler('agentevents_receiver_create')
def handle_receiver_create(consumer, agent_pk, data):
    if "id" in data and not data["id"]:
        del data["id"]
    agent = Agent.objects.get(pk=agent_pk)
    print("DATADATA", data)
    EventHandler.objects.create(agent=agent, **data)
    handle_receiver_list(consumer, agent_pk)

@register_handler('agentevents_receiver_update')
def handle_receiver_update(consumer, receiver_id, data):
    EventHandler.objects.filter(pk=receiver_id).update(**data)
    receiver = EventHandler.objects.get(pk=receiver_id)
    consumer.send(text_data=json.dumps({
        'object': 'AgentEventReceiver',
        'receiver': receiver.as_client_dict(),
        'action': 'updated'
    }))

@register_handler('agentevents_receiver_delete')
def handle_receiver_delete(consumer, receiver_id):
    try:
        receiver = EventHandler.objects.get(pk=receiver_id)
        agent_pk = receiver.agent.pk
        receiver.delete()
        consumer.send(text_data=json.dumps({
            'object': 'AgentEventReceiver',
            'receiver_id': receiver_id,
            'action': 'deleted'
        }))
    except EventHandler.DoesNotExist:
        # Handle error
        pass

@register_handler('agentevents_receiver_list_public')
def handle_receiver_list_public(consumer):
    public_receivers = EventHandler.objects.filter(is_public=True, enabled=True)
    receivers_data = [receiver.as_client_dict() for receiver in public_receivers]
    consumer.send(text_data=json.dumps({
        'object': 'PublicEventReceiverList',
        'receivers': receivers_data
    }))

# --- EventSubscription Handlers ---

@register_handler('agentevents_assignment_list')
def handle_assignment_list(consumer, agent_pk):
    assignments = EventSubscription.objects.filter(agent_id=agent_pk)
    assignments_data = [assignment.as_client_dict() for assignment in assignments]
    consumer.send(text_data=json.dumps({
        'object': 'AgentEventSubscriptionList',
        'agent_pk': agent_pk,
        'assignments': assignments_data
    }))

@register_handler('agentevents_assignment_get')
def handle_assignment_get(consumer, assignment_id):
    try:
        assignment = EventSubscription.objects.get(pk=assignment_id)
        consumer.send(text_data=json.dumps({
            'object': 'AgentEventSubscription',
            'assignment': assignment.as_client_dict()
        }))
    except EventSubscription.DoesNotExist:
        # Handle error
        pass

@register_handler('agentevents_assignment_create')
def handle_assignment_create(consumer, agent_pk, data):
    agent = Agent.objects.get(pk=agent_pk)
    if 'id' in data and not data["id"]: # new items have a empty id field, make it django compatible
        del data['id']
    # You might need to fetch the EventHandler instance from its ID
    receiver_id = data.pop('eventHandler_id', None)
    if receiver_id:
        receiver = EventHandler.objects.get(pk=receiver_id)
        EventSubscription.objects.create(agent=agent, eventHandler=receiver, **data)
    handle_assignment_list(consumer, agent_pk)

@register_handler('agentevents_assignment_update')
def handle_assignment_update(consumer, assignment_id, data):
    receiver_id = data.pop('eventHandler_id', None)
    if receiver_id:
        data['eventHandler'] = EventHandler.objects.get(pk=receiver_id)
    
    EventSubscription.objects.filter(pk=assignment_id).update(**data)
    assignment = EventSubscription.objects.get(pk=assignment_id)
    consumer.send(text_data=json.dumps({
        'object': 'AgentEventSubscription',
        'assignment': assignment.as_client_dict(),
        'action': 'updated'
    }))

@register_handler('agentevents_assignment_delete')
def handle_assignment_delete(consumer, assignment_id):
    try:
        assignment = EventSubscription.objects.get(pk=assignment_id)
        assignment.delete()
        consumer.send(text_data=json.dumps({
            'object': 'AgentEventSubscription',
            'assignment_id': assignment_id,
            'action': 'deleted'
        }))
    except EventSubscription.DoesNotExist:
        # Handle error
        pass

@register_handler('agentevents_public_receiver_list')
def handle_agentevents_public_receiver_list(consumer):
    """
    Handles a request to list all public event receiver functions.
    """
    public_receivers = EventHandler.objects.filter(is_public=True, enabled=True).select_related('agent')
    receivers_data = [receiver.as_client_dict() for receiver in public_receivers]
    
    consumer.send(text_data=json.dumps({
        'object': 'PublicEventReceiverList',
        'receivers': receivers_data
    }))
