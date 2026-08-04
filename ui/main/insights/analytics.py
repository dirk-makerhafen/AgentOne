"""Token & timing analytics view — usage over time, TTFT and throughput graphs.

All charts are rendered as server-side SVG (see ``svgcharts.py``) because the
pyHtmlGui framework re-renders views by replacing their innerHTML, which would
not re-execute inline scripts after a filter change.

The data comes from ``Response`` rows (created by ``call_llm``), filtered by
provider, model and time range. The per-request timing metrics feed the
scatter plots that help reason about cache effectiveness and the optimal
compaction point/size for a session.
"""
from __future__ import annotations

import math
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

from django.db.models import Avg, Count, Sum
from django.db.models.functions import Trunc
from django.utils import timezone

from server.models.queries.response import Response, ResponseStatus
from ui.lib.model_view import ModelView
from ui.main.insights import svgcharts

if TYPE_CHECKING:
    from ui.app import UiApp
    from ui.main.main_view import MainView


RANGE_OPTIONS = [
    ("24h", "Last 24 hours"),
    ("7d", "Last 7 days"),
    ("30d", "Last 30 days"),
    ("90d", "Last 90 days"),
    ("all", "All time"),
]

SCATTER_LIMIT = 800

# Metrics above the 99th percentile are treated as outliers (e.g. a response
# parked in a rate-limit queue for thousands of seconds) and dropped so they
# do not squash the visible axis.
OUTLIER_PERCENTILE = 99.0


def _percentile(values: list[float], pct: float) -> float | None:
    """Return the ``pct`` percentile of ``values`` (linear interpolation)."""
    if not values:
        return None
    vals = sorted(values)
    k = (len(vals) - 1) * (pct / 100.0)
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return vals[int(k)]
    return vals[f] * (c - k) + vals[c] * (k - f)


def _filter_outliers(points: list[tuple[float, float]], pct: float = OUTLIER_PERCENTILE) -> list[tuple[float, float]]:
    """Drop scatter points whose x or y exceeds the given percentile."""
    if not points:
        return points
    x_cap = _percentile([p[0] for p in points], pct)
    y_cap = _percentile([p[1] for p in points], pct)
    if x_cap is None or y_cap is None:
        return points
    return [p for p in points if p[0] <= x_cap and p[1] <= y_cap]


def _human(n: int | float | None) -> str:
    if n is None:
        return "—"
    n = float(n)
    if n >= 1_000_000:
        return f"{n / 1_000_000:.2f}M"
    if n >= 10_000:
        return f"{n / 1_000:.1f}k"
    if n >= 1_000:
        return f"{n:,.0f}"
    return f"{int(n):,}"


def _duration(seconds: float | None) -> str:
    if seconds is None:
        return "—"
    if seconds >= 60:
        return f"{seconds / 60:.2f}m"
    if seconds >= 1:
        return f"{seconds:.2f}s"
    return f"{seconds * 1000:.0f}ms"


def _speed(tokens: float | None) -> str:
    if tokens is None:
        return "—"
    return f"{tokens:,.0f} t/s"


class AnalyticsView(ModelView):
    DOM_ELEMENT_CLASS = "main-view"

    TEMPLATE_STR = '''
        <div class="main-view-header">
            <div class="main-view-title">Token Analytics</div>
            <div class="main-view-actions">
                <button class="panel-head-btn" title="Refresh" onclick="pyview.refresh()">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/></svg>
                </button>
            </div>
        </div>
        <div class="main-view-body">
            <div class="main-view-content" style="max-width:1200px">

                <div class="analytics-filters">
                    <select id="analytics_provider_{{pyview.uid}}" onchange="pyview.apply_filter('provider', this.value)">
                        <option value=""{% if not pyview._provider %} selected{% endif %}>All providers</option>
                        {% for name in pyview.provider_options %}
                        <option value="{{ name }}"{% if pyview._provider == name %} selected{% endif %}>{{ name }}</option>
                        {% endfor %}
                    </select>
                    <select id="analytics_model_{{pyview.uid}}" onchange="pyview.apply_filter('model', this.value)">
                        <option value=""{% if not pyview._model %} selected{% endif %}>All models</option>
                        {% for name in pyview.model_options %}
                        <option value="{{ name }}"{% if pyview._model == name %} selected{% endif %}>{{ name }}</option>
                        {% endfor %}
                    </select>
                    <select id="analytics_range_{{pyview.uid}}" onchange="pyview.apply_filter('range', this.value)">
                        {% for val, label in pyview.range_options %}
                        <option value="{{ val }}"{% if pyview._range == val %} selected{% endif %}>{{ label }}</option>
                        {% endfor %}
                    </select>
                </div>

                <div class="insights-grid">
                    {% for stat in pyview.stat_cards %}
                    <div class="insights-stat">
                        <div class="insights-stat-info">
                            <div class="insights-stat-value">{{ stat.value }}</div>
                            <div class="insights-stat-label">{{ stat.label }}</div>
                        </div>
                    </div>
                    {% endfor %}
                </div>

                <div class="analytics-card">
                    <div class="analytics-card-title">Tokens over time</div>
                    <div class="analytics-card-sub">Prompt (sent) · completion (received) · cached input</div>
                    {{ pyview.token_chart|safe }}
                </div>

                <div class="analytics-row">
                    <div class="analytics-card">
                        <div class="analytics-card-title">Time to first token</div>
                        <div class="analytics-card-sub">Average per bucket, seconds</div>
                        {{ pyview.ttft_chart|safe }}
                    </div>
                    <div class="analytics-card">
                        <div class="analytics-card-title">Generation speed</div>
                        <div class="analytics-card-sub">Completion tokens / stream time, per bucket</div>
                        {{ pyview.speed_chart|safe }}
                    </div>
                </div>

                <div class="analytics-row">
                    <div class="analytics-card">
                        <div class="analytics-card-title">TTFT vs new (non-cached) prompt tokens</div>
                        <div class="analytics-card-sub">Each dot is one response — first-token latency against the uncached portion of the context</div>
                        {{ pyview.ttft_scatter|safe }}
                    </div>
                    <div class="analytics-card">
                        <div class="analytics-card-title">Generation speed vs query size</div>
                        <div class="analytics-card-sub">Tokens/sec against prompt size per response</div>
                        {{ pyview.speed_scatter|safe }}
                    </div>
                </div>

            </div>
        </div>
    '''

    def __init__(self, subject: UiApp, parent: MainView, **kwargs):
        super().__init__(subject, parent, **kwargs)
        self.range_options = RANGE_OPTIONS
        self._provider = ""
        self._model = ""
        self._range = "24h"

    # ------------------------------------------------------------------
    # Filter state
    # ------------------------------------------------------------------

    @property
    def range_days(self) -> int | None:
        return {"24h": 1, "7d": 7, "30d": 30, "90d": 90, "all": None}.get(self._range, 1)

    def apply_filter(self, name: str, value: str) -> None:
        if name == "provider":
            self._provider = value.strip()
            if self._provider and self._model not in self.model_options:
                self._model = ""
        elif name == "model":
            self._model = value.strip()
        elif name == "range":
            self._range = value.strip() if value.strip() else "24h"
        self.update()

    def refresh(self) -> None:
        self.update()

    # ------------------------------------------------------------------
    # Filter option lists
    # ------------------------------------------------------------------

    @property
    def provider_options(self) -> list[str]:
        return list(
            Response.objects.exclude(provider_name="")
            .values_list("provider_name", flat=True)
            .distinct()
            .order_by("provider_name")
        )

    @property
    def model_options(self) -> list[str]:
        qs = Response.objects
        if self._provider:
            qs = qs.filter(provider_name=self._provider)
        return list(
            qs.exclude(model_name="")
            .values_list("model_name", flat=True)
            .distinct()
            .order_by("model_name")
        )

    # ------------------------------------------------------------------
    # Data access
    # ------------------------------------------------------------------

    def _base_qs(self):
        qs = Response.objects.filter(status=ResponseStatus.SUCCESS)
        if self._provider:
            qs = qs.filter(provider_name=self._provider)
        if self._model:
            qs = qs.filter(model_name=self._model)
        days = self.range_days
        if days:
            qs = qs.filter(created_at__gte=timezone.now() - timedelta(days=days))
        return qs

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    @property
    def stat_cards(self) -> list[dict[str, str]]:
        agg = self._base_qs().aggregate(
            requests=Count("id"),
            prompt=Sum("prompt_tokens"),
            completion=Sum("completion_tokens"),
            cached=Sum("cached_tokens"),
            reasoning=Sum("reasoning_tokens"),
            gen_time=Sum("token_generation_time"),
            ttft=Avg("time_to_first_token"),
        )
        gen_time = agg["gen_time"] or 0
        completion = agg["completion"] or 0
        speed = (completion / gen_time) if gen_time else None
        return [
            {"label": "Requests", "value": _human(agg["requests"] or 0)},
            {"label": "Tokens sent (prompt)", "value": _human(agg["prompt"])},
            {"label": "Tokens received (completion)", "value": _human(agg["completion"])},
            {"label": "Cached input tokens", "value": _human(agg["cached"])},
            {"label": "Reasoning tokens", "value": _human(agg["reasoning"])},
            {"label": "Avg time to first token", "value": _duration(agg["ttft"])},
            {"label": "Avg generation speed", "value": _speed(speed)},
        ]

    # ------------------------------------------------------------------
    # Time series
    # ------------------------------------------------------------------

    def _buckets(self) -> tuple[list[datetime], str]:
        """Return a contiguous list of bucket timestamps and the trunc kind."""
        days = self.range_days
        use_hour = days is not None and days <= 7
        tz = timezone.get_current_timezone()
        if use_hour:
            kind = "hour"
        else:
            kind = "day"
        if days:
            start = timezone.now() - timedelta(days=days)
        else:
            first = (
                Response.objects.filter(status=ResponseStatus.SUCCESS)
                .order_by("created_at")
                .values_list("created_at", flat=True)
                .first()
            )
            start = first if first else timezone.now()
        start = start.astimezone(tz)
        if use_hour:
            start = start.replace(minute=0, second=0, microsecond=0)
        else:
            start = start.replace(hour=0, minute=0, second=0, microsecond=0)
        end = timezone.now().astimezone(tz)
        buckets: list[datetime] = []
        current = start
        step = timedelta(hours=1) if use_hour else timedelta(days=1)
        while current <= end:
            buckets.append(current)
            current += step
        if not buckets:
            buckets.append(start)
        return buckets, kind

    def _time_series_rows(self, kind: str, qs=None) -> dict[datetime, dict[str, Any]]:
        tz = timezone.get_current_timezone()
        rows = (
            (qs if qs is not None else self._base_qs())
            .annotate(bucket=Trunc("created_at", kind, tzinfo=tz))
            .values("bucket")
            .annotate(
                prompt=Sum("prompt_tokens"),
                completion=Sum("completion_tokens"),
                cached=Sum("cached_tokens"),
                reasoning=Sum("reasoning_tokens"),
                count=Count("id"),
                gen_time=Sum("token_generation_time"),
                ttft=Avg("time_to_first_token"),
            )
            .order_by("bucket")
        )
        by_bucket = {row["bucket"]: row for row in rows if row["bucket"]}
        return by_bucket

    def _label(self, dt: datetime, kind: str) -> str:
        if kind == "hour":
            return dt.strftime("%H:%M")
        return dt.strftime("%m-%d")

    @property
    def _series(self) -> tuple[list[str], dict[str, list[float | None]], dict[str, list[float | None]]]:
        buckets, kind = self._buckets()
        labels = [self._label(bucket, kind) for bucket in buckets]

        # Token series — plain sums, no outlier filtering needed.
        by_bucket = self._time_series_rows(kind)
        tokens: dict[str, list[float | None]] = {"prompt": [], "completion": [], "cached": []}
        for bucket in buckets:
            row = by_bucket.get(bucket)
            tokens["prompt"].append(float(row["prompt"] or 0) if row else 0.0)
            tokens["completion"].append(float(row["completion"] or 0) if row else 0.0)
            tokens["cached"].append(float(row["cached"] or 0) if row else 0.0)

        # Timing series — drop TTFT outliers before averaging so a single
        # queued response does not skew the bucket average.
        timing_qs = self._base_qs().filter(time_to_first_token__gt=0)
        ttft_vals = list(timing_qs.values_list("time_to_first_token", flat=True))
        ttft_cap = _percentile(ttft_vals, OUTLIER_PERCENTILE)
        if ttft_cap is not None:
            timing_qs = timing_qs.filter(time_to_first_token__lte=ttft_cap)
        by_bucket_t = self._time_series_rows(kind, timing_qs)

        ttft: list[float | None] = []
        speed: list[float | None] = []
        for bucket in buckets:
            row = by_bucket_t.get(bucket)
            if row is None or row["count"] == 0:
                ttft.append(None)
                speed.append(None)
                continue
            ttft.append(float(row["ttft"]) if row["ttft"] else None)
            gen_time = row["gen_time"] or 0
            comp = row["completion"] or 0
            speed.append((comp / gen_time) if gen_time else None)
        return labels, tokens, {"ttft": ttft, "speed": speed}

    # ------------------------------------------------------------------
    # Charts
    # ------------------------------------------------------------------

    @property
    def token_chart(self) -> str:
        labels, tokens, _ = self._series
        return svgcharts.line_chart(
            {"prompt": tokens["prompt"], "completion": tokens["completion"], "cached": tokens["cached"]},
            labels,
            stacked=True,
            colors={"prompt": "#7c8cf8", "completion": "var(--accent)", "cached": "var(--success)"},
            empty_text="No token usage in this range",
        )

    @property
    def ttft_chart(self) -> str:
        labels, _, timing = self._series
        return svgcharts.line_chart(
            {"time to first token": timing["ttft"]},
            labels,
            colors={"time to first token": "var(--warning)"},
            area=False,
            empty_text="No timing data in this range",
        )

    @property
    def speed_chart(self) -> str:
        labels, _, timing = self._series
        return svgcharts.line_chart(
            {"tokens/s": timing["speed"]},
            labels,
            colors={"tokens/s": "var(--info)"},
            area=False,
            empty_text="No timing data in this range",
        )

    @property
    def ttft_scatter(self) -> str:
        rows = list(
            self._base_qs()
            .filter(time_to_first_token__gt=0)
            .values_list("prompt_tokens", "cached_tokens", "time_to_first_token")[:SCATTER_LIMIT]
        )
        points = _filter_outliers(
            [(max((p or 0) - (c or 0), 0), (t or 0)) for p, c, t in rows]
        )
        return svgcharts.scatter_chart(
            points,
            x_label="New (non-cached) prompt tokens",
            y_label="TTFT (s)",
            color="var(--warning)",
            empty_text="No timing data in this range",
        )

    @property
    def speed_scatter(self) -> str:
        rows = list(
            self._base_qs()
            .filter(token_generation_time__gt=0, completion_tokens__gt=0)
            .values_list("prompt_tokens", "completion_tokens", "token_generation_time")[:SCATTER_LIMIT]
        )
        points = _filter_outliers(
            [((p or 0), (c or 0) / gen_time) for p, c, gen_time in rows]
        )
        return svgcharts.scatter_chart(
            points,
            x_label="Prompt size (tokens)",
            y_label="tokens/s",
            color="var(--accent)",
            empty_text="No timing data in this range",
        )
