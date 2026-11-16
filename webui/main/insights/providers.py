"""Provider insight data helpers.

Computes per-provider limits, key state and usage windows from ``Response`` rows. The
Django/htmx web UI renders this via ``webui.views.insights`` +
``webui/templates/webui/insights/page.html``; this module keeps the shared/sortable data
logic (also exercised by ``server.tests.test_insight_tables``).
"""
from __future__ import annotations

from datetime import timedelta

from django.db.models import Count, Sum
from django.utils import timezone

from server.models.providers.api_provider import ApiProvider
from server.models.queries.response import Response, ResponseStatus


LIMIT_LABELS = (
    ("limit_request_per_minute", "RPM"),
    ("limit_request_per_hour", "RPH"),
    ("limit_request_per_day", "RPD"),
    ("limit_request_per_week", "RPW"),
    ("limit_request_per_month", "RPMo"),
    ("limit_tokens_per_minute", "TPM"),
    ("limit_tokens_per_hour", "TPH"),
    ("limit_tokens_per_day", "TPD"),
    ("limit_tokens_per_week", "TPW"),
    ("limit_tokens_per_month", "TPMo"),
    ("limit_parallel_calls", "par"),
)


def _human(n: int | float | None) -> str:
    if not n:
        return "0"
    n = float(n)
    if n >= 1_000_000:
        return f"{n / 1_000_000:.2f}M"
    if n >= 10_000:
        return f"{n / 1_000:.1f}k"
    return f"{int(n):,}"


def _limits_str(provider: ApiProvider) -> str:
    parts = [f"{value} {label}" for field, label in LIMIT_LABELS
             if (value := getattr(provider, field, 0))]
    return " · ".join(parts) if parts else "—"


class ProvidersView:
    """Sortable provider insight data (no UI rendering)."""

    NUMERIC_COLS = ("req_24h", "tok_24h", "req_7d", "tok_7d", "req_30d", "tok_30d")

    def __init__(self, *args, **kwargs):
        self._sort_col = "name"
        self._sort_desc = False
        self._selected_id: int | None = None

    def update(self) -> None:
        """UI refresh hook (no-op outside pyHtmlGui)."""

    def apply_sort(self, col: str) -> None:
        """Toggle direction on repeat, else sort the column
        (names/limits ascending, numbers descending)."""
        if col == self._sort_col:
            self._sort_desc = not self._sort_desc
        else:
            self._sort_col = col
            self._sort_desc = col in self.NUMERIC_COLS or col == "key"
        self.update()

    def sort_arrow(self, col: str) -> str:
        if col != self._sort_col:
            return ""
        return " ▼" if self._sort_desc else " ▲"

    def _window_stats(self, since) -> dict[int, dict[str, int]]:
        rows = (
            Response.objects.filter(
                status=ResponseStatus.SUCCESS,
                created_at__gte=since,
                aimodel__api_provider__isnull=False,
            )
            .values("aimodel__api_provider")
            .annotate(req=Count("id"), prompt=Sum("prompt_tokens"), comp=Sum("completion_tokens"))
        )
        return {
            row["aimodel__api_provider"]: {
                "req": row["req"] or 0,
                "tok": (row["prompt"] or 0) + (row["comp"] or 0),
            }
            for row in rows
        }

    @property
    def provider_rows(self) -> list[dict]:
        now = timezone.now()
        stats = {
            "24h": self._window_stats(now - timedelta(hours=24)),
            "7d": self._window_stats(now - timedelta(days=7)),
            "30d": self._window_stats(now - timedelta(days=30)),
        }
        rows = []
        providers = ApiProvider.objects.filter(enabled=True).order_by("name").prefetch_related("api_keys")
        for provider in providers:
            keys = [k for k in provider.api_keys.all() if k.enabled]
            if provider.default_api_key:
                key_state, key_count = "built-in", 0
            elif keys:
                key_state, key_count = "keys", len(keys)
            else:
                key_state, key_count = "none", 0
            s24 = stats["24h"].get(provider.pk, {"req": 0, "tok": 0})
            s7 = stats["7d"].get(provider.pk, {"req": 0, "tok": 0})
            s30 = stats["30d"].get(provider.pk, {"req": 0, "tok": 0})
            rows.append({
                "id": provider.pk,
                "name": provider.name,
                "key_state": key_state,
                "key_count": key_count,
                "limits": _limits_str(provider),
                "_req_24h": s24["req"], "_tok_24h": s24["tok"],
                "_req_7d": s7["req"], "_tok_7d": s7["tok"],
                "_req_30d": s30["req"], "_tok_30d": s30["tok"],
            })
        key_order = {"none": (0, 0), "built-in": (1, 0), "keys": (2, 0)}

        def sort_key(row: dict):
            col = self._sort_col
            if col in self.NUMERIC_COLS:
                return row[f"_{col}"]
            if col == "key":
                base, _ = key_order[row["key_state"]]
                return (base, row["key_count"])
            if col == "limits":
                return row["limits"]
            return row["name"].lower()

        rows.sort(key=sort_key, reverse=self._sort_desc)
        for row in rows:
            for col in self.NUMERIC_COLS:
                raw = row.pop(f"_{col}")
                row[col] = _human(raw)
        return rows
