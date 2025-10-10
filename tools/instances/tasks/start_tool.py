from celery import shared_task
from django.db import transaction

from tools.primitives import (
    run_python_code,
    manage_tool_process
)
import json
from pathlib import Path
from urllib.parse import urlparse

from tools.definitions.models.tool_installation import ToolInstallation
from tools.definitions.models.tool_installation_log import ToolInstallationLog
from tools.instances.models.tool_instance import ToolInstance

def _log(installation: ToolInstallation, level: str, message: str, tool_instance: ToolInstance = None):
    """Helper function to create a log entry for a tool installation, with optional instance context."""
    instance_info = f" (Instance PK: {tool_instance.pk})" if tool_instance else ""
    ToolInstallationLog.objects.create(
        tool_installation=installation,
        level=level,
        message=f"{message}{instance_info}"
    )

@shared_task
def start_tool(tool_installation_id):
    try:
        tool_installation = ToolInstallation.objects.get(pk=tool_installation_id)
    except ToolInstallation.DoesNotExist:
        # If installation doesn't exist, we can't log to it.
        print(f"ERROR: ToolInstallation with ID {tool_installation_id} not found during start_tool task.")
        return

    _log(tool_installation, 'info', 'Tool start process initiated.')
    system = tool_installation.system
    tool_def = tool_installation.tool_definition

    if not all([system, tool_def, tool_installation.local_path, tool_def.manifest]):
        _log(tool_installation, 'error', 'Cannot start: missing system, tool definition, local path, or manifest.')
        tool_installation.status = ToolInstallation.Status.ERROR # Still relevant for installation status
        tool_installation.save()
        return

    # Check for max_parallel_instances limit
    current_running_instances = ToolInstance.objects.filter(
        tool_installation=tool_installation,
        status__in=[ToolInstance.Status.STARTING, ToolInstance.Status.RUNNING]
    ).count()

    if current_running_instances >= tool_installation.max_parallel_instances:
        error_message = f"Cannot start tool '{tool_def.display_name}'. Max parallel instances ({tool_installation.max_parallel_instances}) already running."
        _log(tool_installation, 'warning', error_message)
        # We don't mark installation as ERROR, as it's not an installation failure, but a runtime limit.
        return

    # Create a new ToolInstance record (ephemeral model)
    tool_instance = ToolInstance.objects.create(
        tool_installation=tool_installation,
        status=ToolInstance.Status.STARTING
    )
    _log(tool_installation, 'info', 'New ToolInstance record created.', tool_instance)

    transport_type = tool_def.transport_type
    tool_manifest_server_config = tool_def.manifest.get('server', {})
    tool_command = tool_manifest_server_config.get('command')
    tool_args = tool_manifest_server_config.get('args', [])
    tool_env_vars = tool_manifest_server_config.get('env', {})

    if not tool_command:
        _log(tool_installation, 'error', 'Tool manifest is missing "server.command".', tool_instance)
        tool_instance.status = ToolInstance.Status.ERROR
        tool_instance.last_error = 'Missing "server.command" in manifest.'
        tool_instance.save()
        return

    # WORKAROUND for PATH issues in Celery: Use an absolute path for node.
    if tool_command == 'node':
        _log(tool_installation, 'warning', 'Applying workaround for Celery PATH issue. Using absolute path for node.', tool_instance)
        tool_command = '/usr/local/bin/node'

    port, endpoint_url = None, None
    tool_installation_config = {'transport_type': transport_type}

    if transport_type == 'tcp':
        _log(tool_installation, 'info', 'Finding an available port for TCP transport.', tool_instance)
        port_result = run_python_code(system=system, python_code_string="import socket;s=socket.socket();s.bind(('',0));port=s.getsockname()[1];s.close()", locals_to_return=['port'])
        if not (port_result.get('status') == 'success' and port_result.get('vars', {}).get('port')):
            error_message = f"Failed to find free port: {port_result.get('message', 'Unknown error')}"
            _log(tool_installation, 'error', error_message, tool_instance)
            tool_instance.status = ToolInstance.Status.ERROR
            tool_instance.last_error = error_message
            tool_instance.save()
            return

        port = port_result['vars']['port']
        executor_host = "127.0.0.1"
        if system.executor_url:
            parsed_url = urlparse(system.executor_url)
            executor_host = parsed_url.hostname or executor_host
        endpoint_url = f'http://{executor_host}:{port}'
        tool_installation_config['endpoint_url'] = endpoint_url
        _log(tool_installation, 'info', f"Assigned port {port}, endpoint will be {endpoint_url}", tool_instance)

    local_path_str = tool_installation.local_path
    processed_args = [
        arg.replace('${__dirname}', local_path_str).replace('{port}', str(port) if port else '')
        for arg in tool_args
    ]

    _log(tool_installation, 'info', f"Requesting tool start with command: '{tool_command}' and args: {processed_args}", tool_instance)
    
    start_result = manage_tool_process(
        system=system,
        action='start',
        process_id=str(tool_instance.pk), # Use ToolInstance PK as unique process ID
        command=tool_command,
        args=processed_args,
        cwd=local_path_str,
        env=tool_env_vars,
        tool_config=tool_installation_config
    )

    if start_result.get('status') != 'success':
        error_message = start_result.get('message', 'Failed to start process via primitive.')
        _log(tool_installation, 'error', error_message, tool_instance)
        tool_instance.status = ToolInstance.Status.ERROR
        tool_instance.last_error = error_message
        tool_instance.save()
        return

    _log(tool_installation, 'info', "Tool client started successfully on executor.", tool_instance)

    # Update ToolInstance with runtime details
    tool_instance.process_id = start_result.get('process_id') # The actual PID from the executor
    tool_instance.endpoint_url = endpoint_url
    tool_instance.status = ToolInstance.Status.RUNNING
    tool_instance.save()
    
    _log(tool_installation, 'info', "ToolInstance record updated with runtime details. Tool is now RUNNING.", tool_instance)
