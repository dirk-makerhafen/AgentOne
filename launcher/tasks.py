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


@shared_task(name="agentone.resolve_local_changes", bind=True, ignore_result=True)
def resolve_local_changes(self, run_id: str, action: str, preference: str = ""):  # pylint: disable=unused-argument
    """Undo or merge local changes that are blocking the self-update."""
    from launcher.local_changes import (  # pylint: disable=import-outside-toplevel
        merge_local_changes,
        undo_local_changes,
    )

    def log(message: str, level: str = "info"):
        append_log(run_id, message, level)

    try:
        if action == "undo":
            log("Saving local changes to git stash...")
            result = undo_local_changes(log=log)
            status = "success"
        elif action == "merge":
            log("Stashing local changes, updating AgentOne, then reapplying them...")
            result = merge_local_changes(preference=preference, log=log)
            status = "needs_attention" if result["status"] == "conflict" else "success"
            if result["status"] == "conflict":
                from webui.features.settings.sessions import start_conflict_session  # pylint: disable=import-outside-toplevel

                session_id = start_conflict_session(
                    conflicts=result["conflicts"],
                    paths=result["paths"],
                    stash_ref=result["stash_ref"],
                    preference=preference,
                )
                result["session_id"] = session_id
                if session_id:
                    log(f"Opened a chat to resolve the conflicts (session {session_id}).", "warning")
                else:
                    log("Could not open a conflict-resolution chat; see the stash reference above.", "error")
        else:
            raise ValueError(f"Unknown local-change action: {action}")
        finish_run(run_id, status, result=result)
    except Exception as exc:  # pylint: disable=broad-exception-caught
        log(f"Could not {action} local changes: {exc}", "error")
        finish_run(run_id, "failed", error=str(exc))
    finally:
        release_queue()
