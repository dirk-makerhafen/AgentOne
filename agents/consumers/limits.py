import json
from agents.models.agent_instance import AgentInstance
from agents.models.history_limit import HistoryLimit
from ui.router import register_handler
import traceback

@register_handler('historylimit_reset')
def handle_historylimit_reset(consumer, instance_pk, rule_name):
    try:
        agent_instance = AgentInstance.objects.get(instance_pk=instance_pk)
    except AgentInstance.DoesNotExist:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'AgentInstance with pk {instance_pk} not found.'}))
        return

    if not rule_name:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': 'rule_name is required for reset.'}))
        return

    parts = rule_name.split(':', 1)
    if len(parts) != 2:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'Invalid rule_name format: {rule_name}. Expected "group_name:rule_name".'}))
        return

    group_name, rule_name_part = (parts[0], parts[1])
    try:
        HistoryLimit.objects.filter(agentInstance=agent_instance, group_name=group_name, rule_name=rule_name_part).delete()
        agent_instance.send_object_to_clients()
    except Exception as e:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'Failed to reset history limit rule: {e} {traceback.format_exc()}'}))

@register_handler('historylimit_update')
def handle_historylimit_update(consumer, instance_pk, rule_name, limits=None):
    if limits is None:
        limits = {}
    try:
        agent_instance = AgentInstance.objects.get(instance_pk=instance_pk)
    except AgentInstance.DoesNotExist:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'AgentInstance with pk {instance_pk} not found.'}))
        return

    if not rule_name:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': 'rule_name is required.'}))
        return

    parts = rule_name.split(':', 1)
    if len(parts) != 2:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'Invalid rule_name format: {rule_name}. Expected "group_name:rule_name".'}))
        return

    group_name, rule_name_part = (parts[0], parts[1])
    try:
        rule, created = HistoryLimit.objects.get_or_create(agentInstance=agent_instance, group_name=group_name, rule_name=rule_name_part, defaults={'is_active': True})
        changed = False
        limit_fields = ['success', 'failed', 'pending', 'max']
        for field in limit_fields:
            if field in limits:
                value = limits[field]
                db_field_name = f'limit_{field}'
                if value == '':
                    value = None
                elif value is not None:
                    try:
                        value = int(value)
                    except (ValueError, TypeError):
                        continue
                if getattr(rule, db_field_name) != value:
                    setattr(rule, db_field_name, value)
                    changed = True
        if changed:
            rule.save()
        agent_instance.send_object_to_clients()
    except Exception as e:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'Failed to update history limit rule: {e} {traceback.format_exc()}'}))


@register_handler('instance_limits_update')
def handle_instance_limits_update(consumer, instance_pk, **kwargs):
    try:
        agent_instance = AgentInstance.objects.get(instance_pk=instance_pk)
    except AgentInstance.DoesNotExist:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'AgentInstance with pk {instance_pk} not found.'}))
        return

    try:
        updated = False
        if 'limit_max_conversation_messages' in kwargs:
            agent_instance.limit_max_conversation_messages = kwargs['limit_max_conversation_messages']
            updated = True
        if 'limit_max_memory_items' in kwargs:
            agent_instance.limit_max_memory_items = kwargs['limit_max_memory_items']
            updated = True
        if 'limit_max_automated_steps' in kwargs:
            agent_instance.limit_max_automated_steps = kwargs['limit_max_automated_steps']
            updated = True

        if updated:
            agent_instance.save()

    except Exception as e:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'Failed to update instance limits: {e} {traceback.format_exc()}'}))
