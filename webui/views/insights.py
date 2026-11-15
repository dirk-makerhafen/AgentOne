"""Insights: aggregate counts, token usage and provider/model breakdown."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

from django.core.cache import cache
from django.db.models import Avg, Count, Sum
from django.db.models.functions import Trunc
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from server.models.agents.agent import AgentModel
from server.models.collections.data_collection import DataCollection
from server.models.cron import Cronjob
from server.models.enums.provider_enums import HealthStatus
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


MODE_LABELS = (
    ("supports_reasoning", "Reason"),
    ("supports_tool_call", "Tools"),
    ("vision", "Vision"),
    ("audio", "Audio"),
    ("video", "Video"),
)

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
    ("limit_parallel_calls", "Parallel calls"),
)

#: Model catalog rows rendered in one page (the table filters client-side).
INSIGHT_MODEL_LIMIT = 500

_HEALTH_PRIORITY = {
    HealthStatus.UNKNOWN: 0,
    HealthStatus.HEALTHY: 1,
    HealthStatus.RATE_LIMITED: 2,
    HealthStatus.DEGRADED: 3,
    HealthStatus.CONFIG_ERROR: 4,
    HealthStatus.UNAVAILABLE: 5,
    HealthStatus.AUTH_ERROR: 6,
}

_STATUS_META = {
    HealthStatus.HEALTHY: ("healthy", "ok"),
    HealthStatus.RATE_LIMITED: ("rate limited", "warn"),
    HealthStatus.DEGRADED: ("degraded", "warn"),
    HealthStatus.CONFIG_ERROR: ("config error", "err"),
    HealthStatus.UNAVAILABLE: ("unavailable", "err"),
    HealthStatus.AUTH_ERROR: ("auth error", "err"),
}


def _status_dict(status: str) -> dict:
    """UI badge data for an observed health status."""
    label, kind = _STATUS_META.get(status, ("", ""))
    return {"label": label, "kind": kind}


def _worst_status(members) -> str:
    """Most severe observed status across *members* (models/providers/keys)."""
    worst = HealthStatus.UNKNOWN
    for member in members:
        status = getattr(member, "status", HealthStatus.UNKNOWN)
        if _HEALTH_PRIORITY.get(status, 0) > _HEALTH_PRIORITY.get(worst, 0):
            worst = status
    return worst


def _params_str(total_parameters: float | None) -> str:
    if not total_parameters:
        return "—"
    value = float(total_parameters)
    if value >= 1:
        return f"{value:g}B"
    return f"{value * 1000:g}M"


def _rank_str(rank: int | None, is_estimate: bool = False) -> str:
    if rank is None:
        return "—"
    return f"~{rank}" if is_estimate else f"#{rank}"


def _context_str(context: int | None) -> str:
    if not context:
        return "—"
    if context >= 1_000_000:
        return f"{context / 1_000_000:g}M"
    if context >= 1_000:
        return f"{context / 1_000:g}k"
    return f"{context:,}"


def _last_usage_display(value) -> str:
    if not value:
        return "—"
    return timezone.localtime(value).strftime("%Y-%m-%d %H:%M")


def _limit_rows(instance) -> list[tuple[str, int]]:
    return [
        (label, getattr(instance, field, 0))
        for field, label in LIMIT_LABELS
        if getattr(instance, field, 0)
    ]


def _limits_str(instance) -> str:
    parts = [
        f"{value} {label}"
        for field, label in LIMIT_LABELS
        if (value := getattr(instance, field, 0))
    ]
    return " · ".join(parts) if parts else "Unlimited"


def _modes_for(members) -> list[str]:
    return [
        label
        for field, label in MODE_LABELS
        if any(getattr(member, field, False) for member in members)
    ]


def _usage_windows(qs, now=None) -> list[dict]:
    """Successful request/token counts for the last 24h, 7d and 30d."""
    now = now or timezone.now()
    windows = []
    for label, delta in (
        ("24h", timedelta(hours=24)),
        ("7d", timedelta(days=7)),
        ("30d", timedelta(days=30)),
    ):
        agg = qs.filter(created_at__gte=now - delta).aggregate(
            requests=Count("pk"),
            prompt=Sum("prompt_tokens"),
            completion=Sum("completion_tokens"),
        )
        windows.append(
            {
                "window": label,
                "requests": agg["requests"] or 0,
                "tokens": (agg["prompt"] or 0) + (agg["completion"] or 0),
            }
        )
    return windows


def _key_state(provider) -> tuple[str, int]:
    if provider.default_api_key:
        return "built-in", 0
    enabled = sum(1 for key in provider.api_keys.all() if key.enabled)
    return ("keys", enabled) if enabled else ("none", 0)


def _model_groups() -> tuple[dict[str, list], list[str]]:
    """Group model variants by canonical identity, preserving name order."""
    variants = list(
        AiModel.objects.select_related("api_provider")
        .prefetch_related("api_provider__api_keys")
        .order_by("name")[:INSIGHT_MODEL_LIMIT]
    )
    groups: dict[str, list] = {}
    order: list[str] = []
    for variant in variants:
        key = variant.canonical_id or variant.leaderboard_id or variant.name
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(variant)
    return groups, order


def _model_representatives() -> dict[int, int]:
    """Map every ``AiModel`` pk to the pk its canonical group renders as."""
    representatives: dict[str, int] = {}
    mapping: dict[int, int] = {}
    for pk, canonical_id, leaderboard_id, name in AiModel.objects.values_list(
        "pk", "canonical_id", "leaderboard_id", "name"
    ):
        key = canonical_id or leaderboard_id or name
        mapping[pk] = representatives.setdefault(key, pk)
    return mapping


def _providers_context(request=None):
    providers = list(
        ApiProvider.objects.prefetch_related("api_keys", "aimodels").order_by("name")
    )
    provider_ids = [provider.pk for provider in providers]
    usage = {provider_id: {} for provider_id in provider_ids}
    now = timezone.now()
    for label, delta in (
        ("24h", timedelta(hours=24)),
        ("7d", timedelta(days=7)),
        ("30d", timedelta(days=30)),
    ):
        stats = (
            Response.objects.filter(
                status=ResponseStatus.SUCCESS,
                created_at__gte=now - delta,
                aimodel__api_provider_id__in=provider_ids,
            )
            .values("aimodel__api_provider_id")
            .annotate(
                requests=Count("pk"),
                prompt=Sum("prompt_tokens"),
                completion=Sum("completion_tokens"),
            )
        )
        by_provider = {row["aimodel__api_provider_id"]: row for row in stats}
        for provider in providers:
            row = by_provider.get(provider.pk, {})
            usage[provider.pk][label] = {
                "requests": row.get("requests") or 0,
                "tokens": (row.get("prompt") or 0) + (row.get("completion") or 0),
            }

    representative = _model_representatives()
    rows = []
    for provider in providers:
        key_state, key_count = _key_state(provider)
        models = sorted(provider.aimodels.all(), key=lambda model: model.name.lower())
        limits = _limits_str(provider)
        search_parts = [
            provider.name,
            provider.slug,
            provider.url,
            provider.litellm_prefix,
            limits,
        ]
        search_parts.extend(model.name for model in models)
        rows.append(
            {
                "id": provider.pk,
                "name": provider.name,
                "slug": provider.slug,
                "is_local": provider.is_local,
                "key_state": key_state,
                "key_count": key_count,
                "limits": limits,
                "requests_24h": usage[provider.pk]["24h"]["requests"],
                "tokens_24h": usage[provider.pk]["24h"]["tokens"],
                "requests_30d": usage[provider.pk]["30d"]["requests"],
                "tokens_30d": usage[provider.pk]["30d"]["tokens"],
                "model_count": len(models),
                "model_links": [
                    {"pk": representative.get(model.pk, model.pk), "name": model.name}
                    for model in models[:2]
                ],
                "status": {**_status_dict(provider.status), "reason": provider.status_reason},
                "enabled": provider.enabled,
                "detail_url": reverse("webui:provider_detail", args=[provider.pk]),
                "search": " ".join(part for part in search_parts if part).lower(),
            }
        )
    return {"providers": rows}


def _models_context(request=None):
    groups, order = _model_groups()
    rows = []
    for key in order:
        members = groups[key]
        first = members[0]
        providers = sorted(
            {member.api_provider for member in members},
            key=lambda provider: provider.name.lower(),
        )
        with_key = sum(
            1
            for provider in providers
            if provider.default_api_key
            or any(api_key.enabled for api_key in provider.api_keys.all())
        )
        ranks = [
            (member.leaderboard_rank, member.leaderboard_rank_is_estimate)
            for member in members
            if member.leaderboard_rank is not None
        ]
        best_rank, best_estimate = (
            min(ranks, key=lambda item: item[0]) if ranks else (None, False)
        )
        params = max((member.total_parameters or 0) for member in members)
        context = max((member.context_length or 0) for member in members)
        modes = _modes_for(members)
        search_parts = [
            first.name,
            first.developer,
            first.family,
            first.canonical_id,
            first.provider_model_id,
        ]
        search_parts.extend(provider.name for provider in providers)
        search_parts.extend(member.provider_model_id for member in members)
        search_parts.extend(modes)
        rows.append(
            {
                "id": first.pk,
                "name": first.name,
                "developer": first.developer,
                "providers": [
                    {"pk": provider.pk, "name": provider.name}
                    for provider in providers[:2]
                ],
                "provider_count": len(providers),
                "with_key": with_key,
                "params": _params_str(params or None),
                "_params": params,
                "context": _context_str(context),
                "_context": context,
                "rank": _rank_str(best_rank, best_estimate),
                "_rank": best_rank if best_rank is not None else "",
                "modes": modes,
                "health": _status_dict(_worst_status(members)),
                "enabled": first.enabled,
                "detail_url": reverse("webui:model_detail", args=[first.pk]),
                "search": " ".join(part for part in search_parts if part).lower(),
            }
        )
    return {"models": rows, "model_limit": INSIGHT_MODEL_LIMIT}


def _model_group_members(model: AiModel) -> list[AiModel]:
    base = AiModel.objects.select_related("api_provider").prefetch_related(
        "api_provider__api_keys"
    )
    if model.canonical_id:
        return list(base.filter(canonical_id=model.canonical_id).order_by("name"))
    if model.leaderboard_id:
        return list(base.filter(leaderboard_id=model.leaderboard_id).order_by("name"))
    return list(base.filter(name=model.name).order_by("name"))


def _model_detail_context(model: AiModel) -> dict:
    from server.tasks.probe_model import get_cached_result, is_running

    members = _model_group_members(model)
    first = members[0] if members else model
    ranks = [
        (member.leaderboard_rank, member.leaderboard_rank_is_estimate)
        for member in members
        if member.leaderboard_rank is not None
    ]
    best_rank, best_estimate = (
        min(ranks, key=lambda item: item[0]) if ranks else (None, False)
    )
    params = max((member.total_parameters or 0) for member in members)
    context = max((member.context_length or 0) for member in members)
    provider_rows = []
    for member in members:
        provider = member.api_provider
        provider_rows.append(
            {
                "id": member.pk,
                "provider_id": provider.pk,
                "provider": provider.name,
                "provider_model_id": member.provider_model_id,
                "has_key": bool(provider.default_api_key)
                or any(key.enabled for key in provider.api_keys.all()),
                "health": _status_dict(member.status),
                "health_reason": member.status_reason,
                "conditions": member.conditions,
                "enabled": member.enabled,
                "probe": get_cached_result(member.pk),
                "probe_running": is_running(member.pk),
            }
        )
    provider_rows.sort(key=lambda row: row["provider"].lower())
    last_usage = max(
        (member.last_usage for member in members if member.last_usage), default=None
    )
    return {
        "model": first,
        "modes": _modes_for(members),
        "rank": _rank_str(best_rank, best_estimate),
        "params": _params_str(params or None),
        "context": _context_str(context),
        "health": _status_dict(_worst_status(members)),
        "limits": _limit_rows(first),
        "provider_rows": provider_rows,
        "usage": _usage_windows(
            Response.objects.filter(
                status=ResponseStatus.SUCCESS,
                aimodel_id__in=[member.pk for member in members],
            )
        ),
        "last_usage": _last_usage_display(last_usage),
    }


def _provider_detail_context(provider: ApiProvider) -> dict:
    from server.tasks.probe_model import get_cached_result, is_running

    now = timezone.now()
    keys = list(provider.api_keys.all().order_by("-enabled", "pk"))
    models = list(provider.aimodels.select_related("api_provider").order_by("name"))
    representative = _model_representatives()
    description = (provider.description or "").strip() or (
        provider.setup_instructions or ""
    ).strip()
    return {
        "provider": provider,
        "description": description,
        "health": _status_dict(provider.status),
        "key_rows": [
            {
                "comment": key.comment or "key",
                "enabled": key.enabled,
                "cooling": bool(key.rate_limit_until and key.rate_limit_until > now),
                "health": _status_dict(key.status),
                "limits": _limit_rows(key),
            }
            for key in keys
        ],
        "limit_rows": _limit_rows(provider),
        "usage": _usage_windows(
            Response.objects.filter(
                status=ResponseStatus.SUCCESS,
                aimodel__api_provider=provider,
            ),
            now=now,
        ),
        "last_usage": _last_usage_display(provider.last_usage),
        "model_rows": [
            {
                "id": model.pk,
                "representative_id": representative.get(model.pk, model.pk),
                "name": model.name,
                "provider_model_id": model.provider_model_id,
                "enabled": model.enabled,
                "health": _status_dict(model.status),
                "last_usage": _last_usage_display(model.last_usage),
                "probe": get_cached_result(model.pk),
                "probe_running": is_running(model.pk),
            }
            for model in models
        ],
    }


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


def model_detail(request, model_id: int):
    """Right-panel fragment for one canonical model group."""
    model = get_object_or_404(AiModel, pk=model_id)
    return render(
        request,
        "webui/insights/_model_detail.html",
        _model_detail_context(model),
    )


def provider_detail(request, provider_id: int):
    """Right-panel fragment for one provider."""
    provider = get_object_or_404(ApiProvider, pk=provider_id)
    return render(
        request,
        "webui/insights/_provider_detail.html",
        _provider_detail_context(provider),
    )
