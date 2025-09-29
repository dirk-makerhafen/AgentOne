from tools_a2a.models import InstancePermission
import json

def handle_permission_set(consumer, payload):
    """
    Handles updating a communication permission between two agent instances.
    The payload can contain either 'can_send' or 'can_receive'.
    """
    from agent.models.agent import AgentInstance
    try:
        source_instance = AgentInstance.objects.get(instance_pk=payload.get('instance_pk'))
    except AgentInstance.DoesNotExist:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'AgentInstance with pk {payload.get('instance_pk', None)} not found.'}))
        return
    target_instance_pk = payload.get('target_instance_pk')
    can_send = payload.get('can_send')
    can_receive = payload.get('can_receive')
    if target_instance_pk is None or (can_send is None and can_receive is None):
        consumer.send(text_data=json.dumps({'object': 'error', 'message': 'target_instance_pk and either can_send or can_receive are required.'}))
        return
    try:
        target_instance = AgentInstance.objects.get(pk=target_instance_pk)
    except AgentInstance.DoesNotExist:
        error_message = f'Target instance with pk {target_instance_pk} not found.'
        print(f'Error: {error_message}', flush=True)
        consumer.send(text_data=json.dumps({'object': 'error', 'message': error_message}))
        return
    defaults = {}
    if can_send is not None:
        defaults['can_send'] = can_send
    if can_receive is not None:
        defaults['can_receive'] = can_receive
    permission, created = InstancePermission.objects.update_or_create(source_instance=source_instance, target_instance=target_instance, defaults=defaults)
    consumer.send(text_data=json.dumps({'object': 'InstancePermissionUpdate', 'status': 'success', 'source_instance_pk': source_instance.pk, 'target_instance_pk': target_instance.pk, 'can_send': permission.can_send, 'can_receive': permission.can_receive}))


def handle_permission_get(consumer, payload):
    from agent.models.agent import AgentInstance
    try:
        source_instance = AgentInstance.objects.get(instance_pk=payload.get('instance_pk'))
    except AgentInstance.DoesNotExist:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'AgentInstance with pk {payload.get('instance_pk', None)} not found.'}))
        return
            
    other_instances = AgentInstance.objects.exclude(pk=source_instance.pk).select_related('agent')
    source_permissions_map = {p.target_instance_id: p for p in source_instance.source_permissions.all()}
    outbound_permissions_list = []
    for instance in other_instances:
        permission = source_permissions_map.get(instance.pk)
        outbound_permissions_list.append({'target_instance_pk': instance.pk, 'target_instance_name': f'{instance.agent.name} - {instance.name or f'Instance {instance.pk}'}', 'target_instance_description': instance.agent.description or '', 'can_send': permission.can_send if permission else False, 'can_receive': permission.can_receive if permission else False})
    target_permissions = source_instance.target_permissions.select_related('source_instance__agent').all()
    inbound_permissions_list = []
    for permission in target_permissions:
        source = permission.source_instance
        inbound_permissions_list.append({'source_instance_pk': source.pk, 'source_instance_name': f'{source.agent.name} - {source.name or f'Instance {source.pk}'}', 'can_send': permission.can_send, 'can_receive': permission.can_receive})
    consumer.send(text_data=json.dumps({
        'object': 'InstancePermissionList',
        'instance_pk': source_instance.pk,
        'outbound_permissions': outbound_permissions_list,
        'inbound_permissions': inbound_permissions_list,
        'all_available_instances': outbound_permissions_list
    }))
