"""
Sleep-guard reconciliation task, split out of ``recovery_scheduler`` /
``tick_scheduler``.

Keeps a single ``caffeinate -dimsu`` running while local models have been
used within the ``sleep_guard_release_delay_minutes`` grace window and power
conditions allow it.  Runs once per minute — Celery prefork makes per-call
worker-local state unreliable, so the guard is owned by this scheduler.

The actual guard logic (pidfile management, process spawning) lives in
``runtime/sleep_guard``; this task is just the beat wrapper around it.
"""

from __future__ import annotations

from celery import shared_task


@shared_task(name="tasks.sleep_guard_scheduler")
def sleep_guard_scheduler() -> None:
    """Reconcile the sleep guard (``caffeinate``) with recent local-LLM
    activity and battery/AC state.  Run on the 60s cadence.
    """
    try:
        from runtime.sleep_guard import manage_sleep_guard
        result = manage_sleep_guard()
        if result["state"] != "off":
            print(f"[sleep-guard] {result['state']} — {result['reason']}")
    except Exception as e:
        print(f"[sleep-guard] error managing sleep guard: {e}")
