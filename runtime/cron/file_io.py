"""Read/write cron job markdown files on disk."""
from __future__ import annotations

from pathlib import Path

import yaml

from server.models.cron import Cronjob


def cron_file_path(name: str) -> Path:
    """Return the expected ``.agentone/cronjobs/<name>.md`` path."""
    from django.conf import settings
    return Path(settings.AGENTONE_ROOT) / "cronjobs" / f"{name}.md"


def write_cron_file(cronjob: Cronjob) -> None:
    """Write a cron job's settings to ``.agentone/cronjobs/<name>.md``."""
    path = cron_file_path(cronjob.name)
    path.parent.mkdir(parents=True, exist_ok=True)

    frontmatter = {
        "name": cronjob.name,
        "description": cronjob.description or "",
        "schedule": cronjob.schedule,
        "agent": cronjob.agent.name if cronjob.agent else "",
        "is_active": cronjob.is_active,
        "workspace": cronjob.workspace.name if cronjob.workspace else "",
        "session_mode": cronjob.session_mode or "new",
        "session_name": cronjob.session_name or "",
        "message": cronjob.message.content if cronjob.message else "",
        "function_type": cronjob.function_type or "",
        "function_name": cronjob.function_name or "",
        "pipe_names": cronjob.pipe_names or [],
    }

    with open(path, "w") as f:
        f.write("---\n")
        yaml.dump(frontmatter, f, default_flow_style=False, allow_unicode=True)
        f.write("---\n")


def delete_cron_file(name: str) -> None:
    """Remove ``.agentone/cronjobs/<name>.md`` if it exists."""
    path = cron_file_path(name)
    if path.exists():
        path.unlink()


def rename_cron_file(old_name: str, new_name: str) -> None:
    """Rename a cron file when the cron job is renamed."""
    old_path = cron_file_path(old_name)
    new_path = cron_file_path(new_name)
    if old_path.exists():
        old_path.rename(new_path)
