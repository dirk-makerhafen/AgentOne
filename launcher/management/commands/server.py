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
    help = "Manages the AgentOne server application (setup, run, services)."

    def add_arguments(self, parser):
        subparsers = parser.add_subparsers(dest="subcommand", required=True, help="Available subcommands")
        parser_setup = subparsers.add_parser("setup", help="Guides through the initial server setup.")
        parser_run = subparsers.add_parser("run", help="Runs the server components (Daphne, Celery).")
        parser_update = subparsers.add_parser("update", help="Update AgentOne to the latest version.")
        parser_service = subparsers.add_parser("service", help="Manages the server system service.")
        parser_service.add_argument("action", choices=["install", "start", "stop", "status", "uninstall"], help="Service action to perform.")

    def handle(self, *args, **options):
        subcommand = options["subcommand"]
        if subcommand == "setup":
            self.handle_setup(**options)
        elif subcommand == "run":
            self.handle_run(**options)
        elif subcommand == "update":
            self.handle_update(**options)
        elif subcommand == "service":
            self.handle_service(**options)
        else:
            self.stdout.write(self.style.ERROR(f"Unknown subcommand: {subcommand}"))

    # ------------------------------------------------------------------
    # Setup
    # ------------------------------------------------------------------

    def handle_setup(self, **options):
        import secrets

        self.stdout.write(self.style.SUCCESS("--- AgentOne Server Setup ---\n"))

        db_config = self._ask_database()
        redis_url = self._ask("Redis URL", "redis://localhost:6379/1")
        listen_addr = self._ask("HTTP listen address", "0.0.0.0")
        listen_port = self._ask("HTTP listen port", "8001")
        secret_key = secrets.token_urlsafe(50)
        client_key = secrets.token_urlsafe(16)

        generate_cert = self._ask_yes_no(
            "Generate self-signed TLS certificate (cert.pem, key.pem)",
            default=True,
        )

        self.stdout.write()
        self._write_local_config(db_config, redis_url, listen_addr, listen_port, secret_key, client_key)
        self.stdout.write()

        if generate_cert:
            self.generate_self_signed_cert()
            self.stdout.write(self.style.SUCCESS("TLS certificate generated (cert.pem, key.pem)."))

        self._configure_database(db_config)
        self._run_migrations()
        self._create_superuser_if_needed()

        self.stdout.write(self.style.SUCCESS("\nSetup complete!"))
        self.stdout.write(self.style.WARNING(
            "Run 'python3 manage.py server run' to start the server."
        ))

    # ------------------------------------------------------------------
    # Database configuration
    # ------------------------------------------------------------------

    def _ask_database(self):
        self.stdout.write("Database backend:")
        self.stdout.write("  1) SQLite  (simple, no setup — good for development)")
        self.stdout.write("  2) MySQL   (production-ready, requires MySQL/MariaDB server)")

        choice = self._ask("Choose [1/2]", "1")

        if choice == "2":
            return self._ask_mysql()
        return self._ask_sqlite()

    def _ask_sqlite(self):
        import os
        from django.conf import settings
        default_path = os.path.join(settings.BASE_DIR, "db.sqlite3")
        path = self._ask("SQLite database path", default_path)
        return {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": path,
        }

    def _ask_mysql(self):
        config = {
            "ENGINE": "django.db.backends.mysql",
            "HOST": self._ask("MySQL host", "localhost"),
            "PORT": self._ask("MySQL port", "3306"),
            "NAME": self._ask("Database name", "AgentOne_v3"),
        }
        user = self._ask("MySQL user (leave blank for socket auth)", default=None)
        if user:
            config["USER"] = user
            password = self._ask_password("MySQL password (leave blank for no password)")
            if password:
                config["PASSWORD"] = password
        config["OPTIONS"] = {
            "init_command": "SET sql_mode='STRICT_TRANS_TABLES'"
        }
        return config

    # ------------------------------------------------------------------
    # User prompts
    # ------------------------------------------------------------------

    def _ask(self, question, default=None):
        if default is not None:
            prompt = f"  {question} [{self.style.SUCCESS(default)}]: "
        else:
            prompt = f"  {question}: "
        answer = input(prompt).strip()
        return answer if answer else (default or "")

    def _ask_password(self, question):
        return input(f"  {question}: ").strip()

    def _ask_yes_no(self, question, default=True):
        hint = "Y/n" if default else "y/N"
        prompt = f"  {question} [{self.style.SUCCESS(hint)}]: "
        answer = input(prompt).strip().lower()
        if not answer:
            return default
        return answer.startswith("y")

    # ------------------------------------------------------------------
    # Write settings_local.py as valid Python
    # ------------------------------------------------------------------

    def _write_local_config(self, db_config, redis_url, listen_addr, listen_port, secret_key, client_key):
        import os
        from django.conf import settings

        path = os.path.join(settings.BASE_DIR, "config", "settings_local.py")

        lines = [
            "# This file is automatically generated by 'python3 manage.py server setup'.",
            "# It overrides defaults in config/settings.py.",
            "",
            "import os",
            "",
            "# ---------------------------------------------------------------------------",
            "# Security",
            "# ---------------------------------------------------------------------------",
            f"SECRET_KEY = {secret_key!r}",
            f"AGENT_SERVER_SECRET_KEY = {client_key!r}",
            "DEBUG = False",
            'ALLOWED_HOSTS = ["*"]',
            "",
            "# ---------------------------------------------------------------------------",
            "# Database",
            "# ---------------------------------------------------------------------------",
            "DATABASES = {",
            '    "default": {',
        ]
        for key, value in db_config.items():
            if key == "OPTIONS":
                lines.append(f"        \"OPTIONS\": {{")
                lines.append(f"            \"init_command\": \"SET sql_mode='STRICT_TRANS_TABLES'\",")
                lines.append(f"        }},")
            else:
                lines.append(f"        {key!r}: {value!r},")
        lines += [
            "    }",
            "}",
            "",
            "",
            "# ---------------------------------------------------------------------------",
            "# Redis (used for cache, channels, Celery broker/backend)",
            "# ---------------------------------------------------------------------------",
            f"REDIS_URL = {redis_url!r}",
            "",
            "# ---------------------------------------------------------------------------",
            "# HTTP server",
            "# ---------------------------------------------------------------------------",
            f"LISTEN_ADDRESS = {listen_addr!r}",
            f"LISTEN_PORT = {listen_port!r}",
            "",
        ]

        content = "\n".join(lines) + "\n"

        try:
            with open(path, "w") as f:
                f.write(content)
            self.stdout.write(self.style.SUCCESS(f"Configuration written to {path}"))
        except OSError as e:
            self.stdout.write(self.style.ERROR(f"Failed to write {path}: {e}"))

    # ------------------------------------------------------------------
    # Superuser creation
    # ------------------------------------------------------------------

    def _configure_database(self, db_config):
        """Point the running Django process at the newly-configured database."""
        from django.conf import settings
        from django.db import connections
        # Purge cached connections so they are recreated with the new config
        connections.close_all()
        try:
            del connections["default"]
        except KeyError:
            pass
        # Merge into existing dict to preserve required keys (TIME_ZONE, etc.)
        settings.DATABASES["default"].update(db_config)

    def _run_migrations(self):
        from django.core.management import call_command
        self.stdout.write("\nApplying database migrations...")
        try:
            call_command("migrate", interactive=False, verbosity=0)
            self.stdout.write(self.style.SUCCESS("Database migrations applied."))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Migration failed: {e}"))
            self.stdout.write(self.style.WARNING(
                "You can retry with 'python3 manage.py migrate'."
            ))

    def _create_superuser_if_needed(self):
        from django.contrib.auth import get_user_model
        User = get_user_model()
        if User.objects.filter(is_superuser=True).exists():
            self.stdout.write("\nSuperuser already exists. Skipping creation.\n")
            return

        self.stdout.write(self.style.WARNING("\nNo superuser found. Create one now?"))
        if not self._ask_yes_no("Create superuser", default=True):
            return

        try:
            username = self._ask("Admin username", "admin")
            email = self._ask("Admin email", "admin@localhost")
            password = self._ask_password("Admin password (leave blank for a random one)")

            if not password:
                import secrets
                password = secrets.token_urlsafe(16)
                self.stdout.write(f"  Generated password: {self.style.SUCCESS(password)}")

            User.objects.create_superuser(username=username, email=email, password=password)
            self.stdout.write(self.style.SUCCESS(f"Superuser '{username}' created."))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Could not create superuser: {e}"))
            self.stdout.write(self.style.WARNING(
                "You can create one later with 'python3 manage.py createsuperuser'."
            ))

    def handle_run(self, **options):
        import subprocess
        import sys
        import os
        import time
        import select
        from django.conf import settings

        self.stdout.write(self.style.SUCCESS("--- AgentOne Server ---"))

        listen_address = getattr(settings, 'LISTEN_ADDRESS', '0.0.0.0')
        listen_port = getattr(settings, 'LISTEN_PORT', '8001')

        self.stdout.write(f"Starting server components...")
        self.stdout.write(f" - Daphne listening on: {self.style.SUCCESS(listen_address + ':' + listen_port)}")
        self.stdout.write(f" - Celery Worker & Beat starting...")
        self.stdout.write(f"Type {self.style.ERROR('.exit')} and press Enter to quit.")

        from server.tasks.recovery_scheduler import startup_cleanup
        startup_cleanup()
        self.stdout.write(" - Startup cleanup queued...")
        log_level = "DEBUG"
        commands = {
            "daphne":        ['daphne', '-b', listen_address, "-e", "tcp:8003", "-b", "0.0.0.0", "-p","8002", "-e", f"ssl:{listen_port}:privateKey=key.pem:certKey=cert.pem", 'config.asgi:application'],
            "celery_worker": ['celery', '-A', 'config', 'worker', '-l', log_level, '-E', '--concurrency', '5'],
            "celery_beat":   ['celery', '-A', 'config', 'beat',   '-l', log_level]
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

    def handle_update(self, **options):
        import subprocess
        import sys
        from pathlib import Path
        from django.conf import settings

        repo_path = Path(settings.BASE_DIR)
        self.stdout.write(self.style.SUCCESS("--- AgentOne Update ---\n"))

        # 1. Verify we are in a git repo
        if not (repo_path / ".git").is_dir():
            self.stdout.write(self.style.ERROR(
                "Not a git repository. AgentOne must be installed via git for updates."
            ))
            return

        # 2. Check for uncommitted changes
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=repo_path, capture_output=True, text=True,
        )
        if result.stdout.strip():
            self.stdout.write(self.style.WARNING(
                "You have uncommitted changes. Stash or commit them first, "
                "then retry."
            ))
            self.stdout.write(result.stdout)
            return

        # 3. Fetch remote tags
        self.stdout.write("Fetching remote...")
        subprocess.run(
            ["git", "fetch", "--tags", "--quiet", "origin"],
            cwd=repo_path, check=True, capture_output=True, text=True,
        )

        # 4. Check current vs latest
        current = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=repo_path, capture_output=True, text=True,
        ).stdout.strip()

        behind = subprocess.run(
            ["git", "rev-list", "--count", "HEAD..origin/HEAD"],
            cwd=repo_path, capture_output=True, text=True,
        ).stdout.strip()

        self.stdout.write(f"  Current commit: {self.style.SUCCESS(current)}")
        if behind and behind != "0":
            self.stdout.write(f"  Behind remote: {self.style.WARNING(behind + ' commits')}")
        else:
            self.stdout.write("  Already up to date with remote.")
            return

        # 5. Pull latest
        self.stdout.write("Pulling latest code...")
        subprocess.run(
            ["git", "pull", "--quiet", "--ff-only", "origin"],
            cwd=repo_path, check=True, capture_output=True, text=True,
        )

        new_current = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=repo_path, capture_output=True, text=True,
        ).stdout.strip()
        self.stdout.write(f"  Updated to: {self.style.SUCCESS(new_current)}")

        # 6. Install / update dependencies
        self.stdout.write("Updating Python dependencies...")
        req_path = repo_path / "requirements.txt"
        if req_path.exists():
            result = subprocess.run(
                [sys.executable, "-m", "pip", "install", "-r", str(req_path)],
                capture_output=True, text=True,
            )
            if result.returncode == 0:
                self.stdout.write(self.style.SUCCESS("  Dependencies updated."))
            else:
                self.stdout.write(self.style.WARNING(
                    f"  pip install had issues:\n{result.stderr[:500]}"
                ))

        # 7. Run migrations
        self.stdout.write("Applying database migrations...")
        try:
            from django.core.management import call_command
            call_command("migrate", interactive=False, verbosity=0)
            self.stdout.write(self.style.SUCCESS("  Migrations applied."))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"  Migration failed: {e}"))
            self.stdout.write(self.style.WARNING(
                "You can retry with 'python3 manage.py migrate'."
            ))

        # 8. Reload manifests
        self.stdout.write("Reloading manifests...")
        try:
            from registry.management.commands.reload_all import run_reload_all
            result = run_reload_all(str(repo_path))
            self.stdout.write(result["summary"])
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"  Reload failed: {e}"))

        self.stdout.write(self.style.SUCCESS("\nUpdate complete!"))

    def handle_service(self, **options):
        import platform
        from launcher.services.linux import LinuxService
        from launcher.services.macos import MacOSService
        from launcher.services.windows import WindowsService

        action = options["action"]
        service_name = "agentone_server"
        display_name = "AgentOne Server"

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

