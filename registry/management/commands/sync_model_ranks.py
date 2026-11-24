"""Download leaderboard ranks, maintain the editable table, apply it to models."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandError

from registry.catalog.ranks import (
    RANKS_FILE,
    ZEROEVAL_KEY_ENV,
    apply_ranks,
    collect_models,
    current_ranks,
    download_leaderboard,
    export_markdown,
    leaderboard_cache_dir,
    match_leaderboard,
    parse_markdown,
    ranks_file,
    zeroeval_token,
)
from runtime.paths import agentone_root


class Command(BaseCommand):
    help = (
        "Refresh model leaderboard ranks from the live sources, write the editable "
        "docs/model-ranks.md table, and apply curated ranks to model JSON files."
    )

    def add_arguments(self, parser: Any) -> None:
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
            help="leaderboard cache directory (default: ~/.agentone/var/cache/free-tier/leaderboard)",
        )
        parser.add_argument(
            "--ranks-file",
            type=Path,
            default=None,
            help=f"editable rank table (default: <root>/../{RANKS_FILE.as_posix()})",
        )
        parser.add_argument(
            "--token",
            default=None,
            help=f"ZeroEval bearer token (default: ${ZEROEVAL_KEY_ENV}) or legacy secret file",
        )
        parser.add_argument(
            "--offline",
            action="store_true",
            help="reuse cached or snapshot leaderboard data without network access",
        )
        action = parser.add_mutually_exclusive_group()
        action.add_argument(
            "--refresh",
            action="store_true",
            help="download ranks, apply them, and regenerate the table (default)",
        )
        action.add_argument(
            "--export",
            action="store_true",
            help="regenerate the table from ranks currently stored in model files",
        )
        action.add_argument(
            "--import",
            dest="import_ranks",
            action="store_true",
            help="apply filled-in cells from the table to model files",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="validate and report without writing files",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        root = Path(options["root"]) if options["root"] else agentone_root()
        cache_dir = Path(options["cache_dir"]) if options["cache_dir"] else leaderboard_cache_dir()
        table = Path(options["ranks_file"]) if options["ranks_file"] else ranks_file(root)
        dry_run = bool(options["dry_run"])
        overrides = parse_markdown(table)

        if options["export"]:
            ranks, names = current_ranks(root)
            rows = export_markdown(root, ranks, names, table, dry_run=dry_run)
            self.stdout.write(
                f"Exported {rows} models to {table}\n"
                f"  ranked: {sum(value is not None for value in ranks.values())}"
            )
            if dry_run:
                self.stdout.write("  dry run: no files changed")
            return

        if options["import_ranks"]:
            summary = apply_ranks(
                root,
                None,
                overrides,
                clear_unranked=False,
                dry_run=dry_run,
            )
            self.stdout.write(
                f"Imported ranks from {table}\n"
                f"  files written: {summary['written']}  "
                f"unchanged: {summary['unchanged']}  models: {summary['models']}"
            )
            if dry_run:
                self.stdout.write("  dry run: no files changed")
            return

        try:
            rows, warnings = download_leaderboard(
                cache_dir,
                token=options["token"] or zeroeval_token(),
                offline=bool(options["offline"]),
            )
        except RuntimeError as exc:
            raise CommandError(str(exc)) from exc
        for warning in warnings:
            self.stdout.write(f"warning: {warning}")

        matches = match_leaderboard(rows, root)
        summary = apply_ranks(root, matches, overrides, clear_unranked=True, dry_run=dry_run)

        if dry_run:
            paths, _ = collect_models(root)
            ranks: dict[str, int | str | None] = {}
            for slug in paths:
                value = overrides.get(slug)
                if value is None and slug in matches:
                    value = int(matches[slug]["leaderboard_rank"])
                ranks[slug] = value
        else:
            ranks, _ = current_ranks(root)
        table_rows = export_markdown(root, ranks, {}, table, dry_run=dry_run)

        self.stdout.write(
            f"Leaderboard: {len(rows)} entries, {len(matches)} matched models\n"
            f"  files written: {summary['written']}  "
            f"unchanged: {summary['unchanged']}  models: {summary['models']}\n"
            f"  table: {table_rows} rows at {table}"
        )
        if dry_run:
            self.stdout.write("  dry run: no files changed")
