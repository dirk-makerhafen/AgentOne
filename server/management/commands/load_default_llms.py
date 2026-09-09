"""Load default LLM providers and models from research frontmatter.

Reads:
  - .agentone/providers/  (one ``<slug>.md`` per provider)
  - .agentone/models/      (model cards; ``providers[]`` entries supply rows)
Creates or updates ApiProvider and AiModel records via the standard loader.
"""
from pathlib import Path
from django.core.management.base import BaseCommand
from registry.loader.load_providers import load_providers_dir

BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
AGENTONE_DIR = BASE_DIR / ".agentone"


class Command(BaseCommand):
    help = "Load default LLM providers and models from YAML manifests"

    def handle(self, *args, **options):
        loaded = 0
        details: list[dict[str, str]] = []
        providers_dir = AGENTONE_DIR / "providers"
        if not providers_dir.is_dir():
            self.stdout.write("  [skip] providers/ — not found")
        else:
            count = load_providers_dir(providers_dir, AGENTONE_DIR / "models", details)
            if count:
                loaded += count
                self.stdout.write(f"  [providers/] {count} provider(s)")
            else:
                self.stdout.write("  [providers/] up to date")

        created = [d for d in details if d.get("action") == "created"]
        updated = [d for d in details if d.get("action") == "updated"]
        self.stdout.write(self.style.SUCCESS(
            f"Done — {loaded} provider(s), "
            f"{len(created)} created, {len(updated)} updated"
        ))
