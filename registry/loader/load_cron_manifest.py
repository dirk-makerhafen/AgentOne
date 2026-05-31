"""Cron manifest loader (cron.md)."""
from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from typing import Any

import frontmatter
from croniter import croniter
from django.db import models
from django.utils import timezone

from registry.install_repo import InstallRepo
from server.models.agents.agent import AgentModel
from server.models.content import GenericContent, ContentType
from server.models.cron import Cronjob
from server.models.workspace import WorkspaceModel


def load_cron_manifest(
    cron_md_path: Path,
    install_repo: InstallRepo,
    parent_project: Any = None,
    seen_names: set | None = None,
) -> Cronjob:
    """Load a ``cron.md`` manifest into the database.

    Creates or updates a ``Cronjob`` by ``(parent_project, name)``.
    If *seen_names* is provided, the cron's name is added to the set so
    the caller can archive any crons that were not mentioned in the
    manifest files.
    """
    manifest = frontmatter.load(cron_md_path)

    name = manifest.get("name", "")
    if not name:
        raise ValueError(f"cron.md at {cron_md_path} is missing 'name'")
    if seen_names is not None:
        seen_names.add(name)

    description = manifest.get("description", "")
    schedule = manifest.get("schedule", "")
    agent_name = manifest.get("agent", "")
    session_mode = manifest.get("session_mode", "new")
    session_name = manifest.get("session_name", "")
    function_type = manifest.get("function_type", "")
    function_name = manifest.get("function_name", "")
    pipe_names = manifest.get("pipe_names", []) or []
    is_active = manifest.get("is_active", True)
    workspace_name = manifest.get("workspace", "")
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

    # Build message content
    message = None
    if message_text:
        if isinstance(message_text, str):
            message = GenericContent.from_text(message_text)
        else:
            message = GenericContent.from_data( message_text)
            

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
            "pipe_names": pipe_names,
            "message": message,
            "next_run_at": next_run_at,
        },
    )
    if not created:
        cronjob.description = description
        cronjob.schedule = schedule
        cronjob.is_active = is_active
        cronjob.is_archived = False
        cronjob.agent = agent
        cronjob.workspace = workspace
        cronjob.session_mode = session_mode
        cronjob.session_name = session_name
        cronjob.function_type = function_type
        cronjob.function_name = function_name
        cronjob.pipe_names = pipe_names
        cronjob.message = message
        cronjob.next_run_at = next_run_at
        cronjob.save()

    return cronjob
