from celery import shared_task
from django.db import transaction

from executor.primitives import (
    rm,
    manage_tool_process
)
import json
from pathlib import Path

from tools.definitions.models.tool_installation import ToolInstallation
from tools.definitions.models.tool_installation_log import ToolInstallationLog
from tools.instances.models.tool_instance import ToolInstance

def _log(installation: ToolInstallation, level: str, message: str, tool_instance: ToolInstance = None):
    """Helper function to create a log entry for a tool installation, with optional instance context."""
    instance_info = f" (Instance PK: {tool_instance.pk})" if tool_instance else ""
    ToolInstallationLog.objects.create(
        tool_installation=installation,
        level=level,
        message=f"{message}{instance_info}"
    )

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

    _log(tool_installation, 'info', 'Tool stop process initiated.', tool_instance)
    tool_instance.status = ToolInstance.Status.STOPPING
    tool_instance.save()

    system = tool_installation.system
    if not system:
        error_message = 'Cannot stop: System not found for installation.'
        _log(tool_installation, 'error', error_message, tool_instance)
        tool_instance.status = ToolInstance.Status.ERROR
        tool_instance.last_error = error_message
        tool_instance.save()
        return

    _log(tool_installation, 'info', f"Requesting client and process stop for ToolInstance ID: {tool_instance.pk}.", tool_instance)
    stop_result = manage_tool_process(system=system, action='stop', process_id=str(tool_instance.pk))

    if stop_result.get('status') == 'success':
        _log(tool_installation, 'info', f"Executor confirmed stop for ToolInstance {tool_instance.pk}.", tool_instance)
        tool_instance.status = ToolInstance.Status.STOPPED
        # Clear runtime-specific fields
        tool_instance.process_id = None
        tool_instance.endpoint_url = None
    else:
        error_message = f"Executor stop command failed or was not necessary: {stop_result.get('message', 'Unknown error')}"
        _log(tool_installation, 'warning', error_message, tool_instance)
        # If the stop command failed, the instance might still be running or in an unknown state
        tool_instance.status = ToolInstance.Status.ERROR
        tool_instance.last_error = error_message

    tool_instance.save()
    _log(tool_installation, 'info', f"ToolInstance record updated. Tool is now {tool_instance.status}.", tool_instance)

    # Note: Uninstallation logic (rm local_path, set ToolInstallation status to NOT_INSTALLED)
    # is now handled by a separate task, as stopping a tool instance is distinct from uninstalling it.
