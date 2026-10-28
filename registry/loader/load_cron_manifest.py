"""Cron manifest loader (cron.md)."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import frontmatter
from croniter import croniter
from django.db import models
from django.utils import timezone

from registry.install_repo import InstallRepo
from runtime.cron.content import build_cron_message
from server.models.agents.agent import AgentModel
from server.models.cron import Cronjob
from server.models.workspace import WorkspaceModel


def _as_str(value: Any) -> str:
    """Coerce YAML values to a string (``None`` → ``""``)."""
    return "" if value is None else str(value)


def load_cron_manifest(
    cron_md_path: Path,
    install_repo: InstallRepo,
    parent_project: Any = None,
    seen_names: set | None = None,
    details: list | None = None,
) -> Cronjob:
    """Load a ``cron.md`` manifest into the database.

    Creates or updates a ``Cronjob`` by ``(parent_project, name)``.
    If *seen_names* is provided, the cron's name is added to the set so
    the caller can archive any crons that were not mentioned in the
    manifest files.
    """
    manifest = frontmatter.load(cron_md_path)

    name = _as_str(manifest.get("name", "")).strip()
    if not name:
        raise ValueError(f"cron.md at {cron_md_path} is missing 'name'")
    if seen_names is not None:
        seen_names.add(name)

    description = _as_str(manifest.get("description", ""))
    schedule = _as_str(manifest.get("schedule", ""))
    agent_name = _as_str(manifest.get("agent", ""))
    session_mode = _as_str(manifest.get("session_mode", "new")) or "new"
    session_name = _as_str(manifest.get("session_name", ""))
    function_type = _as_str(manifest.get("function_type", "")).strip()
    function_name = _as_str(manifest.get("function_name", "")).strip()
    if function_type and not function_name:
        raise ValueError(
            f"cron.md at {cron_md_path} sets 'function_type' without 'function_name'"
        )
    raw_active = manifest.get("is_active", True)
    is_active = True if raw_active is None else bool(raw_active)
    workspace_name = _as_str(manifest.get("workspace", ""))
    message_text = manifest.get("message", "")

    # Resolve agent
    agent = None
    if agent_name:
        agent_qs = AgentModel.objects.filter(name=agent_name)
        if parent_project is not None:
            agent_qs = agent_qs.filter(
                models.Q(parent_project=parent_project) | models.Q(parent_project__isnull=True)
            )
        agent = agent_qs.first()

    # Compute next run
    next_run_at = None
    try:
        next_run_at = croniter(schedule, timezone.localtime()).get_next(datetime)
    except (ValueError, KeyError):
        pass

    # Resolve workspace
    workspace = None
    if workspace_name:
        workspace = WorkspaceModel.objects.filter(name=workspace_name).first()

    # Build message content (JSON kwargs for a function target, text otherwise)
    try:
        message = build_cron_message(message_text, function_type)
    except ValueError as exc:
        raise ValueError(f"{cron_md_path}: {exc}") from exc

    # Upsert by (parent_project, name)
    cronjob, created = Cronjob.objects.get_or_create(
        name=name,
        parent_project=parent_project,
        defaults={
            "description": description,
            "schedule": schedule,
            "is_active": is_active,
            "is_archived": False,
            "agent": agent,
            "workspace": workspace,
            "session_mode": session_mode,
            "session_name": session_name,
            "function_type": function_type,
            "function_name": function_name,
            "message": message,
            "next_run_at": next_run_at,
            "manifest_dir": cron_md_path.parent.as_posix(),
        },
    )
    changed = False
    if not created:
        _fields_to_check = [
            ("description", description),
            ("schedule", schedule),
            ("is_archived", False),
            ("agent", agent),
            ("workspace", workspace),
            ("session_mode", session_mode),
            ("session_name", session_name),
            ("function_type", function_type),
            ("function_name", function_name),
            ("message", message),
            ("next_run_at", next_run_at),
            ("manifest_dir", cron_md_path.parent.as_posix()),
        ]
        for field_name, new_val in _fields_to_check:
            if getattr(cronjob, field_name) != new_val:
                setattr(cronjob, field_name, new_val)
                changed = True
        if changed:
            cronjob.save()
    if details is not None:
        action = "created" if created else ("updated" if changed else "up to date")
        details.append({"name": name, "type": "cron", "action": action})

    return cronjob
