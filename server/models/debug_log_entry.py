"""Immutable log entries for debugging agent sessions."""
from __future__ import annotations

from typing import Any

from django.core.exceptions import ValidationError
from django.db import models

from server.models.base_model import BaseModel


class DebugLogEntry(BaseModel):
    """An immutable debug event recorded during an agent session.

    Once created, existing entries cannot be modified (the ``save`` method
    raises :class:`ValidationError` if ``self.pk`` is already set).
    """

    session: models.ForeignKey | None = models.ForeignKey(
        "server.SessionModel",
        on_delete=models.CASCADE,
        related_name="debug_log_entries",
    )
    event: str = models.CharField(max_length=64)
    status: str = models.CharField(max_length=16)

    def save(self, *args: Any, **kwargs: Any) -> Any:
        """Raise :class:`ValidationError` on update; delegate to super on create."""
        if self.pk:
            raise ValidationError(
                f"You may not edit an existing {self._meta.model_name}"
            )
        return super().save(*args, **kwargs)
