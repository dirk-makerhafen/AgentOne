import json
from agents.models.agent_instance import AgentInstance
from agents.models.agentevents import EventHandler, EventSubscription
from ui.router import register_handler

# --- EventHandler Handlers for AgentInstance ---

@register_handler('agentinstance_events_receiver_list')
def handle_agentinstance_events_receiver_list(consumer, instance_pk):
    """
    Handles a request to list all event receiver functions for a specific agent instance.
    """
    try:
        instance = AgentInstance.objects.get(pk=instance_pk)
        receivers = EventHandler.objects.filter(agentInstance=instance).order_by('name')
        receivers_data = [receiver.as_client_dict() for receiver in receivers]
        consumer.send(text_data=json.dumps({
            'object': 'InstanceEventReceiverList',
            'instance_pk': instance_pk,
            'receivers': receivers_data
        }))
    except AgentInstance.DoesNotExist:
        # Handle error
        pass

@register_handler('agentinstance_events_receiver_create')
def handle_agentinstance_events_receiver_create(consumer, instance_pk, **kwargs):
    try:
        instance = AgentInstance.objects.get(pk=instance_pk)
        receiver = EventHandler.objects.create(
            agentInstance=instance,
            name=kwargs.get('name'),
            description=kwargs.get('description'),
            eventtype=kwargs.get('eventtype'),
            source=kwargs.get('source'),
            is_public=kwargs.get('is_public', False),
            enabled=kwargs.get('enabled', True)
        )
        # Re-fetch the list to send a complete update
        handle_agentinstance_events_receiver_list(consumer, instance_pk)
    except AgentInstance.DoesNotExist:
        pass

@register_handler('agentinstance_events_receiver_update')
def handle_agentinstance_events_receiver_update(consumer, receiver_id, **kwargs):
    try:
        receiver = EventHandler.objects.get(pk=receiver_id)
        receiver.name = kwargs.get('name', receiver.name)
        receiver.description = kwargs.get('description', receiver.description)
        receiver.eventtype = kwargs.get('eventtype', receiver.event)
        receiver.source = kwargs.get('source', receiver.source)
        receiver.is_public = kwargs.get('is_public', receiver.is_public)
        receiver.enabled = kwargs.get('enabled', receiver.enabled)
        receiver.save()
        if receiver.agentInstance:
            handle_agentinstance_events_receiver_list(consumer, receiver.agentInstance.pk)
    except EventHandler.DoesNotExist:
        pass

@register_handler('agentinstance_events_receiver_delete')
def handle_agentinstance_events_receiver_delete(consumer, receiver_id):
    try:
        receiver = EventHandler.objects.get(pk=receiver_id)
        instance_pk = receiver.agentInstance.pk if receiver.agentInstance else None
        receiver.delete()
        if instance_pk:
            handle_agentinstance_events_receiver_list(consumer, instance_pk)
    except EventHandler.DoesNotExist:
        pass

# --- EventSubscription Handlers for AgentInstance ---

@register_handler('agentinstance_events_assignment_list')
def handle_agentinstance_events_assignment_list(consumer, instance_pk):
    try:
        instance = AgentInstance.objects.get(pk=instance_pk)
        assignments = EventSubscription.objects.filter(agentInstance=instance).select_related('eventHandler__agent').order_by('created_at')
        assignments_data = [assignment.as_client_dict() for assignment in assignments]
        consumer.send(text_data=json.dumps({
            'object': 'InstanceEventSubscriptionList',
            'instance_pk': instance_pk,
            'assignments': assignments_data
        }))
    except AgentInstance.DoesNotExist:
        pass

@register_handler('agentinstance_events_assignment_create')
def handle_agentinstance_events_assignment_create(consumer, instance_pk, **kwargs):
    try:
        instance = AgentInstance.objects.get(pk=instance_pk)
        receiver = EventHandler.objects.get(pk=kwargs.get('eventHandler_id'))
        assignment = EventSubscription.objects.create(
            agentInstance=instance,
            eventHandler=receiver,
            description=kwargs.get('description')
        )
        handle_agentinstance_events_assignment_list(consumer, instance_pk)
    except (AgentInstance.DoesNotExist, EventHandler.DoesNotExist):
        pass

@register_handler('agentinstance_events_assignment_update')
def handle_agentinstance_events_assignment_update(consumer, assignment_id, **kwargs):
    try:
        assignment = EventSubscription.objects.get(pk=assignment_id)
        assignment.description = kwargs.get('description', assignment.description)
        if 'eventHandler_id' in kwargs:
            assignment.eventHandler = EventHandler.objects.get(pk=kwargs['eventHandler_id'])
        assignment.save()
        if assignment.agentInstance:
            handle_agentinstance_events_assignment_list(consumer, assignment.agentInstance.pk)
    except (EventSubscription.DoesNotExist, EventHandler.DoesNotExist):
        pass

@register_handler('agentinstance_events_assignment_delete')
def handle_agentinstance_events_assignment_delete(consumer, assignment_id):
    try:
        assignment = EventSubscription.objects.get(pk=assignment_id)
        instance_pk = assignment.agentInstance.pk if assignment.agentInstance else None
        assignment.delete()
        if instance_pk:
            handle_agentinstance_events_assignment_list(consumer, instance_pk)
    except EventSubscription.DoesNotExist:
        pass
