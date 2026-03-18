import hashlib
from importlib.machinery import SourceFileLoader
import os
import sys
import time
import traceback
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from pathlib import Path
from contextlib import contextmanager

#from agents.agent_config import AgentConfig
@contextmanager
def temp_sys_path(path):
    """Temporarily adds a directory to sys.path."""
    path = str(path)
    if path not in sys.path:
        sys.path.insert(0, path)
        try:
            yield
        finally:
            sys.path.remove(path)
    else:
        yield

class Command(BaseCommand):
    help = 'Loads and executes a Python file (e.g., config or bootstrap script) inside the running Django application context.'

    def add_arguments(self, parser):
        parser.add_argument('filename', type=str, help='The path to the Python file to execute.')


    def load_dynamic_file(self, file_path):
     
        filename = Path(file_path)
        namespace_root = "dynamic_scripts"

        # ensure root exists in sys.modules so "dynamic_scripts.*" works
        if namespace_root not in sys.modules:
            pkg = type(sys)(namespace_root)
            pkg.__path__ = []  # mark as namespace package
            sys.modules[namespace_root] = pkg

        # allow multiple versions by adding hash
        hash_id = hashlib.sha1(str(filename).encode()).hexdigest()[:8]
        module_name = f"dynamic_scripts.{filename.stem}"
        loader = SourceFileLoader(module_name, str(filename))
        with temp_sys_path(filename.parent):
            mod = loader.load_module(module_name)
        return mod
    
    def handle(self, *args, **options):
        filename = options['filename']

        # Determine absolute path relative to the project root
        if not os.path.isabs(filename):
            file_path = os.path.join(settings.BASE_DIR, filename)
        else:
            file_path = filename
        
        if not os.path.exists(file_path):
            raise CommandError(f'File not found: {file_path}')

        self.stdout.write(self.style.NOTICE(f'Executing file: {file_path}'))
        mod = self.load_dynamic_file(file_path)
        mod.__main__()
        self.stdout.write(self.style.SUCCESS(f'Successfully executed {filename}'))













