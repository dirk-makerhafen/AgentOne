"""Extract deterministic free-offering leads from the upstream catalogs."""

from __future__ import annotations

# CLI argument boilerplate is deliberately kept parallel to refresh_catalog.
# pylint: disable=duplicate-code

from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandError

from registry.catalog.build import build_dataset
from registry.catalog.cards import load_api_bases
from registry.catalog.free import build_free_dataset, prepare_free_output
from registry.catalog.reviews import CANDIDATES_DIR
from registry.catalog.sources import cache_dir, fetch_provider_model_lists, fetch_sources
from registry.catalog.write import generation_timestamp, sync_free_candidates, sync_free_models
from runtime.paths import agentone_root, free_tier_cache_dir


class Command(BaseCommand):
    help = (
        "Extract free-offering leads into the free-tier cache. "
        "The reviewed dataset in <root>/free/ is written by merge_free_reviews."
    )

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument(
            "--offline",
            action="store_true",
            help="rebuild from cached raw sources without network access",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="report changes without writing files",
        )
        parser.add_argument(
            "--root",
            type=Path,
            default=None,
            help="manifest root (default: AGENTONE_ROOT)",
        )
        parser.add_argument(
            "--cache-dir",
            type=Path,
            default=None,
            help="raw source cache directory (default: ~/.agentone/var/cache/provider-catalog)",
        )
        parser.add_argument(
            "--candidates-dir",
            type=Path,
            default=None,
            help="generated candidate directory (default: ~/.agentone/var/cache/free-tier/candidates)",
        )
        parser.add_argument(
            "--skip-model-lists",
            action="store_true",
            help="do not query provider /models endpoints (use cached payloads in offline mode)",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        # pylint: disable=too-many-locals
        root = Path(options["root"]) if options["root"] else agentone_root()
        target_cache = Path(options["cache_dir"]) if options["cache_dir"] else cache_dir()
        candidates_dir = (
            Path(options["candidates_dir"])
            if options["candidates_dir"]
            else free_tier_cache_dir() / CANDIDATES_DIR
        )

        bundle = fetch_sources(target_cache, offline=options["offline"])
        if not bundle.available():
            raise CommandError(
                "No catalog sources found. Run refresh_catalog first, or check the cache "
                f"at {target_cache}."
            )

        providers, models = build_dataset(bundle)
        if not options["skip_model_lists"]:
            bundle.provider_models = fetch_provider_model_lists(
                providers,
                target_cache,
                offline=options["offline"],
            )

        candidates = build_free_dataset(bundle, providers)
        api_bases = load_api_bases(root)
        prepared = prepare_free_output(candidates, providers, models, api_bases)
        stamp = generation_timestamp()
        try:
            model_summary = sync_free_models(
                prepared["providers"],
                prepared["models"],
                root,
                dry_run=options["dry_run"],
                updated_at=stamp,
            )
            summary = sync_free_candidates(
                prepared["dataset"],
                candidates_dir,
                dry_run=options["dry_run"],
            )
        except ValueError as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write(
            f"Free candidates from {len(candidates['sources'])} sources\n"
            f"  providers: {candidates['counts']['providers']}\n"
            f"  candidates: {candidates['counts']['candidates']}\n"
            f"  model files: {len(prepared['created'])} created, "
            f"{len(prepared['enriched'])} already existed\n"
            f"  written:     {model_summary['written']} model/provider files, "
            f"{summary['written']} free files "
            f"({model_summary['removed']} stale model files pruned)\n"
            f"  free files:  {summary['total_files']} in {summary['directory']} "
            f"({summary['unchanged']} unchanged)"
        )
        for label, paths in (("removed model", model_summary["removed_examples"]),
                             ("removed free", summary["removed_examples"])):
            for path in paths:
                self.stdout.write(f"  {label}: {path}")
        if summary["dry_run"]:
            self.stdout.write("  dry run: no files changed")
