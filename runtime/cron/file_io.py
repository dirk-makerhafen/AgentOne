"""Read/write cron job markdown files on disk."""
from __future__ import annotations

from pathlib import Path

import frontmatter as frontmatter_lib
import yaml

from server.models.cron import Cronjob


def cron_file_path(name: str, project=None) -> Path:
    """Return the expected ``cronjobs/<name>.md`` path.

    Project-scoped crons live under the project's manifest dir
    (``<manifest_dir>/cronjobs/<name>.md`` — ``manifest_dir`` is
    DB-canonical with legacy ``<path>/.agentone`` fallback). Global crons
    live under ``settings.AGENTONE_ROOT/cronjobs/``.
    """
    if project is not None:
        try:
            return project.get_agentone_dir() / "cronjobs" / f"{name}.md"
        except Exception:  # pylint: disable=broad-exception-caught
            pass
        if getattr(project, "path", None):
            return Path(project.path) / ".agentone" / "cronjobs" / f"{name}.md"
    from django.conf import settings
    return Path(settings.AGENTONE_ROOT) / "cronjobs" / f"{name}.md"


def _find_cron_file(directory: Path, name: str) -> Path | None:
    """Find ``name``'s markdown file in *directory*.

    Prefers ``<name>.md`` and falls back to any file whose frontmatter
    ``name`` matches, so renamed/oddly-named files keep working.
    """
    exact = directory / f"{name}.md"
    if exact.is_file():
        return exact
    wanted = (name or "").strip()
    for candidate in sorted(directory.glob("*.md")):
        try:
            manifest = frontmatter_lib.load(candidate)
            if (manifest.get("name") or "").strip() == wanted:
                return candidate
        except Exception:  # pylint: disable=broad-exception-caught
            continue
    return None


def _resolve_cron_path(
    name: str,
    project=None,
    manifest_dir: str = "",
) -> Path:
    """Return the manifest path for *name*, preferring the canonical scope.

    A file in the project/global ``cronjobs/`` directory wins; otherwise the
    stored ``manifest_dir`` (workspace scope) is used.
    """
    canonical = cron_file_path(name, project)
    canonical_dir = canonical.parent
    if canonical_dir.is_dir():
        found = _find_cron_file(canonical_dir, name)
        if found is not None:
            return found
    stored = (manifest_dir or "").strip()
    if stored:
        directory = Path(stored).expanduser()
        if directory.is_dir():
            return _find_cron_file(directory, name) or directory / f"{name}.md"
    return canonical


def cron_file_target(cronjob: Cronjob) -> Path:
    """Return the file a cron job should be written to.

    The canonical project/global ``cronjobs/`` file wins when it exists, so
    a stale workspace copy cannot shadow it.  Workspace-only jobs (no
    canonical file) round-trip to the directory they were loaded from.
    """
    return _resolve_cron_path(
        cronjob.name,
        cronjob.parent_project,
        cronjob.manifest_dir,
    )


def write_cron_file(cronjob: Cronjob) -> None:
    """Write a cron job's settings to its markdown file (scope-aware)."""
    path = cron_file_target(cronjob)
    path.parent.mkdir(parents=True, exist_ok=True)

    try:
        message_value = cronjob.message.get() if cronjob.message else ""
    except Exception:  # pylint: disable=broad-exception-caught
        message_value = cronjob.message.content if cronjob.message else ""

    meta = {
        "name": cronjob.name,
        "description": cronjob.description or "",
        "schedule": cronjob.schedule,
        "agent": cronjob.agent.name if cronjob.agent else "",
        "is_active": cronjob.is_active,
        "workspace": cronjob.workspace.name if cronjob.workspace else "",
        "session_mode": cronjob.session_mode or "new",
        "session_name": cronjob.session_name or "",
        "message": message_value,
        "function_type": cronjob.function_type or "",
        "function_name": cronjob.function_name or "",
    }

    with open(path, "w", encoding="utf-8") as f:
        f.write("---\n")
        yaml.dump(meta, f, default_flow_style=False, allow_unicode=True)
        f.write("---\n")

    # Keep the row pointing at the file we just wrote so a later
    # refresh_from_disk() reads the same manifest instead of a stale copy.
    new_dir = path.parent.as_posix()
    if (cronjob.manifest_dir or "") != new_dir:
        cronjob.manifest_dir = new_dir
        if cronjob.pk is not None:
            Cronjob.objects.filter(pk=cronjob.pk).update(manifest_dir=new_dir)


def delete_cron_file(name: str, project=None, manifest_dir: str = "") -> None:
    """Remove a cron job's markdown file if it exists."""
    path = _resolve_cron_path(name, project, manifest_dir)
    if path.exists():
        path.unlink()


def rename_cron_file(
    old_name: str,
    new_name: str,
    project=None,
    manifest_dir: str = "",
) -> None:
    """Rename a cron file when the cron job is renamed."""
    old_path = _resolve_cron_path(old_name, project, manifest_dir)
    if not old_path.exists():
        return
    new_path = old_path.parent / f"{new_name}.md"
    if old_path != new_path:
        new_path.parent.mkdir(parents=True, exist_ok=True)
        old_path.rename(new_path)
