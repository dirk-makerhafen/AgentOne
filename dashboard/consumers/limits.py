import json
from dashboard.tasks import send_object_to_clients


def handle_limit_reset(consumer, payload):
    from agent.models.agent import AgentInstance
    from agent.models.limits import HistoryLimitingRule

    try:
        agent_instance = AgentInstance.objects.get(instance_pk=payload.get('instance_pk'))
    except AgentInstance.DoesNotExist:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'AgentInstance with pk {payload.get('instance_pk', None)} not found.'}))
        return
    full_rule_name = payload.get('rule_name')
    if not full_rule_name:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': 'full_rule_name is required for reset.'}))
        return
    parts = full_rule_name.split(':', 1)
    if len(parts) != 2:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'Invalid full_rule_name format: {full_rule_name}. Expected "group_name:rule_name".'}))
        return
    group_name, rule_name = (parts[0], parts[1])
    try:
        HistoryLimitingRule.objects.filter(agentInstance=agent_instance, group_name=group_name, rule_name=rule_name).delete()
        send_object_to_clients(agent_instance)
    except Exception as e:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'Failed to reset history limit rule: {e}'}))



def handle_limit_update(consumer, payload):
    from agent.models.agent import AgentInstance
    from agent.models.limits import HistoryLimitingRule
    try:
        agent_instance = AgentInstance.objects.get(instance_pk=payload.get('instance_pk'))
    except AgentInstance.DoesNotExist:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'AgentInstance with pk {payload.get('instance_pk', None)} not found.'}))
        return
    full_rule_name = payload.get('rule_name')
    limits = payload.get('limits', {})
    if not full_rule_name:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': 'full_rule_name is required.'}))
        return
    parts = full_rule_name.split(':', 1)
    if len(parts) != 2:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'Invalid full_rule_name format: {full_rule_name}. Expected "group_name:rule_name".'}))
        return
    group_name, rule_name = (parts[0], parts[1])
    try:
        rule, created = HistoryLimitingRule.objects.get_or_create(agentInstance=agent_instance, group_name=group_name, rule_name=rule_name, defaults={'is_active': True})
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
        send_object_to_clients(agent_instance)
    except Exception as e:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'Failed to update history limit rule: {e}'}))
