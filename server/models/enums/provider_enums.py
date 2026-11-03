"""Enums for provider/model health tracking."""
from __future__ import annotations

from django.db import models


class HealthStatus(models.TextChoices):
    """Observed health of an :class:`AiModel`, :class:`ApiKey` or :class:`ApiProvider`.

    ``enabled`` remains the *intent* (an admin/manifest switch); ``status`` is
    the *observed* state after real calls.  A model can be enabled but
    unavailable because its provider no longer serves it.

    Applicability per state:

    * ``AiModel`` — all states (``UNAVAILABLE`` = model id rejected by provider).
    * ``ApiKey`` — ``HEALTHY``, ``RATE_LIMITED``, ``AUTH_ERROR``, ``DEGRADED``.
    * ``ApiProvider`` — ``HEALTHY``, ``DEGRADED``, ``AUTH_ERROR``.
    """

    UNKNOWN = "UNKNOWN", "Unknown"
    HEALTHY = "HEALTHY", "Healthy"
    DEGRADED = "DEGRADED", "Degraded (temporary errors)"
    RATE_LIMITED = "RATE_LIMITED", "Rate limited"
    UNAVAILABLE = "UNAVAILABLE", "Unavailable (not found)"
    AUTH_ERROR = "AUTH_ERROR", "Authentication error"
    CONFIG_ERROR = "CONFIG_ERROR", "Configuration error"
