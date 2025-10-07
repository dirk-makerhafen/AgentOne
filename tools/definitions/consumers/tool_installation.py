import json
from systems.models.system import System
from tools.definitions.models.tool_definition import ToolDefinition
from tools.definitions.models.tool_installation import ToolInstallation
from tools.definitions.tasks.install_tool import install_tool
from tools.instances.tasks.start_tool import start_tool
from tools.instances.tasks.stop_tool import stop_tool
from ui.router import register_handler

@register_handler('toolinstallation_create')
def handle_toolinstallation_create(consumer, user_pk, payload):
    try:
        tool_definition_pk = payload.get('tool_definition_pk')
        system_pk = payload.get('system_pk')
        
        tool_definition = ToolDefinition.objects.get(pk=tool_definition_pk)
        system = System.objects.get(pk=system_pk)

        if ToolInstallation.objects.filter(tool_definition=tool_definition, system=system).exists():
            consumer.send(text_data=json.dumps({'object': 'error', 'message': f'Tool "{tool_definition.name}" is already installed on system "{system.name}".'}))
            return

        new_installation = ToolInstallation(
            tool_definition=tool_definition,
            system=system,
            status=ToolInstallation.Status.INSTALLING
        )
        new_installation.save()
        install_tool.delay(new_installation.pk, user_pk=user_pk)
    except (ToolDefinition.DoesNotExist, System.DoesNotExist) as e:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': str(e)}))
    except Exception as e:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'Failed to create tool installation: {e}'}))

@register_handler('toolinstallation_get_logs')
def handle_toolinstallation_get_logs(consumer, user_pk, payload):
    installation_id = payload.get('installation_id')
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
def handle_toolinstallation_delete(consumer, user_pk, payload):
    try:
        installation_pk = payload.get('installation_pk')
        installation = ToolInstallation.objects.get(pk=installation_pk)
        stop_tool.delay(installation.pk, uninstall=True, user_pk=user_pk)
    except ToolInstallation.DoesNotExist:
        pass # Fail silently
    except Exception as e:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'Failed to delete tool installation: {e}'}))

@register_handler('toolinstallation_list')
def handle_toolinstallation_list(consumer, user_pk, payload):
    try:
        system_pk = payload.get('system_pk')
        if system_pk:
            installations = ToolInstallation.objects.filter(system__pk=system_pk).order_by('tool_definition__name')
        else:
            installations = ToolInstallation.objects.all().order_by('tool_definition__name')
        
        installations_data = [inst.as_client_dict() for inst in installations]
        consumer.send(text_data=json.dumps({'object': 'ToolInstallationList', 'tool_installations': installations_data}))
    except Exception as e:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'Failed to retrieve tool installations: {e}'}))

@register_handler('toolinstallation_start')
def handle_toolinstallation_start(consumer, user_pk, payload):
    try:
        installation_pk = payload.get('installation_pk')
        installation = ToolInstallation.objects.get(pk=installation_pk)
        start_tool.delay(installation.pk, user_pk=user_pk)
    except ToolInstallation.DoesNotExist:
        pass # Fail silently
    except Exception as e:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'Failed to start tool installation {installation_pk}: {e}'}))

@register_handler('toolinstallation_stop')
def handle_toolinstallation_stop(consumer, user_pk, payload):
    try:
        installation_pk = payload.get('installation_pk')
        installation = ToolInstallation.objects.get(pk=installation_pk)
        stop_tool.delay(installation.pk, user_pk=user_pk)
    except ToolInstallation.DoesNotExist:
        pass # Fail silently
    except Exception as e:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'Failed to stop tool installation {installation_pk}: {e}'}))


