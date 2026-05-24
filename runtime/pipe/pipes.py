"""Query interface for named pipes."""
from __future__ import annotations

from server.models.pipe import NamedPipe


class Pipes:
    """Query interface for NamedPipe model."""

    @staticmethod
    def root():
        """Return all NamedPipe objects."""
        return NamedPipe.objects.all()
