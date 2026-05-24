from __future__ import annotations

import json
from datetime import datetime

from celery import shared_task
from croniter import croniter
from django.db import models
from django.utils import timezone

from server.models.cron import Cronjob
from server.models.sessions.session import SessionModel
from runtime.session.session import Session


@shared_task(name="cron.execute_job")
def execute_cron_job(cronjob_id: int) -> None:
    """Execute a single cron job (runs in a Celery worker)."""
    try:
        _do_execute(cronjob_id)
    except Exception as e:
        print(f"[cron] error executing job {cronjob_id}: {e}")
        Cronjob.objects.filter(pk=cronjob_id).update(last_status=f"error: {e}")


def _do_execute(cronjob_id: int) -> None:
    cronjob = Cronjob.objects.select_related(
        "agent__latest_agent_version", "message"
    ).get(pk=cronjob_id)

    # 1. Resolve session
    auto_name = f"cron:{cronjob.agent.name}:{cronjob.name}"
    if cronjob.session_mode == "new":
        session_name = cronjob.session_name or f"{auto_name}:{int(timezone.now().timestamp())}"
        agent_version = cronjob.agent.latest_agent_version
        session_version = agent_version.get_or_create_session(name=session_name)
        session = Session(
            session_model=session_version.session,
            pinned_session_version=session_version,
        )
    else:
        session_name = cronjob.session_name or auto_name
        session_model, _ = SessionModel.objects.get_or_create(name=session_name)
        session = Session(session_model=session_model)

    # 2. Dispatch
    message_content = cronjob.message.content if cronjob.message else ""

    if cronjob.function_type and cronjob.function_name:
        getter = {
            "task": session.get_task,
            "tool": session.get_tool,
            "command": session.get_command,
        }.get(cronjob.function_type)
        if getter is None:
            raise ValueError(f"Unknown function_type: {cronjob.function_type}")
        bound_task = getter(cronjob.function_name)
        if bound_task is None:
            raise ValueError(
                f"Function {cronjob.function_type}:{cronjob.function_name} "
                f"not found on agent {cronjob.agent.name}"
            )
        args = json.loads(message_content) if message_content else {}
        if not isinstance(args, dict):
            raise ValueError("Message must be a JSON object for function dispatch")
        bound_task.delay(**args)
    else:
        session.add_user_message(parts=[
            {"type": "message", "content_type": "text", "content": message_content},
        ])

    # 3. Update tracking
    next_run = croniter(cronjob.schedule, timezone.localtime()).get_next(datetime)

    Cronjob.objects.filter(pk=cronjob_id).update(
        last_run_at=timezone.now(),
        next_run_at=next_run,
        last_status="success",
        total_runs=models.F("total_runs") + 1,
    )

    print(f"[cron] executed job {cronjob_id} ({cronjob.name})")


def _expand_shorthand(schedule: str) -> str:
    """Convert human-friendly shorthands to cron expressions.

    Supported:
      ``every N (min|m|hour|h)``  →  ``*/N * * * *`` (min) / ``N * * * *`` (hour)
    """
    s = schedule.strip().lower()
    import re
    m = re.match(r"^every\s+(\d+)\s*(min|m|minute|minutes|hour|hours|h)\s*$", s)
    if m:
        n = int(m.group(1))
        unit = m.group(2)
        if unit in ("min", "m", "minute", "minutes"):
            return f"*/{n} * * * *"
        else:
            return f"0 */{n} * * *"
    return schedule


def compute_next_run(schedule: str) -> datetime | None:
    """Compute the next run datetime from a cron expression using croniter.

    Supports standard cron (``*/5 * * * *``), shorthands (``@daily``,
    ``@hourly``), and human-friendly ``every N (min|m|hour|h)``.
    """
    try:
        expanded = _expand_shorthand(schedule)
        return croniter(expanded, timezone.localtime()).get_next(datetime)
    except (ValueError, KeyError):
        return None
