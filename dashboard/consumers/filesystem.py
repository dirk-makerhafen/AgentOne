import json
from tools_filesystem.models import FsLogEntry
from tools_filesystem.tasks import celery_undo_all_filesystem_changes
from tools_filesystem.tasks import celery_undo_filesystem_changes



def handle_filesystem_get(consumer, payload):
    from agent.models.agent import AgentInstance
    try:
        agent_instance = AgentInstance.objects.get(instance_pk=payload.get('instance_pk'))
    except AgentInstance.DoesNotExist:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'AgentInstance with pk {payload.get('instance_pk')} not found.'}))
        return
    latest_files = list(FsLogEntry.objects.filter(agentInstance=agent_instance, is_newest_version=True))
    sorted_items = sorted(latest_files , key=lambda x:x.path)
    fs_items = []
    for item in sorted_items:
        client_dict = item.as_client_dict()
        client_dict['is_initial_state'] = True
        fs_items.append(client_dict)
    consumer.send(text_data=json.dumps({'object': 'InitialFilesystemState', 'items': fs_items, 'agentInstance_id': agent_instance.instance_pk}))

def handle_filesystem_revert(consumer, payload):    
    from agent.models.agent import AgentInstance
    try:
        agent_instance = AgentInstance.objects.get(instance_pk=payload.get('instance_pk'))
    except AgentInstance.DoesNotExist:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'AgentInstance with pk {payload.get('instance_pk', None)} not found.'}))
        return    
    log_entry_pk = payload.get('log_entry_pk')
    comment = payload.get('comment', '')
    if not log_entry_pk:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': 'log_entry_pk is required for file revert.'}))
        return
    celery_undo_filesystem_changes.apply_async(args=[agent_instance.instance_pk, log_entry_pk, comment])

def handle_filesystem_revert_all(consumer, payload):
    from agent.models.agent import AgentInstance
    try:
        agent_instance = AgentInstance.objects.get(instance_pk=payload.get('instance_pk'))
    except AgentInstance.DoesNotExist:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'AgentInstance with pk {payload.get('instance_pk', None)} not found.'}))
        return
    log_entry_pk = payload.get('log_entry_pk')
    comment = payload.get('comment', '')
    if not log_entry_pk:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': 'log_entry_pk is required for revert all filesystem changes.'}))
        return
    celery_undo_all_filesystem_changes.apply_async(args=[agent_instance.instance_pk, log_entry_pk, comment])

def handle_filesystem_getcontent(consumer, payload):
    log_entry_pk = payload.get('log_entry_pk')
    if not log_entry_pk:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': 'log_entry_pk not provided.'}))
        return
    from agent.models.agent import AgentInstance
    try:
        agent_instance = AgentInstance.objects.get(instance_pk=payload.get('instance_pk'))
    except AgentInstance.DoesNotExist:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'AgentInstance with pk {payload.get('instance_pk', None)} not found.'}))
        return

    try:
        log_entry = FsLogEntry.objects.get(pk=log_entry_pk, agentInstance=agent_instance)
        consumer.send(text_data=json.dumps(log_entry.as_client_dict(include_content=True, include_summary=True)))
    except FsLogEntry.DoesNotExist:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'FsLogEntry with pk {log_entry_pk} not found for this instance.'}))

def handle_filesystem_togglepinned(consumer, payload):
    from tools_filesystem.fsutils import get_abs_path
    from tools_filesystem.models import FsLogEntry
    from agent.models.agent import AgentInstance
    try:
        agent_instance = AgentInstance.objects.get(instance_pk=payload.get('instance_pk'))
    except AgentInstance.DoesNotExist:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'AgentInstance with pk {payload.get('instance_pk', None)} not found.'}))
        return
    path = payload.get('path')
    object_type = payload.get('object_type')
    if not path or not object_type:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': 'Path and object_type are required.'}))
        return
    abs_path = get_abs_path(agent_instance.workingdir, path)
    latest_entry = FsLogEntry.objects.filter(agentInstance=agent_instance, path=abs_path, is_newest_version=True, next_versions=None).order_by('pk').first()
    if not latest_entry:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'No loaded item found for path: {path}'}))
        return
    latest_entry.is_pinned = not latest_entry.is_pinned
    latest_entry.save()
