from celery import shared_task
from django.db import transaction

from tools.primitives import rm, manage_tool_process
from tools.definitions.models.tool_installation import ToolInstallation
from tools.definitions.models.tool_installation_log import ToolInstallationLog

def _log(installation: ToolInstallation, level: str, message: str):
    """Helper function to create a log entry for a tool installation."""
    ToolInstallationLog.objects.create(
        tool_installation=installation,
        level=level,
        message=message
    )

@shared_task
def uninstall_tool(tool_installation_id):
    """
    Orchestrates the uninstallation of a tool. This involves stopping all running instances,
    deleting the tool's files from the system, and finally deleting the ToolInstallation record.
    """
    try:
        tool_installation = ToolInstallation.objects.get(pk=tool_installation_id)
    except ToolInstallation.DoesNotExist:
        print(f"ERROR: ToolInstallation with ID {tool_installation_id} not found for uninstall task.")
        return

    _log(tool_installation, 'info', 'Uninstallation process initiated.')
    tool_installation.status = ToolInstallation.Status.UNINSTALLING
    tool_installation.save()

    system = tool_installation.system
    if not system:
        _log(tool_installation, 'error', 'Cannot uninstall: System not found for installation.')
        tool_installation.status = ToolInstallation.Status.ERROR
        tool_installation.save()
        return

    # 1. Stop all running instances associated with this installation
    running_instances = tool_installation.instances.filter(status__in=[
        'running', 'starting'
    ])

    if running_instances.exists():
        _log(tool_installation, 'info', f"Found {running_instances.count()} running instance(s) to stop.")
        for instance in running_instances:
            _log(tool_installation, 'info', f"Stopping instance {instance.pk} (PID: {instance.process_id}).")
            # Directly use the primitive to ensure it's stopped
            stop_result = manage_tool_process(system=system, action='stop', process_id=str(instance.pk))
            if stop_result.get('status') == 'success':
                _log(tool_installation, 'info', f"Instance {instance.pk} stopped successfully.")
                instance.status = 'stopped'
                instance.save(send_to_client=False) # Avoid multiple websocket sends
            else:
                _log(tool_installation, 'warning', f"Failed to stop instance {instance.pk}: {stop_result.get('message')}")
                # We'll proceed with uninstallation anyway, but log the failure.

    # 2. Remove the local installation directory
    local_path = tool_installation.local_path
    if local_path:
        _log(tool_installation, 'info', f"Removing installation directory: {local_path}")
        rm_result = rm(system=system, path=local_path, recursive=True)
        if rm_result.get('status') == 'success':
            _log(tool_installation, 'info', "Installation directory removed successfully.")
        else:
            _log(tool_installation, 'error', f"Failed to remove directory: {rm_result.get('message')}")
            # Log the error but proceed to delete the DB record.
            tool_installation.status = ToolInstallation.Status.ERROR
            tool_installation.save()

    # 3. Delete the ToolInstallation record from the database
    # The model's delete method will broadcast the deletion to the client.
    _log(tool_installation, 'info', "Deleting ToolInstallation record.")
    tool_installation.delete()
    print(f"ToolInstallation {tool_installation_id} uninstalled and deleted successfully.")
