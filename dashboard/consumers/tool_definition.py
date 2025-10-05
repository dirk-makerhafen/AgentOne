import json
from tools_common.models import ToolDefinition

def handle_create_tool_definition(consumer, payload):
    name = payload.get('name')
    display_name = payload.get('display_name', name)
    description = payload.get('description', '')
    is_builtin = payload.get('is_builtin', False)
    transport_type = payload.get('transport_type', 'tcp')
    repository_url = payload.get('repository_url')

    # For new tool definitions, name and display_name can be pre-filled from the UI
    # or will be filled by the async task if a repository_url is provided.
    # If no repository_url, and name/display_name are not provided, we should error.
    if not repository_url and (not name or not display_name):
        consumer.send(text_data=json.dumps({'object': 'error', 'message': 'ToolDefinition name and display_name are required for manual entry tools.'}))
        return

    try:
        tool_def = ToolDefinition.objects.create(
            name=name, # This might be temporary if repository_url is set and task will override
            display_name=display_name, # This might be temporary if repository_url is set and task will override
            description=description,
            is_builtin=is_builtin,
            transport_type=transport_type,
            repository_url=repository_url,
            # Manifest will be filled by the async task
        )
        # The tool_def.save() method will automatically call send_object_to_clients
        # and trigger the async manifest fetch if repository_url is present.
    except Exception as e:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'Failed to create tool definition: {e}'}))

def handle_update_tool_definition(consumer, payload):
    tool_def_id = payload.get('tool_definition_id')
    updates = payload.get('updates', {})

    if not tool_def_id:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': 'ToolDefinition ID is required for update.'}))
        return

    try:
        tool_def = ToolDefinition.objects.get(pk=tool_def_id)

        # Store old URL to check for changes
        old_repository_url = tool_def.repository_url

        # Apply updates
        tool_def.display_name = updates.get('display_name', tool_def.display_name)
        tool_def.name = updates.get('name', tool_def.name) # Allow manual name update
        tool_def.description = updates.get('description', tool_def.description)
        tool_def.transport_type = updates.get('transport_type', tool_def.transport_type)
        tool_def.repository_url = updates.get('repository_url', tool_def.repository_url)
        tool_def.available_on_all_systems = updates.get('available_on_all_systems', tool_def.available_on_all_systems)

        # Handle manual manifest updates if no repository_url is present and manifest data is sent
        if not tool_def.repository_url and 'manifest' in updates:
            # Reconstruct the manifest from manual inputs
            manual_manifest = {
                'server': {
                    'command': updates['manifest'].get('server', {}).get('command'),
                    'args': updates['manifest'].get('server', {}).get('args', []),
                    'platforms': updates['manifest'].get('server', {}).get('platforms', [])
                }
            }
            tool_def.manifest = manual_manifest
        elif tool_def.repository_url and 'repository_url' in updates and tool_def.repository_url != old_repository_url:
            # If repo URL is present and changed, clear manifest temporarily; it will be refetched by task
            tool_def.manifest = None


        tool_def.save() # The save method will trigger the async task if repository_url changed
        # send_object_to_clients(tool_def) # Called by the model's save method

    except ToolDefinition.DoesNotExist:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'ToolDefinition with ID {tool_def_id} not found.'}))
    except Exception as e:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'Failed to update tool definition: {e}'}))

def handle_delete_tool_definition(consumer, payload):
    tool_def_id = payload.get('tool_definition_id')

    if not tool_def_id:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': 'ToolDefinition ID is required for deletion.'}))
        return

    try:
        tool_def = ToolDefinition.objects.get(pk=tool_def_id)
        # Check for existing installations before deleting
        if tool_def.installations.exists():
            consumer.send(text_data=json.dumps({'object': 'error', 'message': f'ToolDefinition {tool_def.name} cannot be deleted because it has active installations. Please uninstall all instances first.'}))
            return

        tool_def.delete()
        consumer.send(text_data=json.dumps({
            'object': 'ToolDefinition',
            'id': tool_def_id,
            'action': 'deleted'
        }))
    except ToolDefinition.DoesNotExist:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'ToolDefinition with ID {tool_def_id} not found.'}))
    except Exception as e:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'Failed to delete tool definition: {e}'}))

def handle_tool_definition_list(consumer, payload):
    try:
        tool_definitions = ToolDefinition.objects.all().order_by('name')
        tool_defs_data = [tool_def.as_client_dict() for tool_def in tool_definitions]
        consumer.send(text_data=json.dumps({
            'object': 'ToolDefinitionList',
            'tool_definitions': tool_defs_data
        }))
    except Exception as e:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'Failed to retrieve tool definitions: {e}'}))

# Removed handle_request_manifest_details as it is now handled asynchronously
# by the model's save method and a Celery task.

def toggle_tool_definition_active(consumer, tool_definition_id):
    """
    Toggles the is_active status of a ToolDefinition.
    """
    try:
        tool_definition = ToolDefinition.objects.get(pk=tool_definition_id)
        tool_definition.is_active = not tool_definition.is_active
        tool_definition.save()
    except ToolDefinition.DoesNotExist:
        pass
    except Exception as e:
        pass

def handle_refresh_tool_definition_manifest(consumer, payload):
    tool_def_id = payload.get('tool_definition_id')
    if not tool_def_id:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': 'ToolDefinition ID is required for refresh.'}))
        return

    try:
        tool_def = ToolDefinition.objects.get(pk=tool_def_id)
        if not tool_def.repository_url:
            consumer.send(text_data=json.dumps({'object': 'error', 'message': 'Cannot refresh manifest for a tool without a repository URL.'}))
            return

        # Set status to updating and trigger the background task
        tool_def.status = ToolDefinition.Status.UPDATING
        tool_def.save() # This will broadcast the 'updating' status to the client

        # Trigger the celery task to perform the refresh
        from tools_common.tasks import fetch_and_update_tool_definition_manifest
        fetch_and_update_tool_definition_manifest.delay(tool_def.pk)

    except ToolDefinition.DoesNotExist:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'ToolDefinition with ID {tool_def_id} not found.'}))
    except Exception as e:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'Failed to trigger tool definition refresh: {e}'}))


from systems.models import System

def handle_assign_system_to_tool(consumer, payload):
    tool_def_id = payload.get('tool_definition_id')
    system_id = payload.get('system_id')

    if not (tool_def_id and system_id):
        consumer.send(text_data=json.dumps({'object': 'error', 'message': 'ToolDefinition ID and System ID are required for assignment.'}))
        return

    try:
        tool_def = ToolDefinition.objects.get(pk=tool_def_id)
        system = System.objects.get(pk=system_id)
        
        tool_def.available_on_systems.add(system)
        tool_def.save() # This will send the updated tool_def to clients
    except ToolDefinition.DoesNotExist:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'ToolDefinition with ID {tool_def_id} not found.'}))
    except System.DoesNotExist:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'System with ID {system_id} not found.'}))
    except Exception as e:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'Failed to assign system to tool: {e}'}))

def handle_unassign_system_from_tool(consumer, payload):
    tool_def_id = payload.get('tool_definition_id')
    system_id = payload.get('system_id')

    if not (tool_def_id and system_id):
        consumer.send(text_data=json.dumps({'object': 'error', 'message': 'ToolDefinition ID and System ID are required for unassignment.'}))
        return

    try:
        tool_def = ToolDefinition.objects.get(pk=tool_def_id)
        system = System.objects.get(pk=system_id)
        
        tool_def.available_on_systems.remove(system)
        tool_def.save() # This will send the updated tool_def to clients
    except ToolDefinition.DoesNotExist:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'ToolDefinition with ID {tool_def_id} not found.'}))
    except System.DoesNotExist:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'System with ID {system_id} not found.'}))
    except Exception as e:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'Failed to unassign system from tool: {e}'}))
