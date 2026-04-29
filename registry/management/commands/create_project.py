import hashlib
from importlib.machinery import SourceFileLoader
import os
import sys
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from pathlib import Path
from contextlib import contextmanager


class Command(BaseCommand):
    help = ''

    def add_arguments(self, parser):
        parser.add_argument('folder', type=str, help='Create new .agentOne subfolder')

    def handle(self, *args, **options):
        path = Path(options['folder']).resolve()
        if not path.exists():
            raise CommandError(f'Folder not found: {path.as_posix()}')

        agentone_path = path / ".agentOne"
        if agentone_path.exists():
            raise CommandError(f'.agentOne exists in {path.as_posix()}')
        
        agentone_path.mkdir(exist_ok=False, parents=False) 

        (agentone_path / "config.yml").write_text("")
        (agentone_path / "projects.yml").write_text("")

        (agentone_path / "agents").mkdir()
        (agentone_path / "agents" / "agents.yml").write_text("")

        (agentone_path / "commands").mkdir()
        (agentone_path / "commands" / "agents.yml").write_text("")

        (agentone_path / "skills").mkdir()
        (agentone_path / "skills" / "skills.yml").write_text("")

        self.stdout.write(self.style.NOTICE(f'Executing file: {agentone_path}'))
        self.stdout.write(self.style.SUCCESS(f'Successfully executed {agentone_path}'))
