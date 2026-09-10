"""Providers insight view — per-provider limits, keys and usage windows.

One table row per enabled provider: configured limits, whether an API key
is set up, and successful request / token counts for the last 24h, 7 days
and 30 days (from ``Response`` rows via their ``AiModel``).
"""
from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

from django.db.models import Count, Sum
from django.utils import timezone

from server.models.providers.api_provider import ApiProvider
from server.models.queries.response import Response, ResponseStatus
from ui.lib.model_view import ModelView

if TYPE_CHECKING:
    from ui.app import UiApp
    from ui.main.main_view import MainView


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


class ProvidersView(ModelView):
    DOM_ELEMENT_CLASS = "main-view"

    NUMERIC_COLS = ("req_24h", "tok_24h", "req_7d", "tok_7d", "req_30d", "tok_30d")

    TEMPLATE_STR = '''
        <div class="main-view-header">
            <div class="main-view-title">Providers</div>
            <div class="main-view-actions">
                <button class="panel-head-btn" title="Refresh" onclick="pyview.refresh()">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/></svg>
                </button>
            </div>
        </div>
        <div class="main-view-body">
            <div class="main-view-content" style="max-width:1200px">
                <div class="analytics-card">
                    <div class="analytics-card-title">Usage by provider</div>
                    <div class="analytics-card-sub">Successful responses in the last 24 hours, 7 days and 30 days — click a column header to sort</div>
                    <table class="insights-table">
                        <thead><tr>
                            <th class="sortable" onclick="pyview.apply_sort('name')">Provider{{ pyview.sort_arrow('name') }}</th>
                            <th class="sortable" onclick="pyview.apply_sort('key')">API key{{ pyview.sort_arrow('key') }}</th>
                            <th class="sortable" onclick="pyview.apply_sort('limits')">Limits{{ pyview.sort_arrow('limits') }}</th>
                            <th class="num sortable" onclick="pyview.apply_sort('req_24h')">Req 24h{{ pyview.sort_arrow('req_24h') }}</th>
                            <th class="num sortable" onclick="pyview.apply_sort('tok_24h')">Tok 24h{{ pyview.sort_arrow('tok_24h') }}</th>
                            <th class="num sortable" onclick="pyview.apply_sort('req_7d')">Req 7d{{ pyview.sort_arrow('req_7d') }}</th>
                            <th class="num sortable" onclick="pyview.apply_sort('tok_7d')">Tok 7d{{ pyview.sort_arrow('tok_7d') }}</th>
                            <th class="num sortable" onclick="pyview.apply_sort('req_30d')">Req 30d{{ pyview.sort_arrow('req_30d') }}</th>
                            <th class="num sortable" onclick="pyview.apply_sort('tok_30d')">Tok 30d{{ pyview.sort_arrow('tok_30d') }}</th>
                        </tr></thead>
                        <tbody>
                        {% for row in pyview.provider_rows %}
                        <tr class="clickable{% if row.id == pyview._selected_id %} selected{% endif %}" onclick="pyview.open_provider({{ row.id }})">
                            <td><strong>{{ row.name }}</strong></td>
                            <td>{% if row.key_state == "built-in" %}<span class="key-badge key-builtin">built-in</span>{% elif row.key_state == "keys" %}<span class="key-badge key-ok">✓ {{ row.key_count }}</span>{% else %}<span class="key-badge key-missing">—</span>{% endif %}</td>
                            <td class="muted">{{ row.limits }}</td>
                            <td class="num">{{ row.req_24h }}</td><td class="num">{{ row.tok_24h }}</td>
                            <td class="num">{{ row.req_7d }}</td><td class="num">{{ row.tok_7d }}</td>
                            <td class="num">{{ row.req_30d }}</td><td class="num">{{ row.tok_30d }}</td>
                        </tr>
                        {% endfor %}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    '''

    def __init__(self, subject: UiApp, parent: MainView, **kwargs):
        super().__init__(subject, parent, **kwargs)
        self._sort_col = "name"
        self._sort_desc = False
        self._selected_id: int | None = None

    def refresh(self) -> None:
        self.update()

    def open_provider(self, provider_id: int) -> None:
        from ui.main.rightpanel.provider.rightpanel_provider import RightPanelProvider
        provider = ApiProvider.objects.filter(pk=provider_id).first()
        if provider is None:
            return
        self._selected_id = provider.pk
        self.parent.parent.rightpanel.set_view(RightPanelProvider, provider)
        self.update()

    def apply_sort(self, col: str) -> None:
        """Header click: toggle direction on repeat, else sort the column
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
            if provider.data.get("default_api_key"):
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
