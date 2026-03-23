from django.core.management.base import BaseCommand
import traceback

class Command(BaseCommand):
    help = "Manages the Carna client application (register, run, services)."

    def add_arguments(self, parser):
        subparsers = parser.add_subparsers(dest="subcommand", required=True, help="Available subcommands")

        # --- Register Subcommand ---
        p_register = subparsers.add_parser("register", help="Registers the client with the Carna server.")
        p_register.add_argument('--path', help="(Optional) The installation/config directory. Uses a system default if not provided.")
        p_register.add_argument('--server-url', help='(Non-interactive) Full URL of the Carna server.')
        p_register.add_argument('--server-secret', help="(Non-interactive) Server's AGENT_SERVER_SECRET_KEY.")
        p_register.add_argument('--client-name', help="(Non-interactive) Name for this client (defaults to hostname).")
        p_register.add_argument('--client-port', default='8123', help="(Non-interactive) Port for this client (default: 8123).")
        p_register.add_argument('--client-listen', default='0.0.0.0', help="(Non-interactive) Listen address for this client (default: 0.0.0.0).")
        p_register.add_argument('--force', action='store_true', help="(Non-interactive) Overwrite existing configuration file.")

        # --- Run Subcommand ---
        p_run = subparsers.add_parser("run", help="Runs the client executor process.")
        p_run.add_argument('--path', help="(Optional) The installation/config directory to read from.")

        # --- Service Subcommand ---
        p_service = subparsers.add_parser("service", help="Manages the client executor system service.")
        p_service.add_argument("action", choices=["install", "start", "stop", "status", "uninstall"], help="Service action to perform.")
        p_service.add_argument('--path', help="(Optional) The installation/config directory.")

    def handle(self, *args, **options):
        subcommand = options.get("subcommand")
        if subcommand == "register":
            self.handle_register(**options)
        elif subcommand == "run":
            self.handle_run(**options)
        elif subcommand == "service":
            self.handle_service(**options)
        else:
            self.stdout.write(self.style.ERROR(f"Unknown subcommand: {subcommand}"))

    def handle_register(self, **options):
        import os
        import json
        import socket
        import requests
        import platform # Added for OS detection

        self.stdout.write(self.style.SUCCESS("--- Carna Client Registration ---"))

        config_dir = self._get_config_path(options)
        os.makedirs(config_dir, exist_ok=True)
        config_path = os.path.join(config_dir, 'client_config.json')

        # Get OS information
        current_os = platform.system()

        # Check for non-interactive mode
        if options.get('server_url') and options.get('server_secret'):
            self.stdout.write("Running in non-interactive mode...")
            if os.path.exists(config_path) and not options.get('force'):
                self.stdout.write(self.style.ERROR(f"Configuration file already exists at '{config_path}'. Use --force to overwrite."))
                return
            config = self._get_config_from_options(options)
        else:
            self.stdout.write("Running in interactive mode...")
            if os.path.exists(config_path):
                overwrite = input(f"Configuration file found at '{config_path}'. Overwrite? (y/n): ").lower()
                if overwrite != 'y':
                    self.stdout.write("Registration cancelled.")
                    return
            config = self._get_config_interactively()

        # Perform registration with the server
        registration_endpoint = f"{config['server_url'].rstrip('/')}/systems/api/register_client/"
        payload = {
            'server_secret': config['server_secret'], 
            'client_name': config['client_name'], 
            'client_port': config['client_port'],
            'platform_os': current_os # Added operating system here
        }

        self.stdout.write(f"Attempting to register with {registration_endpoint}...")
        try:
            response = requests.post(registration_endpoint, json=payload)
            response.raise_for_status()
            response_data = response.json()

            client_api_key = response_data.get('client_api_key')
            resolved_url = response_data.get('resolved_client_url')

            if not client_api_key or not resolved_url:
                self.stdout.write(self.style.ERROR(f"Server response was incomplete. Response: {response.text}"))
                return

            self.stdout.write(self.style.SUCCESS("Registration successful!"))
            self.stdout.write(f"Client registered with address: {resolved_url}")

            # Prepare final config for JSON file
            final_config = {
                'client_name': config['client_name'],
                'client_api_key': client_api_key,
                'server_url': config['server_url'].rstrip('/'),
                'client_port': config['client_port'],
                'client_listen': config['client_listen'],
                'platform_os': current_os # Also store in local config
            }

            with open(config_path, 'w') as f:
                json.dump(final_config, f, indent=4)
            self.stdout.write(self.style.SUCCESS(f"Client configuration saved to '{config_path}'."))

        except requests.exceptions.RequestException as e:
            self.stdout.write(self.style.ERROR(f"Could not connect to the server. Details: {e} {traceback.format_exc()}"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"An unexpected error occurred: {e} {traceback.format_exc()}"))
            if 'response' in locals():
                self.stdout.write(f"Server response: {response.status_code} - {response.text}")
    
    def _get_config_path(self, options):
        config_info = self._determine_paths_and_permissions(options)
        return config_info['config_dir']
    
    def _get_config_from_options(self, options):
        import socket
        return {
            'server_url': options['server_url'],
            'server_secret': options['server_secret'],
            'client_name': options.get('client_name') or socket.gethostname(),
            'client_port': options.get('client_port', '8123'),
            'client_listen': options.get('client_listen', '0.0.0.0')
        }
    def _get_config_interactively(self):
        import socket
        config = {}
        config['server_url'] = input("Enter the full URL of the Carna server (e.g., http://127.0.0.1:8000): ")
        config['server_secret'] = input("Enter the server's AGENT_SERVER_SECRET_KEY: ")
        default_client_name = socket.gethostname()
        config['client_name'] = input(f"Enter a name for this client (default: '{default_client_name}'): ") or default_client_name
        config['client_port'] = input(f"Enter the port this client will listen on (default: '8123'): ") or '8123'
        config['client_listen'] = input(f"Enter the listen address for this client (default: '0.0.0.0'): ") or '0.0.0.0'
        return config
    def handle_run(self, **options):
        import os
        import json
        import subprocess
        import sys
        from django.conf import settings

        self.stdout.write(self.style.SUCCESS("--- Carna Client Executor ---"))

        config_dir = self._get_config_path(options)
        config_path = os.path.join(config_dir, 'client_config.json')

        if not os.path.exists(config_path):
            self.stdout.write(self.style.ERROR(f"Configuration file not found at '{config_path}'."))
            self.stdout.write(self.style.WARNING("Please run 'manage.py client register' first."))
            return

        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
        except json.JSONDecodeError:
            self.stdout.write(self.style.ERROR(f"Could not parse configuration file at '{config_path}'."))
            return

        # Prepare environment variables for the subprocess
        env = os.environ.copy()
        env["CARNA_CLIENT_API_KEY"] = config.get("client_api_key", "")
        env["CARNA_CLIENT_NAME"] = config.get("client_name", "")
        env["CARNA_CLIENT_LISTEN"] = config.get("client_listen", "0.0.0.0")
        env["CARNA_CLIENT_PORT"] = str(config.get("client_port", 8123))

        # We need to ensure the project's root is in the PYTHONPATH so the client can find the 'tools' module.
        project_root = str(settings.BASE_DIR)
        python_path = env.get("PYTHONPATH", "")
        if project_root not in python_path.split(os.pathsep):
            env["PYTHONPATH"] = f"{project_root}{os.pathsep}{python_path}"

        client_script_path = os.path.join(settings.BASE_DIR, "launcher", "client", "http_client.py")

        command = [
            sys.executable,  # Use the same python interpreter running manage.py
            "-m", "uvicorn",
            "launcher.client.http_client:app",
            "--host", env["CARNA_CLIENT_LISTEN"],
            "--port", env["CARNA_CLIENT_PORT"]
        ]

        self.stdout.write(f"Starting client process...")
        try:
            # Using subprocess.run will block until the user presses Ctrl+C
            process = subprocess.run(command, env=env, check=True)
        except subprocess.CalledProcessError as e:
            self.stdout.write(self.style.ERROR(f"Client process failed with return code {e.returncode}"))
        except KeyboardInterrupt:
            self.stdout.write(self.style.SUCCESS("\nClient process stopped by user."))
        except FileNotFoundError:
            self.stdout.write(self.style.ERROR("Error: 'uvicorn' command not found. Is it installed in your environment?"))
    def handle_service(self, **options):
        import platform
        from launcher.services.linux import LinuxService
        from launcher.services.macos import MacOSService
        from launcher.services.windows import WindowsService
        import sys

        action = options["action"]
        config_info = self._determine_paths_and_permissions(options)

        service_name = "carna_executor"
        display_name = "Carna Client Executor"

        system = config_info['system']
        config_dir = config_info['config_dir']
        is_admin = config_info['is_admin']
        current_user = config_info['current_user']

        service_manager = None

        # Check for admin privileges when installing/uninstalling/starting/stopping system services
        if action in ["install", "uninstall", "start", "stop"]:
            if not is_admin:
                self.stdout.write(self.style.ERROR(f"ERROR: Service '{action}' requires administrative privileges."))
                if system == 'Windows':
                    self.stdout.write(self.style.WARNING("Please re-run this command as an Administrator."))
                else:
                    self.stdout.write(self.style.WARNING("Please re-run this command with 'sudo'."))
                sys.exit(1)

        if system == "Linux":
            service_manager = LinuxService(service_name, display_name, self, config_dir, current_user)
        elif system == "Darwin":
            service_manager = MacOSService(service_name, display_name, self, config_dir, current_user)
        elif system == "Windows":
            service_manager = WindowsService(service_name, display_name, self, config_dir, current_user)
        else:
            self.stdout.write(self.style.ERROR(f"Unsupported operating system for service management: {system}"))
            return

        try:
            if action == "install":
                # Pass the config_dir as --path to the 'client run' command
                service_manager.install(command_args=['client', 'run', '--path', config_dir])
            elif action == "uninstall":
                service_manager.uninstall()
            elif action == "start":
                service_manager.start()
            elif action == "stop":
                service_manager.stop()
            elif action == "status":
                # Status check can be done without admin privileges in some cases,
                # but the service manager will handle specific OS requirements.
                service_manager.status()
        except NotImplementedError:
             self.stdout.write(self.style.ERROR(f"The '{action}' action is not yet implemented for {system}."))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"An error occurred during the '{action}' operation: {e} {traceback.format_exc()}"))
    def _determine_paths_and_permissions(self, options):
        import os
        import platform
        import getpass

        system = platform.system()

        # Determine if running with admin privileges
        is_admin_user = False
        if system == 'Windows':
            try:
                import ctypes
                is_admin_user = (ctypes.windll.shell32.IsUserAnAdmin() != 0)
            except AttributeError:
                pass # Not on Windows or ctypes not available
        else: # Linux/macOS
            is_admin_user = (os.getuid() == 0)

        # Get the effective user for config paths
        # For non-root, this is the current user.
        # For root, if sudo was used, this might be SUDO_USER, otherwise it's root.
        current_user = getpass.getuser()

        # Determine base config directory
        if options.get('path'):
            base_config_dir = os.path.abspath(options['path'])
        elif is_admin_user and system != 'Windows': # Linux/macOS as root
            self.stdout.write(self.style.WARNING("WARNING: You are running this command with administrative privileges (root)."))
            self.stdout.write(self.style.WARNING("The Carna client will have root access to the filesystem and can modify system-wide settings."))
            confirm = input("Do you understand and wish to proceed with root access installation? (y/n): ").lower()
            if confirm != 'y':
                self.stdout.write(self.style.ERROR("Installation cancelled by user."))
                exit(1) # Exit cleanly, not with an error code
            base_config_dir = '/etc/carna_executor'
        elif is_admin_user and system == 'Windows': # Windows as Administrator
            base_config_dir = os.path.join(os.environ.get('ProgramData', r'C:\ProgramData'), 'CarnaExecutor')
        else: # Non-root user
            if system == 'Windows':
                base_config_dir = os.path.join(os.environ.get('APPDATA', r'C:\Users\Default\AppData\Roaming'), 'CarnaExecutor')
            elif system == 'Darwin': # macOS
                base_config_dir = os.path.join(os.path.expanduser('~'), 'Library', 'Application Support', 'CarnaExecutor')
            else: # Linux (non-root)
                base_config_dir = os.path.join(os.path.expanduser('~'), '.config', 'carna_executor')

        return {
            'is_admin': is_admin_user,
            'config_dir': base_config_dir,
            'current_user': current_user,
            'system': system
        }
