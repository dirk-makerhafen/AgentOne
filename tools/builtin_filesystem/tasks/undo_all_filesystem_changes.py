from celery import shared_task
import traceback
from server.models.agents.agent_version import AgentVersionModel
from server.models.conversation_message import ConversationMessagePart
from server.models.debug_log_entry import DebugLogEntry
from tools.builtin_filesystem.models.fs_log_entry import FsLogEntry

@shared_task
def celery_undo_all_filesystem_changes(instance_pk, log_entry_pk, comment=''):
    """
    Undoes a sequence of FsLogEntries starting from a given log_entry_pk.
    For each unique path, only the *oldest* relevant entry is undone.
    """
    agent_instance = None
    try:
        agent_instance = AgentVersionModel.objects.get(instance_pk=instance_pk)
        target_log_entry = FsLogEntry.objects.get(pk=log_entry_pk, agentInstance=agent_instance)
        
        # Select items to undo based on user's logic:
        # All entries for the instance created at or after the target_log_entry, ordered by PK.
        items_to_process = FsLogEntry.objects.filter(
            agentInstance=instance_pk,
            created_at__gte=target_log_entry.created_at,
            pk__gte=target_log_entry.pk
        ).order_by("pk")

        paths_undone = set()
        total_undone_actions = 0
        total_failed_actions = 0

        for item_to_undo in items_to_process:
            # User's logic: only undo the oldest version for a path in this batch.
            if item_to_undo.path in paths_undone:
                continue

            try:
                success, result = item_to_undo.undo(toolCall=None)
                if success:
                    paths_undone.add(item_to_undo.path)
                    total_undone_actions += 1
                else:
                    total_failed_actions += 1
                    error_message = result.get('message', 'Unknown error')
                    print(f"Failed to undo FsLogEntry {item_to_undo.pk} for path {item_to_undo.path}: {error_message}")
                    DebugLogEntry.objects.create(
                        agentInstance=agent_instance,
                        event='undo_all_error',
                        data={'log_entry_pk': item_to_undo.pk, 'path': item_to_undo.path, 'error': error_message}
                    )
            except Exception as e:
                total_failed_actions += 1
                error_message = f"Unhandled error undoing FsLogEntry {item_to_undo.pk} for path {item_to_undo.path}: {e}{traceback.format_exc()}"
                print(error_message)
                DebugLogEntry.objects.create(
                    agentInstance=agent_instance,
                    event='undo_all_error',
                    data={'log_entry_pk': item_to_undo.pk, 'path': item_to_undo.path, 'error': error_message}
                )

        # --- Finalize the user message and debug log ---
        summary_parts = [f"User initiated a bulk undo starting from FsLogEntry {log_entry_pk}."]
        if total_undone_actions: 
            summary_parts.append(f"Successfully undid {total_undone_actions} unique file actions.")
        if total_failed_actions: 
            summary_parts.append(f"Failed to undo {total_failed_actions} unique file actions. Check debug logs for details.")
        if comment: 
            summary_parts.append(f"Reason: {comment}")
        
        agent_instance.add_to_conversation(role='user', message='\n'.join(summary_parts))

        print(f"Bulk undo for instance {instance_pk} completed. Undone actions: {total_undone_actions}, Failed: {total_failed_actions}.")
        
        DebugLogEntry.objects.create(
            agentInstance=agent_instance,
            event='undo_all_completed',
            status='success',
            data={
                'target_log_entry_pk': log_entry_pk,
                'comment': comment,
                'total_undone_actions': total_undone_actions,
                'total_failed_actions': total_failed_actions,
            }
        )

    except Exception as e:
        error_message = f"An unexpected error occurred during bulk file undo for FsLogEntry {log_entry_pk}: {e}\n{traceback.format_exc()}"
        print(error_message)
        if agent_instance:
            DebugLogEntry.objects.create(
                agentInstance=agent_instance, 
                event='undo_all_failed', 
                status='failed', 
                data={'error': error_message, 'log_entry_pk': log_entry_pk, 'comment': comment}
            )
            agent_instance.add_to_conversation(role='user' , message= f"SYSTEM ERROR: Failed to perform bulk undo starting from FsLogEntry {log_entry_pk} due to an internal error.")
