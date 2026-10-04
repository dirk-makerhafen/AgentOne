"""SessionHookRun — tracks one detached session-hook dispatch.

A hook firing (see ``docs/session-hooks.md``) spawns a ``SUBTASK_HOOK`` fork
running the hook's task. This row is the unit the timeout reaper operates on:
it records the root call and the wall-clock deadline. Runs are deleted when
their root call ends; the reaper marks expired ones first (short audit
trail, deleted after 7 days — see ``_reap_hook_timeouts``).

Concurrency invariant: at most one non-ended run per (session, hook_name) —
enforced by ``runtime.hooks.maybe_fire_hooks`` checking before dispatch, not
by the DB (a hook may legitimately run again after the previous run ended).
"""
from __future__ import annotations

from django.db import models

from server.models.base_model import BaseModel


class SessionHookRun(BaseModel):
    """One session-hook firing and its detached execution."""

    #: The parent session the hook fired in.
    session = models.ForeignKey(
        "server.SessionModel",
        on_delete=models.CASCADE,
        related_name="hook_runs",
    )

    #: Hook entry name from the agent manifest (``hooks: - name: ...``).
    hook_name: str = models.CharField(max_length=255, db_index=True)

    #: Lifecycle event: ``stop`` | ``pre_compact`` | ``post_compact`` | ``session_end``.
    event: str = models.CharField(max_length=32, db_index=True)

    #: Snapshot anchor message the fork was built on (may be null for
    #: ``session_end`` on an empty session).
    anchor_message = models.ForeignKey(
        "server.Message",
        on_delete=models.SET_NULL,
        default=None,
        null=True,
        blank=True,
        related_name="hook_runs",
    )

    #: Root call of the hook chain in the fork session (null until dispatched).
    root_call = models.ForeignKey(
        "server.AgentTaskCall",
        on_delete=models.SET_NULL,
        default=None,
        null=True,
        blank=True,
        related_name="hook_runs",
    )

    #: Wall-clock deadline (dispatch + ``timeout_seconds``).
    deadline = models.DateTimeField(default=None, null=True, blank=True, db_index=True)

    #: ``dispatched`` → ``ended`` (root call ended, row deletable) |
    #: ``expired`` (reaper cancelled the root call).
    status: str = models.CharField(max_length=16, default="dispatched", db_index=True)

    def __str__(self) -> str:
        return f"hook:{self.hook_name} {self.event} s{self.session_id} [{self.status}]"
