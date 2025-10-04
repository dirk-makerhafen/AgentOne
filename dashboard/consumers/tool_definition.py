import json
import tempfile
import shutil
from pathlib import Path
from tools_common.models  import ToolDefinition
from dashboard.tasks import send_object_to_clients
from executor.primitives import run_shell_script, read_file, rm, mkdir # Import primitives

def handle_create_tool_definition(consumer, payload):
    name = payload.get('name')
    display_name = payload.get('display_name', name)
    description = payload.get('description', '')
    is_builtin = payload.get('is_builtin', False)
    transport_type = payload.get('transport_type', 'tcp') # Get the new transport_type
    repository_url = payload.get('repository_url')

    # These fields are for manual manifest input, will be overridden by fetched manifest
    manual_command = payload.get('command')
    manual_args = payload.get('args')
    manual_platforms = payload.get('platforms')

    if not name:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': 'ToolDefinition name is required.'}))
        return

    manifest_data = None
    if repository_url:
        try:
            manifest_data = _fetch_and_parse_manifest(repository_url, name)
            # Override manual manifest fields if a manifest was fetched
            # We don't want the UI to send pre-parsed manifest parts for repository-based tools.
            # The UI should only send repo_url, and the backend fetches the manifest.
        except Exception as e:
            consumer.send(text_data=json.dumps({'object': 'error', 'message': f'Failed to fetch/parse manifest from repository: {e}'}))
            return
    elif manual_command or manual_args or manual_platforms: # Only create manifest data if manually provided and no repo_url
        manifest_data = {}
        if manual_command:
            manifest_data['command'] = manual_command
        if manual_args:
            if manual_args.strip():
                try:
                    manifest_data['args'] = json.loads(manual_args)
                except json.JSONDecodeError:
                    consumer.send(text_data=json.dumps({'object': 'error', 'message': f'Invalid JSON format for args: {manual_args}'}))
                    return
            else:
                manifest_data['args'] = []
        if manual_platforms:
            manifest_data['platforms'] = [p.strip() for p in manual_platforms.split(',')]


    try:
        tool_def = ToolDefinition.objects.create(
            name=name,
            display_name=display_name,
            description=description,
            is_builtin=is_builtin,
            transport_type=transport_type, # Save the new transport_type field
            repository_url=repository_url,
            manifest=manifest_data # Store the constructed or fetched manifest
        )
        send_object_to_clients(tool_def)
    except Exception as e:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'Failed to create tool definition: {e}'}))

def handle_update_tool_definition(consumer, payload):
    tool_def_id = payload.get('id')
    name = payload.get('name')
    display_name = payload.get('display_name')
    description = payload.get('description')
    transport_type = payload.get('transport_type') # Get the new transport_type
    repository_url = payload.get('repository_url')

    # Manual manifest fields (will be ignored if repository_url is set)
    manual_command = payload.get('command')
    manual_args = payload.get('args')
    manual_platforms = payload.get('platforms')

    if not tool_def_id:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': 'ToolDefinition ID is required for update.'}))
        return

    try:
        tool_def = ToolDefinition.objects.get(pk=tool_def_id)

        # Update scalar fields
        tool_def.name = name if name is not None else tool_def.name
        tool_def.display_name = display_name if display_name is not None else tool_def.display_name
        tool_def.description = description if description is not None else tool_def.description
        tool_def.transport_type = transport_type if transport_type is not None else tool_def.transport_type

        # Check if repository_url changed or was added/removed
        old_repository_url = tool_def.repository_url
        tool_def.repository_url = repository_url if repository_url is not None else tool_def.repository_url

        manifest_needs_update = False
        if tool_def.repository_url and tool_def.repository_url != old_repository_url:
            manifest_needs_update = True
        elif not tool_def.repository_url and old_repository_url: # Repo URL removed, clear manifest
            tool_def.manifest = None
        elif not tool_def.repository_url and (manual_command is not None or manual_args is not None or manual_platforms is not None):
            # No repo URL, but manual fields are provided/updated
            manifest_needs_update = True

        if manifest_needs_update:
            if tool_def.repository_url:
                try:
                    tool_def.manifest = _fetch_and_parse_manifest(tool_def.repository_url, tool_def.name)
                except Exception as e:
                    consumer.send(text_data=json.dumps({'object': 'error', 'message': f'Failed to fetch/parse manifest from repository: {e}'}))
                    return
            else: # Apply manual fields if no repo URL
                if not tool_def.manifest:
                    tool_def.manifest = {}
                if manual_command is not None:
                    tool_def.manifest['command'] = manual_command
                if manual_args is not None:
                    if manual_args.strip():
                        try:
                            tool_def.manifest['args'] = json.loads(manual_args)
                        except json.JSONDecodeError:
                            consumer.send(text_data=json.dumps({'object': 'error', 'message': f'Invalid JSON format for args: {manual_args}'}))
                            return
                    else:
                        tool_def.manifest['args'] = []
                if manual_platforms is not None:
                    tool_def.manifest['platforms'] = [p.strip() for p in manual_platforms.split(',')]

        tool_def.save()
        send_object_to_clients(tool_def)
    except ToolDefinition.DoesNotExist:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'ToolDefinition with ID {tool_def_id} not found.'}))
    except Exception as e:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': f'Failed to update tool definition: {e}'}))

def handle_delete_tool_definition(consumer, payload):
    tool_def_id = payload.get('id')

    if not tool_def_id:
        consumer.send(text_data=json.dumps({'object': 'error', 'message': 'ToolDefinition ID is required for deletion.'}))
        return

    try:
        tool_def = ToolDefinition.objects.get(pk=tool_def_id)
        # Check for existing installations before deleting
        if tool_def.tool_installations.exists():
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
def _fetch_and_parse_manifest(repository_url: str, tool_def_name: str):
    """
    Clones the repository to a temporary directory, reads the manifest.json,
    and returns its content. Handles cleanup.
    """
    temp_dir_parent = Path(tempfile.gettempdir()) / "carna_tool_repos"
    temp_repo_path = temp_dir_parent / tool_def_name

    try:
        # Ensure parent temp directory exists
        mkdir(path=str(temp_dir_parent), parents=True, exist_ok=True)

        # Clean up any previous attempts for this tool definition
        rm(path=str(temp_repo_path), recursive=True)

        # Clone the repository
        clone_command = f"git clone {repository_url} {temp_repo_path}"
        clone_result = run_shell_script(script=clone_command, timeout=120)

        if clone_result.get('return_code') != 0:
            error_msg = clone_result.get('stderr') or clone_result.get('stdout')
            raise Exception(f"Git clone failed for {repository_url}: {error_msg}")

        # Read manifest.json
        manifest_file_path = temp_repo_path / "manifest.json"
        read_result = read_file(path=str(manifest_file_path))

        if read_result.get('status') == 'error':
            raise Exception(f"Failed to read manifest.json from {manifest_file_path}: {read_result.get('message')}")

        manifest_content = read_result.get('content')
        parsed_manifest = json.loads(manifest_content)
        return parsed_manifest

    finally:
        # Clean up the temporary directory
        if temp_repo_path.exists():
            rm(path=str(temp_repo_path), recursive=True)
