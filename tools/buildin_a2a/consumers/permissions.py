import json
from tools.buildin_a2a.models.a2a_permission import AgentToAgentPermission
from agents.models.agent_instance import AgentInstance
from ui.router import register_handler

@register_handler('a2a_permission_set')
def handle_permission_set(consumer, user_pk, payload):
    try:
        source_instance = AgentInstance.objects.get(instance_pk=payload.get('instance_pk'))
        target_instance_pk = payload.get('target_instance_pk')
        can_send = payload.get('can_send')
        can_receive = payload.get('can_receive')
        
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
        handle_permission_list(consumer, user_pk, {'instance_pk': source_instance.instance_pk})

    except AgentInstance.DoesNotExist as e:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'AgentInstance not found: {e}'}))
    except Exception as e:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'Error setting permission: {e}'}))

@register_handler('a2a_permission_list')
def handle_permission_list(consumer, user_pk, payload):
    try:
        source_instance = AgentInstance.objects.get(instance_pk=payload.get('instance_pk'))
        
        other_instances = AgentInstance.objects.exclude(pk=source_instance.pk).select_related('agent')
        permissions_map = {p.target_instance_id: p for p in source_instance.source_permissions.all()}
        
        permissions_list = []
        for instance in other_instances:
            permission = permissions_map.get(instance.pk)
            permissions_list.append({
                'target_instance_pk': instance.pk,
                'target_instance_name': f'{instance.agent.name} - {instance.name or f"Instance {instance.pk}"}',
                'target_instance_description': instance.agent.description or '',
                'can_send': permission.can_send if permission else False,
                'can_receive': permission.can_receive if permission else False
            })

        consumer.send(text_data=json.dumps({
            'object': 'InstancePermissionList',
            'instance_pk': source_instance.pk,
            'permissions': permissions_list
        }))
    except AgentInstance.DoesNotExist:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'AgentInstance with pk {payload.get("instance_pk")} not found.'}))
    except Exception as e:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'Error getting permissions: {e}'}))
