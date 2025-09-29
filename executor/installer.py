import argparse
import json
import os
import platform
import socket
import subprocess
import sys
import requests

# --- Configuration ---
CONFIG_FILE = 'client_config.json'
SERVICE_NAME = 'carna_executor'
SERVICE_DISPLAY_NAME = 'Carna Agent Executor'
EXECUTOR_MAIN_SCRIPT = 'main.py'

# --- Installation Configuration ---
DEFAULT_INSTALL_PATH_WINDOWS = os.path.join(os.environ.get('ProgramFiles', 'C:\\Program Files'), 'CarnaExecutor')
DEFAULT_INSTALL_PATH_LINUX_MAC = '/opt/carna_executor'
# Assumes the installer is in the 'executor' directory with the other source files.
SOURCE_DIR = os.path.dirname(os.path.abspath(__file__))
FILES_TO_COPY = ['main.py', 'primitives.py', 'requirements.txt']


# --- Platform-Specific Service Management ---

def is_admin():
    """Check if the script is running with administrative privileges."""
    try:
        is_admin = (os.getuid() == 0)
    except AttributeError:
        import ctypes
        is_admin = (ctypes.windll.shell32.IsUserAnAdmin() != 0)
    return is_admin

def handle_install_interactive(args):
    """Handles the interactive installation and service creation process."""
    print("--- Carna Agent Executor Installation ---")
    import shutil

    # Determine installation path
    system = platform.system()
    default_path = DEFAULT_INSTALL_PATH_WINDOWS if system == 'Windows' else DEFAULT_INSTALL_PATH_LINUX_MAC
    install_path_input = input(f"Enter installation directory (press Enter for default: '{default_path}'): ")
    install_path = os.path.abspath(install_path_input or default_path)
    print(f"Executor will be installed in: {install_path}")

    # --- Step 1: Create directory and copy files ---
    print(f"\n--- Preparing Installation Directory ---")
    if not os.path.exists(install_path):
        try:
            os.makedirs(install_path, exist_ok=True)
            print(f"Created directory: {install_path}")
        except OSError as e:
            print(f"ERROR: Could not create directory '{install_path}': {e}")
            return
    
    for filename in FILES_TO_COPY:
        source_file = os.path.join(SOURCE_DIR, filename)
        dest_file = os.path.join(install_path, filename)
        if os.path.exists(source_file):
            shutil.copy(source_file, dest_file)
            print(f"Copied '{filename}' to installation directory.")
        else:
            print(f"WARNING: Source file '{source_file}' not found. Skipping.")

    # --- Step 2: Set up Python environment ---
    venv_python = setup_python_env_and_dependencies(install_path)
    if not venv_python:
        print("Python environment setup failed. Aborting installation.")
        return

    # --- Step 3: Run the client registration process ---
    if not register_client_interactive(install_path):
        print("Client registration failed. Aborting installation.")
        return

    # --- Step 4: Ask to install the service ---
    install_service_prompt = input("\nDo you want to install the executor as a system service? (y/n): ").lower()
    if install_service_prompt != 'y':
        print(f"Service installation skipped. You can run the executor manually from '{install_path}'.")
        return

    if not is_admin():
        print("\nERROR: Service installation requires administrative privileges.")
        print("Please re-run this script with 'sudo' (Linux/macOS) or as an Administrator (Windows).")
        return

    if system == 'Linux':
        install_service_linux(venv_python, install_path)
    elif system == 'Darwin':
        install_service_macos(venv_python, install_path)
    elif system == 'Windows':
        install_service_windows(venv_python, install_path)
    else:
        print(f"Unsupported OS for service installation: {system}")

def handle_uninstall(args):
    """Handles the service uninstallation and directory removal process."""
    print(f"--- Uninstalling {SERVICE_DISPLAY_NAME} Service ---")

    system = platform.system()
    default_path = DEFAULT_INSTALL_PATH_WINDOWS if system == 'Windows' else DEFAULT_INSTALL_PATH_LINUX_MAC
    install_path = os.path.abspath(args.path or default_path)

    if not is_admin():
        print("\nERROR: Service uninstallation requires administrative privileges.")
        print("Please re-run this script with 'sudo' (Linux/macOS) or as an Administrator (Windows).")
        return

    # Step 1: Stop and remove the service
    if system == 'Linux':
        uninstall_service_linux()
    elif system == 'Darwin':
        uninstall_service_macos()
    elif system == 'Windows':
        uninstall_service_windows()
    else:
        print(f"Unsupported operating system for service removal: {system}")

    # Step 2: Remove the installation directory
    if os.path.exists(install_path):
        print(f"\nInstallation directory found at: {install_path}")
        confirm = input(f"--> Do you want to delete this directory and all its contents? (y/n): ").lower()
        if confirm == 'y':
            try:
                import shutil
                shutil.rmtree(install_path)
                print("Directory removed successfully.")
            except Exception as e:
                print(f"Error removing directory: {e}")
                print("You may need to remove it manually.")
        else:
            print("Directory removal skipped.")
    else:
        print(f"\nInstallation directory not found at '{install_path}', no files to remove.")

def handle_status():
    """Handles checking the status of the service."""
    print(f"--- Status for {SERVICE_DISPLAY_NAME} Service ---")
    system = platform.system()
    if system == 'Linux':
        get_service_status_linux()
    elif system == 'Darwin':
        get_service_status_macos()
    elif system == 'Windows':
        get_service_status_windows()
    else:
        print(f"Unsupported operating system: {system}")

# --- OS-Specific Implementations (Placeholders) ---

def install_service_linux(venv_python, install_path):
    """Installs the systemd service for Linux."""
    print("\n--- Installing systemd service for Linux ---")
    user = os.getenv("SUDO_USER") or os.getenv("USER")
    if not user:
        print("Could not determine the non-root user to run the service. Aborting.")
        return

    script_path = os.path.join(install_path, EXECUTOR_MAIN_SCRIPT)
    service_file_content = f"""[Unit]
Description={SERVICE_DISPLAY_NAME}
After=network.target

[Service]
User={user}
Group={user}
WorkingDirectory={install_path}
ExecStart={venv_python} {script_path}
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
"""
    service_path = f"/etc/systemd/system/{SERVICE_NAME}.service"
    try:
        print(f"Writing service file to {service_path}...")
        with open(service_path, 'w') as f:
            f.write(service_file_content)
        
        print("Reloading systemd daemon, enabling and starting service...")
        subprocess.run(['systemctl', 'daemon-reload'], check=True)
        subprocess.run(['systemctl', 'enable', f'{SERVICE_NAME}.service'], check=True)
        subprocess.run(['systemctl', 'start', f'{SERVICE_NAME}.service'], check=True)
        print("\nService installation completed successfully.")
        get_service_status_linux()
    except (subprocess.CalledProcessError, IOError) as e:
        print(f"\nError during service installation: {e}")

def uninstall_service_linux():
    service_path = f"/etc/systemd/system/{SERVICE_NAME}.service"
    print(f"Checking for service file at {service_path}...")

    if not os.path.exists(service_path):
        print("Service does not appear to be installed. Nothing to do.")
        return

    try:
        print(f"Stopping {SERVICE_NAME} service...")
        subprocess.run(['systemctl', 'stop', f'{SERVICE_NAME}.service'], check=False) # Don't fail if already stopped

        print(f"Disabling {SERVICE_NAME} service...")
        subprocess.run(['systemctl', 'disable', f'{SERVICE_NAME}.service'], check=False) # Don't fail if not enabled

        print(f"Removing service file: {service_path}")
        os.remove(service_path)

        print("Reloading systemd daemon...")
        subprocess.run(['systemctl', 'daemon-reload'], check=True)

        print("\nService uninstalled successfully.")
        if os.path.exists(CONFIG_FILE):
            print(f"NOTE: The client configuration file '{CONFIG_FILE}' was not removed.")

    except (subprocess.CalledProcessError, IOError) as e:
        print(f"\nAn error occurred during uninstallation: {e}")

def get_service_status_linux():
    try:
        print(f"Checking status of {SERVICE_NAME}.service...")
        subprocess.run(['systemctl', 'status', f'{SERVICE_NAME}.service', '--no-pager'], check=True)
    except FileNotFoundError:
        print("systemctl command not found. Is systemd your init system?")
    except subprocess.CalledProcessError:
        print(f"Service '{SERVICE_NAME}' does not appear to be installed or is in a failed state.")

def install_service_macos(venv_python, install_path):
    """Installs the launchd service for macOS."""
    print("\n--- Installing launchd service for macOS ---")
    script_path = os.path.join(install_path, EXECUTOR_MAIN_SCRIPT)
    service_label = f"com.carna.{SERVICE_NAME}"
    plist_path = f"/Library/LaunchDaemons/{service_label}.plist"

    plist_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>{service_label}</string>
    <key>ProgramArguments</key>
    <array>
        <string>{venv_python}</string>
        <string>{script_path}</string>
    </array>
    <key>WorkingDirectory</key>
    <string>{install_path}</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/tmp/{SERVICE_NAME}.out.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/{SERVICE_NAME}.err.log</string>
</dict>
</plist>
"""
    try:
        print(f"Writing launchd plist to {plist_path}...")
        with open(plist_path, 'w') as f:
            f.write(plist_content)
        
        subprocess.run(['chown', 'root:wheel', plist_path], check=True)
        subprocess.run(['chmod', '644', plist_path], check=True)
        print("Loading and starting service with launchctl...")
        subprocess.run(['launchctl', 'load', '-w', plist_path], check=True, capture_output=True)
        print("\nService installation completed successfully.")
        get_service_status_macos()
    except (subprocess.CalledProcessError, IOError) as e:
        print(f"\nError during service installation: {e}")

def uninstall_service_macos():
    service_label = f"com.carna.{SERVICE_NAME}"
    plist_path = f"/Library/LaunchDaemons/{service_label}.plist"

    print(f"Checking for service file at {plist_path}...")
    if not os.path.exists(plist_path):
        print("Service does not appear to be installed. Nothing to do.")
        return

    try:
        print(f"Unloading {service_label} service...")
        # Unload the service, which stops it as well.
        subprocess.run(['launchctl', 'unload', '-w', plist_path], check=False)

        print(f"Removing service file: {plist_path}")
        os.remove(plist_path)

        print("\nService uninstalled successfully.")
        if os.path.exists(CONFIG_FILE):
            print(f"NOTE: The client configuration file '{CONFIG_FILE}' was not removed.")

    except (subprocess.CalledProcessError, IOError) as e:
        print(f"\nAn error occurred during uninstallation: {e}")

def get_service_status_macos():
    service_label = f"com.carna.{SERVICE_NAME}"
    try:
        print(f"Checking status of {service_label}...")
        # Use launchctl list and grep to find the service
        result = subprocess.run(['launchctl', 'list'], capture_output=True, text=True, check=True)

        service_found = False
        for line in result.stdout.splitlines():
            if service_label in line:
                print("Service is loaded:")
                print(line)
                service_found = True
                break

        if not service_found:
            print("Service is not currently loaded.")

    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        print(f"Could not check service status: {e}")

def install_service_windows(venv_python, install_path):
    """Installs the service for Windows."""
    print("\n--- Installing service for Windows ---")
    script_path = os.path.join(install_path, EXECUTOR_MAIN_SCRIPT)
    # The entire binPath needs to be correctly quoted for sc.exe
    bin_path = f'"{venv_python}" "{script_path}"'
    
    try:
        print(f"Creating service '{SERVICE_NAME}'...")
        # The binPath and DisplayName arguments must be a single string like "binPath= <command>"
        # Note the required space after the '=' sign.
        subprocess.run([
            'sc', 'create', SERVICE_NAME,
            f'binPath= {bin_path}',
            f'DisplayName= "{SERVICE_DISPLAY_NAME}"',
            'start=', 'auto'
        ], check=True, capture_output=True, text=True)
        
        # Optional: Add a description to the service for better management.
        subprocess.run([
            'sc', 'description', SERVICE_NAME, 
            f'"{SERVICE_DISPLAY_NAME} - Runs remote code execution tasks."'
        ], check=False) # Don't fail if this doesn't work

        print("Starting service...")
        subprocess.run(['sc', 'start', SERVICE_NAME], check=True, capture_output=True, text=True)
        print("\nService installation completed successfully.")
        get_service_status_windows()
    except subprocess.CalledProcessError as e:
        print(f"\nError during service installation: {e}")
        # sc.exe often prints useful info to stderr, so we show it.
        print(f"Stderr: {e.stderr}")
    except FileNotFoundError:
        print("\nError: 'sc.exe' command not found. Is it in your system's PATH?")

def uninstall_service_windows():
    try:
        print(f"Stopping {SERVICE_NAME} service...")
        subprocess.run(['sc', 'stop', SERVICE_NAME], check=False, capture_output=True) # Don't fail if already stopped

        print(f"Deleting {SERVICE_NAME} service...")
        result = subprocess.run(['sc', 'delete', SERVICE_NAME], check=True, capture_output=True)

        if "service does not exist" in result.stderr.decode('utf-8').lower():
             print("Service does not appear to be installed. Nothing to do.")
             return

        print("\nService uninstalled successfully.")
        if os.path.exists(CONFIG_FILE):
            print(f"NOTE: The client configuration file '{CONFIG_FILE}' was not removed.")

    except subprocess.CalledProcessError as e:
        # Check if the error is because the service doesn't exist
        stderr_output = e.stderr.decode('utf-8').lower()
        if "does not exist" in stderr_output:
             print("Service does not appear to be installed. Nothing to do.")
        else:
            print(f"\nAn error occurred during uninstallation: {e}")
            print(f"Stderr: {stderr_output}")
    except FileNotFoundError:
        print("\nError: 'sc.exe' command not found.")

def get_venv_python_path(install_path):
    """Gets the path to the python executable in the virtual environment."""
    if platform.system() == 'Windows':
        return os.path.join(install_path, 'venv', 'Scripts', 'python.exe')
    else: # Linux/macOS
        return os.path.join(install_path, 'venv', 'bin', 'python')

def get_service_status_windows():
    try:
        print(f"Querying status of '{SERVICE_NAME}' service...")
        # We need to capture output to check it
        result = subprocess.run(['sc', 'query', SERVICE_NAME], check=True, capture_output=True, text=True)
        print(result.stdout)
    except subprocess.CalledProcessError as e:
        # sc query returns a non-zero exit code if the service doesn't exist
        print(f"Service '{SERVICE_NAME}' does not appear to be installed.")
    except FileNotFoundError:
        print("\nError: 'sc.exe' command not found.")

# --- Client Registration Logic ---

def register_client_interactive(install_path):
    """Guides the user through registering the client with the server."""
    print("\n--- Client Registration ---")
    config_path = os.path.join(install_path, CONFIG_FILE)

    if os.path.exists(config_path):
        overwrite = input(f"A configuration file already exists at '{config_path}'. Overwrite? (y/n): ").lower()
        if overwrite != 'y':
            print("Registration skipped.")
            return os.path.exists(config_path)

    server_url = input("Enter the full URL of the Carna server (e.g., http://127.0.0.1:8000): ")
    server_secret = input("Enter the server's AGENT_SERVER_SECRET_KEY: ")
    default_client_name = socket.gethostname()
    client_name = input(f"Enter a name for this client (default: '{default_client_name}'): ") or default_client_name
    client_port = input(f"Enter the port this client will listen on (default: '8123'): ") or '8123'
    client_listen = input(f"Enter the listen address for this client (default: '0.0.0.0' for all interfaces): ") or '0.0.0.0'

    registration_endpoint = f"{server_url.rstrip('/')}/systems/api/register_client/"
    payload = {'server_secret': server_secret, 'client_name': client_name, 'client_port': client_port}

    print(f"\nAttempting to register with {registration_endpoint}...")
    try:
        response = requests.post(registration_endpoint, json=payload)
        response.raise_for_status()
        response_data = response.json()
        client_api_key = response_data.get('client_api_key')
        resolved_url = response_data.get('resolved_client_url')

        if not client_api_key or not resolved_url:
            print(f"Error: Server response incomplete. Response: {response.text}")
            return False

        print("Registration successful!")
        print(f"Client registered with address: {resolved_url}")

        config_data = {
            'client_name': client_name,
            'client_api_key': client_api_key,
            'server_url': server_url.rstrip('/'),
            'client_port': client_port,
            'client_listen': client_listen
        }
        with open(config_path, 'w') as f:
            json.dump(config_data, f, indent=4)
        print(f"Client configuration saved to '{config_path}'.")
        return True

    except requests.exceptions.RequestException as e:
        print(f"\nError: Could not connect to the server. Details: {e}")
        return False
    except Exception as e:
        print(f"\nAn unexpected error occurred: {e}")
        if 'response' in locals():
            print(f"Server response: {response.status_code} - {response.text}")
        return False


def register_client_non_interactive(args, install_path):
    """Performs non-interactive client registration using provided arguments."""
    print("\n--- Client Registration (Non-Interactive) ---")
    config_path = os.path.join(install_path, CONFIG_FILE)

    if os.path.exists(config_path) and not args.force:
        print(f"ERROR: A configuration file exists at '{config_path}'. Use --force to overwrite.")
        return False

    server_url = args.server_url
    server_secret = args.server_secret
    client_name = args.client_name or socket.gethostname()
    client_port = args.client_port
    client_listen = args.client_listen

    registration_endpoint = f"{server_url.rstrip('/')}/systems/api/register_client/"
    payload = {'server_secret': server_secret, 'client_name': client_name, 'client_port': client_port}

    print(f"Attempting to register with {registration_endpoint}...")
    try:
        response = requests.post(registration_endpoint, json=payload)
        response.raise_for_status()
        response_data = response.json()

        client_api_key = response_data.get('client_api_key')
        resolved_url = response_data.get('resolved_client_url')

        if not client_api_key or not resolved_url:
            print(f"Error: Server response incomplete. Response: {response.text}")
            return False

        print("Registration successful!")
        print(f"Client registered with address: {resolved_url}")

        config_data = {
            'client_name': client_name,
            'client_api_key': client_api_key,
            'server_url': server_url.rstrip('/'),
            'client_port': client_port,
            'client_listen': client_listen
        }
        with open(config_path, 'w') as f:
            json.dump(config_data, f, indent=4)
        print(f"Client configuration saved to '{config_path}'.")
        return True

    except requests.exceptions.RequestException as e:
        print(f"\nError: Could not connect to the server. Details: {e}")
        return False
    except Exception as e:
        print(f"\nAn unexpected error occurred: {e}")
        if 'response' in locals():
            print(f"Server response: {response.status_code} - {response.text}")
        return False


def handle_install_non_interactive(args):
    """Handles the non-interactive installation process."""
    print("--- Carna Agent Executor Installation (Non-Interactive) ---")
    import shutil
    system = platform.system()
    default_path = DEFAULT_INSTALL_PATH_WINDOWS if system == 'Windows' else DEFAULT_INSTALL_PATH_LINUX_MAC
    install_path = os.path.abspath(args.path or default_path)
    print(f"Installation directory: {install_path}")

    # Step 1: Directory and File Copy
    print(f"\n--- Preparing Installation Directory ---")
    os.makedirs(install_path, exist_ok=True)
    for filename in FILES_TO_COPY:
        source_file = os.path.join(SOURCE_DIR, filename)
        dest_file = os.path.join(install_path, filename)
        if os.path.exists(source_file):
            shutil.copy(source_file, dest_file)
    print("Source files copied.")

    # Step 2: Python Environment
    venv_python = setup_python_env_and_dependencies(install_path)
    if not venv_python:
        print("Python environment setup failed. Aborting.")
        sys.exit(1)

    # Step 3: Client Registration
    if not register_client_non_interactive(args, install_path):
        print("Client registration failed. Aborting.")
        sys.exit(1)

    # Step 4: Service Installation
    if args.no_service:
        print("Service installation skipped as requested.")
        return
    if not is_admin():
        print("\nERROR: Service installation requires admin privileges.")
        sys.exit(1)
        
    if system == 'Linux':
        install_service_linux(venv_python, install_path)
    elif system == 'Darwin':
        install_service_macos(venv_python, install_path)
    elif system == 'Windows':
        install_service_windows(venv_python, install_path)
    else:
        print(f"Unsupported OS for service installation: {system}")
        sys.exit(1)


def setup_python_env_and_dependencies(install_path):
    """Creates a venv, gets python executable, and installs dependencies."""
    print("\n--- Setting up Python Virtual Environment ---")
    
    # 1. Create venv
    try:
        subprocess.run([sys.executable, '-m', 'venv', os.path.join(install_path, 'venv')], check=True, capture_output=True)
        print(f"Virtual environment created in '{os.path.join(install_path, 'venv')}'")
    except subprocess.CalledProcessError as e:
        print(f"ERROR: Failed to create virtual environment.")
        print(f"Stderr: {e.stderr.decode('utf-8')}")
        return None

    # 2. Get venv python path
    venv_python = get_venv_python_path(install_path)
    if not os.path.exists(venv_python):
        print(f"ERROR: Could not find python executable in venv at '{venv_python}'")
        return None
        
    print(f"Virtual environment python found at: {venv_python}")

    # 3. Install dependencies into venv
    requirements_path = os.path.join(install_path, 'requirements.txt')
    print(f"\n--- Installing Python Dependencies from '{requirements_path}' ---")
    try:
        subprocess.run(
            [venv_python, '-m', 'pip', 'install', '-r', requirements_path],
            check=True,
            capture_output=True,
            text=True
        )
        print("Dependencies installed successfully into virtual environment.")
        return venv_python
    except subprocess.CalledProcessError as e:
        print("\nERROR: Failed to install Python dependencies into venv.")
        print(f"pip stdout:\n{e.stdout}")
        print(f"pip stderr:\n{e.stderr}")
        return None
    except FileNotFoundError:
        print("\nERROR: 'pip' command not found inside the virtual environment.")
        return None


# --- Main Execution ---

def main():
    parser = argparse.ArgumentParser(
        description=f'{SERVICE_DISPLAY_NAME} Installer & Service Manager.',
        formatter_class=argparse.RawTextHelpFormatter
    )
    subparsers = parser.add_subparsers(dest='command', help='Available commands')

    # Install command
    p_install = subparsers.add_parser('install', help='Run the installer. Interactive by default, or non-interactive with arguments.')
    p_install.add_argument('--path', help='(Optional) The installation directory. Uses a system default if not provided.')
    p_install.add_argument('--server-url', help='(Non-interactive) Full URL of the Carna server')
    p_install.add_argument('--server-secret', help="(Non-interactive) Server's AGENT_SERVER_SECRET_KEY")
    p_install.add_argument('--client-name', help="(Non-interactive) Name for this client (defaults to hostname)")
    p_install.add_argument('--client-port', default='8123', help="(Non-interactive) Port for this client (default: 8123)")
    p_install.add_argument('--client-listen', default='0.0.0.0', help="(Non-interactive) Listen address for this client (default: 0.0.0.0)")
    p_install.add_argument('--no-service', action='store_true', help="(Non-interactive) Only register, do not install the system service.")
    p_install.add_argument('--force', action='store_true', help=f"(Non-interactive) Overwrite existing '{CONFIG_FILE}' in the installation directory.")
    
    # Uninstall command
    p_uninstall = subparsers.add_parser('uninstall', help='Uninstall the system service and delete files.')
    p_uninstall.add_argument('--path', help='(Optional) The installation directory to remove. Uses default if not provided.')
    
    # Status command
    subparsers.add_parser('status', help='Check the status of the system service.')

    args = parser.parse_args()

    # If no command is given, print help and exit.
    if args.command is None:
        parser.print_help()
        return

    if args.command == 'install':
        # Check if we are in non-interactive mode.
        is_non_interactive = args.server_url and args.server_secret
        if is_non_interactive:
            handle_install_non_interactive(args)
        else:
            # If 'install' is specified but without required args, run interactively.
            handle_install_interactive(args)
    elif args.command == 'uninstall':
        handle_uninstall(args)
    elif args.command == 'status':
        handle_status()

if __name__ == '__main__':
    main()
