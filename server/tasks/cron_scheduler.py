"""
Cron job dispatch task, split out of ``tick_scheduler``.

Checks ``Cronjob`` records that are due (``next_run_at <= now``) once per
minute and dispatches each to the Celery queue via ``execute_cron_job``.
The heavy lifting (session resolution, message dispatch, ``next_run_at``
advance) lives in ``runtime/cron``; this task is just the scheduler beat.
"""

from __future__ import annotations

from celery import shared_task


@shared_task(name="tasks.cron_scheduler")
def cron_scheduler() -> None:
    """Dispatch due cron jobs to Celery workers (one-minute cadence)."""
    from runtime.cron.execute import execute_cron_job
    from runtime.cron.crons import Cronjobs

    for cronjob in Cronjobs().due():
        try:
            execute_cron_job(cronjob.pk)
            print(f"[cron] dispatched cron job {cronjob.pk} ({cronjob.name})")
        except Exception as e:
            print(f"[cron] error dispatching cron job {cronjob.pk}: {e}")
