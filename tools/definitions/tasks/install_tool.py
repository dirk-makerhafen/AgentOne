from celery import shared_task

from agents.models.agent_instance import AgentInstance
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
def install_tool(tool_installation_id, agent_instance_pk=None):
    """
    Orchestrates the installation of a tool on its assigned system, with detailed logging.
    This includes support for Node.js (npm) and Python (venv) build processes.
    If agent_instance_pk is provided, the ToolInstallation will be linked to that specific instance.
    """
    tool_installation = ToolInstallation.objects.get(pk=tool_installation_id)
    _log(tool_installation, 'info', 'Installation process started.')
    tool_installation.status = ToolInstallation.Status.INSTALLING
    tool_installation.save()

    system = tool_installation.system
    tool_def = tool_installation.tool_definition
    agent_instance = None

    if agent_instance_pk:
        try:
            agent_instance = AgentInstance.objects.get(pk=agent_instance_pk)
            # Link the installation to the agent instance for dedicated tools
            tool_installation.agent_instance = agent_instance
            tool_installation.save()
            _log(tool_installation, 'info', f'ToolInstallation linked to AgentInstance {agent_instance_pk}.')
        except AgentInstance.DoesNotExist:
            _log(tool_installation, 'error', f'AgentInstance with pk {agent_instance_pk} not found for dedicated tool installation.')
            tool_installation.status = ToolInstallation.Status.ERROR
            tool_installation.save()
            return

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

    # For dedicated tools, create a subdirectory based on the AgentInstance PK
    if agent_instance:
        install_path = install_base_dir / tool_def.name / f"instance_{agent_instance_pk}"
    else:
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

