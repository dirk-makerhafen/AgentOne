from celery import shared_task
from tools_common.models  import ToolInstallation, ToolInstallationLog
from tools_mcp.models import MCPServer
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

def _log(installation: ToolInstallation, level: str, message: str):
    """Helper function to create a log entry for a tool installation."""
    ToolInstallationLog.objects.create(
        tool_installation=installation,
        level=level,
        message=message
    )

@shared_task
def install_tool(tool_installation_id):
    """
    Orchestrates the installation of a tool on its assigned system, with detailed logging.
    This includes support for Node.js (npm) and Python (venv) build processes.
    """
    tool_installation = ToolInstallation.objects.get(pk=tool_installation_id)
    _log(tool_installation, 'info', 'Installation process started.')
    tool_installation.status = ToolInstallation.Status.INSTALLING
    tool_installation.save()

    system = tool_installation.system
    tool_def = tool_installation.tool_definition

    if not system or not tool_def or not tool_def.repository_url:
        _log(tool_installation, 'error', 'System, ToolDefinition, or Repository URL not found.')
        tool_installation.status = ToolInstallation.Status.ERROR
        tool_installation.save()
        return

    home_dir_script = "from pathlib import Path; home = str(Path.home())"
    home_dir_result = run_python_code(system=system, python_code_string=home_dir_script, locals_dict={}, locals_to_return=['home'])
    if not (home_dir_result.get('status') == 'success' and 'vars' in home_dir_result and 'home' in home_dir_result['vars']):
        error_msg = f"Could not determine home directory on remote system: {home_dir_result.get('message')}"
        _log(tool_installation, 'error', error_msg)
        tool_installation.status = ToolInstallation.Status.ERROR
        tool_installation.save()
        return

    home_dir = Path(home_dir_result['vars']['home'])
    install_base_dir = home_dir / ".carna" / "tools"
    install_path = install_base_dir / tool_def.name
    tool_installation.local_path = str(install_path)

    rm(system=system, path=str(install_path), recursive=True)
    mkdir_result = mkdir(system=system, path=str(install_path), parents=True)
    if mkdir_result.get('status') == 'error':
        _log(tool_installation, 'error', f"Failed to create directory: {mkdir_result.get('message')}")
        tool_installation.status = ToolInstallation.Status.ERROR
        tool_installation.save()
        return

    _log(tool_installation, 'info', f"Cloning repository from '{tool_def.repository_url}' into '{install_path}'.")
    clone_result = run_shell_script(system=system, script=f"git clone {tool_def.repository_url} .", env={'GIT_TERMINAL_PROMPT': '0'}, timeout=300, cwd=str(install_path))
    if clone_result.get('return_code') != 0:
        error_msg = clone_result.get('stderr') or clone_result.get('stdout')
        _log(tool_installation, 'error', f"Git clone failed: {clone_result}")
        tool_installation.status = ToolInstallation.Status.ERROR
        tool_installation.save()
        return

    manifest_server_type = tool_def.manifest.get('server', {}).get('type')
    build_successful = True
    if manifest_server_type == 'node' and stat_path(system=system, path=str(install_path / "package.json")).get('exists'):
        _log(tool_installation, 'info', "Node.js tool detected. Running npm install.")
        npm_result = run_shell_script(system=system, script="npm install", timeout=600, cwd=str(install_path))
        if npm_result.get('return_code') != 0:
            _log(tool_installation, 'error', f"npm install failed: {npm_result.get('stderr') or npm_result.get('stdout')}")
            build_successful = False
        else:
            _log(tool_installation, 'info', "npm install successful. Checking for build script.")
            # Check if a build script exists in package.json before running it
            package_json_content = read_file(system=system, path=str(install_path / "package.json")).get('content', '{}')
            if 'build' in json.loads(package_json_content).get('scripts', {}):
                _log(tool_installation, 'info', "Build script found. Running npm run build.")
                build_result = run_shell_script(system=system, script="npm run build", timeout=600, cwd=str(install_path))
                if build_result.get('return_code') != 0:
                    _log(tool_installation, 'error', f"npm run build failed: {build_result.get('stderr') or build_result.get('stdout')}")
                    build_successful = False
            else:
                _log(tool_installation, 'info', "No build script found in package.json, skipping build step.")

    elif (manifest_server_type == 'python' or not manifest_server_type) and stat_path(system=system, path=str(install_path / "requirements.txt")).get('exists'):
        _log(tool_installation, 'info', "Python tool detected. Setting up virtual environment.")
        venv_path = install_path / "venv"
        pip_exe = f'"{venv_path / "Scripts" / "python.exe"}"' if system.os == 'windows' else f'"{venv_path / "bin" / "python"}"'
        venv_script = f'python -m venv "{venv_path}" && {pip_exe} -m pip install -r "requirements.txt"' if system.os == 'windows' else f'python3 -m venv "{venv_path}" && {pip_exe} -m pip install -r "requirements.txt"'
        venv_result = run_shell_script(system=system, script=venv_script, timeout=600, cwd=str(install_path))
        if venv_result.get('return_code') != 0:
            _log(tool_installation, 'error', f"Venv setup failed: {venv_result.get('stderr') or venv_result.get('stdout')}")
            build_successful = False

    if build_successful:
        tool_installation.status = ToolInstallation.Status.INSTALLED
        _log(tool_installation, 'info', "Installation process completed successfully.")
    else:
        tool_installation.status = ToolInstallation.Status.ERROR
        _log(tool_installation, 'error', "Installation process failed during build step.")
    tool_installation.save()


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

    mcp_server, created = MCPServer.objects.get_or_create(tool_installation=tool_installation, defaults={'name': tool_def.display_name, 'endpoint_url': endpoint_url, 'transport_type': transport_type, 'enabled': True})
    if not created:
        mcp_server.endpoint_url, mcp_server.transport_type, mcp_server.enabled = endpoint_url, transport_type, True
        mcp_server.save()
    tool_installation.mcp_server = mcp_server
    tool_installation.save()
    _log(tool_installation, 'info', f"MCPServer record updated. Tool is running for {transport_type} transport.")

@shared_task
def stop_tool(tool_installation_id, uninstall: bool = False):
    tool_installation = ToolInstallation.objects.get(pk=tool_installation_id)
    _log(tool_installation, 'info', f"Stop process initiated. Uninstall: {uninstall}")
    system = tool_installation.system
    if not system: _log(tool_installation, 'error', 'Cannot stop: System not found.'); return

    _log(tool_installation, 'info', f"Requesting client and process stop for ID: {tool_installation.pk}.")
    stop_result = manage_tool_process(system=system, action='stop', process_id=str(tool_installation.pk))
    if stop_result.get('status') == 'success':
        _log(tool_installation, 'info', f"Executor confirmed stop for client {tool_installation.pk}.")
    else:
        _log(tool_installation, 'warning', f"Executor stop command failed or was not necessary: {stop_result.get('message')}")

    tool_installation.process_id, tool_installation.assigned_port = None, None
    if tool_installation.mcp_server:
        tool_installation.mcp_server.enabled = False
        tool_installation.mcp_server.status = 'disconnected'
        tool_installation.mcp_server.save()

    if uninstall:
        if tool_installation.local_path:
            _log(tool_installation, 'info', f"Removing directory '{tool_installation.local_path}'.")
            rm(system=system, path=tool_installation.local_path, recursive=True)
        tool_installation.status = ToolInstallation.Status.NOT_INSTALLED
        tool_installation.local_path = None
        _log(tool_installation, 'info', 'Uninstallation complete.')
    else:
        tool_installation.status = ToolInstallation.Status.STOPPED
        _log(tool_installation, 'info', 'Tool is now stopped.')
    tool_installation.save()

@shared_task
def get_tool_status(tool_installation_id):
    # This function is less critical now but can be a simple check
    tool_installation = ToolInstallation.objects.get(pk=tool_installation_id)
    if tool_installation.status not in [ToolInstallation.Status.RUNNING, ToolInstallation.Status.INSTALLING]:
        return

    # A simple way to check is to try listing tools. A failure implies it's not running.
    # Note: This is an active check, not a passive PID check.
    system = tool_installation.system
    if not system: return

    result = manage_tool_process(system=system, action='list_tools', process_id=str(tool_installation.pk))
    if result.get('status') != 'success' and tool_installation.status == ToolInstallation.Status.RUNNING:
        _log(tool_installation, 'warning', f"Health check failed for running tool: {result.get('message')}")
        tool_installation.status = ToolInstallation.Status.ERROR
        tool_installation.save()
