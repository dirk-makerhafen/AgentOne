"""Abstract base model with dirty-field tracking and observability."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from dirtyfields import DirtyFieldsMixin
from dirtyfields.dirtyfields import reset_state
from django.db import models
from django.utils import timezone

from server.models.observables import ObservableMixin


class BaseModel(ObservableMixin, DirtyFieldsMixin, models.Model):
    """Abstract base model providing created/updated timestamps and dirty-field
    tracking for partial updates."""

    created_at: datetime = models.DateTimeField(db_index=True, editable=False, auto_now_add=True)
    updated_at: datetime = models.DateTimeField(editable=False, auto_now=True)

    class Meta:
        abstract = True

    def save(self, *args: Any, **kwargs: Any) -> Any:
        """Save the model, tracking dirty fields for partial updates.

        Only fields that have changed are included in ``update_fields``, which
        reduces unnecessary DB writes.
        """
        now = timezone.now()
        if not self.pk and self.created_at is None:
            self.created_at = now

        dirty_fields = self.get_dirty_fields(check_relationship=True)
        self.updated_at = now

        if self.pk is not None:
            if "update_fields" not in kwargs:
                fields_to_update = list(dirty_fields.keys())
                if "updated_at" not in fields_to_update:
                    fields_to_update.append("updated_at")
                if fields_to_update:
                    kwargs["update_fields"] = fields_to_update
            elif "updated_at" not in kwargs["update_fields"]:
                kwargs["update_fields"].append("updated_at")

        result = super().save(*args, **kwargs)
        reset_state(
            sender=self.__class__,
            instance=self,
            update_fields=kwargs.get("update_fields", []),
        )
        return result
