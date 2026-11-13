"""Insights: aggregate counts, token usage and provider/model breakdown."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

from django.core.cache import cache
from django.db.models import Avg, Count, Sum
from django.db.models.functions import Trunc
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from server.models.agents.agent import AgentModel
from server.models.collections.data_collection import DataCollection
from server.models.cron import Cronjob
from server.models.message import Message
from server.models.project import Project
from server.models.providers.ai_model import AiModel
from server.models.providers.api_provider import ApiProvider
from server.models.queries.query import Query
from server.models.queries.response import Response, ResponseStatus
from server.models.sessions.session import SessionModel
from server.models.tasks.agent_task_call import AgentTaskCall
from server.models.workitems.work_item import WorkItem
from webui.views.common import render_page

log = logging.getLogger(__name__)

RANGE_OPTIONS = (
    ("24h", "Last 24 hours"),
    ("7d", "Last 7 days"),
    ("30d", "Last 30 days"),
    ("90d", "Last 90 days"),
    ("all", "All time"),
)
_RANGE_DAYS = {"24h": 1, "7d": 7, "30d": 30, "90d": 90, "all": None}
_RANGE_LABELS = dict(RANGE_OPTIONS)

#: Inspect table on the dashboard: rows per page.
INSPECT_LIMIT = 200


def insights(request, tab: str = "dashboard"):
    if tab not in ("dashboard", "analytics", "providers", "models"):
        tab = "dashboard"
    builders = {
        "dashboard": _dashboard_context,
        "analytics": _analytics_context,
        "providers": _providers_context,
        "models": _models_context,
    }
    context = {"tab": tab}
    context.update(builders[tab](request))
    return render_page(request, "insights", "webui/insights/page.html", context)


def _token_totals():
    totals = Response.objects.aggregate(
        prompt=Sum("prompt_tokens"),
        completion=Sum("completion_tokens"),
        cached=Sum("cached_tokens"),
        reasoning=Sum("reasoning_tokens"),
    )
    return {
        "prompt": totals["prompt"] or 0,
        "completion": totals["completion"] or 0,
        "cached": totals["cached"] or 0,
        "reasoning": totals["reasoning"] or 0,
    }


def _dashboard_context(request):
    agent_filter = (request.GET.get("agent") or "").strip()
    status_filter = (request.GET.get("status") or "").strip()
    task_filter = (request.GET.get("task") or "").strip()
    session_filter = (request.GET.get("session") or "").strip()
    calls = AgentTaskCall.objects.select_related(
        "task_definition", "session", "session_version__agent", "parent_taskrun"
    ).order_by("-pk")
    if agent_filter:
        calls = calls.filter(session_version__agent__name__icontains=agent_filter)
    if status_filter:
        calls = calls.filter(status=status_filter)
    if task_filter:
        calls = calls.filter(task_definition__name__icontains=task_filter)
    if session_filter:
        if session_filter.isdigit():
            calls = calls.filter(session__pk=int(session_filter))
        else:
            calls = calls.filter(session__name__icontains=session_filter)
    result_count = calls.count()
    inspect_rows = list(calls[:INSPECT_LIMIT])
    return {
        "stats": [
            ("Agents", AgentModel.objects.filter(is_archived=False).count()),
            ("Projects", Project.objects.count()),
            ("Sessions", SessionModel.objects.count()),
            ("Messages", Message.objects.count()),
            ("Queries", Query.objects.count()),
            ("Responses", Response.objects.count()),
            ("Task calls", AgentTaskCall.objects.count()),
            ("Work items", WorkItem.objects.count()),
            ("Collections", DataCollection.objects.count()),
            ("Cron jobs", Cronjob.objects.filter(is_archived=False).count()),
        ],
        "tokens": _token_totals(),
        "task_status": list(
            AgentTaskCall.objects.values("status")
            .annotate(total=Count("pk"))
            .order_by("-total")[:12]
        ),
        "response_status": list(
            Response.objects.values("status")
            .annotate(total=Count("pk"))
            .order_by("-total")
        ),
        "inspect": {
            "agent": agent_filter,
            "status": status_filter,
            "task": task_filter,
            "session": session_filter,
            "rows": inspect_rows,
            "count": result_count,
            "limit": INSPECT_LIMIT,
            "status_options": list(
                AgentTaskCall.objects.values_list("status", flat=True)
                .order_by("status")
                .distinct()
            ),
        },
    }


def _range_key(request) -> str:
    value = (request.GET.get("range") or "").strip()
    return value if value in _RANGE_DAYS else "24h"


def _analytics_base(request) -> tuple:
    """Return ``(qs, provider, model, range_key)`` for the analytics tab."""
    provider = (request.GET.get("provider") or "").strip()
    model = (request.GET.get("model") or "").strip()
    range_key = _range_key(request)
    qs = Response.objects.filter(status=ResponseStatus.SUCCESS)
    if provider:
        qs = qs.filter(provider_name=provider)
    if model:
        qs = qs.filter(model_name=model)
    days = _RANGE_DAYS[range_key]
    if days:
        qs = qs.filter(created_at__gte=timezone.now() - timedelta(days=days))
    return qs, provider, model, range_key


def _human(value) -> str:
    if value is None:
        return "—"
    value = float(value)
    if value >= 1_000_000:
        return f"{value / 1_000_000:.2f}M"
    if value >= 10_000:
        return f"{value / 1_000:.1f}k"
    if value >= 1_000:
        return f"{value:,.0f}"
    return f"{int(value):,}"


def _duration(seconds) -> str:
    if seconds is None:
        return "—"
    if seconds >= 60:
        return f"{seconds / 60:.2f}m"
    if seconds >= 1:
        return f"{seconds:.2f}s"
    return f"{seconds * 1000:.0f}ms"


def _speed(tokens) -> str:
    if tokens is None:
        return "—"
    return f"{tokens:,.0f} t/s"


def _analytics_buckets(range_key: str) -> tuple[list[datetime], str]:
    """Contiguous bucket timestamps (hour/day/week) and the trunc kind."""
    days = _RANGE_DAYS[range_key]
    tz = timezone.get_current_timezone()
    if days is None:
        first = (
            Response.objects.filter(status=ResponseStatus.SUCCESS)
            .order_by("created_at")
            .values_list("created_at", flat=True)
            .first()
        )
        start = first or timezone.now()
        span_days = (timezone.now() - start).days
        if span_days > 60:
            kind, step = "week", timedelta(days=7)
        else:
            kind, step = "day", timedelta(days=1)
    elif days <= 1:
        kind, step = "hour", timedelta(hours=1)
        start = timezone.now() - timedelta(days=days)
    elif days <= 30:
        kind, step = "day", timedelta(days=1)
        start = timezone.now() - timedelta(days=days)
    else:
        # Long ranges use weekly buckets so the bar chart stays readable.
        kind, step = "week", timedelta(days=7)
        start = timezone.now() - timedelta(days=days)

    start = start.astimezone(tz)
    if kind == "hour":
        start = start.replace(minute=0, second=0, microsecond=0)
    elif kind == "day":
        start = start.replace(hour=0, minute=0, second=0, microsecond=0)
    else:
        start = (start - timedelta(days=start.weekday())).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
    end = timezone.now().astimezone(tz)
    buckets: list[datetime] = []
    current = start
    while current <= end:
        buckets.append(current)
        current += step
    if not buckets:
        buckets.append(start)
    return buckets, kind


def _bucket_label(value: datetime, kind: str) -> str:
    if kind == "hour":
        return value.strftime("%H:%M")
    if kind == "week":
        return value.strftime("%m/%d")
    return value.strftime("%m/%d")


def _daily_series(qs, range_key: str) -> list[dict]:
    buckets, kind = _analytics_buckets(range_key)
    tz = timezone.get_current_timezone()
    rows = (
        qs.annotate(bucket=Trunc("created_at", kind, tzinfo=tz))
        .values("bucket")
        .annotate(
            input_tokens=Sum("prompt_tokens"),
            output_tokens=Sum("completion_tokens"),
            total=Count("pk"),
        )
        .order_by("bucket")
    )
    by_bucket = {row["bucket"]: row for row in rows if row["bucket"]}
    daily = []
    for bucket in buckets:
        row = by_bucket.get(bucket, {})
        daily.append(
            {
                "label": _bucket_label(bucket, kind),
                "input": row.get("input_tokens") or 0,
                "output": row.get("output_tokens") or 0,
                "count": row.get("total") or 0,
            }
        )
    peak = max((item["input"] + item["output"] for item in daily), default=0) or 1
    for item in daily:
        item["input_pct"] = round(item["input"] * 100 / peak, 2)
        item["output_pct"] = round(item["output"] * 100 / peak, 2)
    return daily


def _analytics_context(request):
    base, provider, model, range_key = _analytics_base(request)

    agg = base.aggregate(
        requests=Count("pk"),
        prompt=Sum("prompt_tokens"),
        completion=Sum("completion_tokens"),
        cached=Sum("cached_tokens"),
        reasoning=Sum("reasoning_tokens"),
        gen_time=Sum("token_generation_time"),
        ttft=Avg("time_to_first_token"),
    )
    completion = agg["completion"] or 0
    gen_time = agg["gen_time"] or 0
    analytics_stats = [
        {"label": "Requests", "value": _human(agg["requests"] or 0)},
        {"label": "Prompt tokens", "value": _human(agg["prompt"])},
        {"label": "Completion tokens", "value": _human(agg["completion"])},
        {"label": "Cached tokens", "value": _human(agg["cached"])},
        {"label": "Reasoning tokens", "value": _human(agg["reasoning"])},
        {"label": "Avg time to first token", "value": _duration(agg["ttft"])},
        {
            "label": "Avg generation speed",
            "value": _speed((completion / gen_time) if gen_time else None),
        },
    ]

    daily = _daily_series(base, range_key)

    provider_rows = list(
        base.values("provider_name")
        .annotate(
            total=Count("pk"),
            input_tokens=Sum("prompt_tokens"),
            output_tokens=Sum("completion_tokens"),
        )
        .order_by("-total")[:15]
    )
    peak_provider = max((row["total"] for row in provider_rows), default=0) or 1
    for row in provider_rows:
        row["pct"] = round(row["total"] * 100 / peak_provider, 2)

    model_rows = list(
        base.values("provider_name", "model_name")
        .annotate(
            total=Count("pk"),
            input_tokens=Sum("prompt_tokens"),
            output_tokens=Sum("completion_tokens"),
        )
        .order_by("-total")[:25]
    )
    peak_model = max((row["total"] for row in model_rows), default=0) or 1
    for row in model_rows:
        row["token_total"] = (row["input_tokens"] or 0) + (row["output_tokens"] or 0)
        row["pct"] = round(row["total"] * 100 / peak_model, 2)

    provider_options = list(
        Response.objects.exclude(provider_name="")
        .values_list("provider_name", flat=True)
        .distinct()
        .order_by("provider_name")
    )
    model_qs = Response.objects
    if provider:
        model_qs = model_qs.filter(provider_name=provider)
    model_options = list(
        model_qs.exclude(model_name="")
        .values_list("model_name", flat=True)
        .distinct()
        .order_by("model_name")
    )

    return {
        "tokens": {
            "prompt": agg["prompt"] or 0,
            "completion": agg["completion"] or 0,
            "cached": agg["cached"] or 0,
            "reasoning": agg["reasoning"] or 0,
        },
        "analytics_stats": analytics_stats,
        "daily": daily,
        "providers": provider_rows,
        "models": model_rows,
        "range_options": list(RANGE_OPTIONS),
        "range_key": range_key,
        "range_label": _RANGE_LABELS.get(range_key, "Last 24 hours"),
        "provider_filter": provider,
        "model_filter": model,
        "provider_options": provider_options,
        "model_options": model_options,
    }


def _providers_context(request=None):
    providers = list(
        ApiProvider.objects.prefetch_related("api_keys", "aimodels")
        .annotate(model_total=Count("aimodels", distinct=True))
        .order_by("name")
    )
    provider_ids = [provider.pk for provider in providers]
    windows = (
        ("24h", timedelta(hours=24)),
        ("7d", timedelta(days=7)),
        ("30d", timedelta(days=30)),
    )
    usage = {provider_id: [] for provider_id in provider_ids}
    now = timezone.now()
    for label, delta in windows:
        rows = Response.objects.filter(
            status=ResponseStatus.SUCCESS,
            created_at__gte=now - delta,
            aimodel__api_provider_id__in=provider_ids,
        ).values("aimodel__api_provider_id").annotate(
            requests=Count("pk"),
            prompt=Sum("prompt_tokens"),
            completion=Sum("completion_tokens"),
        )
        by_provider = {row["aimodel__api_provider_id"]: row for row in rows}
        for provider_id in provider_ids:
            row = by_provider.get(provider_id, {})
            tokens = (row.get("prompt") or 0) + (row.get("completion") or 0)
            usage[provider_id].append(
                f'{label}: {row.get("requests") or 0} req · {tokens} tok'
            )
    limit_labels = (
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
        ("limit_parallel_calls", "Parallel calls"),
    )
    for provider in providers:
        provider.detail_usage = usage.get(provider.pk, [])
        provider.limit_rows = [
            (label, getattr(provider, field))
            for field, label in limit_labels
            if getattr(provider, field, 0)
        ]
    return {"providers": providers}


def _models_context(request=None):
    models = list(
        AiModel.objects.select_related("api_provider").order_by("name")[:500]
    )
    variants = list(
        AiModel.objects.select_related("api_provider")
        .prefetch_related("api_provider__api_keys")
        .order_by("name")
    )
    groups: dict[str, list] = {}
    for variant in variants:
        key = variant.canonical_id or variant.leaderboard_id or variant.name
        groups.setdefault(key, []).append(variant)
    for model in models:
        key = model.canonical_id or model.leaderboard_id or model.name
        rows = []
        for variant in groups.get(key, []):
            provider = variant.api_provider
            has_key = bool(provider.default_api_key) or any(
                api_key.enabled for api_key in provider.api_keys.all()
            )
            rows.append(
                {
                    "pk": variant.pk,
                    "provider": provider.name,
                    "provider_model_id": variant.provider_model_id,
                    "key_note": "key" if has_key else "no key",
                    "health": variant.health_label,
                    "health_reason": variant.status_reason,
                    "conditions": variant.conditions,
                }
            )
        rows.sort(key=lambda row: row["provider"].lower())
        model.variant_rows = rows
    return {"models": models}


@require_POST
def model_probe(request, model_id: int):
    """Dispatch a smoke test for one exact model row."""
    model = get_object_or_404(AiModel, pk=model_id)
    try:
        from server.tasks.probe_model import probe_model

        cache.set(_model_probe_requested_key(model.pk), True, timeout=600)
        probe_model.delay(model.pk)
    except Exception:  # pylint: disable=broad-exception-caught
        log.exception("could not dispatch model probe for model %s", model_id)
        cache.delete(_model_probe_requested_key(model.pk))
        return HttpResponse("Could not start the model test.", status=500)
    if request.headers.get("HX-Request") == "true":
        return model_probe_status(request, model.pk)
    return redirect(f"/app/insights/models#model-{model.pk}")


def model_probe_status(request, model_id: int):
    model = get_object_or_404(AiModel, pk=model_id)
    from server.tasks.probe_model import get_cached_result, is_running

    probe = get_cached_result(model.pk)
    running = is_running(model.pk)
    requested_key = _model_probe_requested_key(model.pk)
    requested = bool(cache.get(requested_key))
    if probe is not None:
        cache.delete(requested_key)
    return render(
        request,
        "webui/insights/_model_probe.html",
        {
            "model": model,
            "probe": probe,
            "probe_running": running or (requested and probe is None),
        },
    )


def _model_probe_requested_key(model_id: int) -> str:
    return f"webui:probe:model-requested:{model_id}"
