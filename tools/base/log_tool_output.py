
from tools.definitions.models.tool_installation_log import ToolInstallationLog

def add_toolinstallation_log(installation, level: str, message: str, tool_instance=None):
    """Helper function to create a log entry for a tool installation, with optional instance context."""
    instance_info = f" (Instance PK: {tool_instance.pk})" if tool_instance else ""
    ToolInstallationLog.objects.create(
        tool_installation=installation,
        level=level,
        message=f"{message}{instance_info}"
    )

