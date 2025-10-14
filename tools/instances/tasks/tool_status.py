from celery import shared_task
from tools.base.log_tool_output import add_toolinstallation_log
from tools.primitives import call_tool_session
from tools.definitions.models.tool_installation import ToolInstallation

@shared_task
def get_tool_status(tool_installation_id):
    tool_installation = ToolInstallation.objects.get(pk=tool_installation_id)
    if tool_installation.status not in [ToolInstallation.ToolInstallationStatusChoices.INSTALLING, ToolInstallation.ToolInstallationStatusChoices.UNINSTALLING]:
        return

    system = tool_installation.system
    if not system: return

    result = call_tool_session(system=system, function_name='list_tools', process_id=tool_installation.pk)
    if result.get('status') != 'success' and tool_installation.status == ToolInstallation.ToolInstallationStatusChoices.INSTALLED:
        add_toolinstallation_log(tool_installation, 'warning', f"Health check failed for running tool: {result.get('message')}")
        tool_installation.status = ToolInstallation.ToolInstallationStatusChoices.ERROR
        tool_installation.save()
