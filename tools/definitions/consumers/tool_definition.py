import json
from systems.models.system import System
from tools.definitions.models.tool_definition import ToolDefinition
from ui.router import register_handler

@register_handler('tooldefinition_create')
def handle_tooldefinition_create(consumer, name=None, display_name=None, description='', is_builtin=False, transport_type='stdin_stdout', repository_url=None, execution_mode='shared', manifest=None): # Added manifest
    if display_name is None:
        display_name = name

    if not repository_url and (not name or not display_name):
        consumer.send(text_data=json.dumps({'object': 'error', 'message': 'ToolDefinition name and display_name are required for manual entry.'}))
        return

    try:
        ToolDefinition.objects.create(
            name=name,
            display_name=display_name,
            description=description,
            is_builtin=is_builtin,
            transport_type=transport_type,
            repository_url=repository_url,
            execution_mode=execution_mode,
            manifest=manifest # Added this line
        )
    except Exception as e:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'Failed to create tool definition: {e}'}))

@register_handler('tooldefinition_update')
def handle_tooldefinition_update(consumer, tool_definition_id, updates=None):
    if updates is None:
        updates = {}

    if not tool_definition_id:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': 'ToolDefinition ID is required for update.'}))
        return

    try:
        tool_def = ToolDefinition.objects.get(pk=tool_definition_id)
        tool_def.display_name = updates.get('display_name', tool_def.display_name)
        tool_def.name = updates.get('name', tool_def.name)
        tool_def.description = updates.get('description', tool_def.description)
        tool_def.transport_type = updates.get('transport_type', tool_def.transport_type)
        tool_def.repository_url = updates.get('repository_url', tool_def.repository_url)
        tool_def.available_on_all_systems = updates.get('available_on_all_systems', tool_def.available_on_all_systems)
        tool_def.execution_mode = updates.get('execution_mode', tool_def.execution_mode)

        if not tool_def.repository_url and 'manifest' in updates:
            manual_manifest = {
                'server': {
                    'command': updates['manifest'].get('server', {}).get('command'),
                    'args': updates['manifest'].get('server', {}).get('args', []),
                    'platforms': updates['manifest'].get('server', {}).get('platforms', [])
                }
            }
            tool_def.manifest = manual_manifest

        tool_def.save()
    except ToolDefinition.DoesNotExist:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'ToolDefinition with ID {tool_definition_id} not found.'}))
    except Exception as e:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'Failed to update tool definition: {e}'}))

@register_handler('tooldefinition_delete')
def handle_tooldefinition_delete(consumer, tool_definition_id):
    if not tool_definition_id:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': 'ToolDefinition ID is required for deletion.'}))
        return

    try:
        tool_def = ToolDefinition.objects.get(pk=tool_definition_id)
        if tool_def.installations.exists():
            consumer.send(text_data=json.dumps({'object': 'error', 'message': f'ToolDefinition {tool_def.name} has active installations and cannot be deleted.'}))
            return

        tool_def.delete() # The model's delete method will handle broadcasting

    except ToolDefinition.DoesNotExist:
        # If it doesn't exist, it's already gone. We don't need to do anything here,
        # as the UI update will be handled by the model's delete signal (or lack thereof if not found).
        pass
    except Exception as e:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'Failed to delete tool definition: {e}'}))

@register_handler('tooldefinition_list')
def handle_tooldefinition_list(consumer, **kwargs):
    try:
        tool_definitions = ToolDefinition.objects.all().order_by('name')
        tool_defs_data = [tool_def.as_client_dict() for tool_def in tool_definitions]
        consumer.send(text_data=json.dumps({'object': 'ToolDefinitionList', 'tool_definitions': tool_defs_data}))
    except Exception as e:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'Failed to retrieve tool definitions: {e}'}))

@register_handler('tooldefinition_system_assign')
def handle_tooldefinition_system_assign(consumer, tool_definition_id, system_id):
    try:
        tool_def = ToolDefinition.objects.get(pk=tool_definition_id)
        system = System.objects.get(pk=system_id)
        tool_def.available_on_systems.add(system)
    except (ToolDefinition.DoesNotExist, System.DoesNotExist, Exception) as e:
        pass # Fail silently

@register_handler('tooldefinition_system_unassign')
def handle_tooldefinition_system_unassign(consumer, tool_definition_id, system_id):
    try:
        tool_def = ToolDefinition.objects.get(pk=tool_definition_id)
        system = System.objects.get(pk=system_id)
        tool_def.available_on_systems.remove(system)
    except (ToolDefinition.DoesNotExist, System.DoesNotExist, Exception) as e:
        pass # Fail silently

@register_handler('tooldefinition_manifest_refresh')
def handle_tooldefinition_manifest_refresh(consumer, tool_definition_id):
    if not tool_definition_id:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': 'ToolDefinition ID is required for refresh.'}))
        return

    try:
        tool_def = ToolDefinition.objects.get(pk=tool_definition_id)
        if not tool_def.repository_url:
            consumer.send(text_data=json.dumps({'object': 'error', 'message': 'Cannot refresh manifest for a tool without a repository URL.'}))
            return

        tool_def.status = ToolDefinition.Status.UPDATING
        tool_def.save() 

        from tools.definitions.tasks.refresh_tool_definition import fetch_and_update_tool_definition_manifest
        fetch_and_update_tool_definition_manifest.delay(tool_def.pk)

    except ToolDefinition.DoesNotExist:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'ToolDefinition with ID {tool_definition_id} not found.'}))
    except Exception as e:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'Failed to trigger tool definition refresh: {e}'}))
