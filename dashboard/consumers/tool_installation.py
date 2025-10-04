import json
from django.contrib.auth.models import User
from systems.tool_lifecycle_manager import install_tool, start_tool, stop_tool
from tools_common.models  import ToolInstallation, ToolDefinition
from systems.models import System
from dashboard.tasks import send_object_to_clients

def handle_tool_installation_list(consumer, payload):
    try:
        system_pk = payload.get('system_pk')
        if system_pk:
            installations = ToolInstallation.objects.filter(system__pk=system_pk).order_by('tool_definition__name')
        else:
            installations = ToolInstallation.objects.all().order_by('tool_definition__name')
        
        installations_data = [inst.as_client_dict() for inst in installations]
        consumer.send(text_data=json.dumps({
            'object': 'ToolInstallationList',
            'tool_installations': installations_data
        }))
    except Exception as e:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'Failed to retrieve tool installations: {e}'}))

def handle_tool_installation_create(consumer, user_pk, payload):
    try:
        user = User.objects.get(pk=user_pk)
    except User.DoesNotExist:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'User with pk {user_pk} not found.'}))
        return

    try:
        tool_definition_pk = payload.get('tool_definition_pk')
        system_pk = payload.get('system_pk')
        
        tool_definition = ToolDefinition.objects.get(pk=tool_definition_pk)
        system = System.objects.get(pk=system_pk)

        # Check for existing installation to prevent duplicates
        if ToolInstallation.objects.filter(tool_definition=tool_definition, system=system).exists():
            consumer.send(text_data=json.dumps({'object': 'error', 'message': f'Tool "{tool_definition.name}" is already installed on system "{system.name}".'}))
            return

        new_installation = ToolInstallation.objects.create(
            tool_definition=tool_definition,
            system=system,
            status=ToolInstallation.Status.INSTALLING # Set status to INSTALLING immediately
        )
        send_object_to_clients(new_installation) # Send "installing" status to frontend

        # Trigger the installation process via the tool lifecycle manager
        install_tool.delay(new_installation.pk)
    except ToolDefinition.DoesNotExist:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'ToolDefinition with pk {tool_definition_pk} not found.'}))
    except System.DoesNotExist:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'System with pk {system_pk} not found.'}))
    except Exception as e:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'Failed to create tool installation: {e}'}))


def handle_tool_installation_start(consumer, user_pk, payload):
    try:
        user = User.objects.get(pk=user_pk)
    except User.DoesNotExist:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'User with pk {user_pk} not found.'}))
        return

    try:
        installation_pk = payload.get('installation_pk')
        installation = ToolInstallation.objects.get(pk=installation_pk)
        start_tool.delay(installation.pk)
        consumer.send(text_data=json.dumps({'object': 'info', 'message': f'Starting tool {installation.tool_definition.display_name} on {installation.system.name}.'}))
    except ToolInstallation.DoesNotExist:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'ToolInstallation with pk {installation_pk} not found.'}))
    except Exception as e:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'Failed to start tool installation {installation_pk}: {e}'}))

def handle_tool_installation_stop(consumer, user_pk, payload):
    try:
        user = User.objects.get(pk=user_pk)
    except User.DoesNotExist:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'User with pk {user_pk} not found.'}))
        return

    try:
        installation_pk = payload.get('installation_pk')
        installation = ToolInstallation.objects.get(pk=installation_pk)
        stop_tool.delay(installation.pk)
        consumer.send(text_data=json.dumps({'object': 'info', 'message': f'Stopping tool {installation.tool_definition.display_name} on {installation.system.name}.'}))
    except ToolInstallation.DoesNotExist:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'ToolInstallation with pk {installation_pk} not found.'}))
    except Exception as e:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'Failed to stop tool installation {installation_pk}: {e}'}))

def handle_tool_installation_update(consumer, user_pk, payload):
    # This function will now be used to handle start/stop actions from the UI
    installation_pk = payload.get('installation_pk')
    action_type = payload.get('action_type') # 'start' or 'stop'

    if not installation_pk or not action_type:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': 'Installation PK and action_type are required for update.'}))
        return

    try:
        installation = ToolInstallation.objects.get(pk=installation_pk)
        
        if action_type == 'start':
            start_tool.delay(installation.pk)
            consumer.send(text_data=json.dumps({'object': 'info', 'message': f'Starting tool {installation.tool_definition.display_name} on {installation.system.name}.'}))
        elif action_type == 'stop':
            stop_tool.delay(installation.pk)
            consumer.send(text_data=json.dumps({'object': 'info', 'message': f'Stopping tool {installation.tool_definition.display_name} on {installation.system.name}.'}))
        else:
            consumer.send(text_data=json.dumps({'object': 'error', 'message': f'Unknown action type: {action_type}.'}))

    except ToolInstallation.DoesNotExist:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'ToolInstallation with pk {installation_pk} not found.'}))
    except Exception as e:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'Failed to perform {action_type} action for tool installation {installation_pk}: {e}'}))

def handle_tool_installation_delete(consumer, user_pk, payload):
    try:
        user = User.objects.get(pk=user_pk)
    except User.DoesNotExist:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'User with pk {user_pk} not found.'}))
        return

    try:
        installation_pk = payload.get('installation_pk')
        installation = ToolInstallation.objects.get(pk=installation_pk)
        
        # Stop the tool and uninstall its files. The lifecycle manager handles mcp_server cleanup.
        stop_tool.delay(installation.pk, uninstall=True)

        # The object record should now be deleted.
        try:
            installation.delete()
        except ToolInstallation.DoesNotExist:
            pass # It was likely deleted by the lifecycle manager, which is the desired outcome.

        consumer.send(text_data=json.dumps({
            'object': 'ToolInstallation',
            'id': installation_pk,
            'deleted': True
        }))
    except ToolInstallation.DoesNotExist:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'ToolInstallation with pk {installation_pk} not found.'}))
    except Exception as e:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'Failed to delete tool installation: {e}'}))


def handle_tool_installation_logs_request(consumer, payload):
    installation_id = payload.get('installation_id')
    if not installation_id:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': 'Installation ID is required to fetch logs.'}))
        return

    try:
        from tools_common.models  import ToolInstallation
        installation = ToolInstallation.objects.get(pk=installation_id)
        # We could add permission checks here if necessary
        logs = installation.logs.all().order_by('timestamp')
        log_list = [log.as_client_dict() for log in logs]
        
        consumer.send(text_data=json.dumps({
            'object': 'ToolInstallationLogList',
            'installation_id': installation_id,
            'logs': log_list
        }))
    except ToolInstallation.DoesNotExist:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'ToolInstallation with ID {installation_id} not found.'}))
    except Exception as e:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'An error occurred while fetching logs: {str(e)}'}))


def handle_request_tool_installation_logs(consumer, payload):
    installation_id = payload.get('installation_id')
    if not installation_id:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': 'Installation ID is required to fetch logs.'}))
        return

    try:
        from tools_common.models  import ToolInstallation
        installation = ToolInstallation.objects.get(pk=installation_id)
        # We could add permission checks here if necessary
        logs = installation.logs.all().order_by('timestamp')
        log_list = [log.as_client_dict() for log in logs]
        
        consumer.send(text_data=json.dumps({
            'object': 'ToolInstallationLogList',
            'logs': log_list
        }))
    except ToolInstallation.DoesNotExist:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'ToolInstallation with ID {installation_id} not found.'}))
    except Exception as e:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'An error occurred while fetching logs: {str(e)}'}))
