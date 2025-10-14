from celery import shared_task
from tools.base.log_tool_output import add_toolinstallation_log
from tools.primitives import stop_tool_process
from tools.definitions.models.tool_installation import ToolInstallation
from tools.definitions.models.tool_installation_log import ToolInstallationLog
from tools.instances.models.tool_instance import ToolInstance

@shared_task
def stop_tool(tool_instance_id):
    try:
        tool_instance = ToolInstance.objects.get(pk=tool_instance_id)
        tool_installation = tool_instance.tool_installation
    except ToolInstance.DoesNotExist:
        print(f"ERROR: ToolInstance with ID {tool_instance_id} not found during stop_tool task.")
        return
    except ToolInstallation.DoesNotExist:
        print(f"ERROR: ToolInstallation for ToolInstance ID {tool_instance_id} not found.")
        return

    add_toolinstallation_log(tool_installation, 'info', 'Tool stop process initiated.', tool_instance)
    tool_instance.status = ToolInstance.ToolInstanceStatusChoices.STOPPING
    tool_instance.save()

    system = tool_installation.system
    if not system:
        error_message = 'Cannot stop: System not found for installation.'
        add_toolinstallation_log(tool_installation, 'error', error_message, tool_instance)
        tool_instance.status = ToolInstance.ToolInstanceStatusChoices.ERROR
        tool_instance.last_error = error_message
        tool_instance.save()
        return

    add_toolinstallation_log(tool_installation, 'info', f"Requesting client and process stop for ToolInstance ID: {tool_instance.pk}.", tool_instance)
    stop_result = stop_tool_process(system=system,process_id=tool_instance.pk)

    if stop_result.get('status') == 'success':
        add_toolinstallation_log(tool_installation, 'info', f"Executor confirmed stop for ToolInstance {tool_instance.pk}.", tool_instance)
        tool_instance.status = ToolInstance.ToolInstanceStatusChoices.STOPPED
        # Clear runtime-specific fields
        tool_instance.process_id = None
        tool_instance.endpoint_url = None
    else:
        error_message = f"Executor stop command failed or was not necessary: {stop_result.get('message', 'Unknown error')}"
        add_toolinstallation_log(tool_installation, 'warning', error_message, tool_instance)
        # If the stop command failed, the instance might still be running or in an unknown state
        tool_instance.status = ToolInstance.ToolInstanceStatusChoices.ERROR
        tool_instance.last_error = error_message

    tool_instance.save()
    add_toolinstallation_log(tool_installation, 'info', f"ToolInstance record updated. Tool is now {tool_instance.status}.", tool_instance)

    # Note: Uninstallation logic (rm local_path, set ToolInstallation status to NOT_INSTALLED)
    # is now handled by a separate task, as stopping a tool instance is distinct from uninstalling it.
