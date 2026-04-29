from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from pathlib import Path


class Command(BaseCommand):
    help = ''

    def add_arguments(self, parser):
        parser.add_argument('folder', type=str, help='Remove .AgentOne subdir from Folder')

    def handle(self, *args, **options):
        path = Path(options['folder']).resolve()
        if not path.exists():
            raise CommandError(f'Folder not found: {path.as_posix()}')

        agentone_path = path / ".agentOne"
        if not agentone_path.exists():
            raise CommandError(f'no .agentOne subdir found in {path.as_posix()}')
