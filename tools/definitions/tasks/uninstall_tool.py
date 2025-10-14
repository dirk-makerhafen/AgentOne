from celery import shared_task
from tools.base.log_tool_output import add_toolinstallation_log
from tools.instances.models.tool_instance import ToolInstance
from tools.primitives import rm, stop_tool_process
from tools.definitions.models.tool_installation import ToolInstallation

@shared_task
def uninstall_tool(tool_installation_id, delete_record=True):
    """
    Orchestrates the uninstallation of a tool. This involves stopping all running instances
    and deleting the tool's files. The ToolInstallation record is also deleted by default,
    but this can be prevented by setting delete_record=False, which is useful for update workflows.
    """
    try:
        tool_installation = ToolInstallation.objects.get(pk=tool_installation_id)
    except ToolInstallation.DoesNotExist:
        print(f"ERROR: ToolInstallation with ID {tool_installation_id} not found for uninstall task.")
        return

    add_toolinstallation_log(tool_installation, 'info', 'Uninstallation process initiated.')
    tool_installation.status = ToolInstallation.ToolInstallationStatusChoices.UNINSTALLING
    tool_installation.save()

    system = tool_installation.system
    if not system:
        add_toolinstallation_log(tool_installation, 'error', 'Cannot uninstall: System not found for installation.')
        tool_installation.status = ToolInstallation.ToolInstallationStatusChoices.ERROR
        tool_installation.save()
        return

    # 1. Stop all running instances associated with this installation
    running_instances = tool_installation.instances.filter(status__in=[ToolInstance.ToolInstanceStatusChoices.RUNNING, ToolInstance.ToolInstanceStatusChoices.STARTING])
    if running_instances.exists():
        add_toolinstallation_log(tool_installation, 'info', f"Found {running_instances.count()} running instance(s) to stop.")
        for toolinstance in running_instances:
            add_toolinstallation_log(tool_installation, 'info', f"Stopping instance {toolinstance.pk} (PID: {toolinstance.process_id}).")
            stop_result = stop_tool_process(system=system, process_id=toolinstance.pk)
            if stop_result.get('status') == 'success':
                add_toolinstallation_log(tool_installation, 'info', f"Instance {toolinstance.pk} stopped successfully.")
                toolinstance.status = ToolInstance.ToolInstanceStatusChoices.STOPPED
                toolinstance.save(send_to_client=False)
            else:
                add_toolinstallation_log(tool_installation, 'warning', f"Failed to stop instance {toolinstance.pk}: {stop_result.get('message')}")

    # 2. Remove the local installation directory
    local_path = tool_installation.local_path
    if local_path:
        add_toolinstallation_log(tool_installation, 'info', f"Removing installation directory: {local_path}")
        rm_result = rm(system=system, path=local_path, recursive=True)
        if rm_result.get('status') != 'success':
            add_toolinstallation_log(tool_installation, 'error', f"Failed to remove directory: {rm_result.get('message')}")
            tool_installation.status = ToolInstance.ToolInstanceStatusChoices.ERROR
            tool_installation.save()
            # If we can't remove the directory, we should not proceed with deleting the record.
            return

    if delete_record:
        add_toolinstallation_log(tool_installation, 'info', "Deleting ToolInstallation record.")
        tool_installation.delete()
        print(f"ToolInstallation {tool_installation_id} uninstalled and deleted successfully.")
    else:
        # If we're not deleting the record, the uninstallation is a precursor to an installation.
        # The status will be updated by the subsequent install_tool task.
        add_toolinstallation_log(tool_installation, 'info', "Cleanup complete. Record preserved for update.")
        # We must return the PK for the next task in the chain.
        return tool_installation_id
