from .base import BaseService

class MacOSService(BaseService):
    """Manages launchd services on macOS."""

    def install(self, command_args=None):
        import os
        import sys
        import subprocess
        from django.conf import settings

        if command_args is None:
            command_args = ['server', 'run']

        self.command.stdout.write(self.command.style.SUCCESS(f"--- Installing {self.display_name} launchd service ---"))

        if os.geteuid() != 0:
            self.command.stdout.write(self.command.style.ERROR("This command must be run as root or with sudo."))
            return

        python_executable = sys.executable
        manage_py_path = os.path.join(settings.BASE_DIR, "manage.py")

        program_arguments = [python_executable, manage_py_path] + command_args
        program_arguments_xml = "\n".join(f"        <string>{arg}</string>" for arg in program_arguments)

        service_label = f"com.carna.{self.service_name}"
        plist_path = f"/Library/LaunchDaemons/{service_label}.plist"

        plist_content = f"""<?xml version="1.0" encoding="UTF-8"?>
    <!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
    <plist version="1.0">
    <dict>
        <key>Label</key>
        <string>{service_label}</string>
        <key>ProgramArguments</key>
        <array>
    {program_arguments_xml}
        </array>
        <key>WorkingDirectory</key>
        <string>{settings.BASE_DIR}</string>
        <key>RunAtLoad</key>
        <true/>
        <key>KeepAlive</key>
        <true/>
        <key>StandardOutPath</key>
        <string>/tmp/{self.service_name}.out.log</string>
        <key>StandardErrorPath</key>
        <string>/tmp/{self.service_name}.err.log</string>
    </dict>
    </plist>
    """
        try:
            self.command.stdout.write(f"Writing launchd plist to {plist_path}...")
            with open(plist_path, 'w') as f:
                f.write(plist_content)

            subprocess.run(['chown', 'root:wheel', plist_path], check=True, capture_output=True)
            subprocess.run(['chmod', '644', plist_path], check=True, capture_output=True)

            self.command.stdout.write("Loading and starting service with launchctl...")
            subprocess.run(['launchctl', 'load', '-w', plist_path], check=True, capture_output=True)

            self.command.stdout.write(self.command.style.SUCCESS("\nService installation completed successfully."))
            self.status()

        except (subprocess.CalledProcessError, IOError) as e:
            self.command.stdout.write(self.command.style.ERROR(f"\nError during service installation: {e}"))
            if hasattr(e, 'stderr') and e.stderr:
                self.command.stdout.write(self.command.style.ERROR(f"Stderr: {e.stderr.decode()}"))

    def uninstall(self, *args, **kwargs):
        import os
        import subprocess
        self.command.stdout.write(self.command.style.SUCCESS(f"--- Uninstalling {self.display_name} launchd service ---"))

        if os.geteuid() != 0:
            self.command.stdout.write(self.command.style.ERROR("This command must be run as root or with sudo."))
            return

        service_label = f"com.carna.{self.service_name}"
        plist_path = f"/Library/LaunchDaemons/{service_label}.plist"

        if not os.path.exists(plist_path):
            self.command.stdout.write(self.command.style.WARNING("Service file not found. It may not be installed."))
            return

        try:
            self.command.stdout.write(f"Unloading service '{service_label}'...")
            subprocess.run(['launchctl', 'unload', '-w', plist_path], check=False, capture_output=True)

            self.command.stdout.write(f"Removing service file: {plist_path}")
            os.remove(plist_path)

            self.command.stdout.write(self.command.style.SUCCESS("\nService uninstalled successfully."))

        except (subprocess.CalledProcessError, IOError) as e:
            self.command.stdout.write(self.command.style.ERROR(f"\nError during service uninstallation: {e}"))
            if hasattr(e, 'stderr') and e.stderr:
                self.command.stdout.write(self.command.style.ERROR(f"Stderr: {e.stderr.decode()}"))

    def start(self, *args, **kwargs):
        import os
        import subprocess
        self.command.stdout.write(self.command.style.SUCCESS(f"--- Starting {self.display_name} service ---"))
        if os.geteuid() != 0:
            self.command.stdout.write(self.command.style.ERROR("This command must be run as root or with sudo."))
            return

        service_label = f"com.carna.{self.service_name}"
        try:
            subprocess.run(['launchctl', 'start', service_label], check=True, capture_output=True)
            self.command.stdout.write(self.command.style.SUCCESS("Service started successfully."))
        except subprocess.CalledProcessError as e:
            self.command.stdout.write(self.command.style.ERROR(f"Failed to start service: {e}"))
            self.command.stdout.write(self.command.style.ERROR(f"Stderr: {e.stderr.decode()}"))
            self.command.stdout.write(self.command.style.WARNING("Is the service installed? Try 'launchctl list | grep carna'"))

    def stop(self, *args, **kwargs):
        import os
        import subprocess
        self.command.stdout.write(self.command.style.SUCCESS(f"--- Stopping {self.display_name} service ---"))
        if os.geteuid() != 0:
            self.command.stdout.write(self.command.style.ERROR("This command must be run as root or with sudo."))
            return

        service_label = f"com.carna.{self.service_name}"
        try:
            subprocess.run(['launchctl', 'stop', service_label], check=True, capture_output=True)
            self.command.stdout.write(self.command.style.SUCCESS("Service stopped successfully."))
        except subprocess.CalledProcessError as e:
            self.command.stdout.write(self.command.style.ERROR(f"Failed to stop service: {e}"))
            self.command.stdout.write(self.command.style.ERROR(f"Stderr: {e.stderr.decode()}"))
            self.command.stdout.write(self.command.style.WARNING("Is the service running? Try 'launchctl list | grep carna'"))

    def status(self, *args, **kwargs):
        import subprocess
        self.command.stdout.write(self.command.style.SUCCESS(f"--- Getting status for {self.display_name} service ---"))

        service_label = f"com.carna.{self.service_name}"
        try:
            result = subprocess.run(['launchctl', 'list'], capture_output=True, text=True, check=True)
            service_found = False
            for line in result.stdout.splitlines():
                if service_label in line:
                    self.command.stdout.write("Service is loaded:")
                    self.command.stdout.write(line)
                    service_found = True
                    break
            if not service_found:
                self.command.stdout.write(self.command.style.WARNING("Service is not currently loaded."))
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            self.command.stdout.write(self.command.style.ERROR(f"Could not check service status: {e}"))
