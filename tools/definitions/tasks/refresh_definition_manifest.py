from celery import shared_task
import tempfile
import shutil
import json
from pathlib import Path
import git

from tools.definitions.models.tool_definition import ToolDefinition

@shared_task
def refresh_definition_manifest(tool_definition_id):
    from django.utils import timezone

    """
    A Celery task to fetch a tool's manifest from its git repository,
    parse it, and update the ToolDefinition model instance.
    
    """
    
    try:
        tool_def = ToolDefinition.objects.get(pk=tool_definition_id)
    except ToolDefinition.DoesNotExist:
        # The tool was deleted before the task could run.
        return

    if not tool_def.repository_url:
        tool_def.status = ToolDefinition.ToolDefinitionStatusChoices.ERROR
        tool_def.save()
        return

    temp_dir = None
    try:
        temp_dir = Path(tempfile.mkdtemp())
        git.Repo.clone_from(tool_def.repository_url, temp_dir, depth=1)

        manifest_path = temp_dir / "manifest.json"
        if not manifest_path.exists():
            raise FileNotFoundError("manifest.json not found in the repository root.")

        manifest_content = json.loads(manifest_path.read_text())

        # Update the ToolDefinition instance
        tool_def.manifest = manifest_content
        # Only update these if the manifest provides them and they are not empty
        if manifest_content.get('name'):
            tool_def.name = manifest_content['name']
        if manifest_content.get('display_name'):
            tool_def.display_name = manifest_content['display_name']
        if manifest_content.get('description'):
            tool_def.description = manifest_content['description']

        tool_def.manifest_version = manifest_content.get('version')
        tool_def.status = ToolDefinition.ToolDefinitionStatusChoices.UP_TO_DATE
        tool_def.last_checked_at = timezone.now()

        # The model's save() method will broadcast the update to clients
        tool_def.save()

    except Exception as e:
        # Log the error and update the model with an error status.
        print(f"Error fetching manifest for ToolDefinition {tool_definition_id}: {e}")
        tool_def.status = ToolDefinition.ToolDefinitionStatusChoices.ERROR
        tool_def.last_checked_at = timezone.now()
        tool_def.save()
    finally:
        if temp_dir and temp_dir.exists():
            shutil.rmtree(temp_dir)
