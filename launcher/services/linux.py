from .base import BaseService

class LinuxService(BaseService):
    """Manages systemd services on Linux."""

    def install(self, command_args=None):
        import os
        import sys
        import subprocess
        from django.conf import settings

        if command_args is None:
            command_args = ['client', 'run'] # Default to client run

        self.command.stdout.write(self.command.style.SUCCESS(f"--- Installing {self.display_name} systemd service ---"))

        user_to_run_as = self.current_user
        if not user_to_run_as:
            self.command.stdout.write(self.command.style.ERROR("Could not determine the user to run the service. Aborting."))
            return

        python_executable = sys.executable
        manage_py_path = os.path.join(settings.BASE_DIR, "manage.py")

        exec_start_command = [python_executable, manage_py_path] + command_args
        exec_start_str = ' '.join(exec_start_command)

        service_file_content = f"""[Unit]
Description={self.display_name}
After=network.target

[Service]
User={user_to_run_as}
Group={user_to_run_as}
WorkingDirectory={self.config_dir}
ExecStart={exec_start_str}
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
"""
        service_path = f"/etc/systemd/system/{self.service_name}.service"
        try:
            self.command.stdout.write(f"Writing service file to {service_path}...")
            with open(service_path, 'w') as f:
                f.write(service_file_content)

            self.command.stdout.write("Reloading systemd daemon, enabling and starting service...")
            subprocess.run(['systemctl', 'daemon-reload'], check=True, capture_output=True)
            subprocess.run(['systemctl', 'enable', f'{self.service_name}.service'], check=True, capture_output=True)
            subprocess.run(['systemctl', 'start', f'{self.service_name}.service'], check=True, capture_output=True)

            self.command.stdout.write(self.command.style.SUCCESS("
Service installation completed successfully."))
            self.status()

        except (subprocess.CalledProcessError, IOError) as e:
            self.command.stdout.write(self.command.style.ERROR(f"
Error during service installation: {e}"))
            if hasattr(e, 'stderr') and e.stderr:
                self.command.stdout.write(self.command.style.ERROR(f"Stderr: {e.stderr.decode()}"))))

    def uninstall(self, *args, **kwargs):
        import os
        import subprocess

        self.command.stdout.write(self.command.style.SUCCESS(f"--- Uninstalling {self.display_name} systemd service ---"))

        if os.geteuid() != 0:
            self.command.stdout.write(self.command.style.ERROR("This command must be run as root or with sudo."))
            return

        service_path = f"/etc/systemd/system/{self.service_name}.service"
        if not os.path.exists(service_path):
            self.command.stdout.write(self.command.style.WARNING("Service file not found. It may not be installed."))
            return

        try:
            self.command.stdout.write(f"Stopping service '{self.service_name}'...")
            subprocess.run(['systemctl', 'stop', f'{self.service_name}.service'], check=False, capture_output=True)

            self.command.stdout.write(f"Disabling service '{self.service_name}' from starting on boot...")
            subprocess.run(['systemctl', 'disable', f'{self.service_name}.service'], check=False, capture_output=True)

            self.command.stdout.write(f"Removing service file: {service_path}")
            os.remove(service_path)

            self.command.stdout.write("Reloading systemd daemon...")
            subprocess.run(['systemctl', 'daemon-reload'], check=True, capture_output=True)

            self.command.stdout.write(self.command.style.SUCCESS("\nService uninstalled successfully."))

        except subprocess.CalledProcessError as e:
            self.command.stdout.write(self.command.style.ERROR(f"\nError during service uninstallation: {e}"))
            self.command.stdout.write(self.command.style.ERROR(f"Stderr: {e.stderr.decode()}"))
        except IOError as e:
            self.command.stdout.write(self.command.style.ERROR(f"\nFile Error during service uninstallation: {e}"))

    def start(self, *args, **kwargs):
        import os
        import subprocess
        self.command.stdout.write(self.command.style.SUCCESS(f"--- Starting {self.display_name} service ---"))
        if os.geteuid() != 0:
            self.command.stdout.write(self.command.style.ERROR("This command must be run as root or with sudo."))
            return
        try:
            subprocess.run(['systemctl', 'start', f'{self.service_name}.service'], check=True)
            self.command.stdout.write(self.command.style.SUCCESS("Service started successfully."))
        except subprocess.CalledProcessError as e:
            self.command.stdout.write(self.command.style.ERROR(f"Failed to start service: {e}"))
            self.command.stdout.write(self.command.style.ERROR(f"Stderr: {e.stderr.decode()}"))

    def stop(self, *args, **kwargs):
        import os
        import subprocess
        self.command.stdout.write(self.command.style.SUCCESS(f"--- Stopping {self.display_name} service ---"))
        if os.geteuid() != 0:
            self.command.stdout.write(self.command.style.ERROR("This command must be run as root or with sudo."))
            return
        try:
            subprocess.run(['systemctl', 'stop', f'{self.service_name}.service'], check=True)
            self.command.stdout.write(self.command.style.SUCCESS("Service stopped successfully."))
        except subprocess.CalledProcessError as e:
            self.command.stdout.write(self.command.style.ERROR(f"Failed to stop service: {e}"))
            self.command.stdout.write(self.command.style.ERROR(f"Stderr: {e.stderr.decode()}"))

    def status(self, *args, **kwargs):
        import subprocess
        self.command.stdout.write(self.command.style.SUCCESS(f"--- Getting status for {self.display_name} service ---"))
        try:
            subprocess.run(['systemctl', 'status', f'{self.service_name}.service', '--no-pager'])
        except subprocess.CalledProcessError as e:
            # Status returns a non-zero exit code if the service is inactive or not found, which is expected.
            # We don't treat it as a hard error, as systemctl prints the relevant info itself.
            pass
