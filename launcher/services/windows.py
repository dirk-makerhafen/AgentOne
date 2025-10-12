from .base import BaseService

class WindowsService(BaseService):
    """Manages services on Windows."""

    def install(self, command_args=None):
        import os
        import sys
        import subprocess
        from django.conf import settings

        if command_args is None:
            command_args = ['server', 'run']

        self.command.stdout.write(self.command.style.SUCCESS(f"--- Installing {self.display_name} Windows service ---"))

        python_executable = sys.executable
        manage_py_path = os.path.join(settings.BASE_DIR, "manage.py")

        # The service needs to run the manage.py client command from the config directory
        command_str = ' '.join(command_args)
        # Ensure that the service's working directory is set to self.config_dir
        # The binPath should contain the Python executable and manage.py
        bin_path = f'"{python_executable}" "{manage_py_path}" {command_str}'
        
        try:
            self.command.stdout.write(f"Creating service '{self.service_name}'...")
            # Note: For Windows services created with `sc create`, the working directory is typically
            # the system directory or the directory where sc.exe is run from.
            # It's better to manage the working directory via the command itself or a wrapper script.
            # However, `sc.exe` does not have a direct 'WorkingDirectory' parameter like systemd/launchd.
            # The client `handle_run` command receives the --path, so it will use the correct config dir.
            subprocess.run([
                'sc', 'create', self.service_name,
                f'binPath= {bin_path}',
                f'DisplayName= "{self.display_name}"',
                'start=', 'auto'
            ], check=True, capture_output=True, text=True)

            subprocess.run([
                'sc', 'description', self.service_name, 
                f'"{self.display_name} - Manages the Carna application."'
            ], check=False)

            self.command.stdout.write("Starting service...")
            subprocess.run(['sc', 'start', self.service_name], check=True, capture_output=True, text=True)

            self.command.stdout.write(self.command.style.SUCCESS("\nService installation completed successfully."))
            self.status()

        except subprocess.CalledProcessError as e:
            self.command.stdout.write(self.command.style.ERROR(f"\nError during service installation: {e}"))
            self.command.stdout.write(self.command.style.ERROR(f"Stderr: {e.stderr}"))
        except FileNotFoundError:
            self.command.stdout.write(self.command.style.ERROR("\nError: 'sc.exe' command not found. Is it in your system's PATH?"))

    def uninstall(self, *args, **kwargs):
        import subprocess
        self.command.stdout.write(self.command.style.SUCCESS(f"--- Uninstalling {self.display_name} Windows service ---"))
        try:
            self.command.stdout.write(f"Stopping {self.service_name} service...")
            subprocess.run(['sc', 'stop', self.service_name], check=False, capture_output=True)

            self.command.stdout.write(f"Deleting {self.service_name} service...")
            result = subprocess.run(['sc', 'delete', self.service_name], check=True, capture_output=True, text=True)

            if "service does not exist" in result.stderr.lower():
                 self.command.stdout.write("Service does not appear to be installed. Nothing to do.")
                 return

            self.command.stdout.write(self.command.style.SUCCESS("\nService uninstalled successfully."))

        except subprocess.CalledProcessError as e:
            stderr_output = e.stderr.lower()
            if "does not exist" in stderr_output:
                 self.command.stdout.write("Service does not appear to be installed. Nothing to do.")
            else:
                self.command.stdout.write(self.command.style.ERROR(f"\nAn error occurred during uninstallation: {e}"))
                self.command.stdout.write(self.command.style.ERROR(f"Stderr: {e.stderr}"))
        except FileNotFoundError:
            self.command.stdout.write(self.command.style.ERROR("\nError: 'sc.exe' command not found."))

    def start(self, *args, **kwargs):
        import subprocess
        self.command.stdout.write(self.command.style.SUCCESS(f"--- Starting {self.display_name} service ---"))
        try:
            subprocess.run(['sc', 'start', self.service_name], check=True, capture_output=True, text=True)
            self.command.stdout.write(self.command.style.SUCCESS("Service started successfully."))
        except subprocess.CalledProcessError as e:
            self.command.stdout.write(self.command.style.ERROR(f"Failed to start service: {e}"))
            self.command.stdout.write(self.command.style.ERROR(f"Stderr: {e.stderr}"))

    def stop(self, *args, **kwargs):
        import subprocess
        self.command.stdout.write(self.command.style.SUCCESS(f"--- Stopping {self.display_name} service ---"))
        try:
            subprocess.run(['sc', 'stop', self.service_name], check=True, capture_output=True, text=True)
            self.command.stdout.write(self.command.style.SUCCESS("Service stopped successfully."))
        except subprocess.CalledProcessError as e:
            self.command.stdout.write(self.command.style.ERROR(f"Failed to stop service: {e}"))
            self.command.stdout.write(self.command.style.ERROR(f"Stderr: {e.stderr}"))

    def status(self, *args, **kwargs):
        import subprocess
        self.command.stdout.write(self.command.style.SUCCESS(f"--- Getting status for {self.display_name} service ---"))
        try:
            result = subprocess.run(['sc', 'query', self.service_name], check=True, capture_output=True, text=True)
            self.command.stdout.write(result.stdout)
        except subprocess.CalledProcessError:
            self.command.stdout.write(self.command.style.WARNING(f"Service '{self.service_name}' does not appear to be installed or is in a failed state."))
        except FileNotFoundError:
            self.command.stdout.write(self.command.style.ERROR("\nError: 'sc.exe' command not found."))
