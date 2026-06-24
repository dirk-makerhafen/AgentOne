"""Load default LLM providers and models from YAML manifests.

Reads:
  - .agentone/providers.yaml       (self-hosted / local models)
  - .agentone/free_providers.yaml  (free-tier cloud models)
Creates or updates ApiProvider and AiModel records via the standard YAML loader.
"""
from pathlib import Path
from django.core.management.base import BaseCommand
from registry.loader.load_providers import load_providers_manifest

BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
AGENTONE_DIR = BASE_DIR / ".agentone"

MANIFESTS = [
    "providers.yaml",
    "free_providers.yaml",
]


class Command(BaseCommand):
    help = "Load default LLM providers and models from YAML manifests"

    def handle(self, *args, **options):
        loaded = 0
        details: list[dict[str, str]] = []
        for name in MANIFESTS:
            path = AGENTONE_DIR / name
            if not path.exists():
                self.stdout.write(f"  [skip] {name} — not found")
                continue
            count = load_providers_manifest(path, details)
            if count:
                loaded += count
                self.stdout.write(f"  [{name}] {count} provider(s)")
            else:
                self.stdout.write(f"  [{name}] up to date")

        created = [d for d in details if d.get("action") == "created"]
        updated = [d for d in details if d.get("action") == "updated"]
        self.stdout.write(self.style.SUCCESS(
            f"Done — {loaded} provider(s), "
            f"{len(created)} created, {len(updated)} updated"
        ))
