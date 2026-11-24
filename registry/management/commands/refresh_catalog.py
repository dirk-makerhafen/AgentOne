"""Rebuild the canonical provider/model JSON dataset from upstream sources."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandError

from registry.catalog.build import build_dataset
from registry.catalog.sources import cache_dir, fetch_sources
from registry.catalog.write import generation_timestamp, sync_dataset
from runtime.paths import agentone_root


class Command(BaseCommand):
    help = "Download the upstream LLM catalogs and regenerate .agentone/providers as JSON."

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument(
            "--offline",
            action="store_true",
            help="rebuild from the cached raw sources without network access",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="report changes without writing or deleting files",
        )
        parser.add_argument(
            "--no-prune",
            action="store_true",
            help="keep generated JSON files that are no longer produced by the sources",
        )
        parser.add_argument(
            "--root",
            type=Path,
            default=None,
            help="manifest root containing providers/ and models/ (default: AGENTONE_ROOT)",
        )
        parser.add_argument(
            "--cache-dir",
            type=Path,
            default=None,
            help="raw source cache directory (default: ~/.agentone/var/cache/provider-catalog)",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        root = Path(options["root"]) if options["root"] else agentone_root()
        target_cache = Path(options["cache_dir"]) if options["cache_dir"] else cache_dir()

        bundle = fetch_sources(target_cache, offline=options["offline"])
        sources = bundle.available()
        if not sources:
            raise CommandError(
                "No catalog sources found. Run without --offline first, or check the cache "
                f"at {target_cache}."
            )

        providers, models = build_dataset(bundle)
        summary = sync_dataset(
            providers,
            models,
            root,
            dry_run=options["dry_run"],
            prune=not options["no_prune"],
            updated_at=generation_timestamp(),
        )

        self.stdout.write(
            f"Catalog from {len(sources)} sources: {', '.join(sources)}\n"
            f"  providers:   {len(providers)}\n"
            f"  model files: {len(models)}\n"
            f"  files:       {summary['total_files']} "
            f"({summary['written']} written, {summary['unchanged']} unchanged, "
            f"{summary['removed']} pruned)"
        )
        for error in bundle.manifest.get("errors") or []:
            self.stderr.write(f"  warning: {error} (cached payload used)")
        for path in summary["removed_examples"]:
            self.stdout.write(f"  removed: {path}")
        if options["dry_run"]:
            self.stdout.write("  dry run: no files changed")
