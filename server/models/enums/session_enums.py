from __future__ import annotations

from django.db import models


class SessionType(models.TextChoices):
    """Classification of a session's purpose and lifetime.

    - ``SESSION``: a user-facing conversation (permanent, e.g. main chat).
    - ``SUBSESSION``: a named, reusable background session created via
      ``start_subsession`` (permanent).
    - ``SUBTASK_DELEGATE``: a one-off task sent to another agent via
      ``delegate_task`` (single-use).
    - ``SUBTASK_FORK``: a forked child session via ``spawn_subtask``
      (single-use).
    """

    SESSION = "session", "Session"
    SUBSESSION = "subsession", "Subsession"
    SUBTASK_DELEGATE = "subtask_delegate", "Subtask (delegate)"
    SUBTASK_FORK = "subtask_fork", "Subtask (fork)"
    SUBTASK_COMPACT = "subtask_compaczt", "Subtask (session compaction)"

