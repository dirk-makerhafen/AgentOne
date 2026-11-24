"""Merge curated free-tier reviews into a deterministic free dataset."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandError

from registry.catalog.reviews import (
    CANDIDATES_DIR,
    FREE_DIR,
    REVIEWS_DIR,
    collect_reviews,
    sync_merged,
)
from runtime.paths import agentone_root, free_tier_cache_dir


class Command(BaseCommand):
    help = (
        "Validate cached free-tier reviews and write the reviewed dataset to "
        "<root>/free/. Never edits the generated inputs or the DB."
    )

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument(
            "--root",
            type=Path,
            default=None,
            help="manifest root (default: AGENTONE_ROOT)",
        )
        parser.add_argument(
            "--candidates-dir",
            type=Path,
            default=None,
            help="generated candidate directory (default: ~/.agentone/var/cache/free-tier/candidates)",
        )
        parser.add_argument(
            "--reviews-dir",
            type=Path,
            default=None,
            help="curated review directory (default: ~/.agentone/var/cache/free-tier/reviews)",
        )
        parser.add_argument(
            "--output-dir",
            type=Path,
            default=None,
            help="reviewed dataset directory (default: <root>/free)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="validate and report without writing the merged dataset",
        )
        parser.add_argument(
            "--strict",
            action="store_true",
            help="treat validation warnings as errors",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        root = Path(options["root"]) if options["root"] else agentone_root()
        cache = free_tier_cache_dir()
        candidates_dir = (
            Path(options["candidates_dir"]) if options["candidates_dir"] else cache / CANDIDATES_DIR
        )
        reviews_dir = Path(options["reviews_dir"]) if options["reviews_dir"] else cache / REVIEWS_DIR
        output_dir = Path(options["output_dir"]) if options["output_dir"] else root / FREE_DIR

        result = collect_reviews(root, free_dir=candidates_dir, reviews_dir=reviews_dir)
        for issue in result.issues:
            self.stdout.write(issue.format())

        counts = result.counts
        self.stdout.write(
            f"Reviews: {counts.get('reviewed', 0)}/{counts.get('candidates', 0)} candidates "
            f"across {counts.get('providers', 0)} providers\n"
            f"  free: {counts.get('free', 0)}  "
            f"payment_gated: {counts.get('payment_gated', 0)}  "
            f"rejected: {counts.get('rejected', 0)}  "
            f"needs_followup: {counts.get('needs_followup', 0)}  "
            f"unreviewed: {counts.get('unreviewed', 0)}\n"
            f"  errors: {len(result.errors)}  warnings: {len(result.warnings)}"
        )

        if result.errors:
            raise CommandError(f"{len(result.errors)} review error(s); nothing written")
        if options["strict"] and result.warnings:
            raise CommandError(f"{len(result.warnings)} review warning(s) in strict mode; nothing written")

        try:
            summary = sync_merged(
                result.documents,
                result.index,
                output_dir,
                dry_run=options["dry_run"],
            )
        except ValueError as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write(
            f"Reviewed free dataset: {summary['total_files']} files\n"
            f"  written: {summary['written']}  "
            f"unchanged: {summary['unchanged']}  "
            f"removed: {summary['removed']}\n"
            f"  output: {summary['directory']}"
        )
        if summary["dry_run"]:
            self.stdout.write("  dry run: no files changed")
