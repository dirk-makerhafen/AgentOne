"""Deprecated cron manifest file helpers.

Cron jobs are now DB-canonical and created via the Web UI; ``.md`` cron
manifest files are no longer read or written. This module remains as a
compatibility shim for older imports and returns inert behavior.
"""
from __future__ import annotations

from pathlib import Path


def cron_file_path(name: str, project=None) -> Path:
    """Return the legacy cron manifest path location (unused)."""
    if project is not None:
        try:
            return project.get_agentone_dir() / "cronjobs" / f"{name}.md"
        except Exception:  # pylint: disable=broad-exception-caught
            pass
        if getattr(project, "path", None):
            return Path(project.path) / ".agentone" / "cronjobs" / f"{name}.md"
    from django.conf import settings

    return Path(settings.AGENTONE_ROOT) / "cronjobs" / f"{name}.md"


def cron_file_target(cronjob) -> Path:
    """Return the legacy target path (unused)."""
    return cron_file_path(getattr(cronjob, "name", ""), getattr(cronjob, "parent_project", None))


def write_cron_file(cronjob) -> None:
    """No-op: cron jobs are DB-canonical."""


def delete_cron_file(name: str, project=None, manifest_dir: str = "") -> None:
    """No-op: cron jobs are DB-canonical."""


def rename_cron_file(old_name: str, new_name: str, project=None, manifest_dir: str = "") -> None:
    """No-op: cron jobs are DB-canonical."""
