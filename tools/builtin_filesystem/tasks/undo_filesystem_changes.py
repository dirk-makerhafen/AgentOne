from celery import shared_task
import traceback

from server.models.agents.agent_version import AgentVersionModel
from server.models.message import MessagePart
from server.models.debug_log_entry import DebugLogEntry
from tools.builtin_filesystem.models.fs_log_entry import FsLogEntry
from tools.builtin_filesystem.utils.fsutils import get_relative_path

@shared_task
def celery_undo_filesystem_changes(instance_pk, log_entry_pk, user_comment):
    agent_instance = None
    try:
        agent_instance = AgentVersionModel.objects.get(instance_pk=instance_pk)
        log_entry = FsLogEntry.objects.get(pk=log_entry_pk)
        file_path = log_entry.path

        success, result = log_entry.undo(toolCall=None) # Call the undo method

        if success:
            revert_message = f"User has reverted the file '{get_relative_path(agent_instance.workingdir, file_path)}' to the state before FsLogEntry {log_entry_pk}."
            if user_comment:
                revert_message += f"\nReason: {user_comment}"
            agent_instance.add_to_conversation(role='user',  message= revert_message)
            print(f"Successfully reverted {file_path} for instance {instance_pk}.")
            # The result from undo() is the new_snapshot if successful, which has a PK
            print(f"New FsLogEntry created: {result.pk}")
        else:
            error_message = f"Failed to revert file '{file_path}': {result.get('message', 'Unknown error')}"
            print(error_message)
            DebugLogEntry.objects.create(agentInstance=agent_instance, event='revert_error', data={'error': error_message})
            agent_instance.add_to_conversation(role='user', message= f"SYSTEM ERROR: {error_message}")

    except Exception as e:
        error_message = f"An unexpected error occurred during file revert for FsLogEntry {log_entry_pk}: {e}\n{traceback.format_exc()}"
        print(error_message)
        if agent_instance:
            DebugLogEntry.objects.create(agentInstance=agent_instance, event='revert_error', data={'error': error_message})
            
            agent_instance.add_to_conversation(role='user', message= f"SYSTEM ERROR: Failed to revert file related to FsLogEntry {log_entry_pk} due to an internal error.")

