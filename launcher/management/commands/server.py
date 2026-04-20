import datetime
import os
import socket
from threading import Thread
import time

from django.core.management.base import BaseCommand
import traceback
from flask import Flask, render_template_string, jsonify
from flask_sock import Sock
from zeroconf import ServiceInfo, Zeroconf

NAME = "AgentOne"


class Command(BaseCommand):
    help = "Manages the Carna server application (setup, run, services)."

    def add_arguments(self, parser):
        subparsers = parser.add_subparsers(dest="subcommand", required=True, help="Available subcommands")
        parser_setup = subparsers.add_parser("setup", help="Guides through the initial server setup.")
        parser_run = subparsers.add_parser("run", help="Runs the server components (Daphne, Celery).")
        parser_service = subparsers.add_parser("service", help="Manages the server system service.")
        parser_service.add_argument("action", choices=["install", "start", "stop", "status", "uninstall"], help="Service action to perform.")

    def handle(self, *args, **options):
        subcommand = options["subcommand"]
        if subcommand == "setup":
            self.handle_setup(**options)
        elif subcommand == "run":
            self.handle_run(**options)
        elif subcommand == "service":
            self.handle_service(**options)
        else:
            self.stdout.write(self.style.ERROR(f"Unknown subcommand: {subcommand}"))

    def handle_setup(self, **options):
        import os
        import secrets
        import string
        from django.conf import settings
        from django.contrib.auth import get_user_model
        from django.core.management import call_command

        self.stdout.write(self.style.SUCCESS("--- Carna Server Setup ---"))
        config_path = os.path.join(settings.BASE_DIR, 'config', 'settings_local.py')
        config = self._read_local_config(config_path)

        config['LISTEN_ADDRESS'] = self._ask_question("Listen Address", config.get('LISTEN_ADDRESS', '0.0.0.0'))
        config['LISTEN_PORT'] = self._ask_question("Listen Port", config.get('LISTEN_PORT', '8001'))

        default_client_key = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(8))
        config['AGENT_SERVER_SECRET_KEY'] = self._ask_question("Client Registration Key", config.get('AGENT_SERVER_SECRET_KEY', default_client_key))
        config['REDIS_URL'] = self._ask_question("Redis URL", config.get('REDIS_URL', 'redis://localhost:6379/'))

        if 'SECRET_KEY' not in config or not config['SECRET_KEY']:
            self.stdout.write("\nGenerating new SECRET_KEY...")
            config['SECRET_KEY'] = secrets.token_urlsafe(50)
            self.stdout.write(self.style.SUCCESS("SECRET_KEY generated."))

        self.generate_self_signed_cert()
        self._create_superuser_if_needed()
        self._write_local_config(config_path, config)

        self.stdout.write(self.style.SUCCESS(f"\nConfiguration saved to {config_path}"))
        self.stdout.write(self.style.WARNING("Please restart the server for the new settings to take effect."))

    def _read_local_config(self, path):
        import os
        config = {}
        if not os.path.exists(path):
            return config

        self.stdout.write(f"Reading existing configuration from {path}...")
        try:
            with open(path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue

                    # Remove inline comments before processing
                    if '#' in line:
                        line = line.split('#', 1)[0].strip()
                        if not line:
                            continue

                    if '=' not in line:
                        continue

                    key, value = line.split('=', 1)
                    key = key.strip()
                    value = value.strip()

                    # Robustly strip quotes
                    if (value.startswith("'") and value.endswith("'")) or \
                       (value.startswith('"') and value.endswith('"')):
                        value = value[1:-1]

                    config[key] = value
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Could not read config file: {e} {traceback.format_exc()}"))
        return config

    def _ask_question(self, question, default):
        prompt = f"{question} (default: {self.style.SUCCESS(default)}): "
        answer = input(prompt)
        return answer or default

    def _create_superuser_if_needed(self):
        from django.contrib.auth import get_user_model
        from django.core.management import call_command
        User = get_user_model()
        if User.objects.filter(is_superuser=True).exists():
            self.stdout.write("\nSuperuser already exists. Skipping creation.")
            return

        self.stdout.write(self.style.WARNING("\nNo superuser found. Let's create one."))
        try:
            call_command('createsuperuser', interactive=True)
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Could not create superuser: {e} {traceback.format_exc()}"))

    def _write_local_config(self, path, config):
        self.stdout.write(f"\nWriting configuration to {path}...")
        content = "# This file is automatically generated by 'manage.py server setup'.\n"
        content += "# Do not edit it manually unless you know what you are doing.\n\n"

        for key, value in config.items():
            content += f"{key} = '{value}'\n"

        try:
            with open(path, 'w') as f:
                f.write(content)
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Failed to write config file: {e} {traceback.format_exc()}"))

    def handle_run(self, **options):
        import subprocess
        import sys
        import os
        import time
        import select
        from django.conf import settings

        self.stdout.write(self.style.SUCCESS("--- AgentOne Server ---"))

        config_path = os.path.join(settings.BASE_DIR, 'config', 'settings_local.py')
        config = self._read_local_config(config_path)

        listen_address = config.get('LISTEN_ADDRESS', '0.0.0.0')
        listen_port = config.get('LISTEN_PORT', '8004')

        self.stdout.write(f"Starting server components...")
        self.stdout.write(f" - Daphne listening on: {self.style.SUCCESS(listen_address + ':' + listen_port)}")
        self.stdout.write(f" - Celery Worker & Beat starting...")
        self.stdout.write(f"Type {self.style.ERROR('.exit')} and press Enter to quit.")
        log_level = "DEBUG"
        commands = {
            "daphne": ['daphne', '-b', listen_address, "-e", f"ssl:{listen_port}:privateKey=key.pem:certKey=cert.pem", 'config.asgi:application'],
            "celery_worker": ['celery', '-A', 'config', 'worker', '-l', log_level, '-E', '--concurrency', '2'],
            "celery_beat": ['celery', '-A', 'config', 'beat', '-l', log_level]
        }

        mdns_thread = Thread(target=self.run_zeroconf, daemon=True)
        mdns_thread.start()

        processes = {}
        try:
            for name, cmd in commands.items():
                self.stdout.write(f"Starting {name}...")
                proc = subprocess.Popen(cmd, stdout=sys.stdout, stderr=sys.stderr)
                processes[name] = proc
                time.sleep(1) # Stagger process starts slightly

            # Monitor processes
            while True:
                for name, proc in processes.items():
                    if proc.poll() is not None:
                        self.stdout.write(self.style.ERROR(f"{name} process terminated unexpectedly. Shutting down."))
                        raise KeyboardInterrupt # Trigger the finally block

                # Check for user input without blocking
                if sys.platform != 'win32': # select() doesn't work on Windows for file descriptors
                    if sys.stdin in select.select([sys.stdin], [], [], 0)[0]:
                        line = sys.stdin.readline()
                        if '.exit' in line:
                            self.stdout.write(self.style.WARNING("Exit command received. Shutting down..."))
                            raise KeyboardInterrupt
                else:
                    # Windows doesn't support select on stdin this way.
                    # A more complex solution (e.g., threading) is needed for non-blocking input on Windows.
                    # For now, we will rely on Ctrl+C.
                    pass

                time.sleep(0.5)

        except KeyboardInterrupt:
            self.stdout.write("\nShutting down all processes gracefully (Ctrl+C received)...")
        finally:
            for name, proc in processes.items():
                if proc.poll() is None: # If the process is still running
                    self.stdout.write(f"Terminating {name} (PID: {proc.pid})...")
                    proc.terminate()

            # Wait for all processes to terminate
            for name, proc in processes.items():
                proc.wait()
                self.stdout.write(f"{name} stopped.")

            self.stdout.write(self.style.SUCCESS("All server components shut down."))

    def handle_service(self, **options):
        import platform
        from launcher.services.linux import LinuxService
        from launcher.services.macos import MacOSService
        from launcher.services.windows import WindowsService

        action = options["action"]
        service_name = "carna_server"
        display_name = "Carna Server"

        system = platform.system()
        service_manager = None

        if system == "Linux":
            service_manager = LinuxService(service_name, display_name, self)
        elif system == "Darwin":
            service_manager = MacOSService(service_name, display_name, self)
        elif system == "Windows":
            service_manager = WindowsService(service_name, display_name, self)
        else:
            self.stdout.write(self.style.ERROR(f"Unsupported operating system for service management: {system}"))
            return

        try:
            # We can pass the command's stdout/style directly if needed by the methods
            if action == "install":
                service_manager.install()
            elif action == "uninstall":
                service_manager.uninstall()
            elif action == "start":
                service_manager.start()
            elif action == "stop":
                service_manager.stop()
            elif action == "status":
                service_manager.status()
        except NotImplementedError:
             self.stdout.write(self.style.ERROR(f"The '{action}' action is not yet implemented for {system}."))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"An error occurred during the '{action}' operation: {e} {traceback.format_exc()}"))

    def generate_self_signed_cert(self):
        cert_path, key_path = "cert.pem", "key.pem"
        if os.path.exists(cert_path) and os.path.exists(key_path):
            return (cert_path, key_path)
        
        from cryptography import x509
        from cryptography.x509.oid import NameOID
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import rsa

        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        with open(key_path, "wb") as f:
            f.write(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.TraditionalOpenSSL, serialization.NoEncryption()))
       
        subject = issuer = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, NAME)])
        cert = x509.CertificateBuilder().subject_name(subject).issuer_name(issuer).public_key(key.public_key()).serial_number(x509.random_serial_number()).not_valid_before(datetime.datetime.utcnow()).not_valid_after(datetime.datetime.utcnow() + datetime.timedelta(days=3650)).add_extension(x509.SubjectAlternativeName([x509.DNSName(NAME), x509.DNSName("localhost")]), critical=False).sign(key, hashes.SHA256())
        with open(cert_path, "wb") as f:
            f.write(cert.public_bytes(serialization.Encoding.PEM))
        return (cert_path, key_path)

    def run_zeroconf(self):
        zeroconf = Zeroconf()
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.connect(("8.8.8.8", 80))
        ip_address = s.getsockname()[0]; s.close()
        info = ServiceInfo("_https._tcp.local.", f"{NAME}._https._tcp.local.",
            addresses=[socket.inet_aton(ip_address)], port=5000, server=f"{NAME}.local.")
        zeroconf.register_service(info)
        try:
            while True: time.sleep(1)
        finally:
            zeroconf.unregister_service(info); zeroconf.close()

