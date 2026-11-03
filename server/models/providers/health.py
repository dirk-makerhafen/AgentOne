"""Health/availability tracking shared by models, API keys and providers.

``enabled`` is the admin/manifest intent; these fields record what actually
happened on the wire (a 404 model id, a revoked key, repeated 5xx, ...).
Keeping the two separate means a manifest reload never overwrites an observed
failure and an observed failure never silently hides a model from the admin UI.
"""
from __future__ import annotations

from datetime import timedelta
from typing import Any

from django.db import models
from django.utils import timezone

from server.models.enums.provider_enums import HealthStatus


def _json_safe(value: Any) -> Any:
    """Best-effort JSON-safe copy of a value (drops non-serialisable bits)."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    return str(value)


class HealthTrackedModel(models.Model):
    """Abstract mixin adding an observed-health status and helpers.

    The concrete model decides which failures are relevant; this mixin only
    stores the state and provides the write/read helpers.  ``record_*`` methods
    persist immediately so a worker crash between the call and the next
    admission check cannot leave a stale ``ACTIVE`` health marker behind.
    """

    _HEALTH_LABELS = {
        HealthStatus.UNKNOWN: "",
        HealthStatus.HEALTHY: "",
        HealthStatus.DEGRADED: "degraded",
        HealthStatus.RATE_LIMITED: "rate limited",
        HealthStatus.UNAVAILABLE: "unavailable",
        HealthStatus.AUTH_ERROR: "auth error",
        HealthStatus.CONFIG_ERROR: "config error",
    }

    status = models.CharField(
        max_length=16,
        choices=HealthStatus.choices,
        default=HealthStatus.UNKNOWN,
        db_index=True,
    )
    status_reason = models.CharField(max_length=512, default="", blank=True)
    status_detail = models.JSONField(default=dict, blank=True)
    status_changed_at = models.DateTimeField(default=None, null=True, blank=True)
    status_retry_at = models.DateTimeField(default=None, null=True, blank=True)
    consecutive_failures = models.IntegerField(default=0)

    class Meta:
        abstract = True

    # ------------------------------------------------------------------
    # Read side
    # ------------------------------------------------------------------
    def health_blocks_calls(self, now=None) -> bool:
        """Whether this row must be skipped instead of being tried again.

        * ``UNAVAILABLE`` / ``AUTH_ERROR`` are sticky until a manual probe or a
          successful call clears them.
        * ``DEGRADED`` / ``CONFIG_ERROR`` block only until ``status_retry_at``.
        * ``RATE_LIMITED`` is intentionally handled by the existing key/token
          rate limiter; it is not a hard block here.
        """
        now = now or timezone.now()
        if self.status in (HealthStatus.UNAVAILABLE, HealthStatus.AUTH_ERROR):
            return True
        if self.status in (HealthStatus.DEGRADED, HealthStatus.CONFIG_ERROR):
            return bool(self.status_retry_at and now < self.status_retry_at)
        return False

    @property
    def health_label(self) -> str:
        """Short human label for UI badges (empty when unknown/healthy).

        Temporary states drop the label once their retry window has passed, so
        the badge does not outlive the condition that produced it.
        """
        if self.status in (HealthStatus.DEGRADED, HealthStatus.CONFIG_ERROR):
            if not self.status_retry_at or self.status_retry_at <= timezone.now():
                return ""
        return self._HEALTH_LABELS.get(self.status, "")

    # ------------------------------------------------------------------
    # Write side
    # ------------------------------------------------------------------
    def record_health_error(
        self,
        status: str,
        reason: str = "",
        *,
        detail: dict | None = None,
        retry_after_seconds: float | None = None,
        sticky: bool = False,
    ) -> None:
        """Persist an observed failure.

        ``retry_after_seconds`` sets the earliest retry time for non-sticky
        states (``DEGRADED`` / ``CONFIG_ERROR``).  ``sticky`` states keep
        ``status_retry_at`` null and are only cleared by a probe/success.
        """
        now = timezone.now()
        retry_at = None
        if not sticky and retry_after_seconds:
            retry_at = now + timedelta(seconds=retry_after_seconds)
        self.status = status
        self.status_reason = (reason or "")[:512]
        self.status_detail = _json_safe(detail or {})
        self.status_changed_at = now
        self.status_retry_at = retry_at
        self.consecutive_failures = (self.consecutive_failures or 0) + 1
        self.save(
            update_fields=[
                "status",
                "status_reason",
                "status_detail",
                "status_changed_at",
                "status_retry_at",
                "consecutive_failures",
            ]
        )

    def record_health_success(self) -> None:
        """Clear a failure state after a successful call (no-op when healthy)."""
        if (
            self.status == HealthStatus.HEALTHY
            and not self.status_reason
            and not self.status_retry_at
            and not self.consecutive_failures
        ):
            return
        self.status = HealthStatus.HEALTHY
        self.status_reason = ""
        self.status_detail = {}
        self.status_changed_at = timezone.now()
        self.status_retry_at = None
        self.consecutive_failures = 0
        self.save(
            update_fields=[
                "status",
                "status_reason",
                "status_detail",
                "status_changed_at",
                "status_retry_at",
                "consecutive_failures",
            ]
        )

    def clear_health(self) -> None:
        """Reset to ``UNKNOWN`` — used by a manual probe before re-testing."""
        self.status = HealthStatus.UNKNOWN
        self.status_reason = ""
        self.status_detail = {}
        self.status_changed_at = timezone.now()
        self.status_retry_at = None
        self.consecutive_failures = 0
        self.save(
            update_fields=[
                "status",
                "status_reason",
                "status_detail",
                "status_changed_at",
                "status_retry_at",
                "consecutive_failures",
            ]
        )
