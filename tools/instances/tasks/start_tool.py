from celery import shared_task

from executor.primitives import (
    mkdir,
    read_file,
    rm,
    run_shell_script,
    run_python_code,
    stat_path,
    manage_tool_process
)
import json
from pathlib import Path

from tools.definitions.models.tool_installation import ToolInstallation
from tools.definitions.models.tool_installation_log import ToolInstallationLog

def _log(installation: ToolInstallation, level: str, message: str):
    """Helper function to create a log entry for a tool installation."""
    ToolInstallationLog.objects.create(
        tool_installation=installation,
        level=level,
        message=message
    )

@shared_task
def start_tool(tool_installation_id):
    tool_installation = ToolInstallation.objects.get(pk=tool_installation_id)
    _log(tool_installation, 'info', 'Start process initiated.')
    system = tool_installation.system
    tool_def = tool_installation.tool_definition

    if not all([system, tool_def, tool_installation.local_path, tool_def.manifest]):
        _log(tool_installation, 'error', 'Cannot start: missing system, tool definition, local path, or manifest.')
        tool_installation.status = ToolInstallation.Status.ERROR
        tool_installation.save()
        return

    transport_type = tool_def.transport_type
    mcp_config = tool_def.manifest.get('server', {}).get('mcp_config', {})
    tool_command = mcp_config.get('command')
    tool_args = mcp_config.get('args', [])
    tool_env_vars = mcp_config.get('env', {})

    if not tool_command:
        _log(tool_installation, 'error', 'Tool manifest is missing "server.mcp_config.command".')
        tool_installation.status = ToolInstallation.Status.ERROR; tool_installation.save(); return

    # WORKAROUND for PATH issues in Celery: Use an absolute path for node.
    if tool_command == 'node':
        _log(tool_installation, 'warning', 'Applying workaround for Celery PATH issue. Using absolute path for node.')
        tool_command = '/usr/local/bin/node'

    port, endpoint_url = None, None
    mcp_server_config = {'transport_type': transport_type}

    if transport_type == 'tcp':
        _log(tool_installation, 'info', 'Finding an available port for TCP transport.')
        port_result = run_python_code(system=system, python_code_string="import socket;s=socket.socket();s.bind(('',0));port=s.getsockname()[1];s.close()", locals_to_return=['port'])
        if not (port_result.get('status') == 'success' and port_result.get('vars', {}).get('port')):
            _log(tool_installation, 'error', f"Failed to find free port: {port_result.get('message')}"); tool_installation.status = ToolInstallation.Status.ERROR; tool_installation.save(); return
        port = port_result['vars']['port']
        executor_host = "127.0.0.1"
        if system.executor_url: from urllib.parse import urlparse; executor_host = urlparse(system.executor_url).hostname or executor_host
        endpoint_url = f'http://{executor_host}:{port}'
        mcp_server_config['endpoint_url'] = endpoint_url
        _log(tool_installation, 'info', f"Assigned port {port}, endpoint will be {endpoint_url}")

    local_path_str = tool_installation.local_path
    processed_args = [arg.replace('${__dirname}', local_path_str).replace('{port}', str(port) if port else '') for arg in tool_args]

    _log(tool_installation, 'info', f"Requesting tool start with command: '{tool_command}' and args: {processed_args}")
    start_result = manage_tool_process(
        system=system, 
        action='start', 
        process_id=str(tool_installation.pk), 
        command=tool_command,
        args=processed_args,
        cwd=local_path_str, 
        env=tool_env_vars, 
        mcp_server_config=mcp_server_config
    )

    if start_result.get('status') != 'success':
        _log(tool_installation, 'error', start_result.get('message', 'Failed to start process via primitive.'))
        tool_installation.status = ToolInstallation.Status.ERROR; tool_installation.save(); return

    _log(tool_installation, 'info', "Tool client started successfully on executor.")
    tool_installation.process_id = None
    tool_installation.assigned_port = port
    tool_installation.status = ToolInstallation.Status.RUNNING

    # Pass agent_instance to ToolInstance if it's a dedicated tool
    mcp_server_defaults = {'name': tool_def.display_name, 'endpoint_url': endpoint_url, 'transport_type': transport_type, 'enabled': True}
    if tool_installation.agent_instance:
        mcp_server, created = ToolInstance.objects.get_or_create(tool_installation=tool_installation, agent_instance=tool_installation.agent_instance, defaults=mcp_server_defaults)
    else:
        mcp_server, created = ToolInstance.objects.get_or_create(tool_installation=tool_installation, defaults=mcp_server_defaults)

    if not created:
        mcp_server.endpoint_url, mcp_server.transport_type, mcp_server.enabled = endpoint_url, transport_type, True
        mcp_server.save()
    tool_installation.mcp_server = mcp_server
    tool_installation.save()
    _log(tool_installation, 'info', f"ToolInstance record updated. Tool is running for {transport_type} transport.")
