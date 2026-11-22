#!/usr/bin/env python3
import os
import sys

from launcher.runtime_env import ensure_venv

if __name__ == "__main__":
    # Honour the checkout's venv even when activated from a plain `python3`.
    ensure_venv()
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)
