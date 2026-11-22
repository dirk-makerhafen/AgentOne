"""Celery tasks owned by the launcher app (auto-discovered by config.celery)."""

from __future__ import annotations

from celery import shared_task

from launcher.update_state import append_log, finish_run, release_queue


@shared_task(name="agentone.update", bind=True, ignore_result=True)
def update_agentone(self, run_id: str, restart: bool = True):  # pylint: disable=unused-argument
    """Run the full self-update pipeline for a UI-initiated run."""
    from launcher.updates import UpdateError, run_update

    def log(message: str, level: str = "info"):
        append_log(run_id, message, level)

    try:
        log("Starting AgentOne update...")
        result = run_update(restart=restart, log=log)
        finish_run(run_id, result["status"], result=result)
    except UpdateError as exc:
        log(str(exc), "error")
        finish_run(run_id, "failed", error=str(exc))
    except Exception as exc:  # pylint: disable=broad-exception-caught
        log(f"Unexpected update error: {exc}", "error")
        finish_run(run_id, "failed", error=f"Unexpected error: {exc}")
    finally:
        # The view releases this when queuing fails; the task owns it otherwise.
        release_queue()
