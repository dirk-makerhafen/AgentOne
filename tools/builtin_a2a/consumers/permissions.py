import json
from tools.builtin_a2a.models.a2a_permission import AgentToAgentPermission
from agents.models.agent_instance import AgentInstance
from ui.router import register_handler

@register_handler('a2a_permission_set')
def handle_permission_set(consumer, instance_pk, target_instance_pk=None, can_send=None, can_receive=None):
    try:
        source_instance = AgentInstance.objects.get(instance_pk=instance_pk)

        if target_instance_pk is None or (can_send is None and can_receive is None):
            consumer.send(text_data=json.dumps({'object': 'error', 'message': 'target_instance_pk and either can_send or can_receive are required.'}))
            return

        target_instance = AgentInstance.objects.get(pk=target_instance_pk)

        defaults = {}
        if can_send is not None:
            defaults['can_send'] = can_send
        if can_receive is not None:
            defaults['can_receive'] = can_receive

        permission, created = AgentToAgentPermission.objects.update_or_create(
            source_instance=source_instance, 
            target_instance=target_instance, 
            defaults=defaults
        )

        # After update, re-request the full list to update the UI
        handle_permission_list(consumer, instance_pk=source_instance.instance_pk)

    except AgentInstance.DoesNotExist as e:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'AgentInstance not found: {e}'}))
    except Exception as e:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'Error setting permission: {e}'}))

@register_handler('a2a_permission_list')
def handle_permission_list(consumer, instance_pk):
    try:
        source_instance = AgentInstance.objects.get(pk=instance_pk)

        # Outbound Permissions (what this instance can do to others)
        other_instances = AgentInstance.objects.exclude(pk=source_instance.pk).select_related('agent').order_by('agent__name', 'name')
        outbound_permissions_map = {p.target_instance_id: p for p in source_instance.source_permissions.all()}

        outbound_permissions_list = []
        available_instances_list = [] # For the search functionality
        for instance in other_instances:
            permission = outbound_permissions_map.get(instance.pk)
            outbound_permissions_list.append({
                'target_instance_pk': instance.pk,
                'target_instance_name': f'{instance.agent.name} - {instance.name or f"Instance {instance.pk}"}',
                'target_instance_description': instance.agent.description or '',
                'can_send': permission.can_send if permission else False,
                'can_receive': permission.can_receive if permission else False
            })
            available_instances_list.append({ # Add to available for search
                'target_instance_pk': instance.pk,
                'target_instance_name': f'{instance.agent.name} - {instance.name or f"Instance {instance.pk}"}',
                'target_instance_description': instance.agent.description or '',
                'can_send': False, # Default for search results, actual permissions come from outbound_permissions_list
                'can_receive': False
            })

        # Inbound Permissions (what other instances can do to this one)
        inbound_permissions_map = {p.source_instance_id: p for p in source_instance.target_permissions.all()}
        inbound_permissions_list = []
        for instance in other_instances:
            permission = inbound_permissions_map.get(instance.pk)
            if permission: # Only include if a permission actually exists
                inbound_permissions_list.append({
                    'source_instance_pk': instance.pk,
                    'source_instance_name': f'{instance.agent.name} - {instance.name or f"Instance {instance.pk}"}',
                    'source_instance_description': instance.agent.description or '',
                    'can_send': permission.can_send, # Can this source SEND to me?
                    'can_receive': permission.can_receive # Can this source RECEIVE from me?
                })

        consumer.send(text_data=json.dumps({
            'object': 'InstancePermissionList',
            'instancePk': source_instance.pk, # Renamed to match JS camelCase
            'outbound_permissions': outbound_permissions_list,
            'inbound_permissions': inbound_permissions_list,
            'available_instances': available_instances_list # For frontend search
        }))
    except AgentInstance.DoesNotExist:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'AgentInstance with pk {instance_pk} not found.'}))
    except Exception as e:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'Error getting permissions: {e}'}))
