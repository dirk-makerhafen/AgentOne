from celery import shared_task
from tools.primitives import manage_tool_process
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
def get_tool_status(tool_installation_id):
    # This function is less critical now but can be a simple check
    tool_installation = ToolInstallation.objects.get(pk=tool_installation_id)
    if tool_installation.status not in [ToolInstallation.ToolInstallationStatusChoices.INSTALLING, ToolInstallation.ToolInstallationStatusChoices.UNINSTALLING]:
        return

    # A simple way to check is to try listing tools. A failure implies it's not running.
    # Note: This is an active check, not a passive PID check.
    system = tool_installation.system
    if not system: return

    result = manage_tool_process(system=system, action='list_tools', process_id=str(tool_installation.pk))
    if result.get('status') != 'success' and tool_installation.status == ToolInstallation.ToolInstallationStatusChoices.INSTALLED:
        _log(tool_installation, 'warning', f"Health check failed for running tool: {result.get('message')}")
        tool_installation.status = ToolInstallation.ToolInstallationStatusChoices.ERROR
        tool_installation.save()
