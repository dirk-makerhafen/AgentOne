"""Deprecated cron manifest loader.

Cron jobs are now DB-canonical and created via the Web UI; ``cronjobs/*.md``
manifest files are no longer supported.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any


def load_cron_manifest(
    cron_md_path: Path,
    install_repo: Any = None,
    parent_project: Any = None,
    seen_names: set | None = None,
    details: list | None = None,
):
    """Cron manifest loading has been removed."""
    raise ValueError(
        "Cron job manifest files are no longer supported; cron jobs are DB-canonical "
        "and must be created via the Web UI."
    )
