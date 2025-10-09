import json
from tools.builtin_filesystem.models.fs_log_entry import FsLogEntry
from tools.builtin_filesystem.tasks.undo_all_filesystem_changes import celery_undo_all_filesystem_changes
from tools.builtin_filesystem.tasks.undo_filesystem_changes import celery_undo_filesystem_changes
from agents.models.agent_instance import AgentInstance
from ui.router import register_handler
from tools.builtin_filesystem.utils.fsutils import get_abs_path

@register_handler('filesystem_list')
def handle_filesystem_list(consumer, instance_pk):
    try:
        agent_instance = AgentInstance.objects.get(instance_pk=instance_pk)
        latest_files = list(FsLogEntry.objects.filter(agentInstance=agent_instance, is_newest_version=True))
        sorted_items = sorted(latest_files, key=lambda x: x.path)
        fs_items = [item.as_client_dict() for item in sorted_items]
        consumer.send(text_data=json.dumps({'object': 'InitialFilesystemState', 'items': fs_items, 'agentInstance_id': agent_instance.instance_pk}))
    except AgentInstance.DoesNotExist:
        pass # Fail silently

@register_handler('filesystem_get_filecontent')
def handle_filesystem_get_filecontent(consumer, instance_pk, log_entry_pk=None):
    if not log_entry_pk:
        return
    try:
        agent_instance = AgentInstance.objects.get(instance_pk=instance_pk)
        log_entry = FsLogEntry.objects.get(pk=log_entry_pk, agentInstance=agent_instance)
        consumer.send(text_data=json.dumps(log_entry.as_client_dict(include_content=True, include_summary=True)))
    except (AgentInstance.DoesNotExist, FsLogEntry.DoesNotExist):
        pass

@register_handler('filesystem_update_ispinned')
def handle_filesystem_update_ispinned(consumer, instance_pk, path=None):
    try:
        agent_instance = AgentInstance.objects.get(instance_pk=instance_pk)
        if not path:
            return
        abs_path = get_abs_path(agent_instance.workingdir, path)
        latest_entry = FsLogEntry.objects.filter(agentInstance=agent_instance, path=abs_path, is_newest_version=True).first()
        if latest_entry:
            latest_entry.is_pinned = not latest_entry.is_pinned
            latest_entry.save()
    except AgentInstance.DoesNotExist:
        pass


@register_handler('filesystem_undo')
def handle_filesystem_undo(consumer, instance_pk, log_entry_pk=None, comment=''):
    try:
        agent_instance = AgentInstance.objects.get(instance_pk=instance_pk)
        if log_entry_pk:
            celery_undo_filesystem_changes.delay(agent_instance.instance_pk, log_entry_pk, comment)
    except AgentInstance.DoesNotExist:
        pass # Fail silently

@register_handler('filesystem_undo_all')
def handle_filesystem_undo_all(consumer, instance_pk, log_entry_pk=None, comment=''):
    try:
        agent_instance = AgentInstance.objects.get(instance_pk=instance_pk)
        if log_entry_pk:
            celery_undo_all_filesystem_changes.delay(agent_instance.instance_pk, log_entry_pk, comment)
    except AgentInstance.DoesNotExist:
        pass

