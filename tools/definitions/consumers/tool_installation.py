import json
from systems.models.system import System
from tools.definitions.models.tool_definition import ToolDefinition
from tools.definitions.models.tool_installation import ToolInstallation
from tools.definitions.tasks.install_tool import install_tool
from tools.definitions.tasks.uninstall_tool import uninstall_tool
from tools.instances.tasks.start_tool import start_tool
from ui.router import register_handler
import traceback

@register_handler('toolinstallation_create')
def handle_toolinstallation_create(consumer, tool_definition_pk, system_pk, max_parallel_instances=1):
    try:
        tool_definition = ToolDefinition.objects.get(pk=tool_definition_pk)
        system = System.objects.get(pk=system_pk)

        # For shared tools, ensure only one installation exists.
        if ToolInstallation.objects.filter(tool_definition=tool_definition, system=system, agent_instance__isnull=True).exists():
            consumer.send(text_data=json.dumps({'object': 'error', 'message': f'Tool "{tool_definition.name}" is already installed on system "{system.name}".'}))
            return

        new_installation = ToolInstallation(
            tool_definition=tool_definition,
            system=system,
            status=ToolInstallation.ToolInstallationStatusChoices.INSTALLING,
            max_parallel_instances=max_parallel_instances
        )
        new_installation.save()
        install_tool.delay(new_installation.pk)
    except (ToolDefinition.DoesNotExist, System.DoesNotExist) as e:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': str(e)}))
    except Exception as e:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'Failed to create tool installation: {e} {traceback.format_exc()}'}))

@register_handler('toolinstallation_get_logs')
def handle_toolinstallation_get_logs(consumer, installation_id):
    if not installation_id:
        return
    try:
        installation = ToolInstallation.objects.get(pk=installation_id)
        logs = installation.logs.all().order_by('timestamp')
        log_list = [log.as_client_dict() for log in logs]

        consumer.send(text_data=json.dumps({
            'object': 'ToolInstallationLogList',
            'installation_id': installation_id,
            'logs': log_list
        }))
    except (ToolInstallation.DoesNotExist, Exception):
        pass

@register_handler('toolinstallation_delete')
def handle_toolinstallation_delete(consumer, installation_pk):
    try:
        # The uninstallation task will handle stopping running instances,
        # removing files, and deleting the model instance.
        uninstall_tool.delay(installation_pk)
    except Exception as e:
        # Log error if the task couldn't be queued.
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'Failed to queue tool uninstallation: {e} {traceback.format_exc()}'}))

@register_handler('toolinstallation_list')
def handle_toolinstallation_list(consumer, system_pk=None):
    try:
        if system_pk:
            installations = ToolInstallation.objects.filter(system__pk=system_pk).order_by('tool_definition__name')
        else:
            installations = ToolInstallation.objects.all().order_by('tool_definition__name')

        installations_data = [inst.as_client_dict() for inst in installations]
        consumer.send(text_data=json.dumps({'object': 'ToolInstallationList', 'tool_installations': installations_data}))
    except Exception as e:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'Failed to retrieve tool installations: {e} {traceback.format_exc()}'}))

@register_handler('toolinstallation_start')
def handle_toolinstallation_start(consumer, installation_pk):
    try:
        start_tool.delay(installation_pk)
    except Exception as e:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'Failed to start tool installation {installation_pk}: {e} {traceback.format_exc()}'}))
