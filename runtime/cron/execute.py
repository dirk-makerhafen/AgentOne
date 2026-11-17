from __future__ import annotations

import json

from django.db import models
from django.utils import timezone

from server.models.cron import Cronjob
from server.models.enums.session_enums import SessionType
from runtime.cron.schedule import compute_next_run
from runtime.session.session import Session


def execute_cron_job(cronjob_id: int) -> None:
    """Execute a single cron job (runs in a Celery worker)."""
    try:
        cronjob = Cronjob.objects.get(pk=cronjob_id)

        # 1. Resolve session
        auto_name = f"cron:{cronjob.agent.name}:{cronjob.name}"
        if cronjob.session_mode == "new":
            session_name = cronjob.session_name or f"{auto_name}:{int(timezone.now().timestamp())}"

        else:
            session_name = cronjob.session_name or auto_name
            
        agent_version = cronjob.agent.latest_agent_version
        session_version = agent_version.get_or_create_session(
            name=session_name,
            workspace=cronjob.workspace,
            group_key=f"cron:{cronjob.name or f'job-{cronjob.pk}'}",
            session_type=SessionType.CRONJOB
        )
        session = Session(session_model=session_version.session, pinned_session_version=session_version)

        # 2. Dispatch
        message_data = cronjob.message.get() if cronjob.message else ""

        task = None
        if cronjob.function_type:
            if not cronjob.function_name:
                raise ValueError(
                    "function_name is required when function_type is set"
                )
            if cronjob.function_type == "task":
                task = session.get_task( cronjob.function_name)
            elif cronjob.function_type == "tool":
                task = session.get_tool( cronjob.function_name)
            elif cronjob.function_type == "command":
                task = session.get_command( cronjob.function_name)
            else:
                raise ValueError(f"Unknown function type {cronjob.function_type}")
            if not task:
                raise ValueError(f"Unknown {cronjob.function_type} : {cronjob.function_name}")
            if isinstance(message_data, str):
                # Legacy manifests stored the kwargs as a JSON string.
                try:
                    message_data = json.loads(message_data)
                except (TypeError, ValueError) as exc:
                    raise ValueError("Message must be a JSON object for function dispatch") from exc
            if not isinstance(message_data, dict):
                raise ValueError("Message must be a JSON object for function dispatch")
            task.apply_async(kwargs=message_data, cronjob=cronjob)
        else:
            # Fallback target: ingest_user_message expects a message spec, so a
            # structured payload (legacy JSON args) is sent as JSON text.
            if not isinstance(message_data, str):
                message_data = json.dumps(message_data)
            session.get_task("ingest_user_message").apply_async(kwargs=dict(message=message_data), cronjob=cronjob)
        
        # 3. Update tracking
        next_run = compute_next_run(cronjob.schedule)

        cronjob.atomic_update(
            last_run_at=timezone.now(),
            next_run_at=next_run,
            last_status="success",
            total_runs=models.F("total_runs") + 1,
        )

        print(f"[cron] executed job {cronjob_id} ({cronjob.name})")


    except Exception as e:
        print(f"[cron] error executing job {cronjob_id}: {e}")
        # Advance the schedule even on failure.  Leaving ``next_run_at`` in the
        # past makes the job permanently due, so the one-minute scheduler
        # retries it on every tick with no backoff.  An invalid/empty schedule
        # yields ``None``, which parks the job instead of spinning.
        next_run = compute_next_run(
            Cronjob.objects.filter(pk=cronjob_id)
            .values_list("schedule", flat=True)
            .first()
            or ""
        )
        Cronjob.atomic_update_by_pk(
            cronjob_id,
            last_run_at=timezone.now(),
            next_run_at=next_run,
            last_status="error",
        )
        raise e
