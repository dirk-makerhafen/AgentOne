from celery import shared_task

from executor.primitives import (
    mkdir,
    read_file,
    rm,
    run_shell_script,
    run_python_code,
    stat_path,
    manage_tool_process
)
import json
from pathlib import Path

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
def stop_tool(tool_installation_id, uninstall: bool = False):
    tool_installation = ToolInstallation.objects.get(pk=tool_installation_id)
    _log(tool_installation, 'info', f"Stop process initiated. Uninstall: {uninstall}")
    system = tool_installation.system
    if not system: _log(tool_installation, 'error', 'Cannot stop: System not found.'); return

    _log(tool_installation, 'info', f"Requesting client and process stop for ID: {tool_installation.pk}.")
    stop_result = manage_tool_process(system=system, action='stop', process_id=str(tool_installation.pk))
    if stop_result.get('status') == 'success':
        _log(tool_installation, 'info', f"Executor confirmed stop for client {tool_installation.pk}.")
    else:
        _log(tool_installation, 'warning', f"Executor stop command failed or was not necessary: {stop_result.get('message')}")

    tool_installation.process_id, tool_installation.assigned_port = None, None
    if tool_installation.mcp_server:
        tool_installation.mcp_server.enabled = False
        tool_installation.mcp_server.status = 'disconnected'
        tool_installation.mcp_server.save()

    if uninstall:
        if tool_installation.local_path:
            _log(tool_installation, 'info', f"Removing directory '{tool_installation.local_path}'.")
            rm(system=system, path=tool_installation.local_path, recursive=True)
        tool_installation.status = ToolInstallation.Status.NOT_INSTALLED
        tool_installation.local_path = None
        _log(tool_installation, 'info', 'Uninstallation complete.')
    else:
        tool_installation.status = ToolInstallation.Status.STOPPED
        _log(tool_installation, 'info', 'Tool is now stopped.')
    tool_installation.save()
